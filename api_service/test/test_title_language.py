"""Titles and overviews in the reader's language.

The stored metadata keeps TMDb's default language; listing routes swap in a
translation per person, fetched from TMDb once per item and language.
"""
import asyncio
import sqlite3
import time
from unittest.mock import MagicMock

import pytest
from flask import Flask, g

from api_service.auth.limiter import limiter
from api_service.blueprints.auth import routes as auth_routes
from api_service.blueprints.automation import routes as automation_routes
from api_service.db.components.auth_mixin import AuthMixin
from api_service.db.components.translation_mixin import TranslationMixin
from api_service.services.tmdb import localization


class Store(TranslationMixin, AuthMixin):
    db_type = "sqlite"

    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.executescript("""
            CREATE TABLE metadata_translations (media_id TEXT NOT NULL, media_type TEXT NOT NULL,
                language TEXT NOT NULL, title TEXT, overview TEXT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (media_id, media_type, language));
            CREATE TABLE auth_users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT,
                language TEXT);
            INSERT INTO auth_users (id, username) VALUES (1, 'achim');
            INSERT INTO auth_users (id, username) VALUES (2, 'robert');
        """)

    def get_connection(self):
        return self.connection


def run(coro):
    return asyncio.run(coro)


def _fake_fetch(answers, calls):
    async def fetch(api_key, pairs, language):
        calls.append((tuple(pairs), language))
        return {pair: answers[pair] for pair in pairs if pair in answers}
    return fetch


# --- choosing the language --------------------------------------------------

@pytest.mark.parametrize('value, expected', [
    ('de', 'de'), ('pt-BR', 'pt-BR'), (' de ', 'de'),
    ('german', None), ('DE', None), ('de_DE', None), ('', None), (None, None), (7, None),
])
def test_only_tmdb_language_codes_are_accepted(value, expected):
    assert localization.normalize_language(value) == expected


def test_own_choice_beats_the_default_which_beats_english():
    assert localization.display_language('fr', {'TMDB_LANGUAGE': 'de'}) == 'fr'
    assert localization.display_language(None, {'TMDB_LANGUAGE': 'de'}) == 'de'
    assert localization.display_language(None, {'TMDB_LANGUAGE': 'nonsense'}) == 'en'
    assert localization.display_language(None, {}) == 'en'


def test_english_needs_no_translation():
    assert not localization.needs_translation('en')
    assert not localization.needs_translation('en-GB')
    assert localization.needs_translation('de')


# --- the cache ----------------------------------------------------------------

def test_a_translation_is_fetched_once_and_then_served_from_the_cache(monkeypatch):
    store, calls = Store(), []
    answers = {('10', 'movie'): {'title': 'Der Bote', 'overview': 'Deutsch.'}}
    monkeypatch.setattr(localization, 'fetch_translations', _fake_fetch(answers, calls))

    items = [{'tmdb_id': 10, 'media_type': 'movie', 'title': 'The Messenger', 'overview': 'English.'}]
    localization.localize_items(items, 'de', store, 'key', [('tmdb_id', 'media_type', 'title', 'overview')], run=run)
    assert items[0]['title'] == 'Der Bote' and items[0]['overview'] == 'Deutsch.'

    again = [{'tmdb_id': 10, 'media_type': 'movie', 'title': 'The Messenger', 'overview': 'English.'}]
    localization.localize_items(again, 'de', store, 'key', [('tmdb_id', 'media_type', 'title', 'overview')], run=run)
    assert again[0]['title'] == 'Der Bote'
    assert len(calls) == 1


def test_languages_are_cached_separately(monkeypatch):
    store, calls = Store(), []
    store.save_translation('10', 'movie', 'fr', 'Le Messager', None)
    monkeypatch.setattr(localization, 'fetch_translations', _fake_fetch({}, calls))
    items = [{'tmdb_id': '10', 'media_type': 'movie', 'title': 'The Messenger', 'overview': 'English.'}]
    localization.localize_items(items, 'de', store, 'key', [('tmdb_id', 'media_type', 'title', 'overview')], run=run)
    assert items[0]['title'] == 'The Messenger'
    assert calls == [((('10', 'movie'),), 'de')]


