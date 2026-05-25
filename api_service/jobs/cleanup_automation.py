"""Cleanup automation: prune SuggestArr-originated requests + files when the
underlying media has not been favorited in the configured media server within
a configurable grace period.

Safe by default: only runs when explicitly enabled, and starts in dry-run mode.
"""

import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.services.config_service import ConfigService
from api_service.services.jellyfin.jellyfin_client import JellyfinClient
from api_service.services.plex.plex_client import PlexClient
from api_service.services.seer.seer_client import SeerClient


_run_lock = threading.Lock()
FAVORITE_USER_RATING = 10.0
SUPPORTED_MEDIA_SERVICES = {"plex", "jellyfin", "emby"}


def _normalise_selected_users(raw_users) -> List[Dict]:
    if not isinstance(raw_users, list):
        return []

    users = []
    for user in raw_users:
        if isinstance(user, dict) and user.get('id'):
            users.append(user)
        elif isinstance(user, str) and user:
            users.append({'id': user, 'name': user})
    return users


async def _build_plex_favorite_map(env_vars: Dict) -> Dict[Tuple[str, str], float]:
    """Return mapping of (media_type, tmdb_id) -> userRating from the Plex library."""
    plex_libraries_raw = env_vars.get('PLEX_LIBRARIES') or []
    plex_libraries = plex_libraries_raw if isinstance(plex_libraries_raw, list) else []

    plex_client = PlexClient(
        api_url=env_vars['PLEX_API_URL'],
        token=env_vars['PLEX_TOKEN'],
        max_content=10000,
        library_ids=plex_libraries,
        user_ids=[],
    )
    try:
        library_items = await plex_client.get_all_library_items() or {}
        rating_map: Dict[Tuple[str, str], float] = {}
        for media_type, items in library_items.items():
            for item in items or []:
                tmdb_id = item.get('tmdb_id')
                if not tmdb_id:
                    continue
                try:
                    rating = float(item.get('userRating', 0) or 0)
                except (TypeError, ValueError):
                    rating = 0.0
                rating_map[(media_type, str(tmdb_id))] = rating
        return rating_map
    finally:
        await plex_client.close()


async def _fetch_jellyfin_favorites_for_user(
    client: JellyfinClient,
    user_id: str,
    library_id: Optional[str],
) -> List[Dict]:
    session = await client._get_session()
    params = {
        "Recursive": "true",
        "IncludeItemTypes": "Movie,Series",
        "Fields": "ProviderIds,UserData",
        "Filters": "IsFavorite",
    }
    if library_id:
        params["ParentId"] = library_id

    async with session.get(
        f"{client.api_url}/Users/{user_id}/Items",
        headers=client.headers,
        params=params,
        timeout=client.REQUEST_TIMEOUT,
    ) as response:
        if response.status != 200:
            body = await response.text()
            client.logger.warning(
                "Failed to fetch favorite items for user %s: %s body=%.300s",
                user_id,
                response.status,
                body,
            )
            return []
        data = await response.json()
        return data.get("Items", []) or []


