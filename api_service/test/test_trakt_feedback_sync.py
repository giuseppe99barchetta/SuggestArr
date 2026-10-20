import asyncio
from unittest.mock import MagicMock

import pytest
from flask import Flask, g

from api_service.auth.limiter import limiter
from api_service.blueprints.automation import routes as automation_routes
from api_service.services.trakt import feedback_sync
from api_service.services.trakt.feedback_sync import (
    TraktFeedbackSync,
    is_sync_enabled,
    schedule_seen_feedback_sync,
)
from api_service.services.trakt.trakt_client import TraktClient


ENABLED_ENV = {
    'TRAKT_SYNC_SEEN_FEEDBACK': True,
    'TRAKT_CLIENT_ID': 'client-id',
    'SELECTED_SERVICE': 'plex',
}


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status = status
        self._payload = payload or {}
        self.headers = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self._payload

    async def text(self):
        return str(self._payload)


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.closed = False

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.responses.pop(0)


class FakeTraktClient:
    """Stand-in for TraktClient that records calls and keeps a tiny Trakt state.

    ``movie_plays`` holds Trakt ids of movies with a play; ``show_progress`` maps a
    show's Trakt id to its unwatched seasons. Both persist across instances, so a
    second sync of the same title sees what the first one wrote.
    """
    instances = []
    fail_with = None
    unknown = False
    rating_not_found = False
    movie_plays = set()
    show_progress = {}

    def __init__(self, client_id, client_secret, **kwargs):
        self.client_id = client_id
        self.client_secret = client_secret
        self.kwargs = kwargs
        self.calls = []
        FakeTraktClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def lookup_trakt_id(self, media_type, tmdb_id):
        if FakeTraktClient.fail_with:
            raise FakeTraktClient.fail_with
        return None if FakeTraktClient.unknown else 1000 + int(tmdb_id)

    async def has_movie_play(self, trakt_id):
        return trakt_id in FakeTraktClient.movie_plays

    async def add_to_history(self, media_type, tmdb_id):
        self.calls.append(('history', media_type, tmdb_id))
        FakeTraktClient.movie_plays.add(1000 + int(tmdb_id))
        return {'added': {'movies': 1}, 'not_found': {'movies': []}}

    async def unwatched_episodes(self, trakt_id):
        default = [{'number': 1, 'episodes': [{'number': 1}, {'number': 2}]}]
        return FakeTraktClient.show_progress.get(trakt_id, default)

    async def add_episodes_to_history(self, trakt_id, seasons):
        self.calls.append(('episodes', trakt_id, seasons))
        FakeTraktClient.show_progress[trakt_id] = []
        return {'added': {'episodes': 2}}

    async def add_rating(self, media_type, tmdb_id, rating):
        self.calls.append(('rating', media_type, tmdb_id, rating))
        key = 'movies' if media_type == 'movie' else 'shows'
        if FakeTraktClient.rating_not_found:
            return {'added': {key: 0}, 'not_found': {key: [{'ids': {'tmdb': 1}}]}}
        return {'added': {key: 1}, 'not_found': {key: []}}


@pytest.fixture(autouse=True)
def _reset_fake():
    FakeTraktClient.instances = []
    FakeTraktClient.fail_with = None
    FakeTraktClient.unknown = False
    FakeTraktClient.rating_not_found = False
    FakeTraktClient.movie_plays = set()
    FakeTraktClient.show_progress = {}
    yield


def _db(linked=True, verified=True):
    db = MagicMock()
    db.get_user_media_profiles.return_value = [
        {'provider': 'jellyfin', 'external_user_id': 'jf-1', 'verified': True},
        {'provider': 'plex', 'external_user_id': '318356842', 'verified': verified},
    ]
    db.get_media_user_identity.return_value = {'id': 11}
    db.get_trakt_account_link.return_value = (
        {'id': 3, 'connected': True, 'status': 'connected', 'token_source': 'manual_oauth'} if linked else None
    )
    db.get_trakt_oauth_tokens.return_value = {
        'access_token': 'access', 'refresh_token': 'refresh', 'expires_at': 9999999999,
    }
    return db


