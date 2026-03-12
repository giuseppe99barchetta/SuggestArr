"""
Centralized authentication middleware for the Flask application.

How it works
------------
A single before_request hook (enforce_authentication) intercepts every
incoming request before any route handler runs.  The hook applies the
following decision tree:

  1. Non-/api/* paths → serve frontend static files, no auth needed.
  2. Path is in PUBLIC_ROUTES → explicitly allowed without a token.
  3. SUGGESTARR_AUTH_DISABLED=true env var → bypass auth (escape hatch,
     loudly warned at startup).
  4. No auth_users in the database → system is in first-run "setup mode",
     all routes accessible so the wizard can operate.
  5. Missing or malformed Authorization: Bearer <token> header → 401.
  6. Invalid or expired JWT → 401.
  7. Valid token → store decoded payload in flask.g.current_user and
     continue to the route handler.

Default stance is DENY: every /api/* route is protected unless it appears
in PUBLIC_ROUTES.  Adding a new route never accidentally becomes public.

Role enforcement
----------------
require_role(*roles) is a decorator for route-level RBAC.  Authentication
is already guaranteed by the middleware; require_role only checks the role
claim.  Unauthenticated calls still return 401 (not 403) because g.current_user
is always set before require_role runs for protected routes — the only case
where it can be None is if the decorator is misapplied to a public route.

Error responses
---------------
401 / 403 responses contain only a generic "error" key with no stack traces,
token details, or internal state.  This intentionally limits information
leakage to potential attackers.
"""
import os
import time
import threading
import ipaddress
from functools import wraps
from typing import Optional

from flask import request, jsonify, g

from api_service.auth.auth_service import AuthService
from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager

logger = LoggerManager.get_logger("AuthMiddleware")

# ---------------------------------------------------------------------------
# Public route allowlist
# ---------------------------------------------------------------------------
# Every /api/* path NOT listed here requires a valid JWT.
# Use exact paths or path prefixes (a prefix matches the path itself and any
# child paths: "/api/auth" matches "/api/auth", "/api/auth/login", etc.).
#
# Keep this list as short as possible — every entry is a potential attack
# surface that bypasses authentication.
PUBLIC_ROUTES: frozenset[str] = frozenset({
    "/api/health",          # General health check
    "/api/health/live",     # Docker / reverse-proxy liveness probe — must
                            # always respond even during startup/shutdown.
    "/api/auth/login",      # Credential exchange endpoint.
    "/api/auth/refresh",    # Token renewal via httpOnly cookie.
    "/api/auth/setup",      # First-run admin creation (guarded internally
                            # by user-count check — see auth blueprint).
    "/api/auth/status",     # Read-only setup state for frontend routing
                            # (tells the SPA which screen to show).
    "/api/config/status",   # Minimal setup-completion flags needed by the
                            # SPA on every cold start (no secrets returned).
    "/api/auth/logout",     # Token revocation (guarded internally by user-count check).
    "/api/auth/register",   # Self-registration (gated by ALLOW_REGISTRATION config flag).
})

# ---------------------------------------------------------------------------
# Setup-mode cache
# ---------------------------------------------------------------------------
# When no auth_users exist the system is in "setup mode" and all routes are
# temporarily public so the configuration wizard can run.
# We cache the result for _SETUP_CACHE_TTL_S seconds to avoid a DB round-trip
# on every request, while still detecting when setup completes within 5 s.
_setup_mode_lock = threading.Lock()
_setup_mode_cache: dict = {"value": None, "expires_at": 0.0}
_SETUP_CACHE_TTL_S = 5.0

# Module-level reference to DatabaseManager; resolved lazily on first use of
# _is_setup_mode() to avoid a circular import at load time.
# Exposed at module level so tests can patch
# 'api_service.auth.middleware.DatabaseManager'.
DatabaseManager = None  # type: ignore[assignment]


_DEFAULT_AUTH_TRUSTED_CIDRS = [
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "::1/128",
    "fc00::/7",
]


def _get_database_manager():
    """Lazily resolve DatabaseManager to avoid circular imports."""
    global DatabaseManager
    if DatabaseManager is None:
        from api_service.db.database_manager import DatabaseManager as _DM
        DatabaseManager = _DM
    return DatabaseManager


