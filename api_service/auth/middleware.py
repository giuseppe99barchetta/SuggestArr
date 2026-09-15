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
import secrets
import threading
import ipaddress
from functools import wraps
from typing import Optional

from flask import request, jsonify, g

from api_service.auth.auth_service import AuthService
from api_service.auth.api_key_service import ApiKeyService
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

PUBLIC_V1_ROUTES = frozenset({"/api/v1/status", "/api/v1/openapi.yaml", "/api/v1/openapi.json"})

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


# ---------------------------------------------------------------------------
# Trusted-header (reverse proxy / SSO) defaults
# ---------------------------------------------------------------------------
# In "trusted_header" mode the reverse proxy has already authenticated the
# user and passes the resulting identity in a request header.  Common values
# are "Remote-User" (Authelia, Authentik's proxy outpost) and
# "X-Forwarded-User" (oauth2-proxy, Traefik forward-auth).
_DEFAULT_AUTH_TRUSTED_HEADER = "X-Forwarded-User"

# Longest username we will accept from the header.  Mirrors the limit the
# self-registration endpoint enforces, so both paths agree on what a valid
# username looks like.
_MAX_TRUSTED_HEADER_USERNAME_LEN = 64


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

    if mode not in {"enabled", "local_bypass", "disabled", "trusted_header"}:
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


def _peer_address() -> str:
    """
    Return the address of the machine that actually opened this connection.

    THIS IS NOT request.remote_addr.  app.py wraps the WSGI app in
    ProxyFix(x_for=1), which REPLACES remote_addr with the first entry of
    X-Forwarded-For — a header the client controls.  Trusting that value for
    an authorization decision means anyone who can reach the port can claim to
    be the proxy: send `X-Forwarded-For: <proxy>` plus the identity header and
    the check passes.  Measured 2026-09-12 against a live instance; it
    returned 200 on an admin-only route.

    ProxyFix keeps the untouched WSGI environ under
    'werkzeug.proxy_fix.orig', so the real peer is still available.  Both the
    modern dict form and the older per-key form are handled; if neither is
    present (no ProxyFix in the chain) remote_addr is the peer already.
    """
    orig = request.environ.get("werkzeug.proxy_fix.orig")
    if isinstance(orig, dict) and orig.get("REMOTE_ADDR"):
        return orig["REMOTE_ADDR"]
    return (
        request.environ.get("werkzeug.proxy_fix.orig_remote_addr")
        or request.remote_addr
        or ""
    )


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


def _resolve_trusted_header_name() -> str:
    """
    Resolve the request header that carries the proxy-authenticated username.

    Returns:
        str: Header name from the AUTH_TRUSTED_HEADER env var or config,
             falling back to _DEFAULT_AUTH_TRUSTED_HEADER.
    """
    name = (os.environ.get("AUTH_TRUSTED_HEADER") or "").strip()
    if not name:
        name = str(
            load_env_vars().get("AUTH_TRUSTED_HEADER", _DEFAULT_AUTH_TRUSTED_HEADER)
        ).strip()
    return name or _DEFAULT_AUTH_TRUSTED_HEADER


def _trusted_header_auto_create_enabled() -> bool:
    """
    Report whether unknown usernames may be provisioned on first sight.

    When enabled (the default), the first request carrying a username the
    database has not seen creates a local account with role='user'.  Turn it
    off to restrict access to accounts an admin created up front.

    Returns:
        bool: True when auto-provisioning is enabled.
    """
    raw = os.environ.get("AUTH_TRUSTED_HEADER_AUTO_CREATE")
    if raw is None:
        raw = load_env_vars().get("AUTH_TRUSTED_HEADER_AUTO_CREATE", True)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() not in {"false", "0", "no", "off"}


def _resolve_trusted_header_user() -> Optional[dict]:
    """
    Resolve the user named by the trusted proxy header into an account record.

    The caller MUST have verified that the request originates from a trusted
    proxy before calling this — the header is attacker-controlled otherwise.

    Accounts provisioned here get role='user' (never 'admin') and a random,
    unusable password hash: the account exists to carry an identity, and
    nobody should be able to log into it with a password.  An admin can raise
    the role afterwards through the normal user-management screens.

    Returns:
        dict | None: Full account record (id, username, role, can_manage_ai,
                     visible_tabs, ...), or None when the header is absent,
                     malformed, unknown with auto-create disabled, or the
                     account is deactivated.
    """
    username = (request.headers.get(_resolve_trusted_header_name()) or "").strip()
    if not username or len(username) > _MAX_TRUSTED_HEADER_USERNAME_LEN:
        return None

    db = _get_database_manager()()
    record = db.get_auth_user_by_username(username)

    if record is None:
        if not _trusted_header_auto_create_enabled():
            logger.warning(
                "Trusted-header auth: unknown user %r and auto-create is disabled",
                username,
            )
            return None
        unusable_password = AuthService.hash_password(secrets.token_urlsafe(32))
        try:
            db.create_auth_user(username, unusable_password, role="user")
        except Exception:
            # Most likely a concurrent request created the same account first;
            # re-read before giving up so the race resolves silently.
            logger.debug("Trusted-header auth: create raced for %r, re-reading", username)
        record = db.get_auth_user_by_username(username)
        if record is None:
            logger.warning("Trusted-header auth: could not provision user %r", username)
            return None
        logger.info("Trusted-header auth: provisioned account for %r", username)

    # get_auth_user_by_username omits can_manage_ai/visible_tabs; re-read by id
    # so this path hands _apply_auth_context the same shape the JWT path does.
    full_record = db.get_auth_user_by_id(record["id"]) or record
    if not full_record.get("is_active", True):
        logger.warning("Trusted-header auth: account %r is deactivated", username)
        return None
    return full_record


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