def _sync(db=None, env=None):
    return TraktFeedbackSync(db=db or _db(), env_vars=dict(env or ENABLED_ENV), client_factory=FakeTraktClient)


# --- TraktClient write calls -------------------------------------------------

def test_add_to_history_posts_movie_by_tmdb_id():
    session = FakeSession([FakeResponse(201, {'added': {'movies': 1}})])
    client = TraktClient('cid', access_token='token', session=session, db=MagicMock())

    result = asyncio.run(client.add_to_history('movie', '18240'))

    assert result == {'added': {'movies': 1}}
    method, url, kwargs = session.calls[0]
    assert (method, url) == ('POST', 'https://api.trakt.tv/sync/history')
    assert kwargs['json'] == {'movies': [{'ids': {'tmdb': 18240}}]}
    assert kwargs['headers']['Authorization'] == 'Bearer token'


def test_add_rating_posts_show_with_rating():
    session = FakeSession([FakeResponse(201, {'added': {'shows': 1}})])
    client = TraktClient('cid', access_token='token', session=session, db=MagicMock())

    asyncio.run(client.add_rating('tv', 1399, 8))

    _, url, kwargs = session.calls[0]
    assert url == 'https://api.trakt.tv/sync/ratings'
    assert kwargs['json'] == {'shows': [{'ids': {'tmdb': 1399}, 'rating': 8}]}


@pytest.mark.parametrize('media_type,tmdb_id,rating', [
    ('person', '1', 5), ('movie', 'abc', 5), ('movie', '1', 0), ('movie', '1', 11),
])
def test_write_calls_reject_bad_input(media_type, tmdb_id, rating):
    client = TraktClient('cid', access_token='token', session=FakeSession([]), db=MagicMock())
    with pytest.raises(ValueError):
        asyncio.run(client.add_rating(media_type, tmdb_id, rating))


def _trakt_client(responses):
    session = FakeSession(responses)
    return TraktClient('cid', access_token='token', session=session, db=MagicMock()), session


def test_lookup_trakt_id_searches_by_tmdb_without_user_auth():
    client, session = _trakt_client([FakeResponse(200, [{'type': 'show', 'show': {'ids': {'trakt': 1390}}}])])
    assert asyncio.run(client.lookup_trakt_id('tv', '1399')) == 1390
    method, url, kwargs = session.calls[0]
    assert (method, url) == ('GET', 'https://api.trakt.tv/search/tmdb/1399')
    assert kwargs['params'] == {'type': 'show'}
    assert 'Authorization' not in kwargs['headers']


def test_lookup_trakt_id_returns_none_for_an_unknown_title():
    client, _ = _trakt_client([FakeResponse(200, [])])
    assert asyncio.run(client.lookup_trakt_id('movie', '1')) is None


def test_has_movie_play_reads_one_history_entry():
    client, session = _trakt_client([FakeResponse(200, [{'id': 1}]), FakeResponse(200, [])])
    assert asyncio.run(client.has_movie_play(77)) is True
    assert asyncio.run(client.has_movie_play(78)) is False
    assert session.calls[0][1] == 'https://api.trakt.tv/sync/history/movies/77'
    assert session.calls[0][2]['params'] == {'limit': 1}


def test_unwatched_episodes_lists_only_incomplete_ones():
    progress = {'seasons': [
        {'number': 1, 'episodes': [{'number': 1, 'completed': True}, {'number': 2, 'completed': False}]},
        {'number': 2, 'episodes': [{'number': 1, 'completed': True}]},
        {'number': 3, 'episodes': [{'number': 1, 'completed': False}]},
    ]}
    client, session = _trakt_client([FakeResponse(200, progress)])
    assert asyncio.run(client.unwatched_episodes(1390)) == [
        {'number': 1, 'episodes': [{'number': 2}]},
        {'number': 3, 'episodes': [{'number': 1}]},
    ]
    assert session.calls[0][1] == 'https://api.trakt.tv/shows/1390/progress/watched'


