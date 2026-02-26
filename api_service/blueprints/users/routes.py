"""
User management and media profile linking blueprint.

Admin endpoints (require role='admin'):
  GET    /api/users               — list all SuggestArr accounts
  POST   /api/users               — admin create a new account
  PATCH  /api/users/<id>          — update role / active status
  DELETE /api/users/<id>          — permanently delete an account

Per-user media profile endpoints (any authenticated user):
  GET    /api/users/me/links                   — list current user's media links
  POST   /api/users/me/link/jellyfin           — link a Jellyfin account
  POST   /api/users/me/link/emby               — link an Emby account
  DELETE /api/users/me/link/<provider>         — unlink a media account
  GET    /api/users/me/link/plex/oauth-start   — begin Plex OAuth device flow
  POST   /api/users/me/link/plex/oauth-poll    — poll Plex OAuth completion

Security decisions
------------------
- password_hash is never included in any response.
- access_token is never included in list responses; only fetched internally.
- Admins cannot delete or demote themselves.
- The last active admin account cannot be deleted or demoted.
- Jellyfin / Emby passwords are validated once then discarded — only the
  external user ID and username are persisted.
- Plex tokens are stored to allow future server-side API calls on behalf of
  the user (e.g. personalised recommendations).
"""
import requests as http_requests

from flask import Blueprint, jsonify, request, g

from api_service.auth.auth_service import AuthService, MIN_PASSWORD_LENGTH
from api_service.auth.middleware import require_role
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager

logger = LoggerManager.get_logger("UsersRoute")

users_bp = Blueprint('users', __name__)

_VALID_ROLES = {'admin', 'viewer', 'user'}
_VALID_PROVIDERS = {'jellyfin', 'plex', 'emby'}

# Plex application identifier — stable across instances.
_PLEX_CLIENT_ID = "suggestarr"
_PLEX_CLIENT_NAME = "SuggestArr"
_PLEX_PRODUCT = "SuggestArr"
_PLEX_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_user_id() -> int:
    """Return the integer user id from the JWT payload attached by middleware."""
    return int(g.current_user["id"])


def _plex_headers() -> dict:
    """Return the headers required by Plex.tv API calls."""
    return {
        "X-Plex-Client-Identifier": _PLEX_CLIENT_ID,
        "X-Plex-Product": _PLEX_PRODUCT,
        "X-Plex-Version": _PLEX_VERSION,
        "Accept": "application/json",
    }


# ---------------------------------------------------------------------------
# Admin: list users
# ---------------------------------------------------------------------------

@users_bp.route('', methods=['GET'])
@require_role('admin')
def list_users():
    """
    Return all SuggestArr accounts (password hashes excluded).

    Response (200): list of { id, username, role, is_active, created_at, last_login }
    """
    db = DatabaseManager()
    users = db.get_all_auth_users()
    return jsonify(users), 200


# ---------------------------------------------------------------------------
# Admin: create user
# ---------------------------------------------------------------------------

@users_bp.route('', methods=['POST'])
@require_role('admin')
def create_user():
    """
    Admin-create a new SuggestArr account.

    Request JSON:
      username  (str)  — desired login name
      password  (str)  — must be >= MIN_PASSWORD_LENGTH characters
      role      (str)  — one of 'admin', 'viewer', 'user' (default: 'viewer')

    Response (201): { "id": <int>, "username": <str>, "role": <str> }
    Response (400): { "error": "<validation message>" }
    Response (409): { "error": "Username already taken" }
    """
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = (data.get("role") or "viewer").strip()

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if len(username) > 64:
        return jsonify({"error": "Username must be 64 characters or fewer"}), 400
    if len(password) < MIN_PASSWORD_LENGTH:
        return jsonify({"error": f"Password must be at least {MIN_PASSWORD_LENGTH} characters"}), 400
    if role not in _VALID_ROLES:
        return jsonify({"error": f"Role must be one of: {', '.join(sorted(_VALID_ROLES))}"}), 400

    password_hash = AuthService.hash_password(password)
    try:
        db = DatabaseManager()
        user_id = db.create_auth_user(username, password_hash, role=role)
    except Exception:
        return jsonify({"error": "Username already taken"}), 409

    logger.info("Admin %r created account %r with role %r", g.current_user["username"], username, role)
    return jsonify({"id": user_id, "username": username, "role": role}), 201