def test_a_failed_fetch_keeps_the_default_and_is_tried_again(monkeypatch):
    store, calls = Store(), []
    monkeypatch.setattr(localization, 'fetch_translations', _fake_fetch({}, calls))
    items = [{'tmdb_id': 10, 'media_type': 'movie', 'title': 'The Messenger', 'overview': 'English.'}]
    for _ in range(2):
        localization.localize_items(items, 'de', store, 'key', [('tmdb_id', 'media_type', 'title', 'overview')], run=run)
    assert items[0]['title'] == 'The Messenger'
    assert len(calls) == 2


def test_an_empty_translated_overview_keeps_the_default_one(monkeypatch):
    store, calls = Store(), []
    monkeypatch.setattr(localization, 'fetch_translations',
                        _fake_fetch({('20', 'tv'): {'title': 'Die Serie', 'overview': None}}, calls))
    items = [{'request_id': '20', 'media_type': 'tv', 'title': 'The Show', 'overview': 'English.'}]
    localization.localize_items(items, 'de', store, 'key', [('request_id', 'media_type', 'title', 'overview')], run=run)
    assert items[0] == {'request_id': '20', 'media_type': 'tv', 'title': 'Die Serie', 'overview': 'English.'}


def test_english_readers_cost_no_lookup(monkeypatch):
    store = MagicMock()
    items = [{'tmdb_id': 10, 'media_type': 'movie', 'title': 'The Messenger'}]
    localization.localize_items(items, 'en', store, 'key', [('tmdb_id', 'media_type', 'title', 'overview')], run=run)
    store.get_translations.assert_not_called()


def test_ids_that_are_not_tmdb_ids_are_not_looked_up(monkeypatch):
    store, calls = Store(), []
    monkeypatch.setattr(localization, 'fetch_translations', _fake_fetch({}, calls))
    items = [{'source_id': '0', 'media_type': 'movie', 'source_title': 'x'},
             {'source_id': 'ai_search', 'media_type': 'movie', 'source_title': 'y'}]
    localization.localize_items(items, 'de', store, 'key', [('source_id', 'media_type', 'source_title', None)], run=run)
    assert calls == []


def test_a_broken_cache_shows_the_default_instead_of_failing():
    store = MagicMock()
    store.get_translations.side_effect = RuntimeError('database gone')
    items = [{'tmdb_id': 10, 'media_type': 'movie', 'title': 'The Messenger'}]
    assert localization.localize_items(items, 'de', store, 'key',
                                       [('tmdb_id', 'media_type', 'title', None)], run=run)[0]['title'] == 'The Messenger'


def test_the_user_language_is_stored_and_cleared():
    store = Store()
    assert store.get_user_language(1) is None
    assert store.update_auth_user_profile(1, {'language': 'de'})
    assert store.get_user_language(1) == 'de'
    store.update_auth_user_profile(1, {'language': None})
    assert store.get_user_language(1) is None


def test_a_profile_update_that_fails_writes_no_language():
    """Language and username go into one statement: a taken username leaves
    the language as it was."""
    store = Store()
    with pytest.raises(sqlite3.IntegrityError):
        store.update_auth_user_profile(1, {'language': 'de', 'username': 'robert'})
    assert store.get_user_language(1) is None


# --- the lookup budget and the refresh ------------------------------------------

def _slow_tmdb(monkeypatch, delays):
    """Answer each lookup after its delay in seconds; a pair without one never answers."""
    async def fetch_one(session, semaphore, api_key, media_id, media_type, language):
        async with semaphore:
            await asyncio.sleep(delays.get(media_id, 3600))
        return {'title': f'Titel {media_id}', 'overview': None}
    monkeypatch.setattr(localization, '_fetch_one', fetch_one)