def _apply_auth_context(user: dict, method: str, api_key_id=None, api_key_name=None) -> None:
    g.current_user = {"id": str(user.get("id", user.get("sub"))), "username": user.get("username", ""), "role": user.get("role", "user"), "can_manage_ai": user.get("can_manage_ai", 0), "visible_tabs": user.get("visible_tabs", "requests,jobs,profile")}
    g.auth_method, g.api_key_id, g.api_key_name = method, api_key_id, api_key_name


def require_interactive_auth(f):
    """Profile credential management requires JWT or a real bypass user."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        user = getattr(g, 'current_user', None)
        if not user or getattr(g, 'auth_method', 'jwt') == 'api_key' or str(user.get('id')) == '0':
            return jsonify({"error": "Interactive authentication required"}), 401
        return f(*args, **kwargs)
    return wrapped


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
    if _is_public_route(path) or path in PUBLIC_V1_ROUTES:
        # Public routes never *require* credentials, but some of them REPORT
        # them: /api/auth/status tells the SPA whether anybody is signed in,
        # and the SPA shows its login form when the answer is "no".  Returning
        # early without resolving the trusted header therefore hands a login
        # form to a user the proxy has already authenticated — the one thing
        # this mode exists to avoid.
        #
        # Resolving here only ADDS identity; it never rejects.  A request
        # without the header (a health probe, for instance) is untouched.
        if (
            _resolve_auth_mode() == "trusted_header"
            and getattr(g, "current_user", None) is None
            and _is_trusted_local_ip(_peer_address())
        ):
            trusted_user = _resolve_trusted_header_user()
            if trusted_user is not None:
                _apply_auth_context(trusted_user, "trusted_header")
        return None

    auth_mode = _resolve_auth_mode()

    client_ip = request.remote_addr or ""
    trusted_cidr_networks = _load_trusted_cidrs()
    trusted_cidrs = [str(network) for network in trusted_cidr_networks]
    is_trusted_ip = _is_trusted_local_ip(client_ip)

    logger.debug(
        f"AUTH DEBUG - ip={client_ip} mode={auth_mode} trusted={is_trusted_ip} cidrs={trusted_cidrs}"
    )

    auth_header = request.headers.get("Authorization", "")
    bearer = auth_header[len("Bearer "):].strip() if auth_header.startswith("Bearer ") else None
    api_key = request.headers.get("X-API-Key")
    if bearer and api_key:
        return jsonify({"error": {"code": "ambiguous_credentials", "message": "Use one authentication method."}}), 400
    if api_key and not path.startswith("/api/v1/"):
        return jsonify({"error": "Invalid credentials"}), 401
    if auth_header and not bearer:
        return jsonify({"error": "Invalid credentials"}), 401
    if bearer:
        payload = AuthService.verify_access_token(bearer)
        if payload is None:
            return jsonify({"error": "Invalid or expired token"}), 401
        _apply_auth_context(payload, "jwt")
        return None
    if api_key:
        identity = ApiKeyService(_get_database_manager()()).resolve(api_key)
        if not identity:
            return jsonify({"error": "Invalid credentials"}), 401
        _apply_auth_context(identity['user'], "api_key", identity['api_key_id'], identity['api_key_name'])
        return None
    if auth_mode == "disabled":
        if getattr(g, "current_user", None) is None:
            _apply_auth_context(_load_bypass_user_context(), "disabled")
        return None
    if auth_mode == "local_bypass" and is_trusted_ip:
        if getattr(g, "current_user", None) is None:
            _apply_auth_context(_load_bypass_user_context(), "local_bypass")
        return None
    if auth_mode == "trusted_header":
        # The peer check is what makes the header trustworthy: anyone who can
        # reach the app directly could otherwise set it and pick an identity.
        # Keep AUTH_TRUSTED_CIDRS narrow — ideally just the proxy's address.
        #
        # AGAINST THE REAL PEER, NOT client_ip: the latter comes from
        # X-Forwarded-For via ProxyFix, so it is attacker-controlled.  Checking
        # it here would let anyone who reaches the port send
        # `X-Forwarded-For: <proxy>` and be believed — see _peer_address().
        peer_ip = _peer_address()
        if not _is_trusted_local_ip(peer_ip):
            logger.warning(
                "Trusted-header auth: rejecting request from untrusted peer=%s (claimed ip=%s)",
                peer_ip,
                client_ip,
            )
            return jsonify({"error": "Authentication required"}), 401
        if getattr(g, "current_user", None) is None:
            trusted_user = _resolve_trusted_header_user()
            if trusted_user is None:
                return jsonify({"error": "Authentication required"}), 401
            _apply_auth_context(trusted_user, "trusted_header")
        return None
    if not path.startswith('/api/v1/') and _is_setup_mode():
        return None
    return jsonify({"error": "Authentication required"}), 401


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
