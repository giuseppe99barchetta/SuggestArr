"""HTTP routes for linking and inspecting Simkl accounts.

Mirrors the Trakt blueprint, with two deliberate departures:

* The app ``client_id`` is read from configuration only, never from a request
  body. Trakt's routes accept credentials in the payload and persist them,
  which for Simkl would let any admin-authenticated caller overwrite the
  install's integration config from a link request.
* The in-flight PIN is held server-side against the requesting identity, so a
  caller cannot submit a code they did not request and attach whichever Simkl
  account authorized it to a different media user.
"""
from typing import Any, Optional

from asgiref.sync import async_to_sync
from flask import Blueprint, g, jsonify, request

from api_service.auth.middleware import require_role
from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.services.config_service import ConfigService
from api_service.services.simkl.simkl_client import (
    SimklAuthError,
    SimklClient,
    SimklClientIdError,
    SimklPinExpired,
    SimklPinPending,
)
from api_service.services.simkl.watch_history_sync import (
    SEED_STATUSES,
    SimklWatchHistorySync,
)

logger = LoggerManager.get_logger("SimklRoute")
simkl_bp = Blueprint("simkl", __name__)

_NOT_CONFIGURED = "Configure the Simkl client ID first"
_NOT_LINKED = "Simkl account not linked"


def _CLIENT_ID_FAILED(exc: Exception) -> dict:
    """Body for a 412 from Simkl.

    Carries a stable ``code`` because this failure belongs on the integration
    settings card rather than against the user whose request happened to hit
    it, and the UI should not have to match on message text to tell the
    difference.
    """
    return {"message": str(exc), "status": "error", "code": "client_id_failed"}


def _get_json() -> dict:
    return request.get_json(silent=True) or {}


def _simkl_client_id() -> str:
    """Resolve the app-level Simkl client id from configuration.

    Config is the only source. Simkl's PIN flow has no client secret, so a
    request body carrying Simkl credentials has nothing legitimate to offer.
    """
    config = ConfigService.get_runtime_config()
    integrations = config.get("integrations") if isinstance(config.get("integrations"), dict) else {}
    simkl_config = integrations.get("simkl") if isinstance(integrations.get("simkl"), dict) else {}
    return str(config.get("SIMKL_CLIENT_ID") or simkl_config.get("client_id") or "").strip()


def _tmdb_api_key() -> str:
    return str(ConfigService.get_runtime_config().get("TMDB_API_KEY") or "").strip()


def _selected_provider() -> str:
    return str(load_env_vars().get("SELECTED_SERVICE") or "").lower()


def _selected_media_users() -> list[dict]:
    users = load_env_vars().get("SELECTED_USERS") or []
    return [u for u in users if isinstance(u, dict)]


def _find_selected_user(provider: str, external_user_id: str) -> Optional[dict]:
    """Return the matching configured media user, or None when unknown."""
    if provider.lower() != _selected_provider():
        return None
    for user in _selected_media_users():
        if str(user.get("id")) == str(external_user_id):
            return user
    return None


def _current_user_id() -> int:
    return int(g.current_user["id"])


def _current_user_media_profile(db: DatabaseManager) -> Optional[dict]:
    provider = _selected_provider()
    if provider not in {"jellyfin", "emby", "plex"}:
        return None
    for profile in db.get_user_media_profiles(_current_user_id()):
        if profile.get("provider") == provider:
            return profile
    return None


def _link_status_for_identity(db: DatabaseManager, identity_id: int) -> dict:
    """Return a token-safe Simkl link status for a media-user identity."""
    link = db.get_simkl_account_link(identity_id)
    if not link:
        return {"connected": False}

    # pending_user_code is an in-flight authorization secret, and status/error
    # payloads are the easiest place for it to leak into a log or a browser.
    link.pop("pending_user_code", None)
    link.pop("activities_json", None)

    if link.get("connected"):
        sources = db.get_enabled_simkl_sources(identity_id)
        watched = next((s for s in sources if s["source_type"] == "watched_history"), {})
        link["use_as_seed"] = watched.get("use_as_seed", True)
        link["use_as_exclusion"] = watched.get("use_as_exclusion", True)
        link["cached_items"] = len(db.get_simkl_watched_cache(link["id"]))
        # Distinguishes "linked but the first sync has not run" from "linked
        # and this account genuinely has no watch history", which otherwise
        # look identical and read as a broken link.
        link["initial_sync_complete"] = bool(link.get("last_full_sync_at"))
    return link


