"""Request client that adds titles straight to Radarr/Sonarr instead of going through Seer."""
from api_service.config.config import ARR_INSTANCES, arr_default_profile
from api_service.db.database_manager import DatabaseManager
from api_service.services.arr.arr_client import ArrClient, SUGGESTARR_TAG, arr_tag_label
from api_service.services.seer.seer_client import SeerClient


class ArrRequestClient(SeerClient):
    """Same enqueue flow as :class:`SeerClient` (queue, approvals, ownership, metadata), with
    delivery to Radarr/Sonarr. Everything that talks to Seer is replaced by a no-op."""

    BACKEND = 'arr'

    def __init__(self, env_vars, number_of_seasons='all', exclude_downloaded=True, exclude_requested=True,
                 request_first_season_only=False, queue_context=None):
        """
        :param env_vars: Runtime configuration (``RADARR_*``, ``SONARR_*``, ``ARR_PROFILE_CONFIG``).
        """
        self.env_vars = env_vars
        self._arr_clients = {}  # service -> ArrClient, reused across deliveries (tag ids are cached per client)
        profiles = env_vars.get('ARR_PROFILE_CONFIG')
        profiles = dict(profiles) if isinstance(profiles, dict) else {}
        for media_type in ('movie', 'tv'):  # each empty anime field falls back to the default one
            default = profiles.get(f'default_{media_type}')
            if isinstance(default, dict):
                anime = profiles.get(f'anime_{media_type}')
                profiles[f'anime_{media_type}'] = {**default, **{key: value for key, value in (
                    anime if isinstance(anime, dict) else {}).items() if value not in (None, '', [])}}
        # The URL is never contacted: every network method below is overridden.
        super().__init__('http://arr.invalid', '', number_of_seasons=number_of_seasons,
                         exclude_downloaded=exclude_downloaded, exclude_watched=exclude_requested,
                         anime_profile_config=profiles, request_first_season_only=request_first_season_only,
                         queue_context=queue_context)

    def _instance(self, media_type):
        """Return ``(service, url, token)`` of the instance serving ``media_type``, or None."""
        for service, (url_key, token_key, served) in ARR_INSTANCES.items():
            if served == media_type and self.env_vars.get(url_key) and self.env_vars.get(token_key):
                return service, self.env_vars[url_key], self.env_vars[token_key]
        return None

    def _arr_client(self, service, url, token):
        """Return this client's ArrClient for ``service``, created on first use and closed with it."""
        if service not in self._arr_clients:
            self._arr_clients[service] = ArrClient(service, url, token)
        return self._arr_clients[service]

    async def close(self):
        for client in self._arr_clients.values():
            await client.close()
        await super().close()

    def _extra_tag_labels(self, payload):
        """``suggestarr-user-<name>`` when ARR_TAG_BY_USER is on and the media user's name is known."""
        if self.env_vars.get('ARR_TAG_BY_USER') is not True:
            return []
        name = arr_tag_label(DatabaseManager().get_media_user_name(payload.get('_user_id')))
        return [f'{SUGGESTARR_TAG}-user-{name}'] if name else []

    def _can_enqueue(self, media_type):
        if self._instance(media_type) is None:
            self.logger.warning("No Radarr/Sonarr instance is configured for %s; request skipped.", media_type)
            return False
        if arr_default_profile(self.env_vars, media_type) is None:
            self.logger.warning("No default quality profile and root folder for %s; request skipped.", media_type)
            return False
        return True

    @staticmethod
    def _job_profile_overrides(context, media_type):
        """Per-job Radarr/Sonarr profile (``profileId``, ``rootFolder``, ``tags``), replacing ARR_PROFILE_CONFIG.

        A profile naming a Seer server (``serverId``) is kept for Seer and ignored here.
        """
        profile = (context.get('request_profiles') or {}).get(media_type) or {}
        if profile.get('serverId') is not None or profile.get('profileId') is None or not profile.get('rootFolder'):
            return {}
        return {'profileId': profile['profileId'], 'rootFolder': profile['rootFolder'],
                'tags': list(profile.get('tags') or [])}

    async def init(self):
        """Nothing to synchronise: there is no remote request list."""

    async def has_pending_requests(self) -> bool:
        """Whether any configured Radarr/Sonarr still has downloads in its queue.

        An instance that cannot be asked counts as idle: an unreachable instance must not pause
        jobs forever, and deliveries to it fail and retry on their own.
        """
        for service, (url_key, token_key, _) in ARR_INSTANCES.items():
            if not self.env_vars.get(url_key) or not self.env_vars.get(token_key):
                continue
            try:
                if await self._arr_client(service, self.env_vars[url_key], self.env_vars[token_key]).queue_busy():
                    return True
            except Exception as exc:
                self.logger.warning("Could not read %s's queue; not pausing for it: %s", service.capitalize(), exc)
        return False

    async def get_available_tmdb_ids(self):
        return {}  # Radarr/Sonarr titles are merged separately by load_library_content

    async def submit_queued_request(self, payload):
        """Add one queued request to Radarr/Sonarr.

        :return: True on success (no remote request ID exists to track), False on failure.
        """
        media_type = payload.get('mediaType')
        instance = self._instance(media_type)
        if instance is None:
            self.logger.error("Radarr/Sonarr is not configured for %s: restore the configuration and retry "
                              "the request from the Requests page.", media_type)
            return False
        service, url, token = instance
        try:
            return await self._arr_client(service, url, token).add(payload, self._extra_tag_labels(payload))
        except Exception as exc:
            self.logger.error("%s rejected the request for tmdb:%s: %s", service.capitalize(),
                              payload.get('mediaId'), exc)
            return False
