"""Credential-based media account linking for the authenticated user."""

import requests as http_requests

from flask import Blueprint, g, jsonify, request

from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.services.config_service import ConfigService

logger = LoggerManager.get_logger("IntegrationsRoute")
integrations_bp = Blueprint("integrations", __name__)


def _current_user_id() -> int:
    """Return the currently authenticated SuggestArr user id."""
    return int(g.current_user["id"])


def _read_credentials() -> tuple[str, str]:
    """Read and validate username/password from request JSON."""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        raise ValueError("username and password are required")

    return username, password


def _jellyfin_auth_headers() -> dict[str, str]:
    """Build authentication headers used by Jellyfin/Emby auth endpoint."""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Emby-Authorization": (
            'MediaBrowser Client="SuggestArr", Device="SuggestArr", '
            'DeviceId="suggestarr", Version="1.0.0"'
        ),
    }


def _link_jellyfin_like(provider: str):
    """Authenticate with Jellyfin/Emby using user credentials and persist mapping."""
    try:
        username, password = _read_credentials()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    config = ConfigService.get_runtime_config()
    server_url = (config.get("JELLYFIN_API_URL") or "").rstrip("/")
    if not server_url:
        return jsonify({"error": f"{provider.capitalize()} server not configured"}), 503

    auth_url = f"{server_url}/Users/AuthenticateByName"
    payload_candidates = [
        {"Username": username, "Pw": password},
        {"Username": username, "Password": password},
    ]

    response = None
    for payload in payload_candidates:
        try:
            response = http_requests.post(
                auth_url,
                json=payload,
                headers=_jellyfin_auth_headers(),
                timeout=10,
            )
        except Exception as exc:
            logger.error("Failed %s auth request: %s", provider, exc)
            return jsonify({"error": f"Could not reach {provider.capitalize()} server"}), 502

        if 200 <= response.status_code < 300:
            break

    if response is None:
        return jsonify({"error": f"Could not reach {provider.capitalize()} server"}), 502

    if response.status_code in (401, 403):
        return jsonify({"error": f"{provider.capitalize()} credentials invalid"}), 401

    if not (200 <= response.status_code < 300):
        return jsonify({"error": f"Failed to authenticate with {provider.capitalize()}"}), 502

    try:
        body = response.json()
    except Exception:
        return jsonify({"error": f"Invalid {provider.capitalize()} response"}), 502

    user_data = body.get("User") or {}
    external_user_id = str(user_data.get("Id") or "")
    external_username = (user_data.get("Name") or username).strip()

    if not external_user_id or not external_username:
        return jsonify({"error": f"Invalid {provider.capitalize()} user response"}), 502

    db = DatabaseManager()
    db.create_user_media_profile(
        _current_user_id(), provider, external_user_id, external_username, access_token=None
    )

    logger.info("User id=%d linked %s account: %r", _current_user_id(), provider, external_username)
    return jsonify(
        {
            "message": f"{provider.capitalize()} account linked",
            "provider": provider,
            "external_user_id": external_user_id,
            "external_username": external_username,
        }
    ), 200


@integrations_bp.route("/jellyfin/link", methods=["POST"])
def link_my_jellyfin_account():
    """Allow an authenticated user to link their own Jellyfin account."""
    return _link_jellyfin_like("jellyfin")


@integrations_bp.route("/emby/link", methods=["POST"])
def link_my_emby_account():
    """Allow an authenticated user to link their own Emby account."""
    return _link_jellyfin_like("emby")


@integrations_bp.route("/plex/link", methods=["POST"])
def link_my_plex_account():
    """Allow an authenticated user to link their own Plex account using credentials."""
    try:
        username, password = _read_credentials()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        response = http_requests.post(
            "https://plex.tv/users/sign_in.json",
            auth=(username, password),
            headers={
                "Accept": "application/json",
                "X-Plex-Client-Identifier": "SuggestArr",
                "X-Plex-Product": "SuggestArr",
                "X-Plex-Version": "1.0.0",
            },
            timeout=10,
        )
    except Exception as exc:
        logger.error("Failed Plex sign-in request: %s", exc)
        return jsonify({"error": "Could not reach Plex.tv"}), 502

    if response.status_code in (401, 403):
        return jsonify({"error": "Plex credentials invalid"}), 401

    if not (200 <= response.status_code < 300):
        return jsonify({"error": "Failed to authenticate with Plex"}), 502

    try:
        body = response.json() or {}
    except Exception:
        return jsonify({"error": "Invalid Plex response"}), 502

    user_data = body.get("user") or {}
    external_user_id = str(user_data.get("id") or "")
    external_username = (user_data.get("username") or user_data.get("email") or username).strip()

    if not external_user_id or not external_username:
        return jsonify({"error": "Invalid Plex user response"}), 502

    db = DatabaseManager()
    db.create_user_media_profile(
        _current_user_id(), "plex", external_user_id, external_username, access_token=None
    )

    logger.info("User id=%d linked plex account: %r", _current_user_id(), external_username)
    return jsonify(
        {
            "message": "Plex account linked",
            "provider": "plex",
            "external_user_id": external_user_id,
            "external_username": external_username,
        }
    ), 200