def test_add_episodes_to_history_posts_by_trakt_id():
    client, session = _trakt_client([FakeResponse(201, {'added': {'episodes': 1}})])
    seasons = [{'number': 1, 'episodes': [{'number': 2}]}]
    asyncio.run(client.add_episodes_to_history(1390, seasons))
    assert session.calls[0][2]['json'] == {'shows': [{'ids': {'trakt': 1390}, 'seasons': seasons}]}


# --- TraktFeedbackSync -------------------------------------------------------

def test_is_sync_enabled_needs_switch_and_client_id():
    assert is_sync_enabled(ENABLED_ENV)
    assert not is_sync_enabled({**ENABLED_ENV, 'TRAKT_SYNC_SEEN_FEEDBACK': False})
    assert not is_sync_enabled({**ENABLED_ENV, 'TRAKT_SYNC_SEEN_FEEDBACK': 'true'})
    assert not is_sync_enabled({**ENABLED_ENV, 'TRAKT_CLIENT_ID': ''})
    assert is_sync_enabled({'TRAKT_SYNC_SEEN_FEEDBACK': True, 'integrations': {'trakt': {'client_id': 'x'}}})


def test_already_seen_adds_history_without_rating():
    db = _db()
    result = asyncio.run(_sync(db).sync(7, '18240', 'movie', 'already_seen'))

    assert result == {'status': 'synced', 'rating': None, 'history': 'added'}
    client = FakeTraktClient.instances[0]
    assert client.calls == [('history', 'movie', '18240')]
    assert client.client_id == 'client-id'
    assert client.kwargs['link_id'] == 3
    assert client.kwargs['access_token'] == 'access'
    db.get_media_user_identity.assert_called_once_with('plex', '318356842')


@pytest.mark.parametrize('feedback,rating', [('seen_liked', 8), ('seen_disliked', 3)])
def test_seen_verdicts_rate_a_movie_and_add_its_play(feedback, rating):
    result = asyncio.run(_sync().sync(7, '42', 'movie', feedback))
    assert result == {'status': 'synced', 'rating': rating, 'history': 'added'}
    assert FakeTraktClient.instances[0].calls == [('history', 'movie', '42'), ('rating', 'movie', '42', rating)]


def test_explicit_star_rating_replaces_the_default():
    result = asyncio.run(_sync().sync(7, '42', 'movie', 'seen_liked', rating=10))
    assert result['rating'] == 10
    assert FakeTraktClient.instances[0].calls == [('history', 'movie', '42'), ('rating', 'movie', '42', 10)]


def test_neutral_star_rating_is_still_sent():
    # 5 or 6 stars is saved locally as plain "seen", but the user did pick a rating.
    asyncio.run(_sync().sync(7, '42', 'movie', 'already_seen', rating=6))
    assert FakeTraktClient.instances[0].calls == [('history', 'movie', '42'), ('rating', 'movie', '42', 6)]


# --- TV is opt-in for history ------------------------------------------------

def test_show_without_mark_watched_is_only_rated():
    # The sent-request page never sends mark_watched; a show must not get every
    # aired episode marked watched by default.
    result = asyncio.run(_sync().sync(7, '1399', 'tv', 'seen_liked'))
    assert result == {'status': 'synced', 'rating': 8, 'history': 'not requested'}
    assert FakeTraktClient.instances[0].calls == [('rating', 'tv', '1399', 8)]


def test_show_marked_watched_adds_only_its_unwatched_episodes():
    FakeTraktClient.show_progress[2399] = [{'number': 2, 'episodes': [{'number': 5}]}]
    result = asyncio.run(_sync().sync(7, '1399', 'tv', 'seen_liked', rating=9, mark_watched=True))
    assert result == {'status': 'synced', 'rating': 9, 'history': 'added'}
    assert FakeTraktClient.instances[0].calls == [
        ('episodes', 2399, [{'number': 2, 'episodes': [{'number': 5}]}]), ('rating', 'tv', '1399', 9)]


