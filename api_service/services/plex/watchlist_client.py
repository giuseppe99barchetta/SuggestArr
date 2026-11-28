"""Request client that watchlists titles on the Plex account instead of downloading them."""
from api_service.exceptions.api_exceptions import BackendUnavailableError, is_transport_error
from api_service.services.seer.seer_client import SeerClient

# Plex's Discover provider serves account-level metadata and the watchlist actions.
DISCOVER_URL = 'https://discover.provider.plex.tv'
# SuggestArr media type -> (Plex search type id, the ``type`` a match must come back as).
# TMDb numbers movies and shows in separate namespaces, so the same id means a different
# title for each type and the search type id is what selects the right one. The returned
# type is then checked, so a match of the other kind is never watchlisted.
PLEX_MEDIA_TYPES = {'movie': (1, 'movie'), 'tv': (2, 'show')}


class PlexWatchlistClient(SeerClient):
    """Same enqueue flow as :class:`SeerClient` (queue, approvals, ownership, metadata), with
    delivery to the Plex account's watchlist.

    Nothing is downloaded and no Seer, Radarr or Sonarr instance is involved. The title appears
    on the Watchlist row of every client signed into the account, across every server on it,
    whether or not any of them holds the file.
    """

    BACKEND = 'plex_watchlist'

    def __init__(self, env_vars, number_of_seasons='all', exclude_downloaded=True, exclude_requested=True,
                 request_first_season_only=False, queue_context=None):
        """
        :param env_vars: Runtime configuration; only ``PLEX_TOKEN`` is used.
        """
        self.env_vars = env_vars
        # The Seer URL is never contacted: every method that talked to Seer is overridden below.
        super().__init__(DISCOVER_URL, '', number_of_seasons=number_of_seasons,
                         exclude_downloaded=exclude_downloaded, exclude_watched=exclude_requested,
                         anime_profile_config={}, request_first_season_only=request_first_season_only,
                         queue_context=queue_context)
        # Discover is a public Plex endpoint. Listing it as a private URL would let the SSRF
        # guard accept private addresses for it, so only the allow-list names it.
        self.private_urls = ()
        self.allowed_urls = (DISCOVER_URL,)

    @property
    def plex_token(self):
        """The account token the watchlist belongs to."""
        return self.env_vars.get('PLEX_TOKEN') or ''

    def _headers(self):
        """Auth and content negotiation. The token travels as a header, never in the URL."""
        return {'X-Plex-Token': self.plex_token, 'Accept': 'application/json'}

    def _can_enqueue(self, media_type):
        if not self.plex_token:
            self.logger.warning("No Plex token is configured; watchlist request skipped.")
            return False
        if media_type not in PLEX_MEDIA_TYPES:
            self.logger.warning("Plex has no watchlist for %s; request skipped.", media_type)
            return False
        return True

    @staticmethod
    def _job_profile_overrides(context, media_type):
        """No profiles apply: the watchlist has no quality profile or root folder."""
        return {}

    async def init(self):
        """Nothing to synchronise: the watchlist is not a request list."""

    async def has_pending_requests(self) -> bool:
        """A watchlist has no queue or approval step of its own, so it is never busy."""
        return False

    async def get_available_tmdb_ids(self):
        return {}  # What the libraries already hold is merged separately by load_library_content

    async def resolve_rating_key(self, media_type, tmdb_id):
        """Map a TMDb id onto the Plex ``ratingKey`` for the same title.

        Matching is by id, never by title: Plex's title search is fuzzy enough to return
        sequels and unrelated titles ("Kindergarten Cop" also matches "Kindergarten Cop 2"
        and "PMS Cop"), while ``guid=tmdb://<id>`` is exact. TMDb numbers movies and shows
        separately, so ``media_type`` selects which namespace the id is read in.

        :return: The ``ratingKey`` string, or None when Plex knows no such title.
        :raises BackendUnavailableError: When Discover could not be reached.
        """
        search_type, expected_type = PLEX_MEDIA_TYPES[media_type]
        url = f'{DISCOVER_URL}/library/metadata/matches'
        params = {'type': search_type, 'guid': f'tmdb://{tmdb_id}'}
        try:
            session = await self._get_session()
            async with session.get(url, params=params, headers=self._headers()) as response:
                if response.status in (401, 403):
                    self.logger.error("Plex rejected the account token; watchlist delivery cannot proceed.")
                    return None
                if response.status not in self.HTTP_OK:
                    raise BackendUnavailableError(
                        f"Plex Discover answered HTTP {response.status}", "Plex")
                payload = await response.json()
        except BackendUnavailableError:
            raise
        except Exception as exc:
            raise BackendUnavailableError(f"Plex Discover is unavailable: {exc}", "Plex") from exc

        for item in (payload.get('MediaContainer') or {}).get('Metadata') or []:
            # Only accept a match of the kind that was asked for.
            if item.get('type') == expected_type and item.get('ratingKey'):
                return str(item['ratingKey'])
        return None

    async def submit_queued_request(self, payload):
        """Add one queued title to the Plex account's watchlist.

        Adding a title already on the watchlist is a no-op at Plex's end, so a retry of an
        apparently failed delivery cannot duplicate an entry.

        :return: True once the title is on the watchlist, False when Plex does not know it
            (no amount of retrying would help).
        :raises BackendUnavailableError: When no token is configured or Plex could not be reached.
        """
        media_type = payload.get('mediaType')
        tmdb_id = payload.get('mediaId')
        if not self.plex_token:
            # Not a verdict on the request: it stays queued until a token is configured.
            raise BackendUnavailableError("No Plex token is configured", "Plex")
        if media_type not in PLEX_MEDIA_TYPES:
            self.logger.error("Plex has no watchlist for %s (tmdb:%s).", media_type, tmdb_id)
            return False

        rating_key = await self.resolve_rating_key(media_type, tmdb_id)
        if rating_key is None:
            self.logger.warning("Plex knows no %s for tmdb:%s; it cannot be watchlisted.", media_type, tmdb_id)
            return False

        try:
            session = await self._get_session()
            async with session.put(f'{DISCOVER_URL}/actions/addToWatchlist',
                                   params={'ratingKey': rating_key}, headers=self._headers()) as response:
                if response.status in self.HTTP_OK:
                    self.logger.info("Watchlisted %s tmdb:%s on Plex (ratingKey %s).",
                                     media_type, tmdb_id, rating_key)
                    return True
                if response.status in (401, 403):
                    raise BackendUnavailableError("Plex rejected the account token", "Plex")
                self.logger.error("Plex refused to watchlist %s tmdb:%s: HTTP %s",
                                  media_type, tmdb_id, response.status)
                return False
        except BackendUnavailableError:
            raise
        except Exception as exc:
            if is_transport_error(exc):
                raise BackendUnavailableError(f"Plex is unavailable: {exc}", "Plex") from exc
            self.logger.error("Could not watchlist %s tmdb:%s: %s", media_type, tmdb_id, exc)
            return False
