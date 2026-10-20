"""Title logos (the transparent title artwork shown on backdrop cards).

Suggestions are stored from TMDb list results, which carry no logos, so most
requested titles start without one.  Listing routes pass their items through
`fill_logos`, which fetches the missing logos from TMDb in a background thread
and stores them, so the list is not slowed down and each title is looked up once.
"""
import asyncio
import threading

import aiohttp

from api_service.config.logger_manager import LoggerManager

logger = LoggerManager.get_logger("TmdbLogos")

TMDB_BASE_URL = "https://api.themoviedb.org/3"
LOGO_URL = "https://image.tmdb.org/t/p/w500{}"
_MAX_PARALLEL = 8
# Runs off the request path, so it can wait longer than the translation lookups.
LOOKUP_BUDGET_SECONDS = 30.0
# shortcut: titles TMDb has no logo for are remembered in memory only, so they are asked again after a restart; move to a DB column if that gets costly.
_NO_LOGO = set()
# Pairs a worker is already fetching, so concurrent list loads do not ask twice.
_in_flight = set()
_lock = threading.Lock()


def pick_logo(logos, language='en'):
    """
    Choose the best logo: the reader's language, then English, then a
    language-less one, then any (titles with only original-language artwork);
    the most voted wins within each tier.

    Args:
        logos: TMDb `logos` list from the /images endpoint.
        language: Reader's TMDb language code ('it', 'pt-BR').

    Returns:
        str | None: The chosen logo's file_path.
    """
    preferred = [(language or 'en').split('-')[0], 'en', None]

    def rank(logo):
        lang = logo.get('iso_639_1')
        tier = preferred.index(lang) if lang in preferred else len(preferred)
        return tier, -(logo.get('vote_average') or 0), -(logo.get('vote_count') or 0)

    logos = [logo for logo in logos or [] if logo.get('file_path')]
    return min(logos, key=rank)['file_path'] if logos else None


async def _fetch_one(session, semaphore, api_key, media_id, media_type, language):
    async with semaphore:
        # No include_image_language: TMDb then returns logos in every language.
        url = f"{TMDB_BASE_URL}/{media_type}/{media_id}/images"
        try:
            async with session.get(url, params={'api_key': api_key}) as response:
                if response.status != 200:
                    logger.debug("No images for %s %s: HTTP %s", media_type, media_id, response.status)
                    return False
                data = await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.debug("Logo fetch failed for %s %s: %s", media_type, media_id, type(exc).__name__)
            return False
    path = pick_logo(data.get('logos'), language)
    return LOGO_URL.format(path) if path else None


async def fetch_logos(api_key, pairs, language, budget=LOOKUP_BUDGET_SECONDS):
    """
    Fetch logos for (media_id, media_type) pairs within one time budget.

    Returns:
        dict: {pair: url or None}; None means TMDb has no logo.  Failed and
        cancelled lookups are left out, so they are tried again next time.
    """
    if not pairs:
        return {}
    semaphore = asyncio.Semaphore(_MAX_PARALLEL)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=budget)) as session:
        tasks = [asyncio.ensure_future(_fetch_one(session, semaphore, api_key, media_id, media_type, language))
                 for media_id, media_type in pairs]
        done, pending = await asyncio.wait(tasks, timeout=budget)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
    return {pair: task.result() for pair, task in zip(pairs, tasks)
            if task in done and task.exception() is None and task.result() is not False}


def _store_logos(pairs, language, db, api_key, run):
    try:
        found = run(fetch_logos(api_key, pairs, language))
    except Exception as exc:  # a missing logo must not break anything
        logger.warning("Logo lookup skipped: %s", exc)
        found = {}
    try:
        for pair, url in found.items():
            if not url:
                _NO_LOGO.add(pair)
                continue
            try:
                db.update_logo(pair[0], pair[1], url)
            except Exception as exc:
                logger.warning("Could not store logo for %s %s: %s", pair[1], pair[0], exc)
    finally:
        with _lock:
            _in_flight.difference_update(pairs)


def fill_logos(groups, language, db, api_key, run=asyncio.run):
    """
    Fetch and store, in the background, logos for listed items that have none.

    The list is answered right away; the logos show from the next load on.

    Args:
        groups: list of (items, fields) as taken by localization.localize_groups;
            only the first field's id_key and type_key are used (the item's own
            title, not e.g. its source).  Items without a `logo_path` key are
            left alone.
        run: Runs a coroutine to completion in the worker thread.

    Returns:
        threading.Thread | None: The started worker, if any.
    """
    if not api_key:
        return None
    pairs = set()
    for items, fields in groups:
        for item in items or []:
            if 'logo_path' not in item or item['logo_path'] or not fields:
                continue
            id_key, type_key = fields[0][0], fields[0][1]
            media_id, media_type = str(item.get(id_key) or ''), item.get(type_key)
            if media_id.isdigit() and media_type in ('movie', 'tv'):
                pairs.add((media_id, media_type))
    with _lock:
        pairs = list(pairs - _NO_LOGO - _in_flight)
        _in_flight.update(pairs)
    if not pairs:
        return None
    worker = threading.Thread(target=_store_logos, args=(pairs, language, db, api_key, run),
                              name="logo-backfill", daemon=True)
    worker.start()
    return worker