def test_show_already_fully_watched_gets_no_new_plays():
    FakeTraktClient.show_progress[2399] = []
    result = asyncio.run(_sync().sync(7, '1399', 'tv', 'already_seen', mark_watched=True))
    assert result['history'] == 'already watched'
    assert FakeTraktClient.instances[0].calls == []


def test_unrated_show_without_history_sends_nothing():
    # The dialog's default for a show: no stars, episodes box unticked.
    result = asyncio.run(_sync().sync(7, '1399', 'tv', 'already_seen', rating=None, mark_watched=False))
    assert result == {'status': 'skipped', 'reason': 'nothing to send'}
    assert FakeTraktClient.instances == []


def test_unrated_show_without_mark_watched_sends_nothing():
    assert asyncio.run(_sync().sync(7, '1399', 'tv', 'already_seen'))['reason'] == 'nothing to send'


# --- idempotency -------------------------------------------------------------

def test_repeated_movie_feedback_adds_one_play_only():
    asyncio.run(_sync().sync(7, '42', 'movie', 'seen_liked'))
    second = asyncio.run(_sync().sync(7, '42', 'movie', 'seen_liked', rating=9))
    assert second == {'status': 'synced', 'rating': 9, 'history': 'already watched'}
    plays = [c for i in FakeTraktClient.instances for c in i.calls if c[0] == 'history']
    assert plays == [('history', 'movie', '42')]
    assert FakeTraktClient.instances[1].calls == [('rating', 'movie', '42', 9)]


def test_movie_already_watched_on_trakt_gets_no_new_play():
    FakeTraktClient.movie_plays.add(1042)
    result = asyncio.run(_sync().sync(7, '42', 'movie', 'already_seen'))
    assert result['history'] == 'already watched'
    assert FakeTraktClient.instances[0].calls == []


def test_repeated_show_feedback_adds_episodes_once():
    asyncio.run(_sync().sync(7, '1399', 'tv', 'already_seen', mark_watched=True))
    asyncio.run(_sync().sync(7, '1399', 'tv', 'already_seen', mark_watched=True))
    assert len([c for i in FakeTraktClient.instances for c in i.calls if c[0] == 'episodes']) == 1


# --- whose account -----------------------------------------------------------

def test_unverified_media_profile_is_never_written_through():
    # A self-selected media id can belong to someone else's linked Trakt account.
    db = _db(verified=False)
    result = asyncio.run(_sync(db).sync(7, '42', 'movie', 'seen_liked'))
    assert result == {'status': 'skipped', 'reason': 'no linked Trakt account'}
    assert FakeTraktClient.instances == []
    db.get_media_user_identity.assert_not_called()


def test_profile_without_verified_flag_counts_as_unverified():
    db = _db()
    db.get_user_media_profiles.return_value = [{'provider': 'plex', 'external_user_id': '318356842'}]
    assert asyncio.run(_sync(db).sync(7, '42', 'movie', 'seen_liked'))['status'] == 'skipped'


@pytest.mark.parametrize('feedback', ['interested', 'not_interested', 'too_similar', 'save_for_later'])
def test_other_feedback_is_ignored(feedback):
    result = asyncio.run(_sync().sync(7, '1', 'movie', feedback))
    assert result['status'] == 'skipped'
    assert FakeTraktClient.instances == []


def test_disabled_option_skips_without_touching_the_database():
    db = _db()
    env = {**ENABLED_ENV, 'TRAKT_SYNC_SEEN_FEEDBACK': False}
    result = asyncio.run(_sync(db, env).sync(7, '1', 'movie', 'already_seen'))
    assert result == {'status': 'skipped', 'reason': 'disabled'}
    db.get_user_media_profiles.assert_not_called()


def test_user_without_trakt_link_is_skipped():
    result = asyncio.run(_sync(_db(linked=False)).sync(7, '1', 'movie', 'already_seen'))
    assert result == {'status': 'skipped', 'reason': 'no linked Trakt account'}
    assert FakeTraktClient.instances == []