async def _build_jellyfin_favorite_map(env_vars: Dict) -> Dict[Tuple[str, str], float]:
    """Return mapping of (media_type, tmdb_id) -> favorite score for Jellyfin/Emby."""
    jellyfin_libraries_raw = env_vars.get('JELLYFIN_LIBRARIES') or []
    jellyfin_libraries = jellyfin_libraries_raw if isinstance(jellyfin_libraries_raw, list) else []
    selected_users = _normalise_selected_users(env_vars.get('SELECTED_USERS') or [])

    client = JellyfinClient(
        env_vars['JELLYFIN_API_URL'],
        env_vars['JELLYFIN_TOKEN'],
        max_content=10000,
        library_ids=jellyfin_libraries,
    )

    try:
        library_items = await client.get_all_library_items() or {}
        rating_map: Dict[Tuple[str, str], float] = {}
        for media_type, items in library_items.items():
            for item in items or []:
                tmdb_id = item.get('tmdb_id') or item.get("ProviderIds", {}).get("Tmdb")
                if tmdb_id:
                    rating_map[(media_type, str(tmdb_id))] = 0.0

        if not selected_users:
            selected_users = await client.get_all_users()

        libraries = client.libraries or []
        library_ids = [
            lib.get('id')
            for lib in libraries
            if isinstance(lib, dict) and lib.get('id')
        ]
        if not library_ids:
            library_ids = [None]

        for user in selected_users:
            user_id = str(user.get('id') or '')
            if not user_id:
                continue
            for library_id in library_ids:
                favorite_items = await _fetch_jellyfin_favorites_for_user(client, user_id, library_id)
                for item in favorite_items:
                    item_type = item.get("Type")
                    if item_type not in ("Movie", "Series"):
                        continue
                    tmdb_id = item.get("ProviderIds", {}).get("Tmdb")
                    if not tmdb_id:
                        continue
                    media_type = "tv" if item_type == "Series" else "movie"
                    rating_map[(media_type, str(tmdb_id))] = FAVORITE_USER_RATING

        return rating_map
    finally:
        await client.close()


async def _build_favorite_map(env_vars: Dict, media_service: str) -> Dict[Tuple[str, str], float]:
    if media_service == "plex":
        return await _build_plex_favorite_map(env_vars)
    if media_service in {"jellyfin", "emby"}:
        return await _build_jellyfin_favorite_map(env_vars)
    return {}


def _missing_service_config(env_vars: Dict, media_service: str) -> Optional[str]:
    if media_service == "plex":
        if not env_vars.get('PLEX_API_URL') or not env_vars.get('PLEX_TOKEN'):
            return "Plex is not configured (PLEX_API_URL / PLEX_TOKEN missing)."
    elif media_service in {"jellyfin", "emby"}:
        if not env_vars.get('JELLYFIN_API_URL') or not env_vars.get('JELLYFIN_TOKEN'):
            label = "Emby" if media_service == "emby" else "Jellyfin"
            return f"{label} is not configured (JELLYFIN_API_URL / JELLYFIN_TOKEN missing)."
    return None


