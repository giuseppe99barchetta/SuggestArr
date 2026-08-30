"""Shared Simkl services: resolver, watch-history source, augmentor.

Mirrors :mod:`api_service.services.trakt.media_user_augmentor` so the media
handlers can treat both providers the same way. The structural difference is
that nothing here calls Simkl's library endpoints directly: reads go through
:class:`~api_service.services.simkl.watch_history_sync.SimklWatchHistorySync`,
which decides whether the network is touched at all.

All failures are isolated per profile.
"""
from dataclasses import dataclass, field
from typing import Optional

from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.services.simkl.simkl_client import SimklAuthError, SimklClientIdError
from api_service.services.simkl.watch_history_sync import (
    EXCLUSION_STATUSES,
    SEED_STATUSES,
    SimklWatchHistorySync,
)

# needs_reauth belongs here for the same reason revoked does: the link cannot
# work again until the user re-runs the PIN flow, and retrying only burns quota
# against a token Simkl has already rejected.
_SKIP_STATUSES = {"revoked", "error", "needs_reauth", "pending"}


@dataclass
class SimklAugmentation:
    """Result of augmenting one media user with Simkl history."""
    seed_items: list = field(default_factory=list)
    watched_ids: dict = field(default_factory=lambda: {"movie": set(), "tv": set()})


class SimklAccountResolver:
    """Resolve a media user's Simkl link + token, keyed by media_user_identity_id."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()

    def resolve(self, media_user_identity_id: int) -> Optional[dict]:
        """Return link metadata plus the access token, or None when unusable."""
        link = self.db.get_simkl_account_link(media_user_identity_id)
        if not link or not link["connected"]:
            return None
        if str(link.get("status") or "").lower() in _SKIP_STATUSES:
            return None

        result = dict(link)
        if link.get("token_source") == "manual_oauth":
            tokens = self.db.get_simkl_oauth_tokens(link["id"])
            if tokens:
                result["access_token"] = tokens["access_token"]
        return result if result.get("access_token") else None


class SimklWatchHistorySource:
    """Serve a media user's Simkl watch history out of the local cache."""

    def __init__(
        self, client_id: str,
        db: Optional[DatabaseManager] = None,
        logger=None, max_content: int = 10,
        use_as_seed: Optional[bool] = None,
        use_as_exclusion: Optional[bool] = None,
        tmdb_api_key: str = "",
    ):
        self.client_id = (client_id or "").strip()
        self.db = db or DatabaseManager()
        self.logger = logger or LoggerManager.get_logger("SimklWatchHistorySource")
        self.max_content = max_content
        self.resolver = SimklAccountResolver(self.db)
        self.sync = SimklWatchHistorySync(
            self.client_id, db=self.db, logger=self.logger, tmdb_api_key=tmdb_api_key
        )
        self._use_as_seed_override = use_as_seed
        self._use_as_exclusion_override = use_as_exclusion

    @property
    def enabled(self) -> bool:
        # The PIN flow needs no client secret, so a client id alone is enough.
        return bool(self.client_id)

    async def load(self, media_user_identity_id: int) -> Optional[SimklAugmentation]:
        """Sync once, then derive both seeds and exclusions from the cache.

        Seeds and exclusions are read together because they come from the same
        cache refresh; fetching them separately, as the Trakt source does,
        would double the sync entry points for no benefit.
        """
        if not self.enabled:
            return None
        resolved = self.resolver.resolve(media_user_identity_id)
        if not resolved:
            return None

        use_as_seed, use_as_exclusion = self._resolve_flags(media_user_identity_id)
        if not use_as_seed and not use_as_exclusion:
            return None

        link_id = resolved["id"]
        await self.sync.ensure_synced(resolved, resolved["access_token"])

        seeds = self._build_seeds(link_id) if use_as_seed else []
        watched = self._build_watched_ids(link_id) if use_as_exclusion else {
            "movie": set(), "tv": set()
        }
        return SimklAugmentation(seed_items=seeds, watched_ids=watched)

    def _resolve_flags(self, media_user_identity_id: int) -> tuple[bool, bool]:
        """Job-level overrides win; otherwise fall back to the per-user source row."""
        use_as_seed = self._use_as_seed_override
        use_as_exclusion = self._use_as_exclusion_override
        if use_as_seed is None or use_as_exclusion is None:
            source = self._get_watched_history_source(media_user_identity_id)
            if use_as_seed is None:
                use_as_seed = source.get("use_as_seed", True) if source else False
            if use_as_exclusion is None:
                use_as_exclusion = source.get("use_as_exclusion", True) if source else False
        return bool(use_as_seed), bool(use_as_exclusion)

    def _build_seeds(self, link_id: int) -> list:
        """Take the most recently watched titles as recommendation seeds.

        The cache is already ordered newest-first, so this is a truncation
        rather than a sort. ``watched_at`` is the key the handlers copy into
        ``date`` before merging with media-server seeds.
        """
        rows = self.db.get_simkl_watched_cache(link_id, SEED_STATUSES)
        seeds = []
        for row in rows:
            if not row.get("tmdb_id"):
                continue
            seeds.append({
                "tmdb_id": str(row["tmdb_id"]),
                "media_type": row["media_type"],
                "title": row.get("title") or "",
                "year": row.get("year"),
                "watched_at": row.get("last_watched_at") or 0,
            })
            if len(seeds) >= self.max_content:
                break
        return seeds

    def _build_watched_ids(self, link_id: int) -> dict:
        """Return {movie, tv} sets of finished TMDb IDs to suppress."""
        rows = self.db.get_simkl_watched_cache(link_id, EXCLUSION_STATUSES)
        watched = {"movie": set(), "tv": set()}
        for row in rows:
            tmdb_id = row.get("tmdb_id")
            media_type = row.get("media_type")
            if tmdb_id and media_type in watched:
                watched[media_type].add(str(tmdb_id))
        return watched

    def _get_watched_history_source(self, media_user_identity_id: int) -> Optional[dict]:
        """Find the enabled watched_history simkl_source row for a profile."""
        for source in self.db.get_enabled_simkl_sources(media_user_identity_id):
            if source["source_type"] == "watched_history":
                return source
        return None