def _media_user_payload(profile: dict, link: dict) -> dict:
    return {
        "provider": profile.get("provider"),
        "external_user_id": str(profile.get("external_user_id")),
        "external_username": profile.get("external_username"),
        "simkl": link,
    }


async def _request_pin(client_id: str) -> dict[str, Any]:
    async with SimklClient(client_id) as client:
        return await client.request_pin_code()


async def _exchange_pin(client_id: str, user_code: str) -> tuple[str, dict[str, Any]]:
    """Exchange an authorized PIN for a token and the account identity."""
    async with SimklClient(client_id) as client:
        access_token = await client.poll_for_token(user_code)
        settings = await client.get_user_settings()
    return access_token, settings


async def _preview_items(
    client_id: str, tmdb_api_key: str, db: DatabaseManager, link: dict,
    access_token: str, limit: int,
) -> list[dict[str, Any]]:
    """Return the most recently watched cached titles, syncing first if due."""
    sync = SimklWatchHistorySync(client_id, db=db, tmdb_api_key=tmdb_api_key)
    await sync.ensure_synced(link, access_token)
    rows = db.get_simkl_watched_cache(link["id"], SEED_STATUSES)
    return [
        {
            "tmdb_id": row.get("tmdb_id"),
            "media_type": row.get("media_type"),
            "title": row.get("title"),
            "year": row.get("year"),
            "watched_at": row.get("last_watched_at"),
            "status": row.get("status"),
        }
        for row in rows[:limit]
    ]


def _link_and_persist(
    db: DatabaseManager, identity: dict, access_token: str, settings: dict
) -> dict:
    """Persist a completed link, its token, and the default source."""
    # Captured before the upsert overwrites it. A re-link may point at a
    # different Simkl account than the cache was built from, and those stale
    # rows would otherwise be served as the new account's history.
    previous = db.get_simkl_account_link(identity["id"]) or {}
    previous_account = str(previous.get("simkl_user_id") or "")
    new_account = str(settings.get("simkl_user_id") or "")

    link_id = db.upsert_simkl_account_link(
        media_user_identity_id=identity["id"],
        simkl_user_id=settings.get("simkl_user_id"),
        simkl_username=settings.get("simkl_username"),
        token_source="manual_oauth",
        status="connected",
    )
    db.upsert_simkl_oauth_tokens(link_id=link_id, access_token=access_token)
    db.upsert_simkl_source(
        media_user_identity_id=identity["id"],
        source_type="watched_history",
        source_key="watched_history",
        enabled=True,
        use_as_seed=True,
        use_as_exclusion=True,
    )
    if previous_account and previous_account != new_account:
        logger.info(
            "Simkl link now points at a different account; clearing %d cached rows",
            db.clear_simkl_watched_cache(link_id),
        )
        # Force a full rebuild rather than a delta against the old account's
        # activity timestamps.
        db.update_simkl_sync_state(link_id, activities={})
    return {
        "connected": True,
        "status": "connected",
        "simkl_user_id": settings.get("simkl_user_id"),
        "simkl_username": settings.get("simkl_username"),
    }


def _resolve_token(db: DatabaseManager, identity_id: int) -> tuple[Optional[dict], Optional[str]]:
    """Return a connected link and its access token, or (None, None)."""
    link = db.get_simkl_account_link(identity_id)
    if not link or not link.get("connected"):
        return None, None
    tokens = db.get_simkl_oauth_tokens(link["id"])
    if not tokens or not tokens.get("access_token"):
        return None, None
    return link, tokens["access_token"]


# ---- Status ------------------------------------------------------------------

@simkl_bp.route("/media-users", methods=["GET"])
@require_role("admin")
def list_media_users():
    """Admin: list media-server users with token-safe Simkl status."""
    db = DatabaseManager()
    provider = _selected_provider()
    result = []
    for user in _selected_media_users():
        ext_id = str(user.get("id"))
        try:
            identity = db.get_media_user_identity(provider, ext_id)
            link = _link_status_for_identity(db, identity["id"])
        except ValueError:
            link = {"connected": False}
        result.append({
            "provider": provider,
            "external_user_id": ext_id,
            "external_username": user.get("name"),
            "simkl": link,
        })
    return jsonify({"media_users": result}), 200


