from typing import Any, Optional

from asgiref.sync import async_to_sync
from flask import Blueprint, jsonify, request

from api_service.auth.middleware import require_role
from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.services.config_service import ConfigService
from api_service.services.trakt.trakt_client import (
    TraktClient,
    TraktDeviceDenied,
    TraktDeviceExpired,
    TraktDevicePending,
)

logger = LoggerManager.get_logger("TraktRoute")
trakt_bp = Blueprint("trakt", __name__)


def _get_json() -> dict:
    """Return the request JSON payload or an empty dict."""
    return request.get_json(silent=True) or {}


def _trakt_credentials_from_payload(payload: dict) -> tuple[str, str]:
    """Extract app-level Trakt OAuth credentials from accepted payload keys."""
    client_id = payload.get("client_id") or payload.get("TRAKT_CLIENT_ID") or ""
    client_secret = payload.get("client_secret") or payload.get("TRAKT_CLIENT_SECRET") or ""
    return str(client_id).strip(), str(client_secret).strip()


def _trakt_credentials_from_config() -> tuple[str, str]:
    """Extract app-level Trakt OAuth credentials from runtime configuration."""
    config = ConfigService.get_runtime_config()
    integrations = config.get("integrations") if isinstance(config.get("integrations"), dict) else {}
    trakt_config = integrations.get("trakt") if isinstance(integrations.get("trakt"), dict) else {}
    client_id = config.get("TRAKT_CLIENT_ID") or trakt_config.get("client_id") or ""
    client_secret = config.get("TRAKT_CLIENT_SECRET") or trakt_config.get("client_secret") or ""
    return str(client_id).strip(), str(client_secret).strip()


def _resolve_trakt_credentials(payload: dict) -> tuple[str, str, bool]:
    """Resolve app-level Trakt OAuth credentials.

    Returns:
        tuple: client_id, client_secret, whether both values came from payload.
    """
    payload_client_id, payload_client_secret = _trakt_credentials_from_payload(payload)
    if payload_client_id and payload_client_secret:
        return payload_client_id, payload_client_secret, True

    config_client_id, config_client_secret = _trakt_credentials_from_config()
    return config_client_id, config_client_secret, False


def _save_app_credentials_if_supplied(db: DatabaseManager, client_id: str, client_secret: str, from_payload: bool) -> None:
    """Persist only app-level Trakt OAuth credentials when explicitly supplied."""
    if from_payload:
        db.set_integration("trakt", {
            "client_id": client_id,
            "client_secret": client_secret,
        })


def _selected_provider() -> str:
    """Return the configured media-server provider (lowercased)."""
    config = load_env_vars()
    return str(config.get("SELECTED_SERVICE") or "").lower()


def _selected_media_users() -> list[dict]:
    """Return the configured media-server users as a list of dicts."""
    config = load_env_vars()
    users = config.get("SELECTED_USERS") or []
    return [u for u in users if isinstance(u, dict)]


def _find_selected_user(provider: str, external_user_id: str) -> Optional[dict]:
    """Return the matching media user, or None when provider/user is unknown.

    The provider must match the configured ``SELECTED_SERVICE`` and the id must
    appear in ``SELECTED_USERS``; otherwise the target is treated as unknown.
    """
    if provider.lower() != _selected_provider():
        return None
    for user in _selected_media_users():
        if str(user.get("id")) == str(external_user_id):
            return user
    return None


async def _request_device_code(client_id: str, client_secret: str, db: DatabaseManager) -> dict[str, Any]:
    """Request a Trakt device-code activation payload."""
    async with TraktClient(client_id, client_secret, db=db) as client:
        return await client.request_device_code()