class MediaUserSimklAugmentor:
    """Augment a media user with Simkl seeds + watched skip IDs."""

    def __init__(self, client_id: str, db=None, logger=None, max_content: int = 10,
                 use_as_seed: Optional[bool] = None, use_as_exclusion: Optional[bool] = None,
                 tmdb_api_key: str = ""):
        self.db = db or DatabaseManager()
        self.source = SimklWatchHistorySource(
            client_id, db=self.db, logger=logger, max_content=max_content,
            use_as_seed=use_as_seed, use_as_exclusion=use_as_exclusion,
            tmdb_api_key=tmdb_api_key,
        )
        self.logger = logger or LoggerManager.get_logger("SimklAugmentor")

    @classmethod
    def from_env(cls, env_vars: dict, max_content: int = 10,
                 use_as_seed: Optional[bool] = None,
                 use_as_exclusion: Optional[bool] = None):
        """Build an augmentor from app-level Simkl credentials.

        Reads ``SIMKL_CLIENT_ID`` (falling back to the ``integrations.simkl``
        config block) and returns ``None`` when it is not configured. Unlike
        Trakt there is no client secret to check: the PIN flow does not use one.
        """
        env_vars = env_vars if isinstance(env_vars, dict) else {}
        integrations = env_vars.get('integrations') if isinstance(env_vars.get('integrations'), dict) else {}
        simkl_cfg = integrations.get('simkl') if isinstance(integrations.get('simkl'), dict) else {}
        client_id = env_vars.get('SIMKL_CLIENT_ID') or simkl_cfg.get('client_id') or ''
        augmentor = cls(
            str(client_id).strip(),
            max_content=max_content,
            use_as_seed=use_as_seed,
            use_as_exclusion=use_as_exclusion,
            tmdb_api_key=str(env_vars.get('TMDB_API_KEY') or '').strip(),
        )
        return augmentor if augmentor.enabled else None

    @property
    def enabled(self) -> bool:
        return self.source.enabled

    async def augment(self, media_user_identity_id: int) -> Optional[SimklAugmentation]:
        """Fetch seeds + watched IDs for a profile, isolating all failures."""
        if not self.enabled:
            return None
        try:
            augmentation = await self.source.load(media_user_identity_id)
            if augmentation is None:
                return None
            if not augmentation.seed_items and not any(augmentation.watched_ids.values()):
                return None
            return augmentation
        except SimklAuthError as exc:
            # Terminal: no refresh grant exists, so the UI has to ask for a new
            # PIN. Recorded distinctly from a generic error so it can say so.
            self.logger.warning(
                "Simkl re-authorization required for media user %s", media_user_identity_id
            )
            self._mark_link(media_user_identity_id, "needs_reauth", str(exc))
            return None
        except SimklClientIdError as exc:
            # Install-wide, not this user's fault; marking their link would
            # point the UI at the wrong remedy.
            self.logger.error("Simkl client ID rejected: %s", exc)
            return None
        except Exception as exc:
            self.logger.warning(
                "Simkl augmentation failed for media user %s: %s",
                media_user_identity_id, exc, exc_info=True,
            )
            # last_error is rendered verbatim on the user's Simkl card, and
            # this branch catches everything — including failures from layers
            # whose messages carry connection strings or file paths. The detail
            # goes to the log; the card gets a message safe to show.
            self._mark_link(
                media_user_identity_id, "error", "Could not read Simkl watch history",
            )
            return None

    def _mark_link(self, media_user_identity_id: int, status: str, message: str) -> None:
        try:
            self.db.mark_simkl_account_link_error(media_user_identity_id, status, message)
        except Exception:
            pass