# ---------------------------------------------------------------------------
# Admin: update user
# ---------------------------------------------------------------------------

@users_bp.route('/<int:user_id>', methods=['PATCH'])
@require_role('admin')
def update_user(user_id: int):
    """
    Update a user's role and/or active status.

    Guards:
      - Admins cannot change their own role or active status.
      - The last active admin cannot be demoted or deactivated.

    Request JSON (all optional):
      role       (str)  — one of 'admin', 'viewer', 'user'
      is_active  (bool) — True to activate, False to deactivate

    Response (200): { "message": "User updated" }
    Response (400): { "error": "<validation message>" }
    Response (403): { "error": "<guard message>" }
    Response (404): { "error": "User not found" }
    """
    caller_id = _current_user_id()
    if user_id == caller_id:
        return jsonify({"error": "Admins cannot modify their own account"}), 403

    data = request.get_json(silent=True) or {}
    updates = {}

    if "role" in data:
        role = (data["role"] or "").strip()
        if role not in _VALID_ROLES:
            return jsonify({"error": f"Role must be one of: {', '.join(sorted(_VALID_ROLES))}"}), 400
        updates["role"] = role

    if "is_active" in data:
        updates["is_active"] = 1 if data["is_active"] else 0

    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400

    db = DatabaseManager()
    target = db.get_auth_user_by_id(user_id)
    if not target:
        return jsonify({"error": "User not found"}), 404

    # Guard: prevent removing the last active admin.
    if target["role"] == "admin":
        demoting = updates.get("role") not in (None, "admin")
        deactivating = updates.get("is_active") == 0
        if (demoting or deactivating) and db.get_admin_count() <= 1:
            return jsonify({"error": "Cannot remove the last active admin account"}), 403

    updated = db.update_auth_user(user_id, updates)
    if not updated:
        return jsonify({"error": "User not found"}), 404

    logger.info(
        "Admin %r updated user id=%d: %s",
        g.current_user["username"], user_id, updates,
    )
    return jsonify({"message": "User updated"}), 200


# ---------------------------------------------------------------------------
# Admin: delete user
# ---------------------------------------------------------------------------

@users_bp.route('/<int:user_id>', methods=['DELETE'])
@require_role('admin')
def delete_user(user_id: int):
    """
    Permanently delete a SuggestArr account.

    Guards:
      - Admins cannot delete their own account.
      - The last active admin cannot be deleted.

    Response (200): { "message": "User deleted" }
    Response (403): { "error": "<guard message>" }
    Response (404): { "error": "User not found" }
    """
    caller_id = _current_user_id()
    if user_id == caller_id:
        return jsonify({"error": "Admins cannot delete their own account"}), 403

    db = DatabaseManager()
    target = db.get_auth_user_by_id(user_id)
    if not target:
        return jsonify({"error": "User not found"}), 404

    if target["role"] == "admin" and db.get_admin_count() <= 1:
        return jsonify({"error": "Cannot delete the last active admin account"}), 403

    db.delete_auth_user(user_id)
    logger.info("Admin %r deleted user id=%d (%r)", g.current_user["username"], user_id, target["username"])
    return jsonify({"message": "User deleted"}), 200


# ===========================================================================
# Media profile linking — any authenticated user
# ===========================================================================

# ---------------------------------------------------------------------------
# List linked profiles
# ---------------------------------------------------------------------------

@users_bp.route('/me/links', methods=['GET'])
def get_my_links():
    """
    Return the current user's linked external media accounts.

    Access tokens are never included in the response.

    Response (200): list of { id, provider, external_username, created_at }
    """
    db = DatabaseManager()
    links = db.get_user_media_profiles(_current_user_id())
    return jsonify(links), 200


# ---------------------------------------------------------------------------
# Link Jellyfin
# ---------------------------------------------------------------------------

