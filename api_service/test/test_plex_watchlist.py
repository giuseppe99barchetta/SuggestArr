"""Plex watchlist backend: configuration rules, TMDb -> Plex mapping, delivery, queue routing."""
import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api_service.config.config import validate_request_backend
from api_service.exceptions.api_exceptions import BackendUnavailableError
from api_service.jobs.queue_worker import _run_worker
from api_service.services.plex.watchlist_client import DISCOVER_URL, PlexWatchlistClient
from api_service.utils.clients import build_request_client

ENV = {'REQUEST_BACKEND': 'plex_watchlist', 'PLEX_TOKEN': 'tok'}
MOVIE_MATCH = {'MediaContainer': {'totalSize': 1, 'Metadata': [
    {'ratingKey': '5d77682854f42c001f8c2c44', 'type': 'movie', 'title': 'Kindergarten Cop'}]}}
SHOW_MATCH = {'MediaContainer': {'totalSize': 1, 'Metadata': [
    {'ratingKey': '5d9c086b705e7a001e6dbda3', 'type': 'show', 'title': 'How I Met Your Mother'}]}}
NO_MATCH = {'MediaContainer': {'totalSize': 0}}
MOVIE_PAYLOAD = {'mediaType': 'movie', 'mediaId': 951}
TV_PAYLOAD = {'mediaType': 'tv', 'mediaId': 1100}


class _Response:
    def __init__(self, status, payload=None):
        self.status = status
        self._payload = payload

    async def json(self):
        return self._payload


class _Session:
    """Minimal stand-in for GuardedSession: records calls and replays queued answers."""

    def __init__(self, *answers):
        self._answers = list(answers)
        self.calls = []

    @asynccontextmanager
    async def _answer(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs.get('params')))
        answer = self._answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        yield answer

    def get(self, url, **kwargs):
        return self._answer('GET', url, **kwargs)

    def put(self, url, **kwargs):
        return self._answer('PUT', url, **kwargs)


def _client(*answers, env=None):
    client = PlexWatchlistClient(env if env is not None else ENV)
    session = _Session(*answers)
    client._get_session = AsyncMock(return_value=session)
    return client, session


# --- configuration ---------------------------------------------------------

def test_the_watchlist_backend_needs_a_plex_token():
    with pytest.raises(ValueError, match='Plex token'):
        validate_request_backend({'REQUEST_BACKEND': 'plex_watchlist'}, {'SETUP_COMPLETED': True})


def test_a_plex_token_is_all_the_watchlist_backend_needs():
    # Deliberately no Seer, Radarr or Sonarr: the watchlist needs none of them.
    validate_request_backend(ENV, {})


def test_losing_the_token_of_the_active_watchlist_backend_is_rejected():
    current = {**ENV, 'SETUP_COMPLETED': True}
    with pytest.raises(ValueError, match='Plex token'):
        validate_request_backend({**current, 'PLEX_TOKEN': ''}, current)


def test_the_backend_choice_builds_the_watchlist_client():
    client = build_request_client(ENV, 'all', True, True, False)
    assert isinstance(client, PlexWatchlistClient) and client.BACKEND == 'plex_watchlist'


def test_discover_is_allowed_but_never_treated_as_private():
    # Marking a public host private would let the SSRF guard accept private addresses for it.
    client = PlexWatchlistClient(ENV)
    assert client.allowed_urls == (DISCOVER_URL,) and client.private_urls == ()


# --- TMDb -> Plex mapping --------------------------------------------------

@pytest.mark.parametrize('media_type,answer,expected_type,rating_key', [
    ('movie', MOVIE_MATCH, 1, '5d77682854f42c001f8c2c44'),
    ('tv', SHOW_MATCH, 2, '5d9c086b705e7a001e6dbda3'),
])
def test_titles_are_matched_by_tmdb_id_not_by_title(media_type, answer, expected_type, rating_key):
    client, session = _client(_Response(200, answer))
    assert asyncio.run(client.resolve_rating_key(media_type, 951)) == rating_key
    method, url, params = session.calls[0]
    assert (method, url) == ('GET', f'{DISCOVER_URL}/library/metadata/matches')
    assert params == {'type': expected_type, 'guid': 'tmdb://951'}


def test_a_title_plex_does_not_know_maps_to_nothing():
    client, _ = _client(_Response(200, NO_MATCH))
    assert asyncio.run(client.resolve_rating_key('movie', 999999999)) is None


def test_a_match_of_the_wrong_kind_is_refused():
    """Only a match of the kind asked for may be watchlisted, so a movie coming back for
    a TV lookup is discarded rather than delivered as a show."""
    client, _ = _client(_Response(200, MOVIE_MATCH))
    assert asyncio.run(client.resolve_rating_key('tv', 951)) is None


def test_an_unreachable_discover_is_not_a_verdict_on_the_request():
    client, _ = _client(_Response(503))
    with pytest.raises(BackendUnavailableError):
        asyncio.run(client.resolve_rating_key('movie', 951))


def test_a_refused_token_does_not_strand_the_lookup():
    client, _ = _client(_Response(401))
    assert asyncio.run(client.resolve_rating_key('movie', 951)) is None