@simkl_bp.route("/me", methods=["GET"])
def get_my_simkl_status():
    """Authenticated user: return own media-profile Simkl status."""
    db = DatabaseManager()
    profile = _current_user_media_profile(db)
    if not profile:
        return jsonify({"message": "Link your media server account first", "status": "error"}), 404

    identity = db.upsert_media_user_identity(
        profile["provider"], profile["external_user_id"], profile.get("external_username"),
    )
    link = _link_status_for_identity(db, identity["id"])
    return jsonify({"media_user": _media_user_payload(profile, link)}), 200


# ---- PIN flow ----------------------------------------------------------------

def _start_pin(db: DatabaseManager, identity: dict, label: str):
    """Request a PIN and bind it to an identity for the later exchange."""
    client_id = _simkl_client_id()
    if not client_id:
        return jsonify({"message": _NOT_CONFIGURED, "status": "error"}), 400

    try:
        activation = async_to_sync(_request_pin)(client_id)
    except SimklClientIdError as exc:
        logger.warning("Simkl rejected the client ID while starting a PIN: %s", exc)
        return jsonify(_CLIENT_ID_FAILED(exc)), 400
    except Exception as exc:
        logger.error("Simkl PIN request failed for %s: %s", label, exc, exc_info=True)
        return jsonify({"message": "Error requesting a Simkl PIN", "status": "error"}), 500

    user_code = activation.get("user_code")
    if not user_code:
        return jsonify({"message": "Simkl returned no PIN", "status": "error"}), 502

    db.set_simkl_pending_user_code(identity["id"], user_code)
    # The code is returned to the caller who requested it but never logged:
    # anyone holding it can complete the authorization.
    return jsonify({
        "user_code": user_code,
        "verification_uri": activation.get("verification_uri"),
        "expires_in": activation.get("expires_in"),
        "interval": activation.get("interval"),
    }), 200


def _finish_pin(db: DatabaseManager, identity: dict, label: str):
    """Exchange the identity's pending PIN for a token, if the user authorized it."""
    client_id = _simkl_client_id()
    if not client_id:
        return jsonify({"message": _NOT_CONFIGURED, "status": "error"}), 400

    # Read the code from server-side state rather than the request body.
    user_code = db.get_simkl_pending_user_code(identity["id"])
    if not user_code:
        return jsonify({"message": "Request a Simkl PIN first", "status": "error"}), 400

    try:
        access_token, settings = async_to_sync(_exchange_pin)(client_id, user_code)
    except SimklPinPending:
        return jsonify({"connected": False, "status": "pending"}), 202
    except SimklPinExpired:
        db.set_simkl_pending_user_code(identity["id"], None)
        return jsonify({"message": "The Simkl PIN expired. Request a new one.", "status": "error"}), 400
    except SimklClientIdError as exc:
        return jsonify(_CLIENT_ID_FAILED(exc)), 400
    except Exception as exc:
        logger.error("Simkl PIN exchange failed for %s: %s", label, exc, exc_info=True)
        db.mark_simkl_account_link_error(identity["id"], "error", "Simkl connection failed")
        return jsonify({"message": "Error connecting Simkl", "status": "error"}), 500

    result = _link_and_persist(db, identity, access_token, settings)
    db.set_simkl_pending_user_code(identity["id"], None)
    return jsonify(result), 200


@simkl_bp.route("/me/pin/code", methods=["POST"])
def request_my_pin_code():
    """Authenticated user: start the Simkl PIN flow for own media profile."""
    db = DatabaseManager()
    profile = _current_user_media_profile(db)
    if not profile:
        return jsonify({"message": "Link your media server account first", "status": "error"}), 404
    identity = db.upsert_media_user_identity(
        profile["provider"], profile["external_user_id"], profile.get("external_username"),
    )
    return _start_pin(db, identity, f"user id={_current_user_id()}")


@simkl_bp.route("/me/pin/token", methods=["POST"])
def poll_my_pin_token():
    """Authenticated user: complete the Simkl PIN flow for own media profile."""
    db = DatabaseManager()
    profile = _current_user_media_profile(db)
    if not profile:
        return jsonify({"message": "Link your media server account first", "status": "error"}), 404
    identity = db.upsert_media_user_identity(
        profile["provider"], profile["external_user_id"], profile.get("external_username"),
    )
    return _finish_pin(db, identity, f"user id={_current_user_id()}")


