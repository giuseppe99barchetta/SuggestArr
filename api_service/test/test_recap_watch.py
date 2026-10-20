"""Watched suggestions: ledger migration, play matching, hit rate and annual gamification."""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from api_service.db.recap_repository import RecapRepository, initialize_recap_schema
from api_service.db.year_recap_repository import YearRecapRepository
from api_service.services import year_recap
from api_service.services.year_recap import RecapWatchSync, match_plays
from api_service.test.test_recap import db, seed, ADMIN, USER, NOW, route_client  # noqa: F401

PLEX_ENV = {'SELECTED_SERVICE': 'plex', 'PLEX_API_URL': 'https://media.example', 'PLEX_TOKEN': 'test-only'}
JELLYFIN_ENV = {'SELECTED_SERVICE': 'jellyfin', 'JELLYFIN_API_URL': 'https://media.example', 'JELLYFIN_TOKEN': 'test-only'}
ALICE = [{'provider': 'plex', 'external_user_id': 'alice'}]


@pytest.fixture(autouse=True)
def fresh_sync_throttle():
    year_recap._last_sync.clear()
    yield
    year_recap._last_sync.clear()


def ts(*args):
    return datetime(*args, tzinfo=timezone.utc)


def watched_rows(db):
    with db.get_connection() as conn:
        return {row[0]: row[1] for row in conn.execute('SELECT tmdb_id, watched_at FROM recap_titles WHERE watched_at IS NOT NULL')}


def test_existing_ledger_gains_watched_column_without_losing_titles(db):
    with db.get_connection() as conn:
        conn.execute('DROP TABLE recap_titles')
        conn.execute('''CREATE TABLE recap_titles (media_type VARCHAR(16) NOT NULL, tmdb_id VARCHAR(64) NOT NULL,
            user_id VARCHAR(191), requested_at TIMESTAMP NOT NULL, PRIMARY KEY (media_type, tmdb_id))''')
        conn.execute("INSERT INTO recap_titles VALUES ('movie','7','alice','2026-01-01 00:00:00')")
        conn.commit()
    initialize_recap_schema(db)
    initialize_recap_schema(db)  # Repeatable.
    with db.get_connection() as conn:
        assert [tuple(row) for row in conn.execute('SELECT tmdb_id, watched_at FROM recap_titles')] == [('7', None)]


def test_matching_requires_the_recipient_and_a_play_after_the_request():
    requested = ts(2026, 5, 1)
    pending = [('movie', '1', 'alice', requested), ('movie', '2', 'alice', requested),
               ('tv', '3', 'alice', requested), ('movie', '4', None, requested)]
    entries = [
        {'kind': 'movie', 'tmdb': '1', 'account': 'alice', 'date': ts(2026, 6, 2)},
        {'kind': 'movie', 'tmdb': '1', 'account': 'alice', 'date': ts(2026, 5, 20)},
        {'kind': 'movie', 'tmdb': '2', 'account': 'bob', 'date': ts(2026, 6, 1)},     # Someone else.
        {'kind': 'episode', 'tmdb': '3', 'account': 'alice', 'date': ts(2026, 4, 1)},  # Before the request.
        {'kind': 'movie', 'tmdb': '4', 'account': 'bob', 'date': ts(2026, 6, 1)},     # No recorded recipient.
        {'kind': 'movie', 'tmdb': None, 'account': 'alice', 'date': ts(2026, 6, 1)},
    ]
    assert match_plays(pending, entries) == [(ts(2026, 5, 20), 'movie', '1'), (ts(2026, 6, 1), 'movie', '4')]


def test_mark_watched_keeps_the_first_observed_play(db):
    seed(db, 2)
    repo = RecapRepository(db)
    assert repo.mark_watched([(ts(2026, 10, 1), 'movie', '0')]) == 1
    assert repo.mark_watched([(ts(2026, 10, 5), 'movie', '0')]) == 0
    assert str(watched_rows(db)['0']).startswith('2026-10-01')
    assert [row[1] for row in repo.pending_watch(None)] == ['1']


def run_sync(db, user, env, payloads, now=NOW):
    client = RecapWatchSync()
    client._json = AsyncMock(side_effect=payloads)
    return asyncio.run(client.sync(RecapRepository(db), user, env, now)), client


def test_plex_sync_resolves_tmdb_ids_in_batches_and_updates_the_hit_rate(db):
    seed(db, 4, age=30)  # IDs 0 and 2 are movies, 1 and 3 are TV series, all for alice.
    played = (NOW - timedelta(days=2)).timestamp()
    history = {'MediaContainer': {'totalSize': 3, 'Metadata': [
        {'ratingKey': 'm0', 'type': 'movie', 'viewedAt': played, 'accountID': 'alice'},
        {'ratingKey': 'e1', 'type': 'episode', 'grandparentRatingKey': 's1', 'viewedAt': played, 'accountID': 'alice'},
        {'ratingKey': 'm9', 'type': 'movie', 'viewedAt': played, 'accountID': 'alice'},
    ]}}
    metadata = {'MediaContainer': {'Metadata': [
        {'ratingKey': 'm0', 'Guid': [{'id': 'imdb://tt1'}, {'id': 'tmdb://0'}]},
        {'ratingKey': 's1', 'Guid': [{'id': 'tmdb://1'}]},
        {'ratingKey': 'm9', 'Guid': [{'id': 'tmdb://999'}]},
    ]}}
    with patch.object(db, 'get_user_media_profiles', return_value=ALICE):
        result, client = run_sync(db, USER, PLEX_ENV, [history, metadata])
        assert result == {'status': 'ok', 'matched': 2}
        assert client._json.call_args_list[0].args[2]['accountID'] == 'alice'
        lookup = client._json.call_args_list[1]
        assert lookup.args[0] == 'https://media.example/library/metadata/m0,m9,s1'
        assert lookup.args[2] == {'includeGuids': 1}
        summary = RecapRepository(db).summary(USER, PLEX_ENV, now=NOW)
        assert (summary['watched'], summary['hit_rate'], summary['watch_tracking']) == (2, 50, True)
        assert 'watched_1' in [badge['id'] for badge in summary['badges'] if badge['unlocked']]
        # A second scan within the interval is skipped; the server is not contacted again.
        assert run_sync(db, USER, PLEX_ENV, [])[0]['status'] == 'skipped'