# --- delivery --------------------------------------------------------------

def test_a_delivered_title_is_put_on_the_watchlist():
    client, session = _client(_Response(200, MOVIE_MATCH), _Response(200))
    assert asyncio.run(client.submit_queued_request(MOVIE_PAYLOAD)) is True
    method, url, params = session.calls[1]
    assert (method, url) == ('PUT', f'{DISCOVER_URL}/actions/addToWatchlist')
    assert params == {'ratingKey': '5d77682854f42c001f8c2c44'}


def test_a_show_is_delivered_whole_without_season_or_profile_fields():
    client, session = _client(_Response(200, SHOW_MATCH), _Response(200))
    assert asyncio.run(client.submit_queued_request(TV_PAYLOAD)) is True
    assert session.calls[1][2] == {'ratingKey': '5d9c086b705e7a001e6dbda3'}
    assert PlexWatchlistClient._job_profile_overrides({'request_profiles': {'tv': {'profileId': 6}}}, 'tv') == {}


def test_a_title_plex_does_not_know_is_a_rejection_not_a_retry():
    client, session = _client(_Response(200, NO_MATCH))
    assert asyncio.run(client.submit_queued_request(MOVIE_PAYLOAD)) is False
    assert len(session.calls) == 1  # nothing was added


def test_a_missing_token_leaves_the_request_queued():
    client, _ = _client(env={'REQUEST_BACKEND': 'plex_watchlist'})
    with pytest.raises(BackendUnavailableError):
        asyncio.run(client.submit_queued_request(MOVIE_PAYLOAD))


def test_a_token_refused_at_delivery_leaves_the_request_queued():
    client, _ = _client(_Response(200, MOVIE_MATCH), _Response(403))
    with pytest.raises(BackendUnavailableError):
        asyncio.run(client.submit_queued_request(MOVIE_PAYLOAD))


def test_a_transport_failure_leaves_the_request_queued():
    client, _ = _client(_Response(200, MOVIE_MATCH), TimeoutError('timed out'))
    with pytest.raises(BackendUnavailableError):
        asyncio.run(client.submit_queued_request(MOVIE_PAYLOAD))


def test_plex_refusing_the_title_is_a_rejection():
    client, _ = _client(_Response(200, MOVIE_MATCH), _Response(422))
    assert asyncio.run(client.submit_queued_request(MOVIE_PAYLOAD)) is False


def test_a_media_type_plex_has_no_watchlist_for_is_refused():
    client, _ = _client()
    assert asyncio.run(client.submit_queued_request({'mediaType': 'person', 'mediaId': 1})) is False
    assert client._can_enqueue('person') is False


# --- what the watchlist is not --------------------------------------------

def test_a_watchlist_has_no_queue_and_no_library_of_its_own():
    client, _ = _client()
    # Nothing to synchronise, nothing to pause for, and availability still comes from the libraries.
    assert asyncio.run(client.init()) is None
    assert asyncio.run(client.has_pending_requests()) is False
    assert asyncio.run(client.get_available_tmdb_ids()) == {}


def test_delivery_is_gated_on_a_configured_token():
    assert PlexWatchlistClient(ENV)._can_enqueue('movie') is True
    assert PlexWatchlistClient({'REQUEST_BACKEND': 'plex_watchlist'})._can_enqueue('movie') is False


# --- queue routing ---------------------------------------------------------

class _Client:
    def __init__(self, result):
        self.submit_queued_request = AsyncMock(return_value=result)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def init(self):
        return None


def _row(row_id, backend):
    payload = '{"mediaType": "movie", "_backend": "%s"}' % backend
    return {'id': row_id, 'tmdb_id': str(row_id), 'media_type': 'movie', 'retry_count': 0,
            'job_id': 1, 'payload': payload}


def test_a_watchlist_row_is_delivered_to_the_watchlist_and_never_to_seer():
    """The queue worker picks the client per row, so it has to know this backend too.

    Without it a plex_watchlist row falls through to Seer and is downloaded — the exact
    opposite of what the backend is for.
    """
    watchlist, seer = _Client(True), _Client({'id': 5, 'createdAt': '2026-01-01T00:00:00.000Z'})
    db = MagicMock()
    db.expire_pending_approvals.return_value = 0
    db.check_request_exists.return_value = False
    db.get_due_requests.return_value = [_row(1, 'plex_watchlist')]
    env = {**ENV, 'SEER_API_URL': 'http://seer:5055', 'SEER_TOKEN': 'k'}  # stale Seer credentials present
    with patch('api_service.jobs.queue_worker.DatabaseManager', return_value=db), \
            patch('api_service.jobs.queue_worker.ConfigService.get_runtime_config', return_value=env), \
            patch('api_service.jobs.queue_worker.SeerClient', return_value=seer), \
            patch('api_service.jobs.queue_worker.PlexWatchlistClient', return_value=watchlist):
        assert asyncio.run(_run_worker()) == 1

    assert watchlist.submit_queued_request.await_count == 1
    assert seer.submit_queued_request.await_count == 0
    # Nothing remote to track: the watchlist returns no request id.
    assert db.track_seer_request.call_count == 0