def test_user_without_media_profile_for_selected_service_is_skipped():
    db = _db()
    db.get_user_media_profiles.return_value = [{'provider': 'jellyfin', 'external_user_id': 'jf-1', 'verified': True}]
    result = asyncio.run(_sync(db).sync(7, '1', 'movie', 'already_seen'))
    assert result['reason'] == 'no linked Trakt account'


def test_unknown_identity_is_skipped():
    db = _db()
    db.get_media_user_identity.side_effect = ValueError('missing')
    result = asyncio.run(_sync(db).sync(7, '1', 'movie', 'already_seen'))
    assert result['status'] == 'skipped'


def test_trakt_errors_are_reported_not_raised():
    FakeTraktClient.fail_with = RuntimeError('Trakt API request failed: 401')
    result = asyncio.run(_sync().sync(7, '1', 'movie', 'seen_liked'))
    assert result['status'] == 'error'
    assert '401' in result['reason']


def test_title_unknown_to_trakt_is_an_error():
    FakeTraktClient.unknown = True
    result = asyncio.run(_sync().sync(7, '1', 'movie', 'already_seen'))
    assert result == {'status': 'error', 'reason': 'not found on Trakt'}
    assert FakeTraktClient.instances[0].calls == []


def test_rejected_rating_is_an_error():
    FakeTraktClient.rating_not_found = True
    result = asyncio.run(_sync().sync(7, '1', 'movie', 'seen_liked'))
    assert result == {'status': 'error', 'reason': 'not found on Trakt'}


# --- scheduling ----------------------------------------------------------------

def test_schedule_runs_sync_for_seen_feedback(monkeypatch):
    monkeypatch.setattr(feedback_sync, 'load_env_vars', lambda: dict(ENABLED_ENV))
    captured = []
    monkeypatch.setattr(feedback_sync, 'TraktFeedbackSync', lambda env_vars: MagicMock(
        sync=lambda *args: captured.append((args, env_vars))))

    schedule_seen_feedback_sync('7', {'feedback': 'seen_liked', 'tmdb_id': '42', 'media_type': 'movie'},
                                runner=lambda factory: factory())
    schedule_seen_feedback_sync(7, {'feedback': 'seen_liked', 'tmdb_id': '43', 'media_type': 'tv'},
                                rating=9, mark_watched=False, runner=lambda factory: factory())

    assert captured == [((7, '42', 'movie', 'seen_liked', None, None), ENABLED_ENV),
                        ((7, '43', 'tv', 'seen_liked', 9, False), ENABLED_ENV)]


@pytest.mark.parametrize('saved', [
    None,
    {'feedback': 'interested', 'tmdb_id': '42', 'media_type': 'movie'},
    {'feedback': 'already_seen', 'media_type': 'movie'},
    {'feedback': 'already_seen', 'tmdb_id': '42', 'media_type': 'person'},
])
def test_schedule_ignores_rows_that_do_not_apply(monkeypatch, saved):
    load = MagicMock(return_value=dict(ENABLED_ENV))
    monkeypatch.setattr(feedback_sync, 'load_env_vars', load)
    runner = MagicMock()
    assert schedule_seen_feedback_sync(7, saved, runner=runner) is None
    runner.assert_not_called()
    load.assert_not_called()


def test_schedule_does_nothing_when_disabled(monkeypatch):
    monkeypatch.setattr(feedback_sync, 'load_env_vars', lambda: {**ENABLED_ENV, 'TRAKT_SYNC_SEEN_FEEDBACK': False})
    runner = MagicMock()
    schedule_seen_feedback_sync(7, {'feedback': 'already_seen', 'tmdb_id': '42', 'media_type': 'movie'},
                                runner=runner)
    runner.assert_not_called()


# --- routes ----------------------------------------------------------------------

def _client(monkeypatch, db):
    monkeypatch.setattr(automation_routes, 'DatabaseManager', MagicMock(return_value=db))
    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=False)
    app.secret_key = 'test-secret'

    @app.before_request
    def authenticate():
        g.current_user = {'id': '7', 'role': 'admin'}

    limiter.init_app(app)
    app.register_blueprint(automation_routes.automation_bp, url_prefix='/api/automation')
    return app.test_client()