@users_bp.route('/me/link/jellyfin', methods=['POST'])
def link_jellyfin():
    """
    Validate Jellyfin credentials and store the resulting profile link.

    The password is used only for validation and is never stored.

    Request JSON:
      username    (str) — Jellyfin username
      password    (str) — Jellyfin password
      server_url  (str, optional) — Jellyfin server URL; falls back to
                  JELLYFIN_API_URL from config if omitted

    Response (200): { "message": "Jellyfin account linked", "external_username": <str> }
    Response (400): { "error": "<validation message>" }
    Response (401): { "error": "Jellyfin credentials invalid" }
    """
    return _link_jellyfin_or_emby('jellyfin')


# ---------------------------------------------------------------------------
# Link Emby
# ---------------------------------------------------------------------------

@users_bp.route('/me/link/emby', methods=['POST'])
def link_emby():
    """
    Validate Emby credentials and store the resulting profile link.

    Emby uses the same authentication API format as Jellyfin.

    Request JSON:
      username    (str) — Emby username
      password    (str) — Emby password
      server_url  (str, optional) — Emby server URL

    Response (200): { "message": "Emby account linked", "external_username": <str> }
    Response (400): { "error": "<validation message>" }
    Response (401): { "error": "Emby credentials invalid" }
    """
    return _link_jellyfin_or_emby('emby')


def _link_jellyfin_or_emby(provider: str):
    """
    Shared handler for Jellyfin and Emby profile linking.

    Both servers expose the same /Users/AuthenticateByName endpoint.
    Validates credentials, stores only the external user ID and username,
    then discards the plaintext password.

    Args:
        provider: 'jellyfin' or 'emby'
    """
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    server_url = (data.get("server_url") or "").rstrip("/")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    if not server_url:
        from api_service.services.config_service import ConfigService
        config = ConfigService.get_runtime_config()
        if provider == 'jellyfin':
            server_url = (config.get('JELLYFIN_API_URL') or "").rstrip("/")
        else:
            # Emby doesn't have a dedicated config key; caller must provide it.
            server_url = ""

    if not server_url:
        return jsonify({"error": "server_url is required"}), 400

    auth_url = f"{server_url}/Users/AuthenticateByName"
    # Jellyfin / Emby require a specific Authorization header format.
    auth_header = (
        f'MediaBrowser Client="{_PLEX_CLIENT_NAME}", '
        f'Device="SuggestArr", '
        f'DeviceId="{_PLEX_CLIENT_ID}", '
        f'Version="{_PLEX_VERSION}"'
    )
    try:
        resp = http_requests.post(
            auth_url,
            json={"Username": username, "Pw": password},
            headers={"X-Emby-Authorization": auth_header, "Content-Type": "application/json"},
            timeout=10,
        )
    except Exception as exc:
        logger.error("%s auth request failed: %s", provider.capitalize(), exc)
        return jsonify({"error": f"Could not reach {provider.capitalize()} server"}), 502

    if resp.status_code != 200:
        logger.warning("%s auth failed for user %r: HTTP %d", provider.capitalize(), username, resp.status_code)
        return jsonify({"error": f"{provider.capitalize()} credentials invalid"}), 401

    try:
        body = resp.json()
        external_user_id = body["User"]["Id"]
        external_username = body["User"]["Name"]
    except (KeyError, ValueError) as exc:
        logger.error("Unexpected %s auth response: %s", provider.capitalize(), exc)
        return jsonify({"error": "Unexpected response from server"}), 502

    db = DatabaseManager()
    # We do not store an access token for Jellyfin/Emby — password-based auth
    # is sufficient for future re-validation if needed.
    db.create_user_media_profile(
        _current_user_id(), provider, external_user_id, external_username
    )
    logger.info("User id=%d linked %s account: %r", _current_user_id(), provider, external_username)
    return jsonify({"message": f"{provider.capitalize()} account linked", "external_username": external_username}), 200


# ---------------------------------------------------------------------------
# Unlink a provider
# ---------------------------------------------------------------------------

@users_bp.route('/me/link/<provider>', methods=['DELETE'])
def unlink_provider(provider: str):
    """
    Remove the current user's link to an external media account.

    Response (200): { "message": "Account unlinked" }
    Response (400): { "error": "Invalid provider" }
    Response (404): { "error": "No linked account found for provider" }
    """
    if provider not in _VALID_PROVIDERS:
        return jsonify({"error": f"Invalid provider. Must be one of: {', '.join(sorted(_VALID_PROVIDERS))}"}), 400

    db = DatabaseManager()
    deleted = db.delete_user_media_profile(_current_user_id(), provider)
    if not deleted:
        return jsonify({"error": f"No linked account found for {provider}"}), 404

    logger.info("User id=%d unlinked %s account", _current_user_id(), provider)
    return jsonify({"message": "Account unlinked"}), 200