def _resolve_auth_mode() -> str:
    """Resolve auth mode from backward-compatible env/config settings."""
    if os.environ.get("SUGGESTARR_AUTH_DISABLED", "").lower() == "true":
        return "disabled"

    mode = (os.environ.get("AUTH_MODE") or "").strip().lower()
    if not mode:
        mode = str(load_env_vars().get("AUTH_MODE", "enabled")).strip().lower()

    if mode not in {"enabled", "local_bypass", "disabled"}:
        logger.warning("Invalid AUTH_MODE=%r, defaulting to 'enabled'", mode)
        return "enabled"
    return mode


def _load_trusted_cidrs() -> list[ipaddress._BaseNetwork]:
    """Load and parse trusted CIDR ranges for local-bypass mode."""
    raw = os.environ.get("AUTH_TRUSTED_CIDRS")
    if raw is None:
        raw = load_env_vars().get("AUTH_TRUSTED_CIDRS", _DEFAULT_AUTH_TRUSTED_CIDRS)

    if isinstance(raw, str):
        cidr_values = [x.strip() for x in raw.split(",") if x.strip()]
    elif isinstance(raw, (list, tuple, set)):
        cidr_values = [str(x).strip() for x in raw if str(x).strip()]
    else:
        cidr_values = list(_DEFAULT_AUTH_TRUSTED_CIDRS)

    networks: list[ipaddress._BaseNetwork] = []
    for cidr in cidr_values:
        try:
            networks.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid AUTH_TRUSTED_CIDRS entry: %r", cidr)

    if not networks:
        networks = [ipaddress.ip_network(c, strict=False) for c in _DEFAULT_AUTH_TRUSTED_CIDRS]

    return networks


def _is_trusted_local_ip(client_ip: str) -> bool:
    """Return True when client_ip belongs to configured trusted local CIDRs."""
    if not client_ip:
        return False
    try:
        ip = ipaddress.ip_address(client_ip)
    except ValueError:
        return False

    for network in _load_trusted_cidrs():
        if ip in network:
            return True
    return False


def _build_synthetic_bypass_user() -> dict:
    """Build a minimal synthetic admin context for bypass modes."""
    username = (os.environ.get("AUTH_BYPASS_USERNAME") or "").strip()
    if not username:
        username = str(load_env_vars().get("AUTH_BYPASS_USERNAME", "local_admin")).strip() or "local_admin"

    return {
        "id": "0",
        "username": username,
        "role": "admin",
        "can_manage_ai": 1,
        "visible_tabs": "requests,ai_search,services,jobs,database,advanced,users,profile,logs",
    }


def _load_bypass_user_context() -> dict:
    """
    Resolve a valid request user context for auth-bypass modes.

    Resolution order:
      1) AUTH_BYPASS_USERNAME (default local_admin)
      2) First active admin user in DB
      3) Synthetic local admin context
    """
    configured_username = (os.environ.get("AUTH_BYPASS_USERNAME") or "").strip()
    if not configured_username:
        configured_username = str(load_env_vars().get("AUTH_BYPASS_USERNAME", "local_admin")).strip() or "local_admin"

    try:
        db = _get_database_manager()()

        configured_user = db.get_auth_user_by_username(configured_username)
        if configured_user and configured_user.get("is_active", True):
            return {
                "id": str(configured_user["id"]),
                "username": configured_user.get("username", configured_username),
                "role": configured_user.get("role", "admin"),
                "can_manage_ai": int(bool(configured_user.get("can_manage_ai", 0))),
                "visible_tabs": configured_user.get("visible_tabs", "requests,jobs,profile"),
            }

        users = db.get_all_auth_users()
        for user in users:
            if user.get("role") == "admin" and user.get("is_active", True):
                return {
                    "id": str(user["id"]),
                    "username": user.get("username", "admin"),
                    "role": user.get("role", "admin"),
                    "can_manage_ai": int(bool(user.get("can_manage_ai", 0))),
                    "visible_tabs": user.get("visible_tabs", "requests,jobs,profile"),
                }
    except Exception as exc:
        logger.warning("Could not resolve bypass user from DB; using synthetic user: %s", exc)

    return _build_synthetic_bypass_user()


