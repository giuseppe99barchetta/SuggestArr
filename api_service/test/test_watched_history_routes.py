import asyncio
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

from flask import Flask, g

from api_service.blueprints.watched_history import routes
from api_service.blueprints.watched_history.routes import watched_history_bp


def make_app(role='user'):
    app = Flask(__name__)
    app.config['TESTING'] = True

    @app.before_request
    def inject_user():
        g.current_user = {'id': '7', 'username': 'alice', 'role': role}

    app.register_blueprint(watched_history_bp, url_prefix='/api/watched-history')
    return app


def _db():
    db = MagicMock()
    db.get_user_media_profiles.return_value = [{
        'provider': 'jellyfin', 'external_user_id': 'jf-1', 'external_username': 'alice',
    }]
    db.upsert_media_user_identity.return_value = {'id': 42, 'external_user_id': 'jf-1'}
    return db


def _patches(db):
    return (
        patch('api_service.blueprints.watched_history.routes.DatabaseManager', return_value=db),
        patch('api_service.blueprints.watched_history.routes.ConfigService.get_runtime_config', return_value={
            'SELECTED_SERVICE': 'jellyfin',
        }),
    )


def test_list_my_watched_media_is_scoped_to_current_media_profile():
    db = _db()
    db.list_watched_media.return_value = [{'id': 3, 'title': 'Arrival'}]
    p1, p2 = _patches(db)
    with p1, p2:
        response = make_app().test_client().get('/api/watched-history/me')
    assert response.status_code == 200
    assert response.get_json()['items'] == [{'id': 3, 'title': 'Arrival'}]
    db.list_watched_media.assert_called_once_with(42, limit=10000)


def _sync(db, titles_result=None, side_effect=None):
    p1, p2 = _patches(db)
    with p1, p2, patch.dict(routes._last_sync, clear=True), \
            patch('api_service.services.watch_history_sync.PlayedTitles') as titles:
        titles.return_value.titles = AsyncMock(return_value=titles_result, side_effect=side_effect)
        client = make_app().test_client()
        first = client.post('/api/watched-history/me/sync')
        second = client.post('/api/watched-history/me/sync')
    return first, second, titles.return_value.titles


def test_first_sync_reads_everything_and_stores_plays():
    db = _db()
    db.latest_server_play.return_value = None
    db.record_server_plays.return_value = 2
    played = [{'tmdb_id': '2', 'media_type': 'tv', 'title': 'Bluey', 'year': None, 'watched_at': datetime(2026, 10, 1)}]
    first, second, titles = _sync(db, (played, False))
    assert first.get_json() == {'status': 'success', 'server_status': 'ok', 'added': 2, 'updated': 1}
    titles.assert_awaited_once_with('jellyfin', 'jf-1', {'SELECTED_SERVICE': 'jellyfin'}, since=None)
    db.record_server_plays.assert_called_once_with(42, played)
    # A second visit within the interval does not hit the media server again.
    assert second.get_json()['server_status'] == 'skipped'


def test_later_syncs_only_read_recent_plays():
    db = _db()
    db.latest_server_play.return_value = datetime(2026, 10, 10, 12, 0)
    db.record_server_plays.return_value = 0
    _first, _second, titles = _sync(db, ([], True))
    assert titles.await_args.kwargs['since'] == datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def test_sync_failure_is_reported_and_retried_next_time():
    db = _db()
    db.latest_server_play.return_value = None
    first, second, _titles = _sync(db, side_effect=OSError('down'))
    assert first.status_code == 200
    assert first.get_json()['server_status'] == 'unavailable'
    assert second.get_json()['server_status'] == 'unavailable'
    db.record_server_plays.assert_not_called()


def test_admin_can_open_another_profile_but_users_cannot():
    for role, expected in (('admin', 'jf-9'), ('user', None)):
        db = _db()
        db.list_watched_media.return_value = []
        p1, p2 = _patches(db)
        with p1, p2:
            make_app(role).test_client().get('/api/watched-history/me?user=jf-9')
        if expected:
            db.upsert_media_user_identity.assert_called_once_with('jellyfin', 'jf-9')
        else:
            db.upsert_media_user_identity.assert_called_once_with('jellyfin', 'jf-1', 'alice')


def test_csv_import_uses_fixed_columns_and_stores_csv_source():
    db = _db()
    p1, p2 = _patches(db)
    csv_data = b'tmdb_id,media_type,title,year,rating\n27205,movie,Inception,2010,9\n'
    with p1, p2:
        response = make_app().test_client().post(
            '/api/watched-history/me/import',
            data={'file': (BytesIO(csv_data), 'history.csv')},
            content_type='multipart/form-data',
        )
    assert response.status_code == 200
    assert response.get_json()['imported'] == 1
    db.upsert_watched_media.assert_called_once_with(
        42, '27205', 'movie', 'Inception', '2010', '9', source='csv_import',
    )


