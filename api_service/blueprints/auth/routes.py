"""
Authentication blueprint.

Public endpoints (no JWT required — listed in middleware.PUBLIC_ROUTES):
  GET  /api/auth/status   — frontend routing helper (is setup done? is auth done?)
  POST /api/auth/setup    — first-run admin creation (self-guards via user count)
  POST /api/auth/login    — credential exchange → JWT + refresh cookie
  POST /api/auth/refresh  — refresh cookie → new JWT

Protected endpoints (JWT required — enforced by middleware):
  POST /api/auth/logout   — revoke refresh token, clear cookie
  GET  /api/auth/me       — current user identity

Security decisions
------------------
- Login always calls verify_password even when the username is not found.
  This prevents timing-based username enumeration (the response time is
  dominated by the bcrypt computation regardless of whether the user exists).
- The refresh token is sent as an httpOnly cookie scoped to /api/auth/refresh.
  JavaScript cannot read it, which prevents XSS-based token theft.
- SameSite=Strict means the cookie is never sent with cross-site requests,
  providing CSRF protection for the refresh endpoint without a CSRF token.
- 401 and 403 responses contain only a generic "error" key — no stack traces,
  no token details, no internal state.
- Login errors are logged at WARNING level with the username (not the password)
  to support anomaly detection without leaking credentials to log consumers.
"""
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, make_response, g

from api_service.auth.auth_service import AuthService, MIN_PASSWORD_LENGTH, REFRESH_TOKEN_EXPIRE_DAYS
from api_service.auth.limiter import limiter
from api_service.auth.middleware import invalidate_setup_cache
from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager

logger = LoggerManager.get_logger("AuthRoute")

auth_bp = Blueprint('auth', __name__)

# Name of the httpOnly cookie that carries the opaque refresh token.
_REFRESH_COOKIE = "suggestarr_refresh"

# Dummy bcrypt hash used for constant-time comparison when a username is not
# found.  The hash is pre-computed so it cannot be timed differently from a
# real hash lookup.  It deliberately does NOT match any password.
_DUMMY_HASH = "$2b$12$invalidhashpadding000000000000000000000000000000000000000"


# ---------------------------------------------------------------------------
# Public: setup-state probe
# ---------------------------------------------------------------------------

@auth_bp.route('/status', methods=['GET'])
def auth_status():
    """
    Return the current setup state so the SPA can decide which screen to show.

    This endpoint is intentionally public (no JWT required) because the
    frontend needs it before any authentication takes place.

    Response JSON:
      auth_setup_complete  — True once the first admin account has been created.
      app_setup_complete   — True once SETUP_COMPLETED is set in config.yaml.
    """
    try:
        db = DatabaseManager()
        auth_done = db.get_auth_user_count() > 0

        config = load_env_vars()
        app_done = bool(config.get('SETUP_COMPLETED', False))

        return jsonify({
            "auth_setup_complete": auth_done,
            "app_setup_complete": app_done,
        }), 200
    except Exception as exc:
        logger.error("Error reading auth status: %s", exc)
        # Fail open so the frontend can still reach the wizard.
        return jsonify({
            "auth_setup_complete": False,
            "app_setup_complete": False,
        }), 200


# ---------------------------------------------------------------------------
# Public: first-run admin creation
# ---------------------------------------------------------------------------