@simkl_bp.route("/media-users/<provider>/<external_user_id>/pin/code", methods=["POST"])
@require_role("admin")
def request_media_user_pin_code(provider: str, external_user_id: str):
    """Admin: start the Simkl PIN flow for a target media user."""
    db = DatabaseManager()
    user = _find_selected_user(provider, external_user_id)
    if user is None:
        return jsonify({"message": "Media user not found", "status": "error"}), 404
    identity = db.upsert_media_user_identity(
        provider.lower(), str(external_user_id), user.get("name"),
    )
    return _start_pin(db, identity, f"{provider}/{external_user_id}")


@simkl_bp.route("/media-users/<provider>/<external_user_id>/pin/token", methods=["POST"])
@require_role("admin")
def poll_media_user_pin_token(provider: str, external_user_id: str):
    """Admin: complete the Simkl PIN flow for a target media user."""
    db = DatabaseManager()
    user = _find_selected_user(provider, external_user_id)
    if user is None:
        return jsonify({"message": "Media user not found", "status": "error"}), 404
    identity = db.upsert_media_user_identity(
        provider.lower(), str(external_user_id), user.get("name"),
    )
    return _finish_pin(db, identity, f"{provider}/{external_user_id}")


def _cancel_pin(db: DatabaseManager, provider: str, external_user_id: str):
    """Drop the identity's pending PIN.

    A Simkl PIN stays valid for up to fifteen minutes, so a user who abandons
    the flow would otherwise leave a live code that anyone reaching this
    identity's poll endpoint could complete on their behalf.

    An identity that was never created has no pending code, which is the state
    the caller asked for, so a missing row is success rather than an error.
    """
    try:
        identity = db.get_media_user_identity(provider.lower(), str(external_user_id))
        db.set_simkl_pending_user_code(identity["id"], None)
    except (ValueError, KeyError):
        pass
    return jsonify({"status": "cancelled"}), 200


@simkl_bp.route("/me/pin", methods=["DELETE"])
def cancel_my_pin():
    """Authenticated user: abandon an in-flight PIN for own media profile."""
    db = DatabaseManager()
    profile = _current_user_media_profile(db)
    if not profile:
        return jsonify({"message": "Link your media server account first", "status": "error"}), 404
    return _cancel_pin(db, profile["provider"], profile["external_user_id"])


@simkl_bp.route("/media-users/<provider>/<external_user_id>/pin", methods=["DELETE"])
@require_role("admin")
def cancel_media_user_pin(provider: str, external_user_id: str):
    """Admin: abandon an in-flight PIN for a target media user."""
    db = DatabaseManager()
    if _find_selected_user(provider, external_user_id) is None:
        return jsonify({"message": "Media user not found", "status": "error"}), 404
    return _cancel_pin(db, provider, external_user_id)


# ---- Unlink ------------------------------------------------------------------

def _unlink_response() -> tuple:
    """Simkl exposes no token revocation endpoint.

    The local link and cached history are deleted, but the authorization
    itself stays live on Simkl's side until the user removes the app, so the
    response says so rather than implying a revocation that did not happen.
    """
    return jsonify({
        "connected": False,
        "status": "deleted",
        "revoked_upstream": False,
        "message": (
            "Simkl access was removed locally. To revoke it at Simkl, remove "
            "SuggestArr at simkl.com/settings/connected-apps."
        ),
    }), 200


@simkl_bp.route("/media-users/<provider>/<external_user_id>", methods=["DELETE"])
@require_role("admin")
def delete_media_user_simkl_account(provider: str, external_user_id: str):
    """Admin: unlink the Simkl account associated with a media user."""
    db = DatabaseManager()
    if _find_selected_user(provider, external_user_id) is None:
        return jsonify({"message": "Media user not found", "status": "error"}), 404
    try:
        identity = db.get_media_user_identity(provider.lower(), str(external_user_id))
        db.unlink_simkl_account(identity["id"])
    except (ValueError, KeyError):
        pass
    return _unlink_response()


@simkl_bp.route("/me", methods=["DELETE"])
def delete_my_simkl_account():
    """Authenticated user: unlink own Simkl account."""
    db = DatabaseManager()
    profile = _current_user_media_profile(db)
    if not profile:
        return jsonify({"message": "Link your media server account first", "status": "error"}), 404
    try:
        identity = db.get_media_user_identity(profile["provider"], str(profile["external_user_id"]))
        db.unlink_simkl_account(identity["id"])
    except (ValueError, KeyError):
        pass
    return _unlink_response()


# ---- Preview -----------------------------------------------------------------

