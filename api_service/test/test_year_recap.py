"""Annual privacy, calendar boundaries and truthful native watch-state coverage."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from api_service.db.year_recap_repository import YearRecapRepository
from api_service.services.year_recap import YearWatchActivity
from api_service.test.test_recap import db, seed, ADMIN, USER, NOW, route_client  # noqa: F401


def yearly(db, user=ADMIN, env=None, year=2026, scope='server'):
    return YearRecapRepository(db).summary(user, env or {}, year, scope, now=NOW)


def test_calendar_counts_metadata_genres_and_cleanup(db):
    seed(db, 3)
    seed(db, 2, start=3, age=500)
    seed(db, 2, start=5, requested_by='Seer')
    with db.get_connection() as conn:
        conn.executemany('INSERT INTO metadata (media_id,media_type,title,genre_ids) VALUES (?,?,?,?)',
                         [('0', 'movie', 'First', '[878,18]'), ('1', 'tv', 'Second', '[18]'), ('2', 'movie', 'Third', '[53]')])
        conn.execute('DELETE FROM requests')
        conn.commit()
    data = yearly(db)
    assert data['requested'] == {'total': 3, 'movies': 2, 'series': 1}
    assert sum(month['requests'] for month in data['monthly']) == 3
    assert data['monthly'][8]['requests'] == 3
    assert sum(genre['percent'] for genre in data['genres']) == 100
    assert data['genres'][0] == {'label': 'Drama', 'percent': 50}
    assert data['genreCoverage'] == 3
    assert len(data['titles']) == 3
    assert data['watched'] is None and data['watchMinutes'] is None
    assert data['availableYears'] == [2026, 2025]
    assert yearly(db, year=2025)['requested']['total'] == 2


def test_utc_year_boundaries_and_future_records(db):
    seed(db, 4)
    with db.get_connection() as conn:
        for i, date in enumerate(['2025-12-31 23:59:59', '2026-01-01 00:00:00', '2026-10-19 12:00:01', '2027-01-01 00:00:00']):
            conn.execute('UPDATE recap_titles SET requested_at=? WHERE tmdb_id=?', (date, str(i)))
        conn.commit()
    data = yearly(db)
    assert data['requested']['total'] == 1
    assert data['monthly'][0]['requests'] == 1
    assert data['isYearToDate']


@pytest.mark.parametrize('mode', ['all', 'own', 'own_all'])
def test_personal_isolation_and_forbidden_server_scope(db, mode):
    seed(db, 3)
    seed(db, 4, start=3, user_id='bob')
    with patch.object(db, 'get_user_media_profiles', return_value=[{'provider': 'plex', 'external_user_id': 'alice'}]):
        data = yearly(db, USER, {'REQUEST_VISIBILITY': mode}, scope='personal')
        assert data['requested']['total'] == 3
        assert data['allowedScopes'] == ['personal']
        with pytest.raises(PermissionError):
            yearly(db, USER, {'REQUEST_VISIBILITY': mode})
        if mode == 'own_all':
            with pytest.raises(PermissionError):
                yearly(db, ADMIN, {'REQUEST_VISIBILITY': mode})


def test_no_profiles_and_synthetic_admin(db):
    seed(db)
    with patch.object(db, 'get_user_media_profiles', return_value=[]):
        assert yearly(db, USER, scope='personal')['requested']['total'] == 0
        assert not yearly(db, USER, scope='personal')['hasLinkedProfiles']
        assert yearly(db, {'id': 0, 'role': 'admin'})['requested']['total'] == 100


@pytest.mark.parametrize('query', ['user_id=1', 'owner=1', 'scope=installation', 'year=9999', 'year=nope',
                                     'include_playback=maybe', 'year=2025&year=2026', 'year=²', 'year=' + '1' * 5000])
def test_route_rejects_overrides_and_invalid_arguments(db, query):
    assert route_client(db, USER).get('/api/recap/year?' + query).status_code == 400


def test_authenticated_route_real_db_and_explicit_watch_loading(db):
    from api_service.blueprints.recap import routes
    seed(db, 3)
    with patch.object(routes, 'DatabaseManager', return_value=db), patch.object(routes, 'load_env_vars', return_value={}), \
            patch.object(routes.YearWatchActivity, 'load', new_callable=AsyncMock, return_value={'watchStatus': 'unavailable'}) as watch:
        client = route_client(db, ADMIN)
        assert client.get('/api/recap/year?year=2026&scope=server').json['data']['requested']['total'] == 3
        watch.assert_not_called()
        assert client.get('/api/recap/year?year=2026&scope=server&include_playback=true').status_code == 200
        watch.assert_awaited_once()
    assert route_client(db, USER).get('/api/recap/year?scope=server').status_code == 403
    assert route_client(db, None).get('/api/recap/year').status_code == 401


def activity_data(provider='plex', scope='personal'):
    return {'provider': provider, 'providerLabel': provider.title(), 'scope': scope, 'year': 2026,
            'generatedAt': NOW.isoformat()}


def run_watch(data, profiles, payloads):
    import asyncio
    client = YearWatchActivity()
    client._json = AsyncMock(side_effect=payloads)
    env = {f'{data["provider"].upper()}_API_URL': 'https://media.example', f'{data["provider"].upper()}_TOKEN': 'test-only'}
    return asyncio.run(client.load(data, profiles, env)), client


def test_plex_deduplicates_replays_checks_account_and_year():
    date = int(datetime(2026, 6, 1, tzinfo=timezone.utc).timestamp())
    items = [{'ratingKey': '1', 'type': 'movie', 'viewedAt': date, 'accountID': 'alice', 'duration': 9000000}] * 2
    items += [{'ratingKey': '2', 'type': 'episode', 'grandparentRatingKey': 's1', 'viewedAt': date, 'accountID': 'alice'},
              {'ratingKey': '3', 'type': 'movie', 'viewedAt': date, 'accountID': 'bob'},
              {'ratingKey': '4', 'type': 'movie', 'viewedAt': 1, 'accountID': 'alice'}]
    result, client = run_watch(activity_data(), [{'provider': 'plex', 'external_user_id': 'alice'}],
                              [{'MediaContainer': {'Metadata': items, 'totalSize': len(items)}}])
    assert result['watched'] == {'movies': 1, 'episodes': 1, 'series': 1}
    assert result['watchStatus'] == 'partial'
    assert 'watchMinutes' not in result  # Runtime is not actual watch time.
    assert client._json.call_args.args[2]['accountID'] == 'alice'


def test_jellyfin_last_played_snapshot_ignores_lifetime_play_count():
    items = [{'Id': '1', 'Type': 'Movie', 'UserData': {'LastPlayedDate': '2026-06-01T12:00:00Z', 'PlayCount': 75}},
             {'Id': '2', 'Type': 'Episode', 'SeriesId': 'series', 'UserData': {'LastPlayedDate': '2025-12-31T23:59:59Z'}},
             {'Id': '3', 'Type': 'Movie', 'UserData': {'PlayCount': 10}}]
    result, client = run_watch(activity_data('jellyfin'), [{'provider': 'jellyfin', 'external_user_id': 'alice'}],
                              [{'Items': items, 'TotalRecordCount': 3}])
    assert result['watched']['movies'] == 1
    assert result['watched']['episodes'] == 0
    assert 'snapshot' in result['watchNote']
    assert '/Users/alice/Items' in client._json.call_args.args[0]


def test_missing_link_never_fetches_global_history_and_errors_remain_private():
    result, client = run_watch(activity_data(), [], [])
    assert result['watchStatus'] == 'no_profiles'
    client._json.assert_not_called()
    result, _ = run_watch(activity_data(), [{'provider': 'plex', 'external_user_id': 'alice'}],
                          [RuntimeError('private-token-and-address')])
    assert result['watchStatus'] == 'unavailable'
    assert 'private-token' not in str(result)


def test_pagination_advances_and_stops_at_older_year():
    first = {'MediaContainer': {'Metadata': [{'ratingKey': '1', 'type': 'movie', 'viewedAt': NOW.timestamp(), 'accountID': 'alice'}], 'totalSize': 3}}
    second = {'MediaContainer': {'Metadata': [{'ratingKey': '2', 'type': 'movie', 'viewedAt': 1, 'accountID': 'alice'}], 'totalSize': 3}}
    with patch('api_service.services.year_recap.PAGE_SIZE', 1):
        result, client = run_watch(activity_data(), [{'provider': 'plex', 'external_user_id': 'alice'}], [first, second])
    assert result['watched']['movies'] == 0  # The generation instant is an exclusive bound.
    assert client._json.call_count == 2
    assert client._json.call_args.args[2]['X-Plex-Container-Start'] == 1


def test_annual_endpoint_with_production_jwt_middleware_and_own_all(db):
    import jwt
    from datetime import timedelta
    from flask import Flask
    from api_service.auth import auth_service, middleware
    from api_service.blueprints.recap import routes
    seed(db, 4)
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.before_request(middleware.enforce_authentication)
    app.register_blueprint(routes.recap_bp, url_prefix='/api/recap')
    client = app.test_client()
    key = 'annual-test-signing-key-never-used-in-production'
    token = jwt.encode({'sub': '1', 'role': 'admin', 'username': 'test-admin',
                        'exp': datetime.now(timezone.utc) + timedelta(minutes=5)}, key, algorithm='HS256')
    with patch.object(auth_service, 'load_secret_key', return_value=key), \
            patch.object(middleware, 'load_env_vars', return_value={'AUTH_MODE': 'enabled'}), \
            patch.object(middleware, '_is_setup_mode', return_value=False), \
            patch.object(routes, 'DatabaseManager', return_value=db), \
            patch.object(routes, 'load_env_vars', return_value={'REQUEST_VISIBILITY': 'own_all'}), \
            patch.object(db, 'get_user_media_profiles', return_value=[]):
        assert client.get('/api/recap/year').status_code == 401
        client.environ_base['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        result = client.get('/api/recap/year')
        assert result.status_code == 200
        assert result.json['data']['requested']['total'] == 0
        assert result.json['data']['allowedScopes'] == ['personal']
        assert client.get('/api/recap/year?scope=server').status_code == 403