def _is_setup_mode() -> bool:
    """
    Return True when no SuggestArr auth users exist (first-run wizard mode).

    Result is cached for _SETUP_CACHE_TTL_S seconds so the check is cheap
    on every request without hammering the database.

    Returns:
        bool: True if the system has not yet had an admin account created.
    """
    global DatabaseManager

    now = time.monotonic()
    with _setup_mode_lock:
        cached = _setup_mode_cache
        if cached["value"] is not None and now < cached["expires_at"]:
            return cached["value"]  # type: ignore[return-value]

    try:
        count = _get_database_manager()().get_auth_user_count()
        result = count == 0
    except Exception:
        # If the DB is not yet reachable (e.g., first startup), fail open so
        # the wizard can complete.  This is a conscious trade-off: a transient
        # DB error temporarily allows unauthenticated access, which is
        # preferable to locking out the operator entirely.
        logger.warning("Could not query auth_users count; defaulting to setup mode")
        result = True

    with _setup_mode_lock:
        _setup_mode_cache["value"] = result
        _setup_mode_cache["expires_at"] = now + _SETUP_CACHE_TTL_S

    return result


def invalidate_setup_cache() -> None:
    """
    Flush the setup-mode cache.

    Must be called after an auth user is created so that subsequent requests
    immediately start enforcing authentication.
    """
    with _setup_mode_lock:
        _setup_mode_cache["value"] = None
        _setup_mode_cache["expires_at"] = 0.0


def _is_public_route(path: str) -> bool:
    """
    Check whether a request path matches the PUBLIC_ROUTES allowlist.

    A route is public if it exactly equals a listed entry OR starts with
    that entry followed by '/'.

    Args:
        path: The request path (e.g. '/api/auth/login').

    Returns:
        bool: True if the path is on the public allowlist.
    """
    for public in PUBLIC_ROUTES:
        if path == public or path.startswith(public + "/"):
            return True
    return False


# ---------------------------------------------------------------------------
# Main middleware hook
# ---------------------------------------------------------------------------

def enforce_authentication() -> Optional[tuple]:
    """
    before_request hook that enforces JWT authentication on all /api/* routes.

    Register with: app.before_request(enforce_authentication)

    Returns:
        None if the request may proceed.
        A (Response, status_code) tuple to short-circuit the request with an
        error response.
    """
    path = request.path

    # Non-API paths serve the Vue.js SPA and static assets — always public.
    if not path.startswith("/api/"):
        return None

    # OPTIONS requests are CORS preflight checks issued by the browser before
    # the real request.  They carry no credentials and must succeed for CORS to
    # work.  Returning None lets Flask/the CORS extension handle the response;
    # no auth token is required or expected on a preflight.
    if request.method == "OPTIONS":
        return None

    # Explicit public allowlist — auth endpoints, health probe, etc.
    if _is_public_route(path):
        return None

    auth_mode = _resolve_auth_mode()

    if auth_mode == "disabled":
        g.current_user = _load_bypass_user_context()
        return None

    if auth_mode == "local_bypass" and _is_trusted_local_ip(request.remote_addr or ""):
        g.current_user = _load_bypass_user_context()
        return None

    # Setup mode: if no admin account exists yet, allow everything so the
    # first-run wizard can configure the application.
    if _is_setup_mode():
        return None

    # --- From here the request MUST carry a valid Bearer token ---

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        # No token at all or wrong scheme.
        return jsonify({"error": "Authentication required"}), 401

    token = auth_header[len("Bearer "):]
    payload = AuthService.verify_access_token(token)

    if payload is None:
        # Expired or cryptographically invalid token.
        return jsonify({"error": "Invalid or expired token"}), 401

    # Attach decoded identity to the request context so route handlers and
    # the require_role decorator can access it without re-decoding the token.
    g.current_user = {
        "id": payload["sub"],
        "username": payload.get("username", ""),
        "role": payload.get("role", "user"),
        "can_manage_ai": payload.get("can_manage_ai", 0),
        "visible_tabs": payload.get("visible_tabs", "requests,jobs,profile"),
    }

    return None  # Allow the request to continue.


# ---------------------------------------------------------------------------
# Optional role-enforcement decorator
# ---------------------------------------------------------------------------

def require_role(*roles: str):
    """
    Route decorator that restricts access to users with a matching role.

    Authentication is guaranteed by the middleware before this decorator
    runs on protected routes.  This decorator only adds a role check.

    Usage::

        @config_bp.route('/save', methods=['POST'])
        @require_role('admin')
        def save_config():
            ...

    Args:
        *roles: Accepted role strings (e.g. 'admin', 'user').

    Returns:
        Flask response with 401/403 on failure, or the route result on success.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user = getattr(g, 'current_user', None)
            if user is None:
                # Should not happen on protected routes, but guard anyway.
                return jsonify({"error": "Authentication required"}), 401
            if user["role"] not in roles:
                # Authenticated but not authorised — 403 not 401.
                return jsonify({"error": "Insufficient permissions"}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator
