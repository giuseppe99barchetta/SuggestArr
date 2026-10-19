"""Write "Seen it" feedback back to the user's linked Trakt account.

When a user marks a suggestion as already seen, SuggestArr stores the verdict
locally (see ``SuggestionFeedbackMixin``). With ``TRAKT_SYNC_SEEN_FEEDBACK``
enabled, the same verdict is also sent to Trakt so the two stay in step:

- ``already_seen``  -> added to Trakt watch history
- ``seen_liked``    -> added to history and rated ``LIKED_RATING``
- ``seen_disliked`` -> added to history and rated ``DISLIKED_RATING``

A caller can pass an explicit 1-10 ``rating`` (the star picker does), which
replaces those defaults, and ``mark_watched=False`` to rate without adding a
play - useful for a show the user has only partly watched, since adding a
show to history marks every aired episode.

The Trakt account used is the one linked to the *acting* SuggestArr user's own
media profile, since "I have seen this" is a statement about the person
clicking. The sync is best-effort: it runs in the background, never changes the
HTTP response of the feedback call, and only logs on failure.
"""
import asyncio
import threading
from typing import Any, Optional

from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.services.trakt.media_user_augmentor import TraktAccountResolver
from api_service.services.trakt.trakt_client import TraktClient

logger = LoggerManager.get_logger("TraktFeedbackSync")

SEEN_FEEDBACK = frozenset({'already_seen', 'seen_liked', 'seen_disliked'})
LIKED_RATING = 8
DISLIKED_RATING = 3
FEEDBACK_RATINGS = {'seen_liked': LIKED_RATING, 'seen_disliked': DISLIKED_RATING}
_MEDIA_PROVIDERS = {'plex', 'jellyfin', 'emby'}


def _trakt_credentials(env_vars: dict) -> tuple[str, str]:
    """Return the app-level Trakt client id and optional secret from runtime config."""
    integrations = env_vars.get('integrations') if isinstance(env_vars.get('integrations'), dict) else {}
    trakt_cfg = integrations.get('trakt') if isinstance(integrations.get('trakt'), dict) else {}
    client_id = env_vars.get('TRAKT_CLIENT_ID') or trakt_cfg.get('client_id') or ''
    client_secret = env_vars.get('TRAKT_CLIENT_SECRET') or trakt_cfg.get('client_secret') or ''
    return str(client_id).strip(), str(client_secret).strip()


def is_sync_enabled(env_vars: dict) -> bool:
    """Whether seen feedback should be written to Trakt.

    Args:
        env_vars: Runtime configuration.

    Returns:
        bool: True only when the option is switched on and a Trakt app is configured.
    """
    return env_vars.get('TRAKT_SYNC_SEEN_FEEDBACK') is True and bool(_trakt_credentials(env_vars)[0])


class TraktFeedbackSync:
    """Send one seen verdict to the acting user's linked Trakt account."""

    def __init__(self, db: Optional[DatabaseManager] = None, env_vars: Optional[dict] = None,
                 client_factory=TraktClient):
        """
        Args:
            db: Database manager; a new one is created when omitted.
            env_vars: Runtime configuration; loaded when omitted.
            client_factory: Trakt client class, replaceable in tests.
        """
        self.db = db or DatabaseManager()
        self.env_vars = env_vars if env_vars is not None else load_env_vars()
        self.client_factory = client_factory

    def _resolve_link(self, user_id: int) -> Optional[dict]:
        """Return the Trakt link and tokens for the user's own media profile, or None."""
        provider = str(self.env_vars.get('SELECTED_SERVICE') or '').lower()
        if provider not in _MEDIA_PROVIDERS:
            return None
        profile = next((p for p in self.db.get_user_media_profiles(user_id)
                        if p.get('provider') == provider), None)
        if not profile:
            return None
        try:
            identity = self.db.get_media_user_identity(provider, str(profile['external_user_id']))
        except ValueError:
            return None
        return TraktAccountResolver(self.db).resolve(identity['id'])

    async def sync(self, user_id: int, tmdb_id: str, media_type: str, feedback: str,
                   rating: Optional[int] = None, mark_watched: bool = True) -> dict[str, Any]:
        """Write the verdict to Trakt.

        Args:
            user_id: SuggestArr user who gave the feedback.
            tmdb_id: TMDb id of the title.
            media_type: ``movie`` or ``tv``.
            feedback: One of ``SEEN_FEEDBACK``.
            rating: Explicit 1-10 Trakt rating; defaults to the verdict's rating.
            mark_watched: Whether to add a play to Trakt history.

        Returns:
            dict[str, Any]: ``{'status': 'synced'|'skipped'|'error', ...}``.
        """
        if feedback not in SEEN_FEEDBACK or media_type not in ('movie', 'tv'):
            return {'status': 'skipped', 'reason': 'not seen feedback'}
        if not is_sync_enabled(self.env_vars):
            return {'status': 'skipped', 'reason': 'disabled'}
        rating = rating if rating is not None else FEEDBACK_RATINGS.get(feedback)
        if not mark_watched and not rating:
            return {'status': 'skipped', 'reason': 'nothing to send'}
        link = self._resolve_link(user_id)
        if not link:
            return {'status': 'skipped', 'reason': 'no linked Trakt account'}

        client_id, client_secret = _trakt_credentials(self.env_vars)
        try:
            async with self.client_factory(
                client_id, client_secret,
                access_token=link.get('access_token', ''),
                refresh_token=link.get('refresh_token', ''),
                expires_at=link.get('expires_at'),
                db=self.db,
                link_id=link['id'],
                token_source=link.get('token_source', 'manual_oauth'),
            ) as client:
                history = await client.add_to_history(media_type, tmdb_id) if mark_watched else None
                rated = await client.add_rating(media_type, tmdb_id, rating) if rating else None
        except Exception as exc:
            logger.warning("Trakt sync of '%s' for %s %s failed: %s", feedback, media_type, tmdb_id, exc)
            return {'status': 'error', 'reason': str(exc)}

        not_found = any((response or {}).get('not_found', {}).get(key)
                        for response in (history, rated) for key in ('movies', 'shows'))
        if not_found:
            logger.warning("Trakt does not know %s %s; '%s' was not recorded", media_type, tmdb_id, feedback)
            return {'status': 'error', 'reason': 'not found on Trakt'}
        logger.info("Recorded '%s' for %s %s on Trakt (watched: %s, rating: %s)", feedback, media_type,
                    tmdb_id, mark_watched, rating)
        return {'status': 'synced', 'rating': rating, 'watched': mark_watched}


def _run_in_thread(coro_factory) -> threading.Thread:
    """Run a coroutine on its own event loop in a daemon thread."""
    def runner():
        try:
            asyncio.run(coro_factory())
        except Exception:
            logger.error("Background Trakt feedback sync crashed", exc_info=True)

    thread = threading.Thread(target=runner, name="trakt-feedback-sync", daemon=True)
    thread.start()
    return thread


def schedule_seen_feedback_sync(user_id: int, saved: Optional[dict], rating: Optional[int] = None,
                                mark_watched: bool = True, runner=_run_in_thread):
    """Queue a background Trakt sync for a just-saved feedback row, if it applies.

    Cheap to call for every feedback write: non-seen verdicts and a disabled
    option return before any database or network work is done.

    Args:
        user_id: SuggestArr user who gave the feedback.
        saved: The dict returned by ``set_media_feedback`` (needs ``feedback``,
               ``tmdb_id`` and ``media_type``).
        rating: Optional explicit 1-10 Trakt rating.
        mark_watched: Whether to add a play to Trakt history.
        runner: Callable that executes the coroutine factory; replaceable in tests.

    Returns:
        The runner's return value, or None when nothing was scheduled.
    """
    if not isinstance(saved, dict) or saved.get('feedback') not in SEEN_FEEDBACK:
        return None
    tmdb_id, media_type = saved.get('tmdb_id'), saved.get('media_type')
    if not tmdb_id or media_type not in ('movie', 'tv'):
        return None
    try:
        env_vars = load_env_vars()
    except Exception:
        logger.warning("Could not load configuration for Trakt feedback sync", exc_info=True)
        return None
    if not is_sync_enabled(env_vars):
        return None
    return runner(lambda: TraktFeedbackSync(env_vars=env_vars).sync(
        int(user_id), str(tmdb_id), media_type, saved['feedback'], rating, mark_watched))