def test_feedback_routes_hand_saved_rows_to_the_trakt_sync(monkeypatch):
    calls = []
    monkeypatch.setattr(automation_routes, 'schedule_seen_feedback_sync',
                        lambda user_id, saved, **trakt: calls.append((user_id, saved, trakt)))
    db = MagicMock()
    pending = {'feedback': 'already_seen', 'tmdb_id': '42', 'media_type': 'movie', 'media_user_id': 'plex-a'}
    sent = {'feedback': 'seen_liked', 'tmdb_id': '43', 'media_type': 'tv', 'media_user_id': 'plex-a'}
    db.set_suggestion_feedback.return_value = pending
    db.set_media_feedback.return_value = sent
    db.has_visible_suggestarr_request.return_value = True
    client = _client(monkeypatch, db)

    assert client.put('/api/automation/requests/workflow/5/feedback',
                      json={'feedback': 'already_seen'}).status_code == 200
    assert client.put('/api/automation/requests/media/tv/43/feedback',
                      json={'feedback': 'seen_liked', 'media_user_id': 'plex-a', 'rating': 9,
                            'mark_watched': False}).status_code == 200

    assert calls == [(7, pending, {'rating': None, 'mark_watched': None}),
                     (7, sent, {'rating': 9, 'mark_watched': False})]


def test_sent_tv_feedback_without_mark_watched_never_marks_the_show(monkeypatch):
    # The sent-request page (RequestsPage.vue) posts only {feedback, media_user_id}.
    # End to end, that must rate the show and add no plays.
    monkeypatch.setattr(feedback_sync, 'load_env_vars', lambda: dict(ENABLED_ENV))
    monkeypatch.setattr(feedback_sync, 'TraktFeedbackSync',
                        lambda env_vars: TraktFeedbackSync(db=_db(), env_vars=env_vars,
                                                           client_factory=FakeTraktClient))
    monkeypatch.setattr(automation_routes, 'schedule_seen_feedback_sync',
                        lambda user_id, saved, **trakt: schedule_seen_feedback_sync(
                            user_id, saved, runner=lambda factory: asyncio.run(factory()), **trakt))
    db = MagicMock()
    db.has_visible_suggestarr_request.return_value = True
    db.set_media_feedback.return_value = {'feedback': 'seen_liked', 'tmdb_id': '1399', 'media_type': 'tv',
                                          'media_user_id': 'plex-a'}
    client = _client(monkeypatch, db)

    response = client.put('/api/automation/requests/media/tv/1399/feedback',
                          json={'feedback': 'seen_liked', 'media_user_id': 'plex-a'})

    assert response.status_code == 200
    assert FakeTraktClient.instances[0].calls == [('rating', 'tv', '1399', 8)]


@pytest.mark.parametrize('extra', [
    {'rating': 0}, {'rating': 11}, {'rating': '8'}, {'rating': 7.5}, {'rating': True}, {'mark_watched': 'no'},
])
def test_feedback_route_rejects_bad_trakt_details(monkeypatch, extra):
    db = MagicMock()
    client = _client(monkeypatch, db)
    response = client.put('/api/automation/requests/workflow/5/feedback', json={'feedback': 'seen_liked', **extra})
    assert response.status_code == 400
    db.set_suggestion_feedback.assert_not_called()


def test_feedback_route_succeeds_even_if_scheduling_fails(monkeypatch):
    def boom(user_id, saved, **trakt):
        raise RuntimeError('config unreadable')

    monkeypatch.setattr(automation_routes, 'schedule_seen_feedback_sync', boom)
    db = MagicMock()
    db.set_suggestion_feedback.return_value = {'feedback': 'already_seen', 'tmdb_id': '42', 'media_type': 'movie'}
    client = _client(monkeypatch, db)

    response = client.put('/api/automation/requests/workflow/5/feedback', json={'feedback': 'already_seen'})
    assert response.status_code == 200
    assert response.get_json()['status'] == 'success'