def test_lookups_share_one_budget_and_the_rest_is_skipped(monkeypatch):
    """An unreachable TMDb must not hold a list request for batch after batch
    of timeouts: whatever has not answered when the budget is used up is left
    for the next request."""
    _slow_tmdb(monkeypatch, {'1': 0.01, '2': 0.02})
    pairs = [(str(media_id), 'movie') for media_id in range(1, 101)]
    started = time.monotonic()
    found = asyncio.run(localization.fetch_translations('key', pairs, 'de', budget=0.3))
    assert time.monotonic() - started < 1.5
    assert set(found) == {('1', 'movie'), ('2', 'movie')}


def test_the_default_budget_is_a_few_seconds():
    assert 2 <= localization.LOOKUP_BUDGET_SECONDS <= 5


def test_skipped_lookups_are_not_cached_and_the_stored_title_is_shown(monkeypatch):
    _slow_tmdb(monkeypatch, {'1': 0.01})
    monkeypatch.setattr(localization, 'LOOKUP_BUDGET_SECONDS', 0.3)
    store = Store()
    items = [{'tmdb_id': media_id, 'media_type': 'movie', 'title': f'Title {media_id}'} for media_id in ('1', '2')]
    localization.localize_items(items, 'de', store, 'key', [('tmdb_id', 'media_type', 'title', None)], run=run)
    assert [item['title'] for item in items] == ['Titel 1', 'Title 2']
    assert set(store.get_translations([('1', 'movie'), ('2', 'movie')], 'de')) == {('1', 'movie')}


def _age(store, days):
    store.connection.execute(
        "UPDATE metadata_translations SET fetched_at = datetime('now', ?)", (f'-{days} days',))


def test_an_old_translation_is_fetched_again(monkeypatch):
    store, calls = Store(), []
    store.save_translation('10', 'movie', 'de', 'Der alte Titel', None)
    _age(store, localization.REFRESH_AFTER.days + 1)
    monkeypatch.setattr(localization, 'fetch_translations',
                        _fake_fetch({('10', 'movie'): {'title': 'Der neue Titel', 'overview': None}}, calls))
    items = [{'tmdb_id': '10', 'media_type': 'movie', 'title': 'The Title'}]
    localization.localize_items(items, 'de', store, 'key', [('tmdb_id', 'media_type', 'title', None)], run=run)
    assert items[0]['title'] == 'Der neue Titel'
    assert len(calls) == 1
    assert store.get_translations([('10', 'movie')], 'de')[('10', 'movie')]['title'] == 'Der neue Titel'


def test_an_old_translation_is_still_shown_when_its_refresh_fails(monkeypatch):
    store, calls = Store(), []
    store.save_translation('10', 'movie', 'de', 'Der alte Titel', None)
    _age(store, localization.REFRESH_AFTER.days + 1)
    monkeypatch.setattr(localization, 'fetch_translations', _fake_fetch({}, calls))
    items = [{'tmdb_id': '10', 'media_type': 'movie', 'title': 'The Title'}]
    localization.localize_items(items, 'de', store, 'key', [('tmdb_id', 'media_type', 'title', None)], run=run)
    assert items[0]['title'] == 'Der alte Titel'
    assert len(calls) == 1


def test_a_recent_translation_is_not_fetched_again(monkeypatch):
    store, calls = Store(), []
    store.save_translation('10', 'movie', 'de', 'Der Titel', None)
    _age(store, localization.REFRESH_AFTER.days - 1)
    monkeypatch.setattr(localization, 'fetch_translations', _fake_fetch({}, calls))
    items = [{'tmdb_id': '10', 'media_type': 'movie', 'title': 'The Title'}]
    localization.localize_items(items, 'de', store, 'key', [('tmdb_id', 'media_type', 'title', None)], run=run)
    assert items[0]['title'] == 'Der Titel'
    assert calls == []


# --- the routes ---------------------------------------------------------------

def _app(monkeypatch, db, env, blueprint, prefix):
    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=False)

    @app.before_request
    def authenticate():
        g.current_user = {'id': '1', 'username': 'achim', 'role': 'user'}

    limiter.init_app(app)
    app.register_blueprint(blueprint, url_prefix=prefix)
    return app.test_client()


