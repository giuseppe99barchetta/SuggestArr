"""Show titles and overviews in the reader's language.

Suggestions store TMDb's default-language title once per item.  Each person
can pick a display language on their profile (`auth_users.language`); an
admin can set the default for everyone else (`TMDB_LANGUAGE`).  Listing
routes pass their items through `localize_items`, which swaps in cached
translations and fetches the missing ones from TMDb, once per item and
language.

Only what is shown changes.  Stored metadata, search, sorting, requests sent
to Jellyseerr and the text the recommender sees keep the default language.

Lookups happen on the request path, so they get a small overall budget: what
TMDb has not answered by then is skipped, the stored title is shown, and the
lookup is tried again on the next request.
"""
import asyncio
import re
from datetime import datetime, timedelta, timezone

import aiohttp

from api_service.config.logger_manager import LoggerManager
from api_service.utils.asyncio_loop import run_coroutine_sync

logger = LoggerManager.get_logger("Localization")

TMDB_BASE_URL = "https://api.themoviedb.org/3"
# TMDb serves its default titles in English; nothing to translate then.
DEFAULT_LANGUAGE = 'en'
_LANGUAGE_PATTERN = re.compile(r'^[a-z]{2}(-[A-Z]{2})?$')
_MAX_PARALLEL = 8
# For all missing lookups of one list request together, not per lookup.
LOOKUP_BUDGET_SECONDS = 3.0
# A cached translation older than this is fetched again (TMDb titles and
# overviews do get corrected); until a refresh succeeds the old one is shown.
REFRESH_AFTER = timedelta(days=60)


def normalize_language(value):
    """Return a TMDb language code ('de', 'pt-BR') or None for anything else."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if _LANGUAGE_PATTERN.match(value) else None


def display_language(user_language, env):
    """
    The language a person reads in: their own choice, else the configured
    default, else TMDb's default.
    """
    return (normalize_language(user_language)
            or normalize_language((env or {}).get('TMDB_LANGUAGE'))
            or DEFAULT_LANGUAGE)


def needs_translation(language):
    return language.split('-')[0] != DEFAULT_LANGUAGE


async def _fetch_one(session, semaphore, api_key, media_id, media_type, language):
    async with semaphore:
        url = f"{TMDB_BASE_URL}/{media_type}/{media_id}"
        try:
            async with session.get(url, params={'api_key': api_key, 'language': language}) as response:
                if response.status != 200:
                    logger.debug("No translation for %s %s (%s): HTTP %s", media_type, media_id, language, response.status)
                    return None
                data = await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.debug("Translation fetch failed for %s %s: %s", media_type, media_id, type(exc).__name__)
            return None
    title = data.get('title') if media_type == 'movie' else data.get('name')
    return {'title': title or None, 'overview': data.get('overview') or None}


async def fetch_translations(api_key, pairs, language, budget=LOOKUP_BUDGET_SECONDS):
    """
    Fetch titles/overviews for (media_id, media_type) pairs within one time budget.

    Args:
        api_key: TMDb API key.
        pairs: (media_id, media_type) pairs to look up.
        language: TMDb language code.
        budget: Seconds for all lookups together, waiting for a free slot
            included.  Lookups still running then are cancelled.

    Returns:
        dict: {pair: {'title': ..., 'overview': ...}} for the lookups that
        succeeded in time; failed, cancelled and skipped ones are left out.
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
            logger.debug("Translation budget of %ss used up; %d of %d lookups left for later",
                         budget, len(pending), len(tasks))
    return {pair: task.result() for pair, task in zip(pairs, tasks)
            if task in done and task.exception() is None and task.result() is not None}


def _is_stale(fetched_at, now):
    """True when a cached translation is older than REFRESH_AFTER."""
    if isinstance(fetched_at, str):
        try:
            fetched_at = datetime.fromisoformat(fetched_at)
        except ValueError:
            return False
    if not isinstance(fetched_at, datetime):
        return False
    return now - fetched_at.replace(tzinfo=None) > REFRESH_AFTER


def translations_for(db, api_key, pairs, language, run):
    """
    Cached translations for the pairs, fetching and storing missing ones.

    A fetch that fails is not stored, so it is tried again next time.  A
    fetch that succeeds is stored even when TMDb has no translation (it then
    answers with the original title), so it is not asked again until the
    entry is older than REFRESH_AFTER.  A stale entry is still shown when its
    refresh fails.

    Args:
        run: Runs a coroutine synchronously.
    """
    # Only real TMDb ids: requests without a source carry '0', AI search 'ai_search'.
    pairs = list(dict.fromkeys((str(media_id), media_type) for media_id, media_type in pairs
                               if str(media_id or '').isdigit() and int(media_id) > 0
                               and media_type in ('movie', 'tv')))
    if not pairs:
        return {}
    found = db.get_translations(pairs, language)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    missing = [pair for pair in pairs
               if pair not in found or _is_stale(found[pair].get('fetched_at'), now)]
    if missing and api_key:
        fetched = run(fetch_translations(api_key, missing, language))
        for (media_id, media_type), value in fetched.items():
            try:
                db.save_translation(media_id, media_type, language, value['title'], value['overview'])
            except Exception as exc:  # a full cache must not break a list
                logger.warning("Could not cache translation for %s %s: %s", media_type, media_id, exc)
        found.update(fetched)
    return found


def localize_items(items, language, db, api_key, fields, run=run_coroutine_sync):
    """
    Replace title/overview fields in list items in place.

    Args:
        items: dicts to change.
        fields: list of (id_key, type_key, title_key, overview_key) — one entry
            per title shown on an item (a request and its source, say).
            `type_key` may be a fixed 'movie'/'tv' prefixed with '=' .
        run: Runs a coroutine synchronously.
    Returns:
        items, for chaining.
    """
    localize_groups([(items, fields)], language, db, api_key, run)
    return items


def localize_groups(groups, language, db, api_key, run=run_coroutine_sync):
    """
    Localize several lists of items with one cache query and one lookup budget.

    Args:
        groups: list of (items, fields) as taken by localize_items — for
            example the sources of a page and the requests under them.
        run: Runs a coroutine synchronously.
    """
    groups = [(items, fields) for items, fields in groups if items]
    if not groups or not needs_translation(language):
        return

    def media_type_of(item, type_key):
        return type_key[1:] if type_key.startswith('=') else item.get(type_key)

    pairs = [(item.get(id_key), media_type_of(item, type_key))
             for items, fields in groups for item in items for id_key, type_key, _, _ in fields]
    try:
        found = translations_for(db, api_key, pairs, language, run)
    except Exception as exc:
        # Showing the default language is always better than showing nothing.
        logger.warning("Localization skipped: %s", exc)
        return
    for items, fields in groups:
        _apply(items, fields, found, media_type_of)


def _apply(items, fields, found, media_type_of):
    for item in items:
        for id_key, type_key, title_key, overview_key in fields:
            value = found.get((str(item.get(id_key)), media_type_of(item, type_key)))
            if not value:
                continue
            if value.get('title'):
                item[title_key] = value['title']
            if overview_key and value.get('overview'):
                item[overview_key] = value['overview']
