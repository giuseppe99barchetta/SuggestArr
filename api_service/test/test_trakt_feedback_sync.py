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


class FakeTraktClient:
    instances = []
    fail_with = None
    not_found = False

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

    def _response(self, key):
        if FakeTraktClient.not_found:
            return {'added': {key: 0}, 'not_found': {key: [{'ids': {'tmdb': 1}}]}}
        return {'added': {key: 1}, 'not_found': {key: []}}

    async def add_to_history(self, media_type, tmdb_id):
        if FakeTraktClient.fail_with:
            raise FakeTraktClient.fail_with
        self.calls.append(('history', media_type, tmdb_id))
        return self._response('movies' if media_type == 'movie' else 'shows')

    async def add_rating(self, media_type, tmdb_id, rating):
        self.calls.append(('rating', media_type, tmdb_id, rating))
        return self._response('movies' if media_type == 'movie' else 'shows')


@pytest.fixture(autouse=True)
def _reset_fake():
    FakeTraktClient.instances = []
    FakeTraktClient.fail_with = None
    FakeTraktClient.not_found = False
    yield


def _db(linked=True):
    db = MagicMock()
    db.get_user_media_profiles.return_value = [
        {'provider': 'jellyfin', 'external_user_id': 'jf-1'},
        {'provider': 'plex', 'external_user_id': '318356842'},
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

    assert result == {'status': 'synced', 'rating': None, 'watched': True}
    client = FakeTraktClient.instances[0]
    assert client.calls == [('history', 'movie', '18240')]
    assert client.client_id == 'client-id'
    assert client.kwargs['link_id'] == 3
    assert client.kwargs['access_token'] == 'access'
    db.get_media_user_identity.assert_called_once_with('plex', '318356842')


@pytest.mark.parametrize('feedback,rating', [('seen_liked', 8), ('seen_disliked', 3)])
def test_seen_verdicts_also_rate(feedback, rating):
    result = asyncio.run(_sync().sync(7, '1399', 'tv', feedback))

    assert result == {'status': 'synced', 'rating': rating, 'watched': True}
    assert FakeTraktClient.instances[0].calls == [('history', 'tv', '1399'), ('rating', 'tv', '1399', rating)]


def test_explicit_star_rating_replaces_the_default():
    result = asyncio.run(_sync().sync(7, '42', 'movie', 'seen_liked', rating=10))
    assert result['rating'] == 10
    assert FakeTraktClient.instances[0].calls == [('history', 'movie', '42'), ('rating', 'movie', '42', 10)]


def test_neutral_star_rating_is_still_sent():
    # 5 or 6 stars is saved locally as plain "seen", but the user did pick a rating.
    asyncio.run(_sync().sync(7, '42', 'movie', 'already_seen', rating=6))
    assert FakeTraktClient.instances[0].calls == [('history', 'movie', '42'), ('rating', 'movie', '42', 6)]


def test_rating_only_skips_history_for_a_partly_watched_show():
    result = asyncio.run(_sync().sync(7, '1399', 'tv', 'seen_liked', rating=9, mark_watched=False))
    assert result == {'status': 'synced', 'rating': 9, 'watched': False}
    assert FakeTraktClient.instances[0].calls == [('rating', 'tv', '1399', 9)]


def test_nothing_to_send_when_unrated_and_not_marked_watched():
    result = asyncio.run(_sync().sync(7, '1399', 'tv', 'already_seen', rating=None, mark_watched=False))
    assert result == {'status': 'skipped', 'reason': 'nothing to send'}
    assert FakeTraktClient.instances == []


@pytest.mark.parametrize('feedback', ['interested', 'not_interested', 'too_similar', 'save_for_later'])
def test_other_feedback_is_ignored(feedback):
    result = asyncio.run(_sync().sync(7, '1', 'movie', feedback))
    assert result['status'] == 'skipped'
    assert FakeTraktClient.instances == []


def test_disabled_option_skips_without_touching_the_database():
    db = _db()
    result = asyncio.run(_sync(db, {**ENABLED_ENV, 'TRAKT_SYNC_SEEN_FEEDBACK': False}).sync(7, '1', 'movie', 'already_seen'))
    assert result == {'status': 'skipped', 'reason': 'disabled'}
    db.get_user_media_profiles.assert_not_called()


def test_user_without_trakt_link_is_skipped():
    result = asyncio.run(_sync(_db(linked=False)).sync(7, '1', 'movie', 'already_seen'))
    assert result == {'status': 'skipped', 'reason': 'no linked Trakt account'}
    assert FakeTraktClient.instances == []


def test_user_without_media_profile_for_selected_service_is_skipped():
    db = _db()
    db.get_user_media_profiles.return_value = [{'provider': 'jellyfin', 'external_user_id': 'jf-1'}]
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
    FakeTraktClient.not_found = True
    result = asyncio.run(_sync().sync(7, '1', 'movie', 'already_seen'))
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

    assert captured == [((7, '42', 'movie', 'seen_liked', None, True), ENABLED_ENV),
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

    assert calls == [(7, pending, {'rating': None, 'mark_watched': True}),
                     (7, sent, {'rating': 9, 'mark_watched': False})]


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