def test_jellyfin_sync_uses_inline_provider_ids_and_series_fallback(db):
    seed(db, 2, age=30)
    played = (NOW - timedelta(days=1)).isoformat()
    items = {'TotalRecordCount': 2, 'Items': [
        {'Id': 'a', 'Type': 'Movie', 'ProviderIds': {'Tmdb': '0'}, 'UserData': {'LastPlayedDate': played}},
        {'Id': 'b', 'Type': 'Episode', 'SeriesId': 'series-1', 'UserData': {'LastPlayedDate': played}},
    ]}
    series = {'Items': [{'Id': 'series-1', 'ProviderIds': {'Tmdb': '1'}}]}
    with patch.object(db, 'get_user_media_profiles', return_value=[{'provider': 'jellyfin', 'external_user_id': 'alice'}]):
        result, client = run_sync(db, USER, JELLYFIN_ENV, [items, series])
    assert result['matched'] == 2
    assert client._json.call_args_list[0].args[2]['Fields'] == 'ProviderIds,SeriesProviderIds'
    assert client._json.call_args_list[1].args[2] == {'Ids': 'series-1', 'Fields': 'ProviderIds'}


def test_sync_scope_privacy_and_failures(db):
    seed(db, 2)
    with patch.object(db, 'get_user_media_profiles', return_value=[]):
        result, client = run_sync(db, USER, PLEX_ENV, [])
        assert result['status'] == 'no_profiles'
        client._json.assert_not_called()
    assert run_sync(db, ADMIN, {}, [])[0]['status'] == 'not_configured'
    result, _ = run_sync(db, ADMIN, PLEX_ENV, [RuntimeError('private-token-and-address')])
    assert result == {'status': 'unavailable', 'matched': 0}
    # A failed scan does not hold the throttle, so the next visit can retry.
    assert run_sync(db, ADMIN, PLEX_ENV, [{'MediaContainer': {'Metadata': [], 'totalSize': 0}}])[0]['status'] == 'ok'


def test_hit_rate_is_hidden_without_a_media_server(db):
    seed(db, 2)
    summary = RecapRepository(db).summary(ADMIN, {}, now=NOW)
    assert summary['watch_tracking'] is False and summary['hit_rate'] is None and summary['watched'] is None


def test_year_recap_hit_rate_streak_badges_and_top_rated_titles(db):
    seed(db, 12, age=200)
    with db.get_connection() as conn:
        conn.executemany('INSERT INTO metadata (media_id,media_type,title,rating) VALUES (?,?,?,?)',
                         [('0', 'movie', 'Low', 5.0), ('2', 'movie', 'High', 9.0), ('1', 'tv', 'Middle', 7.0)])
        conn.commit()
    repo = RecapRepository(db)
    repo.mark_watched([(ts(2026, 6, 1), 'movie', '0'), (ts(2026, 7, 1), 'movie', '2'), (ts(2026, 8, 1), 'tv', '1')])
    data = YearRecapRepository(db).summary(ADMIN, PLEX_ENV, 2026, 'server', now=NOW)
    assert data['hitRate'] == {'watched': 3, 'total': 12, 'percent': 25, 'movies': 2, 'series': 1}
    assert data['streak'] == {'longest': 3, 'months': 3}
    assert [title['title'] for title in data['titles']] == ['High', 'Middle', 'Low']
    assert data['titles'][0]['detail'] == 'Movie · Watched'
    unlocked = [badge['id'] for badge in data['badgesUnlocked']]
    # Requests in April unlock title badges before the first June play.
    assert unlocked == ['titles_10', 'watched_1', 'streak_3']
    assert all('unlockedAt' in badge for badge in data['badgesUnlocked'])
    assert YearRecapRepository(db).summary(ADMIN, {}, 2026, 'server', now=NOW)['hitRate'] is None


def test_watch_sync_route_requires_authentication_and_reports_status(db):
    from api_service.blueprints.recap import routes
    seed(db, 1)
    assert route_client(db, None).post('/api/recap/watch-sync').status_code == 401
    with patch.object(routes, 'DatabaseManager', return_value=db), patch.object(routes, 'load_env_vars', return_value={}):
        response = route_client(db, USER).post('/api/recap/watch-sync')
    assert response.status_code == 200
    assert response.json['data'] == {'status': 'not_configured', 'matched': 0}
