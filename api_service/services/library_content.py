"""
Helpers that work out which titles are already in the user's library.

Two sources are combined so "Exclude Downloaded Content" covers as much of the
library as possible:

- The configured media server (Jellyfin, Emby or Plex), read through each
  item's TMDB provider ID.
- Seer's availability data, which also covers library items whose
  media-server metadata has no TMDB ID (for example shows matched only
  through TVDB).
"""
from typing import Any, Dict, Optional, Set

from api_service.config.logger_manager import LoggerManager

logger = LoggerManager.get_logger(__name__)


def existing_content_to_sets(existing_content: Optional[Dict[str, Any]]) -> Dict[str, Set[str]]:
    """Normalize a client existing-content map into media-type keyed TMDB ID sets.

    :param existing_content: ``existing_content`` from a Jellyfin or Plex client,
        mapping media type to a list of item dicts (with ``tmdb_id``) or raw IDs.
    :return: Dict mapping media type to a set of TMDB ID strings; media types
        without any ID are omitted.
    """
    content_sets: Dict[str, Set[str]] = {}
    if not existing_content:
        return content_sets

    for media_type, items in existing_content.items():
        ids = set()
        for item in items or []:
            if isinstance(item, dict) and item.get("tmdb_id"):
                ids.add(str(item["tmdb_id"]))
            elif item:
                ids.add(str(item))
        if ids:
            content_sets[media_type] = ids
    return content_sets


def merge_content_sets(target: Dict[str, Set[str]], extra: Optional[Dict[str, Set[str]]]) -> Dict[str, Set[str]]:
    """Add the TMDB IDs from ``extra`` into ``target`` in place.

    :param target: Media-type keyed TMDB ID sets to extend.
    :param extra: Media-type keyed TMDB IDs to add; ``None`` or empty is a no-op.
    :return: ``target``, for chaining.
    """
    for media_type, ids in (extra or {}).items():
        if ids:
            target.setdefault(media_type, set()).update(str(tmdb_id) for tmdb_id in ids)
    return target


async def load_media_server_content(env_vars: Dict[str, Any]) -> Dict[str, Set[str]]:
    """Load the TMDB IDs of every item in the configured media-server libraries.

    :param env_vars: Runtime configuration providing ``SELECTED_SERVICE`` and the
        matching media-server URL, token and library selection.
    :return: Dict mapping 'movie' / 'tv' to sets of TMDB ID strings; empty when
        no supported media server is configured.
    """
    provider = str(env_vars.get("SELECTED_SERVICE") or "").lower()
    max_content = int(env_vars.get("MAX_CONTENT_CHECK") or env_vars.get("MAX_CONTENT") or 10)

    if provider in ("jellyfin", "emby"):
        from api_service.services.jellyfin.jellyfin_client import JellyfinClient

        jellyfin_libraries_raw = env_vars.get("JELLYFIN_LIBRARIES")
        jellyfin_libraries = jellyfin_libraries_raw if isinstance(jellyfin_libraries_raw, list) else []
        client = JellyfinClient(
            env_vars.get("JELLYFIN_API_URL"),
            env_vars.get("JELLYFIN_TOKEN"),
            max_content,
            jellyfin_libraries,
        )
        try:
            await client.init_existing_content()
            return existing_content_to_sets(client.existing_content)
        finally:
            await client.close()

    if provider == "plex":
        from api_service.services.plex.plex_client import PlexClient, normalize_guid_provider_id

        plex_libraries_raw = env_vars.get("PLEX_LIBRARIES")
        plex_libraries = plex_libraries_raw if isinstance(plex_libraries_raw, list) else []
        client = PlexClient(
            api_url=env_vars.get("PLEX_API_URL"),
            token=env_vars.get("PLEX_TOKEN"),
            max_content=max_content,
            library_ids=plex_libraries,
        )
        try:
            await client.init_existing_content()
            existing = existing_content_to_sets(client.existing_content)
            return {
                media_type: {
                    normalize_guid_provider_id(f"tmdb://{tmdb_id}", "tmdb") or str(tmdb_id)
                    for tmdb_id in ids
                }
                for media_type, ids in existing.items()
            }
        finally:
            await client.close()

    return {}


async def load_library_content(env_vars: Dict[str, Any], seer_client) -> Dict[str, Set[str]]:
    """Return the TMDB IDs already in the library, from the media server and Seer.

    Makes no request when "Exclude Downloaded Content" is off for this run,
    because nothing would be checked against the result. Each source is
    best-effort: if one fails, the other is still used.

    :param env_vars: Runtime configuration (see :func:`load_media_server_content`).
    :param seer_client: SeerClient for this run; its ``exclude_downloaded`` flag
        decides whether the library is loaded at all.
    :return: Dict mapping 'movie' / 'tv' to sets of TMDB ID strings.
    """
    if not seer_client.exclude_downloaded:
        logger.info("Exclude Downloaded Content is off; skipping library load.")
        return {}

    try:
        content = await load_media_server_content(env_vars)
    except Exception as exc:
        logger.warning("Could not load the media server library; using Seer availability only: %s", exc)
        content = {}
    return merge_content_sets(content, await seer_client.get_available_tmdb_ids())