def test_a_person_sets_and_clears_their_own_language(monkeypatch):
    db = MagicMock()
    db.get_user_language.return_value = 'de'
    monkeypatch.setattr(auth_routes, 'DatabaseManager', MagicMock(return_value=db))
    monkeypatch.setattr(auth_routes, 'load_env_vars', lambda: {'TMDB_LANGUAGE': 'fr'})
    client = _app(monkeypatch, db, {}, auth_routes.auth_bp, '/api/auth')

    assert client.patch('/api/auth/me', json={'language': 'de'}).status_code == 200
    db.update_auth_user_profile.assert_called_with(1, {'language': 'de'})
    assert client.patch('/api/auth/me', json={'language': None}).status_code == 200
    db.update_auth_user_profile.assert_called_with(1, {'language': None})
    db.update_auth_user_profile.reset_mock()
    assert client.patch('/api/auth/me', json={'language': 'Deutsch'}).status_code == 400
    db.update_auth_user_profile.assert_not_called()

    me = client.get('/api/auth/me').get_json()
    assert me['language'] == 'de' and me['display_language'] == 'de'
    db.get_user_language.return_value = None
    assert client.get('/api/auth/me').get_json()['display_language'] == 'fr'


def test_the_suggestion_list_is_shown_in_the_readers_language(monkeypatch):
    db = MagicMock()
    db.get_user_language.return_value = 'de'
    db.get_integration.return_value = {'api_key': 'key'}
    db.list_suggestions.return_value = ([{'tmdb_id': '10', 'media_type': 'movie', 'title': 'The Messenger', 'overview': 'English.'}], 1)
    db.get_media_user_profiles = MagicMock(return_value=[])
    db.get_user_media_profiles.return_value = []
    db.get_translations.return_value = {('10', 'movie'): {'title': 'Der Bote', 'overview': 'Deutsch.'}}
    monkeypatch.setattr(automation_routes, 'DatabaseManager', MagicMock(return_value=db))
    monkeypatch.setattr(automation_routes, 'load_env_vars', lambda: {})
    client = _app(monkeypatch, db, {}, automation_routes.automation_bp, '/api/automation')

    body = client.get('/api/automation/requests/workflow').get_json()
    assert body['items'][0]['title'] == 'Der Bote'
    assert body['items'][0]['overview'] == 'Deutsch.'


def _translating_db():
    db = MagicMock()
    db.get_user_language.return_value = 'de'
    db.get_integration.return_value = {'api_key': 'key'}
    db.get_user_media_profiles.return_value = []
    german = {('1', 'movie'): {'title': 'Quelle', 'overview': 'Q.'}, ('2', 'movie'): {'title': 'Vorschlag', 'overview': 'V.'}}
    db.get_translations.side_effect = lambda pairs, language: {pair: german[pair] for pair in pairs if pair in german}
    return db


def test_the_grouped_request_list_is_shown_in_the_readers_language(monkeypatch):
    db = _translating_db()
    db.get_all_requests_grouped_by_source.return_value = {'data': [{
        'source_id': '1', 'media_type': 'movie', 'source_title': 'Source', 'source_overview': 'S.',
        'requests': [{'request_id': '2', 'media_type': 'movie', 'title': 'Suggestion', 'overview': 'X.'}],
    }]}
    monkeypatch.setattr(automation_routes, 'DatabaseManager', MagicMock(return_value=db))
    monkeypatch.setattr(automation_routes, 'load_env_vars', lambda: {})
    client = _app(monkeypatch, db, {}, automation_routes.automation_bp, '/api/automation')

    source = client.get('/api/automation/requests').get_json()['data'][0]
    assert (source['source_title'], source['source_overview']) == ('Quelle', 'Q.')
    assert (source['requests'][0]['title'], source['requests'][0]['overview']) == ('Vorschlag', 'V.')


def test_the_ai_search_list_is_shown_in_the_readers_language(monkeypatch):
    db = _translating_db()
    db.get_ai_search_requests.return_value = {'data': [
        {'request_id': '2', 'media_type': 'movie', 'title': 'Suggestion', 'overview': 'X.'},
    ]}
    monkeypatch.setattr(automation_routes, 'DatabaseManager', MagicMock(return_value=db))
    monkeypatch.setattr(automation_routes, 'load_env_vars', lambda: {})
    client = _app(monkeypatch, db, {}, automation_routes.automation_bp, '/api/automation')

    assert client.get('/api/automation/requests/ai-search').get_json()['data'][0]['title'] == 'Vorschlag'