def test_csv_import_rejects_wrong_headers():
    db = _db()
    p1, p2 = _patches(db)
    with p1, p2:
        response = make_app().test_client().post(
            '/api/watched-history/me/import',
            data={'file': (BytesIO(b'id,title\n1,Arrival\n'), 'history.csv')},
            content_type='multipart/form-data',
        )
    assert response.status_code == 400
    assert 'headers' in response.get_json()['message']


def test_patch_updates_rating_and_exclusion_for_current_profile_only():
    db = _db()
    db.update_watched_media.return_value = {'id': 3, 'rating': 8.0, 'excluded': True, 'source': 'csv_import'}
    p1, p2 = _patches(db)
    with p1, p2:
        response = make_app().test_client().patch(
            '/api/watched-history/me/3', json={'rating': 8, 'excluded': True, 'source': 'manual'},
        )
    assert response.status_code == 200
    assert response.get_json()['item']['source'] == 'csv_import'
    db.update_watched_media.assert_called_once_with(42, 3, {'rating': 8, 'excluded': True})


def test_patch_unknown_title_returns_404():
    db = _db()
    db.update_watched_media.return_value = None
    p1, p2 = _patches(db)
    with p1, p2:
        response = make_app().test_client().patch('/api/watched-history/me/99', json={'excluded': False})
    assert response.status_code == 404


# Raw TMDb payloads: /search/movie and /search/tv results carry no media_type (only /search/multi does).
_TMDB_SEARCH = {
    '/search/movie': {'results': [{'id': 1, 'title': 'Arrival', 'release_date': '2016-11-11'}]},
    '/search/tv': {'results': [{'id': 2, 'name': 'Colin from Accounts', 'first_air_date': '2022-01-01'}]},
}


class _FakeResponse:
    status = 200

    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    """Stands in for aiohttp only, so the real TMDbClient search and formatting run."""
    closed = False

    def get(self, url, **kwargs):
        return _FakeResponse(next(body for path, body in _TMDB_SEARCH.items() if path in url))

    async def close(self):
        self.closed = True


def _tmdb_patches():
    return (
        patch('api_service.blueprints.watched_history.routes.ConfigService.get_runtime_config',
              return_value={'SELECTED_SERVICE': 'jellyfin', 'TMDB_API_KEY': 'key'}),
        patch('api_service.services.tmdb.tmdb_client.TMDbClient._get_session',
              new=AsyncMock(side_effect=lambda: _FakeSession())),
    )


def _search(media_type):
    p1, p2 = _tmdb_patches()
    with p1, p2:
        return asyncio.run(routes._search_tmdb('query', media_type))


def test_search_tags_movie_results_with_movie_type():
    assert [(r['tmdb_id'], r['media_type']) for r in _search('movie')] == [('1', 'movie')]


def test_search_tags_tv_results_with_tv_type():
    assert [(r['tmdb_id'], r['media_type']) for r in _search('tv')] == [('2', 'tv')]


def test_search_tags_each_result_with_the_search_it_came_from_for_both():
    assert [(r['tmdb_id'], r['media_type'], r['year']) for r in _search('both')] == [
        ('1', 'movie', '2016'), ('2', 'tv', '2022'),
    ]


def test_searched_tv_show_can_be_added_to_watch_history(tmp_path):
    import api_service.db.database_manager as dm_mod
    dm_mod.DatabaseManager._instance = None
    p1, p2 = _tmdb_patches()
    try:
        with p1, p2, patch.object(dm_mod, 'DB_PATH', str(tmp_path / 'test.db')),                 patch('api_service.db.database_manager.load_env_vars', return_value={'DB_TYPE': 'sqlite'}):
            client = make_app('admin').test_client()
            search = client.get('/api/watched-history/me/search?query=colin&media_type=tv')
            picked = search.get_json()['results'][0]
            added = client.post('/api/watched-history/me?user=jf-1', json={**picked, 'rating': 8})
            db = dm_mod.DatabaseManager()
            stored = db.list_watched_media(db.upsert_media_user_identity('jellyfin', 'jf-1')['id'])
    finally:
        dm_mod.DatabaseManager._instance = None
    assert added.status_code == 201, added.get_json()
    assert [(row['tmdb_id'], row['media_type'], row['title'], row['year'], row['rating']) for row in stored] == [
        ('2', 'tv', 'Colin from Accounts', 2022, 8.0),
    ]