@auth_bp.route('/setup', methods=['POST'])
@limiter.limit("5 per hour")
def setup():
    """
    Create the very first admin account.

    Self-guarded: returns 403 if any auth user already exists so this
    endpoint cannot be used to escalate privileges after initial setup.

    Rate-limited to 5 attempts per hour per IP.

    Request JSON:
      username  (str) — desired login name
      password  (str) — must be >= MIN_PASSWORD_LENGTH characters

    Response (201): { "message": "Admin account created" }
    Response (400): { "error": "<validation message>" }
    Response (403): { "error": "Setup already completed" }
    """
    db = DatabaseManager()
    if db.get_auth_user_count() > 0:
        # After setup, this endpoint becomes a no-op regardless of credentials.
        return jsonify({"error": "Setup already completed"}), 403

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if len(username) > 64:
        return jsonify({"error": "Username must be 64 characters or fewer"}), 400
    if len(password) < MIN_PASSWORD_LENGTH:
        return jsonify({"error": f"Password must be at least {MIN_PASSWORD_LENGTH} characters"}), 400

    password_hash = AuthService.hash_password(password)
    db.create_auth_user(username, password_hash, role="admin")

    # Immediately invalidate the setup-mode cache so the middleware starts
    # enforcing authentication on the very next request.
    invalidate_setup_cache()

    logger.info("Initial admin account created: %r", username)
    return jsonify({"message": "Admin account created"}), 201


# ---------------------------------------------------------------------------
# Public: credential exchange
# ---------------------------------------------------------------------------

@auth_bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    """
    Authenticate with username and password.

    On success:
      - Returns a short-lived JWT access token in the JSON body.
      - Sets an httpOnly refresh token cookie scoped to /api/auth/refresh.

    Rate-limited to 10 attempts per minute per IP to mitigate brute-force.

    Request JSON:
      username  (str)
      password  (str)

    Response (200):
      { "access_token": "<jwt>", "role": "<role>", "username": "<username>" }
    Response (400): { "error": "Username and password are required" }
    Response (401): { "error": "Invalid credentials" }
    Response (403): { "error": "Account is disabled" }
    """
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    db = DatabaseManager()
    user = db.get_auth_user_by_username(username)

    # Always run bcrypt even if the user does not exist so that the response
    # time is constant regardless of username validity (timing-safe).
    stored_hash = user["password_hash"] if user else _DUMMY_HASH
    password_ok = AuthService.verify_password(password, stored_hash)

    if not password_ok or user is None:
        logger.warning("Failed login attempt for username: %r from %s", username, request.remote_addr)
        return jsonify({"error": "Invalid credentials"}), 401

    if not user.get("is_active", True):
        logger.warning("Login attempt for disabled account: %r", username)
        return jsonify({"error": "Account is disabled"}), 403

    # Issue tokens
    access_token = AuthService.create_access_token(user["id"], user["username"], user["role"])
    raw_refresh, hashed_refresh = AuthService.generate_refresh_token()
    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    db.store_refresh_token(user["id"], hashed_refresh, expires_at)
    db.update_last_login(user["id"])

    logger.info("Successful login: %r from %s", username, request.remote_addr)

    response = make_response(
        jsonify({
            "access_token": access_token,
            "role": user["role"],
            "username": user["username"],
        }),
        200,
    )

    # httpOnly — JavaScript cannot read this cookie (XSS protection).
    # SameSite=Strict — cookie is not sent on cross-site requests (CSRF protection).
    # path=/api/auth/refresh — cookie is only sent to the refresh endpoint,
    #   not to every API call, which limits its exposure window.
    response.set_cookie(
        _REFRESH_COOKIE,
        raw_refresh,
        httponly=True,
        samesite="Strict",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth/refresh",
    )

    return response


# ---------------------------------------------------------------------------
# Public: access-token renewal
# ---------------------------------------------------------------------------