def _recent_response(db: DatabaseManager, identity_id: int, provider: str, external_user_id: str):
    """Shared handler for both recent-items preview routes."""
    client_id = _simkl_client_id()
    if not client_id:
        return jsonify({"message": _NOT_CONFIGURED, "status": "error"}), 400

    try:
        limit = max(1, min(int(request.args.get("limit", 10)), 50))
    except (TypeError, ValueError):
        limit = 10

    link, access_token = _resolve_token(db, identity_id)
    if not link:
        return jsonify({"message": _NOT_LINKED, "status": "error"}), 404

    try:
        items = async_to_sync(_preview_items)(
            client_id, _tmdb_api_key(), db, link, access_token, limit,
        )
    except SimklAuthError:
        db.mark_simkl_account_link_error(identity_id, "needs_reauth", "Simkl token rejected")
        return jsonify({
            "message": "Simkl access expired. Link the account again.",
            "status": "needs_reauth",
        }), 400
    except SimklClientIdError as exc:
        return jsonify(_CLIENT_ID_FAILED(exc)), 400
    except Exception as exc:
        logger.error(
            "Simkl preview failed for %s/%s: %s", provider, external_user_id, exc, exc_info=True
        )
        return jsonify({"message": "Error fetching Simkl history", "status": "error"}), 500

    return jsonify({
        "status": "success",
        "provider": provider,
        "external_user_id": str(external_user_id),
        "simkl_username": link.get("simkl_username"),
        # Lets the UI say "still syncing" instead of "no history" when the
        # first sync has not finished yet.
        "initial_sync_complete": bool(
            (db.get_simkl_account_link_by_id(link["id"]) or {}).get("last_full_sync_at")
        ),
        "items": items,
    }), 200


@simkl_bp.route("/media-users/<provider>/<external_user_id>/recent", methods=["GET"])
@require_role("admin")
def preview_media_user_recent_items(provider: str, external_user_id: str):
    """Admin: preview recently watched items from a linked Simkl account."""
    db = DatabaseManager()
    if _find_selected_user(provider, external_user_id) is None:
        return jsonify({"message": "Media user not found", "status": "error"}), 404
    try:
        identity = db.get_media_user_identity(provider.lower(), str(external_user_id))
    except ValueError:
        return jsonify({"message": "Media user not found", "status": "error"}), 404
    return _recent_response(db, identity["id"], provider.lower(), external_user_id)


@simkl_bp.route("/me/recent", methods=["GET"])
def preview_my_recent_items():
    """Authenticated user: preview recently watched items from own Simkl account."""
    db = DatabaseManager()
    profile = _current_user_media_profile(db)
    if not profile:
        return jsonify({"message": "Link your media server account first", "status": "error"}), 404
    try:
        identity = db.get_media_user_identity(profile["provider"], str(profile["external_user_id"]))
    except ValueError:
        return jsonify({"message": "Media user not found", "status": "error"}), 404
    return _recent_response(
        db, identity["id"], profile["provider"], str(profile["external_user_id"])
    )


# ---- Sources -----------------------------------------------------------------

@simkl_bp.route("/sources/<provider>/<external_user_id>", methods=["PUT"])
@require_role("admin")
def update_simkl_source(provider: str, external_user_id: str):
    """Admin: toggle use_as_seed / use_as_exclusion for a user's watched_history source."""
    db = DatabaseManager()
    payload = _get_json()

    try:
        identity = db.get_media_user_identity(provider.lower(), str(external_user_id))
    except ValueError:
        return jsonify({"message": "Media user not found", "status": "error"}), 404

    watched_source = next(
        (s for s in db.get_simkl_sources(identity["id"]) if s["source_type"] == "watched_history"),
        None,
    )
    if not watched_source:
        return jsonify({"message": "No watched_history source found", "status": "error"}), 404

    use_as_seed = payload.get("use_as_seed", watched_source["use_as_seed"])
    use_as_exclusion = payload.get("use_as_exclusion", watched_source["use_as_exclusion"])

    db.upsert_simkl_source(
        media_user_identity_id=identity["id"],
        source_type="watched_history",
        source_key="watched_history",
        enabled=watched_source["enabled"],
        use_as_seed=bool(use_as_seed),
        use_as_exclusion=bool(use_as_exclusion),
    )
    return jsonify({
        "use_as_seed": bool(use_as_seed),
        "use_as_exclusion": bool(use_as_exclusion),
    }), 200
