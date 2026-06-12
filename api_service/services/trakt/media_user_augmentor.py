"""Shared Trakt services: resolver, watch-history source, augmentor.

Used by the media-server handlers (Plex, Jellyfin) to additively enrich
recommendations with each linked user's Trakt watch history.
All failures are isolated per profile.
"""
from dataclasses import dataclass, field
from typing import Optional

from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.services.trakt.trakt_client import TraktClient

_SKIP_STATUSES = {"revoked", "error"}


@dataclass
class TraktAugmentation:
    """Result of augmenting one media user with Trakt history."""
    seed_items: list = field(default_factory=list)
    watched_ids: dict = field(default_factory=lambda: {"movie": set(), "tv": set()})


class TraktAccountResolver:
    """Resolve a media user's Trakt link + tokens, keyed by media_user_identity_id (the (provider, external_user_id) anchor)."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()

    def resolve(self, media_user_identity_id: int) -> Optional[dict]:
        """Return link metadata + tokens for a profile, or None.

        Returns None when no link exists, status is revoked/error, or
        no tokens are available (future plugin sources).
        """
        link = self.db.get_trakt_account_link(media_user_identity_id)
        if not link or not link["connected"]:
            return None
        if str(link.get("status") or "").lower() in _SKIP_STATUSES:
            return None

        result = dict(link)
        if link.get("token_source") == "manual_oauth":
            tokens = self.db.get_trakt_oauth_tokens(link["id"])
            if tokens:
                result["access_token"] = tokens["access_token"]
                result["refresh_token"] = tokens["refresh_token"]
                result["expires_at"] = tokens["expires_at"]
        # Future: plugin sources fetch token externally
        return result if result.get("access_token") else None


class TraktWatchHistorySource:
    """Fetch watched history from a media user's linked Trakt account."""

    def __init__(
        self, client_id: str, client_secret: str,
        db: Optional[DatabaseManager] = None,
        logger=None, max_content: int = 10,
        use_as_seed: Optional[bool] = None,
        use_as_exclusion: Optional[bool] = None,
    ):
        self.client_id = (client_id or "").strip()
        self.client_secret = (client_secret or "").strip()
        self.db = db or DatabaseManager()
        self.logger = logger or LoggerManager.get_logger("TraktWatchHistorySource")
        self.max_content = max_content
        self.resolver = TraktAccountResolver(self.db)
        self._use_as_seed_override = use_as_seed
        self._use_as_exclusion_override = use_as_exclusion

    @property
    def enabled(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def get_recent_items(self, media_user_identity_id: int) -> list:
        """Return normalized recent-watched items for a profile."""
        if not self.enabled:
            return []
        resolved = self.resolver.resolve(media_user_identity_id)
        if not resolved:
            return []
        use_as_seed = self._use_as_seed_override
        if use_as_seed is None:
            source = self._get_watched_history_source(media_user_identity_id)
            use_as_seed = source.get("use_as_seed", True) if source else None
        if not use_as_seed:
            return []
        try:
            async with TraktClient(
                self.client_id, self.client_secret,
                access_token=resolved.get("access_token", ""),
                refresh_token=resolved.get("refresh_token", ""),
                expires_at=resolved.get("expires_at"),
                db=self.db,
                link_id=resolved["id"],
                token_source=resolved.get("token_source", "manual_oauth"),
            ) as client:
                return await client.get_recent_items(self.max_content) or []
        except Exception as exc:
            self.logger.warning("Trakt recent items failed for media user %s: %s", media_user_identity_id, exc)
            return []

    async def get_watched_ids(self, media_user_identity_id: int) -> dict:
        """Return {movie: set(), tv: set()} of watched TMDB IDs."""
        if not self.enabled:
            return {"movie": set(), "tv": set()}
        resolved = self.resolver.resolve(media_user_identity_id)
        if not resolved:
            return {"movie": set(), "tv": set()}
        use_as_exclusion = self._use_as_exclusion_override
        if use_as_exclusion is None:
            source = self._get_watched_history_source(media_user_identity_id)
            use_as_exclusion = source.get("use_as_exclusion", True) if source else None
        if not use_as_exclusion:
            return {"movie": set(), "tv": set()}
        try:
            async with TraktClient(
                self.client_id, self.client_secret,
                access_token=resolved.get("access_token", ""),
                refresh_token=resolved.get("refresh_token", ""),
                expires_at=resolved.get("expires_at"),
                db=self.db,
                link_id=resolved["id"],
                token_source=resolved.get("token_source", "manual_oauth"),
            ) as client:
                await client.init_existing_content()
                watched = client.existing_content or {}
            return {
                "movie": {str(i["tmdb_id"]) for i in watched.get("movie", []) if i.get("tmdb_id")},
                "tv": {str(i["tmdb_id"]) for i in watched.get("tv", []) if i.get("tmdb_id")},
            }
        except Exception as exc:
            self.logger.warning("Trakt watched IDs failed for media user %s: %s", media_user_identity_id, exc)
            return {"movie": set(), "tv": set()}

    def _get_watched_history_source(self, media_user_identity_id: int) -> Optional[dict]:
        """Find the enabled watched_history trakt_source row for a profile."""
        sources = self.db.get_enabled_trakt_sources(media_user_identity_id)
        for s in sources:
            if s["source_type"] == "watched_history":
                return s
        return None


class MediaUserTraktAugmentor:
    """Thin wrapper: augment a media user with Trakt seeds + watched skip IDs.

    Delegates to TraktWatchHistorySource. Isolates failures (silent no-op on error).
    """

    def __init__(self, client_id: str, client_secret: str, db=None, logger=None, max_content: int = 10,
                 use_as_seed: Optional[bool] = None, use_as_exclusion: Optional[bool] = None):
        self.db = db or DatabaseManager()
        self.source = TraktWatchHistorySource(
            client_id, client_secret, db=self.db, logger=logger, max_content=max_content,
            use_as_seed=use_as_seed, use_as_exclusion=use_as_exclusion,
        )
        self.logger = logger or LoggerManager.get_logger("TraktAugmentor")

    @classmethod
    def from_env(cls, env_vars: dict, max_content: int = 10,
                 use_as_seed: Optional[bool] = None,
                 use_as_exclusion: Optional[bool] = None):
        """Build an augmentor from app-level Trakt credentials.

        Reads ``TRAKT_CLIENT_ID``/``TRAKT_CLIENT_SECRET`` (falling back to the
        ``integrations.trakt`` config block). Returns ``None`` when no usable
        credentials are configured.

        ``use_as_seed``/``use_as_exclusion`` override the per-user Trakt
        source settings when set (e.g. from a job filter). When ``None`` the
        per-user DB settings are used.
        """
        env_vars = env_vars if isinstance(env_vars, dict) else {}
        integrations = env_vars.get('integrations') if isinstance(env_vars.get('integrations'), dict) else {}
        trakt_cfg = integrations.get('trakt') if isinstance(integrations.get('trakt'), dict) else {}
        client_id = env_vars.get('TRAKT_CLIENT_ID') or trakt_cfg.get('client_id') or ''
        client_secret = env_vars.get('TRAKT_CLIENT_SECRET') or trakt_cfg.get('client_secret') or ''
        augmentor = cls(str(client_id).strip(), str(client_secret).strip(), max_content=max_content,
                        use_as_seed=use_as_seed, use_as_exclusion=use_as_exclusion)
        return augmentor if augmentor.enabled else None

    @property
    def enabled(self) -> bool:
        return self.source.enabled

    async def augment(self, media_user_identity_id: int) -> Optional[TraktAugmentation]:
        """Fetch recent seeds + full watched IDs for a profile."""
        if not self.enabled:
            return None
        try:
            seeds = await self.source.get_recent_items(media_user_identity_id)
            watched_ids = await self.source.get_watched_ids(media_user_identity_id)
            if not seeds and not any(watched_ids.values()):
                return None
            return TraktAugmentation(seed_items=seeds or [], watched_ids=watched_ids)
        except Exception as exc:
            self.logger.warning("Trakt augmentation failed for media user %s: %s", media_user_identity_id, exc)
            try:
                self.db.mark_trakt_account_link_error(media_user_identity_id, "error", str(exc))
            except Exception:
                pass
            return None