@auth_bp.route('/refresh', methods=['POST'])
@limiter.limit("30 per minute")
def refresh():
    """
    Issue a new short-lived JWT access token using the httpOnly refresh cookie.

    The refresh cookie is sent automatically by the browser because the
    request path matches the cookie's path attribute.

    Response (200): { "access_token": "<jwt>" }
    Response (401): { "error": "<reason>" }
    """
    raw_refresh = request.cookies.get(_REFRESH_COOKIE)
    if not raw_refresh:
        return jsonify({"error": "Refresh token missing"}), 401

    token_hash = AuthService.hash_refresh_token(raw_refresh)
    db = DatabaseManager()
    record = db.get_refresh_token(token_hash)

    if not record:
        # Token not found or already revoked.
        return jsonify({"error": "Invalid refresh token"}), 401

    # Check expiry in Python (DB stores as ISO string, not a DB-native check).
    expires_raw = record["expires_at"]
    if isinstance(expires_raw, str):
        expires_at = datetime.fromisoformat(expires_raw)
    else:
        expires_at = expires_raw

    # Ensure timezone-aware comparison.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(tz=timezone.utc):
        db.revoke_refresh_token(token_hash)
        return jsonify({"error": "Refresh token expired"}), 401

    user = db.get_auth_user_by_id(record["user_id"])
    if not user or not user.get("is_active", True):
        return jsonify({"error": "User not found or disabled"}), 401

    access_token = AuthService.create_access_token(user["id"], user["username"], user["role"])
    return jsonify({"access_token": access_token}), 200


# ---------------------------------------------------------------------------
# Protected: logout
# ---------------------------------------------------------------------------

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    Revoke the current refresh token and clear the cookie.

    The JWT access token naturally expires after ACCESS_TOKEN_EXPIRE_MINUTES
    (15 min) — no server-side access-token blocklist is maintained.

    This endpoint does NOT require the JWT middleware to pass (the middleware
    runs first and will enforce auth for non-public routes), but it is
    intentionally safe even if called without a valid JWT because the only
    state change is revoking a cookie-bound refresh token.

    Response (200): { "message": "Logged out" }
    """
    raw_refresh = request.cookies.get(_REFRESH_COOKIE)
    if raw_refresh:
        token_hash = AuthService.hash_refresh_token(raw_refresh)
        DatabaseManager().revoke_refresh_token(token_hash)

    response = make_response(jsonify({"message": "Logged out"}), 200)
    # Clear the cookie by expiring it immediately.
    response.delete_cookie(_REFRESH_COOKIE, path="/api/auth/refresh")
    return response


# ---------------------------------------------------------------------------
# Protected: current-user identity
# ---------------------------------------------------------------------------

@auth_bp.route('/register', methods=['POST'])
@limiter.limit("5 per hour")
def register():
    """
    Self-registration endpoint for new user accounts.

    Gated by the ALLOW_REGISTRATION config flag.  When disabled (the default),
    this endpoint always returns 403 so that only admins can create accounts.
    When enabled, anyone can create a viewer-level account with role='user'.

    Rate-limited to 5 attempts per hour per IP to limit abuse.

    Request JSON:
      username  (str) — desired login name
      password  (str) — must be >= MIN_PASSWORD_LENGTH characters

    Response (201): { "message": "Account created" }
    Response (400): { "error": "<validation message>" }
    Response (403): { "error": "Registration is disabled" }
    Response (409): { "error": "Username already taken" }
    """
    config = load_env_vars()
    if not config.get('ALLOW_REGISTRATION', False):
        return jsonify({"error": "Registration is disabled"}), 403

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if len(username) > 64:
        return jsonify({"error": "Username must be 64 characters or fewer"}), 400
    if len(password) < MIN_PASSWORD_LENGTH:
        return jsonify({"error": f"Password must be at least {MIN_PASSWORD_LENGTH} characters"}), 400

    password_hash = AuthService.hash_password(password)
    try:
        DatabaseManager().create_auth_user(username, password_hash, role="user")
    except Exception:
        return jsonify({"error": "Username already taken"}), 409

    logger.info("Self-registration: new account created: %r", username)
    return jsonify({"message": "Account created"}), 201


# ---------------------------------------------------------------------------
# Protected: current-user identity
# ---------------------------------------------------------------------------

@auth_bp.route('/me', methods=['GET'])
def me():
    """
    Return the authenticated user's identity.

    Requires a valid JWT (enforced by the middleware — g.current_user is
    guaranteed to be set by the time this handler runs).

    Response (200):
      { "id": "<user_id>", "username": "<name>", "role": "<role>" }
    """
    return jsonify(g.current_user), 200