async def execute_cleanup_job(force_run: bool = False, override_dry_run: Optional[bool] = None) -> Dict:
    """Run the cleanup pass.

    :param force_run: If True, bypass the 'enabled' gate (used by 'Run now').
    :param override_dry_run: If set, override the configured dry_run flag for this run only.
    :return: Summary dict.
    """
    logger = LoggerManager.get_logger("CleanupAutomation")
    db = DatabaseManager()
    settings = db.get_cleanup_settings()
    enabled = settings.get('enabled')
    dry_run = settings.get('dry_run') if override_dry_run is None else bool(override_dry_run)
    grace_days = max(1, int(settings.get('grace_days') or 7))

    if not enabled and not force_run:
        logger.debug("Cleanup job disabled; skipping.")
        return {'status': 'skipped', 'message': 'Cleanup is disabled.'}

    env_vars = ConfigService.get_runtime_config()
    media_service = (env_vars.get('SELECTED_SERVICE') or env_vars.get('MEDIA_SERVICE') or 'plex').lower()
    if media_service not in SUPPORTED_MEDIA_SERVICES:
        msg = f"Cleanup supports Plex, Jellyfin, and Emby (configured service: {media_service or 'unknown'})."
        logger.warning(msg)
        db.update_cleanup_settings(last_run_at=datetime.utcnow().isoformat(),
                                   last_run_status='unsupported', last_run_summary=msg)
        return {'status': 'unsupported', 'message': msg}

    missing_config = _missing_service_config(env_vars, media_service)
    if missing_config:
        msg = missing_config
        logger.warning(msg)
        db.update_cleanup_settings(last_run_at=datetime.utcnow().isoformat(),
                                   last_run_status='not_configured', last_run_summary=msg)
        return {'status': 'not_configured', 'message': msg}

    cutoff = (datetime.utcnow() - timedelta(days=grace_days)).isoformat()
    candidates: List[Dict] = db.get_suggestarr_requests_older_than(cutoff)
    logger.info("Cleanup: %d candidate request(s) older than %d day(s) (cutoff=%s, dry_run=%s).",
                len(candidates), grace_days, cutoff, dry_run)

    if not candidates:
        summary = f"No requests older than {grace_days} days."
        db.update_cleanup_settings(last_run_at=datetime.utcnow().isoformat(),
                                   last_run_status='ok', last_run_summary=summary)
        return {'status': 'ok', 'summary': summary, 'deleted': 0, 'kept': 0, 'missing': 0}

    favorite_map = await _build_favorite_map(env_vars, media_service)

    seer_client = None
    if not dry_run:
        seer_client = SeerClient(
            env_vars['SEER_API_URL'],
            env_vars['SEER_TOKEN'],
            env_vars.get('SEER_USER_NAME'),
            env_vars.get('SEER_USER_PSW'),
            env_vars.get('SEER_SESSION_TOKEN'),
            'all',
            False,
            False,
            {},
            False,
        )

    deleted = kept = missing = errors = 0
    for cand in candidates:
        tmdb_id = cand['tmdb_id']
        media_type = cand['media_type']
        title = cand.get('title') or f"tmdb:{tmdb_id}"
        rating = favorite_map.get((media_type, str(tmdb_id)))

        if rating is None:
            missing += 1
            db.add_cleanup_log(tmdb_id=tmdb_id, media_type=media_type, title=title,
                               action='skipped_not_in_library', was_dry_run=dry_run,
                               user_rating=None,
                               reason=f'Not present in {media_service.title()} library; nothing to delete here.')
            continue

        if rating >= FAVORITE_USER_RATING:
            kept += 1
            db.add_cleanup_log(tmdb_id=tmdb_id, media_type=media_type, title=title,
                               action='kept_favorited', was_dry_run=dry_run,
                               user_rating=rating, reason='Favorited (userRating >= 10).')
            continue

        if dry_run:
            db.add_cleanup_log(tmdb_id=tmdb_id, media_type=media_type, title=title,
                               action='would_delete', was_dry_run=True,
                               user_rating=rating,
                               reason=f'Not favorited after {grace_days} days; would request file deletion from Seer.')
            deleted += 1
            continue

        try:
            ok = await seer_client.delete_media_file_by_tmdb(int(tmdb_id), media_type)
            if ok:
                deleted += 1
                db.delete_request_row(tmdb_id, media_type)
                db.add_cleanup_log(tmdb_id=tmdb_id, media_type=media_type, title=title,
                                   action='deleted', was_dry_run=False,
                                   user_rating=rating,
                                   reason=f'Not favorited after {grace_days} days; Seer accepted the file deletion request.')
            else:
                errors += 1
                db.add_cleanup_log(tmdb_id=tmdb_id, media_type=media_type, title=title,
                                   action='delete_failed', was_dry_run=False,
                                   user_rating=rating,
                                   reason='Seer DELETE returned a non-success status; see logs.')
        except Exception as exc:
            errors += 1
            logger.error("Cleanup: error deleting tmdb_id=%s media_type=%s: %s", tmdb_id, media_type, exc)
            db.add_cleanup_log(tmdb_id=tmdb_id, media_type=media_type, title=title,
                               action='error', was_dry_run=False, user_rating=rating,
                               reason=str(exc)[:500])

    if seer_client is not None:
        try:
            await seer_client.close()
        except Exception:
            pass

    summary = (f"Candidates={len(candidates)} "
               f"{'would_delete' if dry_run else 'deleted'}={deleted} "
               f"kept_favorited={kept} not_in_library={missing} errors={errors}")
    db.update_cleanup_settings(last_run_at=datetime.utcnow().isoformat(),
                               last_run_status=('dry_run' if dry_run else 'ok'),
                               last_run_summary=summary)
    logger.info("Cleanup run finished: %s", summary)
    return {'status': 'ok', 'summary': summary, 'dry_run': dry_run,
            'deleted': deleted, 'kept': kept, 'missing': missing, 'errors': errors}