async def _poll_device_token(
    client_id: str,
    client_secret: str,
    device_code: str,
    db: DatabaseManager,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Exchange a device code and fetch authenticated Trakt account metadata.

    The client is constructed WITHOUT provider/external_user_id so the initial
    token exchange does not attempt to persist via ``update_media_user_trakt_tokens``
    (a guaranteed 0-row UPDATE before the account row exists). The caller's
    ``upsert_media_user_trakt_account`` is the single source of truth for persisting
    the freshly obtained tokens against the correct target media user.
    """
    async with TraktClient(client_id, client_secret, db=db) as client:
        token_payload = await client.poll_for_token(device_code)
        user_settings = await client.get_user_settings()
    return token_payload, user_settings


def _mark_error_unless_connected(db: DatabaseManager, provider: str, external_user_id: str, message: str) -> None:
    """Mark a media user's Trakt link errored, unless it is already connected."""
    try:
        identity = db.get_media_user_identity(provider.lower(), str(external_user_id))
    except (ValueError, KeyError):
        return
    link = db.get_trakt_account_link(identity["id"])
    if link and not link["connected"]:
        db.mark_trakt_account_link_error(identity["id"], "error", message)


@trakt_bp.route("/media-users", methods=["GET"])
@require_role("admin")
def list_media_users():
    """Admin: list media-server users with token-safe Trakt status."""
    db = DatabaseManager()
    provider = _selected_provider()
    result = []
    for user in _selected_media_users():
        ext_id = str(user.get("id"))
        link = {"connected": False}
        try:
            identity = db.get_media_user_identity(provider, ext_id)
            existing = db.get_trakt_account_link(identity["id"])
            if existing:
                link = existing
                if link.get("connected"):
                    sources = db.get_enabled_trakt_sources(identity["id"])
                    watched = next((s for s in sources if s["source_type"] == "watched_history"), {})
                    link["use_as_seed"] = watched.get("use_as_seed", True)
                    link["use_as_exclusion"] = watched.get("use_as_exclusion", True)
        except ValueError:
            link = {"connected": False}
        result.append({
            "provider": provider,
            "external_user_id": ext_id,
            "external_username": user.get("name"),
            "trakt": link,
        })
    return jsonify({"media_users": result}), 200


@trakt_bp.route("/media-users/<provider>/<external_user_id>/device/code", methods=["POST"])
@require_role("admin")
def request_media_user_device_code(provider: str, external_user_id: str):
    """Admin: start Trakt device-code OAuth for a target media user."""
    db = DatabaseManager()
    if _find_selected_user(provider, external_user_id) is None:
        return jsonify({"message": "Media user not found", "status": "error"}), 404

    payload = _get_json()
    client_id, client_secret, from_payload = _resolve_trakt_credentials(payload)
    if not client_id or not client_secret:
        return jsonify({"message": "Configure Trakt app credentials first", "status": "error"}), 400

    _save_app_credentials_if_supplied(db, client_id, client_secret, from_payload)

    try:
        activation = async_to_sync(_request_device_code)(client_id, client_secret, db)
        return jsonify(activation), 200
    except RuntimeError as exc:
        logger.warning("Trakt device-code request failed for %s/%s: %s", provider, external_user_id, exc)
        return jsonify({"message": str(exc), "status": "error"}), 400
    except Exception as exc:
        logger.error("Unexpected Trakt device-code error for %s/%s: %s", provider, external_user_id, exc, exc_info=True)
        return jsonify({"message": "Error requesting Trakt device code", "status": "error"}), 500


@trakt_bp.route("/media-users/<provider>/<external_user_id>/device/token", methods=["POST"])
@require_role("admin")
def poll_media_user_device_token(provider: str, external_user_id: str):
    """Admin: poll Trakt OAuth completion and persist tokens for a target media user."""
    db = DatabaseManager()
    user = _find_selected_user(provider, external_user_id)
    if user is None:
        return jsonify({"message": "Media user not found", "status": "error"}), 404

    payload = _get_json()
    device_code = payload.get("device_code")
    if not device_code:
        return jsonify({"message": "device_code is required", "status": "error"}), 400

    client_id, client_secret, _ = _resolve_trakt_credentials(payload)
    if not client_id or not client_secret:
        return jsonify({"message": "Configure Trakt app credentials first", "status": "error"}), 400

    provider = provider.lower()
    external_user_id = str(external_user_id)

    try:
        token_payload, user_settings = async_to_sync(_poll_device_token)(
            client_id, client_secret, str(device_code), db,
        )
        # 1. Upsert media user identity (the (provider, external_user_id) anchor)
        identity = db.upsert_media_user_identity(
            provider, external_user_id, user.get("name"),
        )

        # 2. Upsert Trakt account link (keyed by the media user identity)
        link_id = db.upsert_trakt_account_link(
            media_user_identity_id=identity["id"],
            trakt_user_id=user_settings.get("trakt_user_id"),
            trakt_username=user_settings.get("trakt_username"),
            token_source="manual_oauth",
            status="connected",
        )

        # 3. Upsert OAuth tokens
        db.upsert_trakt_oauth_tokens(
            link_id=link_id,
            access_token=token_payload.get("access_token", ""),
            refresh_token=token_payload.get("refresh_token", ""),
            expires_at=token_payload.get("expires_at"),
        )

        # 4. Upsert default watched_history source
        db.upsert_trakt_source(
            media_user_identity_id=identity["id"],
            source_type="watched_history",
            source_key="watched_history",
            enabled=True,
            use_as_seed=True,
            use_as_exclusion=True,
        )

        return jsonify({
            "connected": True,
            "status": "connected",
            "trakt_user_id": user_settings.get("trakt_user_id"),
            "trakt_username": user_settings.get("trakt_username"),
            "expires_at": token_payload.get("expires_at"),
        }), 200
    except TraktDevicePending:
        return jsonify({"connected": False, "status": "pending"}), 202
    except (TraktDeviceExpired, TraktDeviceDenied) as exc:
        _mark_error_unless_connected(db, provider, external_user_id, str(exc))
        logger.info("Trakt device-token poll failed for %s/%s: %s", provider, external_user_id, exc)
        return jsonify({"message": str(exc), "status": "error"}), 400
    except RuntimeError as exc:
        logger.info("Trakt device-token poll failed for %s/%s: %s", provider, external_user_id, exc)
        _mark_error_unless_connected(db, provider, external_user_id, "Trakt connection failed")
        return jsonify({"message": "Trakt connection failed", "status": "error"}), 400
    except Exception as exc:
        logger.error("Unexpected Trakt device-token error for %s/%s: %s", provider, external_user_id, exc, exc_info=True)
        _mark_error_unless_connected(db, provider, external_user_id, "Trakt connection failed")
        return jsonify({"message": "Error connecting Trakt", "status": "error"}), 500


@trakt_bp.route("/media-users/<provider>/<external_user_id>", methods=["DELETE"])
@require_role("admin")
def delete_media_user_trakt_account(provider: str, external_user_id: str):
    """Admin: unlink the Trakt account associated with a media user."""
    db = DatabaseManager()
    if _find_selected_user(provider, external_user_id) is None:
        return jsonify({"message": "Media user not found", "status": "error"}), 404
    try:
        identity = db.get_media_user_identity(provider.lower(), str(external_user_id))
        db.unlink_trakt_account(identity["id"])
    except (ValueError, KeyError):
        pass
    return jsonify({"connected": False, "status": "deleted"}), 200


@trakt_bp.route("/sources/<provider>/<external_user_id>", methods=["PUT"])
@require_role("admin")
def update_trakt_source(provider: str, external_user_id: str):
    """Admin: toggle use_as_seed / use_as_exclusion for a media user's watched_history source."""
    db = DatabaseManager()
    payload = _get_json()

    try:
        identity = db.get_media_user_identity(provider.lower(), str(external_user_id))
    except ValueError:
        return jsonify({"message": "Media user not found", "status": "error"}), 404

    sources = db.get_trakt_sources(identity["id"])
    watched_source = None
    for s in sources:
        if s["source_type"] == "watched_history":
            watched_source = s
            break

    if not watched_source:
        return jsonify({"message": "No watched_history source found", "status": "error"}), 404

    use_as_seed = payload.get("use_as_seed", watched_source["use_as_seed"])
    use_as_exclusion = payload.get("use_as_exclusion", watched_source["use_as_exclusion"])

    db.upsert_trakt_source(
        media_user_identity_id=identity["id"],
        source_type="watched_history",
        source_key="watched_history",
        enabled=watched_source["enabled"],
        use_as_seed=bool(use_as_seed),
        use_as_exclusion=bool(use_as_exclusion),
        list_id=watched_source.get("list_id"),
        list_slug=watched_source.get("list_slug"),
        username=watched_source.get("username"),
    )

    return jsonify({
        "use_as_seed": bool(use_as_seed),
        "use_as_exclusion": bool(use_as_exclusion),
    }), 200