# ---------------------------------------------------------------------------
# Plex OAuth: start
# ---------------------------------------------------------------------------

@users_bp.route('/me/link/plex/oauth-start', methods=['GET'])
def plex_oauth_start():
    """
    Begin the Plex OAuth device flow.

    Calls plex.tv to generate a one-time PIN and returns the PIN id and
    the Plex auth URL for the frontend to open in a popup/tab.

    Response (200): { "pin_id": <int>, "auth_url": <str> }
    Response (502): { "error": "Could not reach Plex.tv" }
    """
    try:
        resp = http_requests.post(
            "https://plex.tv/api/v2/pins",
            headers={**_plex_headers(), "Content-Type": "application/x-www-form-urlencoded"},
            data={"strong": "true"},
            timeout=10,
        )
        resp.raise_for_status()
        body = resp.json()
    except Exception as exc:
        logger.error("Failed to create Plex PIN: %s", exc)
        return jsonify({"error": "Could not reach Plex.tv"}), 502

    pin_id = body["id"]
    pin_code = body["code"]
    auth_url = (
        f"https://app.plex.tv/auth#?"
        f"clientID={_PLEX_CLIENT_ID}"
        f"&code={pin_code}"
        f"&context%5Bdevice%5D%5Bproduct%5D={_PLEX_PRODUCT}"
    )

    logger.debug("Plex OAuth started: pin_id=%s for user id=%d", pin_id, _current_user_id())
    return jsonify({"pin_id": pin_id, "auth_url": auth_url}), 200


# ---------------------------------------------------------------------------
# Plex OAuth: poll
# ---------------------------------------------------------------------------

@users_bp.route('/me/link/plex/oauth-poll', methods=['POST'])
def plex_oauth_poll():
    """
    Poll plex.tv to check whether the user has authorised the PIN.

    When the PIN has been claimed (authToken is present), validates the token
    by fetching the Plex user profile and stores the link.

    Request JSON:
      pin_id  (int) — the PIN id returned by oauth-start

    Response (200): { "status": "pending" }               — not yet authorised
    Response (200): { "status": "linked", "external_username": <str> }
    Response (400): { "error": "pin_id is required" }
    Response (502): { "error": "Could not reach Plex.tv" }
    """
    data = request.get_json(silent=True) or {}
    pin_id = data.get("pin_id")
    if not pin_id:
        return jsonify({"error": "pin_id is required"}), 400

    try:
        resp = http_requests.get(
            f"https://plex.tv/api/v2/pins/{pin_id}",
            headers=_plex_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        body = resp.json()
    except Exception as exc:
        logger.error("Failed to poll Plex PIN %s: %s", pin_id, exc)
        return jsonify({"error": "Could not reach Plex.tv"}), 502

    auth_token = body.get("authToken")
    if not auth_token:
        return jsonify({"status": "pending"}), 200

    # Token granted — fetch the user's Plex identity.
    try:
        user_resp = http_requests.get(
            "https://plex.tv/api/v2/user",
            headers={**_plex_headers(), "X-Plex-Token": auth_token},
            timeout=10,
        )
        user_resp.raise_for_status()
        user_body = user_resp.json()
    except Exception as exc:
        logger.error("Failed to fetch Plex user info: %s", exc)
        return jsonify({"error": "Could not retrieve Plex user info"}), 502

    external_user_id = str(user_body.get("id", ""))
    external_username = user_body.get("username") or user_body.get("email") or "unknown"

    db = DatabaseManager()
    db.create_user_media_profile(
        _current_user_id(), "plex", external_user_id, external_username, access_token=auth_token
    )
    logger.info(
        "User id=%d linked Plex account: %r (plex_id=%s)",
        _current_user_id(), external_username, external_user_id,
    )
    return jsonify({"status": "linked", "external_username": external_username}), 200