def test_a_rejected_profile_update_keeps_the_old_language(monkeypatch):
    """Language plus a wrong password is refused as a whole — nothing is written."""
    db = MagicMock()
    db.get_auth_user_by_id.return_value = {'id': 1, 'username': 'achim', 'role': 'user', 'password_hash': 'hash'}
    monkeypatch.setattr(auth_routes, 'DatabaseManager', MagicMock(return_value=db))
    monkeypatch.setattr(auth_routes.AuthService, 'verify_password', lambda password, hashed: False)
    client = _app(monkeypatch, db, {}, auth_routes.auth_bp, '/api/auth')

    response = client.patch('/api/auth/me', json={
        'language': 'de', 'current_password': 'wrong', 'new_password': 'long-enough-password'})
    assert response.status_code == 401
    db.update_auth_user_profile.assert_not_called()

    assert client.patch('/api/auth/me', json={'language': 'de', 'username': ''}).status_code == 200
    assert client.patch('/api/auth/me', json={'language': 'de', 'new_password': 'short'}).status_code == 400
    db.update_auth_user_profile.assert_called_once_with(1, {'language': 'de'})


def test_language_and_username_are_saved_together(monkeypatch):
    db = MagicMock()
    db.get_auth_user_by_id.return_value = {'id': 1, 'username': 'achim2', 'role': 'user'}
    monkeypatch.setattr(auth_routes, 'DatabaseManager', MagicMock(return_value=db))
    client = _app(monkeypatch, db, {}, auth_routes.auth_bp, '/api/auth')

    assert client.patch('/api/auth/me', json={'language': 'fr', 'username': 'achim2'}).status_code == 200
    db.update_auth_user_profile.assert_called_once_with(1, {'language': 'fr', 'username': 'achim2'})


@pytest.mark.parametrize('path, method', [
    ('/api/automation/requests', 'get_all_requests_grouped_by_source'),
    ('/api/automation/requests/ai-search', 'get_ai_search_requests'),
])
def test_list_routes_cap_per_page(monkeypatch, path, method):
    """Each listed item may cost a lookup, so no route lists more than 100."""
    db = _translating_db()
    getattr(db, method).return_value = {'data': []}
    monkeypatch.setattr(automation_routes, 'DatabaseManager', MagicMock(return_value=db))
    monkeypatch.setattr(automation_routes, 'load_env_vars', lambda: {})
    client = _app(monkeypatch, db, {}, automation_routes.automation_bp, '/api/automation')

    assert client.get(f'{path}?per_page=100000&page=-3').status_code == 200
    assert getattr(db, method).call_args.kwargs['per_page'] == 100
    assert getattr(db, method).call_args.kwargs['page'] == 1
    client.get(f'{path}?per_page=0')
    assert getattr(db, method).call_args.kwargs['per_page'] == 1


def test_the_grouped_request_list_uses_one_lookup_for_sources_and_requests(monkeypatch):
    db = _translating_db()
    db.get_translations.side_effect = lambda pairs, language: {}
    db.get_all_requests_grouped_by_source.return_value = {'data': [{
        'source_id': '1', 'media_type': 'movie', 'source_title': 'Source', 'source_overview': 'S.',
        'requests': [{'request_id': '2', 'media_type': 'movie', 'title': 'Suggestion', 'overview': 'X.'}],
    }]}
    calls = []
    monkeypatch.setattr(localization, 'fetch_translations', _fake_fetch({}, calls))
    monkeypatch.setattr(automation_routes, 'DatabaseManager', MagicMock(return_value=db))
    monkeypatch.setattr(automation_routes, 'load_env_vars', lambda: {})
    client = _app(monkeypatch, db, {}, automation_routes.automation_bp, '/api/automation')

    assert client.get('/api/automation/requests').status_code == 200
    assert calls == [((('1', 'movie'), ('2', 'movie')), 'de')]
