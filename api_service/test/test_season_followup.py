"""Next-season follow-up: history scan, per-server progress, the request rule and delivery."""
import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from api_service.jobs import season_followup as sf
from api_service.services.arr.arr_client import ArrClient
from api_service.services.seer.seer_client import SeerClient
from api_service.services.year_recap import YearWatchActivity


NOW = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)
ENV = {'SEASON_FOLLOWUP_ENABLED': True, 'SEASON_FOLLOWUP_EPISODES_BEFORE_END': 2,
       'SEASON_FOLLOWUP_WINDOW_DAYS': 180, 'SEASON_FOLLOWUP_ONLY_SUGGESTARR': False,
       'SELECTED_SERVICE': 'jellyfin', 'JELLYFIN_API_URL': 'http://jf.local:8096', 'JELLYFIN_TOKEN': 'test-only',
       'TMDB_API_KEY': 'tmdb-test', 'REQUEST_BACKEND': 'seer', 'SEER_API_URL': 'http://seer.local'}
KEY = sf.server_key('jellyfin', 'http://jf.local:8096')


@pytest.fixture
def db():
    import api_service.db.database_manager as dm_mod
    dm_mod.DatabaseManager._instance = None
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    with patch.object(dm_mod, 'DB_PATH', path), \
         patch('api_service.db.database_manager.load_env_vars', return_value={'DB_TYPE': 'sqlite'}):
        yield dm_mod.DatabaseManager()
    dm_mod.DatabaseManager._instance = None
    try:
        os.unlink(path)
    except (FileNotFoundError, PermissionError):
        pass


def play(tmdb, season, episode, day, **extra):
    return {'account': 'a', 'kind': 'episode', 'id': f'{tmdb}-{season}-{episode}-{day}', 'series_id': 's',
            'tmdb': tmdb, 'season': season, 'episode': episode,
            'date': NOW - timedelta(days=day), **extra}


# --- _scan keeps season and episode numbers -------------------------------------------------

def test_scan_reads_plex_and_jellyfin_episode_numbers():
    client = YearWatchActivity()
    viewed = int((NOW - timedelta(days=1)).timestamp())
    client._json = AsyncMock(return_value={'MediaContainer': {'Metadata': [
        {'ratingKey': '2', 'type': 'episode', 'grandparentRatingKey': 's1', 'parentIndex': 3, 'index': 7,
         'viewedAt': viewed, 'accountID': '1'}], 'totalSize': 1}})
    entries, _ = asyncio.run(client._scan(True, [None], 'http://plex', {}, NOW - timedelta(days=5), NOW, server=True))
    assert (entries[0]['season'], entries[0]['episode']) == (3, 7)

    client._json = AsyncMock(side_effect=[[{'Id': 'alice'}], {'Items': [
        {'Id': '9', 'Type': 'Episode', 'SeriesId': 'series', 'ParentIndexNumber': 2, 'IndexNumber': 5,
         'SeriesProviderIds': {'Tmdb': '100'}, 'UserData': {'LastPlayedDate': (NOW - timedelta(days=1)).isoformat()}},
        {'Id': '8', 'Type': 'Movie', 'ProviderIds': {'Tmdb': '7'},
         'UserData': {'LastPlayedDate': (NOW - timedelta(days=1)).isoformat()}}], 'TotalRecordCount': 2}])
    entries, _ = asyncio.run(client._scan(False, [], 'http://jf', {}, NOW - timedelta(days=5), NOW, server=True))
    episode, movie = entries
    assert (episode['season'], episode['episode'], episode['tmdb']) == (2, 5, '100')
    assert (movie['season'], movie['episode']) == (None, None)


def _paged_jellyfin(pages_per_account):
    """Fake Jellyfin: ``/Users`` then one play per page, newest first, per account."""
    def answer(url, headers, params=None):
        if url.endswith('/Users'):
            return [{'Id': account} for account in pages_per_account]
        account = url.split('/Users/')[1].split('/')[0]
        offset, total = params['StartIndex'], pages_per_account[account]
        if offset >= total:
            return {'Items': [], 'TotalRecordCount': total}
        date = (NOW - timedelta(hours=offset + 1)).isoformat()
        return {'Items': [{'Id': f'{account}{offset}', 'Type': 'Episode', 'SeriesId': 's', 'IndexNumber': offset,
                           'ParentIndexNumber': 1, 'UserData': {'LastPlayedDate': date}}],
                'TotalRecordCount': total}
    return AsyncMock(side_effect=answer)


def test_scan_page_cap_is_per_account_and_raised_only_on_request():
    with patch('api_service.services.year_recap.PAGE_SIZE', 1):
        client = YearWatchActivity()
        client._json = _paged_jellyfin({'busy': 15, 'quiet': 1})
        entries, truncated = asyncio.run(client._scan(False, [], 'http://jf', {}, NOW - timedelta(days=5), NOW,
                                                      server=True, max_pages=100))
        assert not truncated
        assert sum(e['account'] == 'busy' for e in entries) == 15
        assert sum(e['account'] == 'quiet' for e in entries) == 1

        client._json = _paged_jellyfin({'busy': 15, 'quiet': 1})
        entries, truncated = asyncio.run(client._scan(False, [], 'http://jf', {}, NOW - timedelta(days=5), NOW,
                                                      server=True))
        assert truncated  # existing callers keep the default 10-page cap
        assert sum(e['account'] == 'busy' for e in entries) == 10


def test_read_resolves_plex_shows_and_cuts_after_an_unresolved_play():
    entries = [play(None, 1, 1, 9, series_id='ok'), play(None, 1, 2, 5, series_id='flaky'),
               play(None, 1, 3, 2, series_id='ok'), {**play('7', 0, 0, 1), 'kind': 'movie'}]

    async def resolve_json(url, headers, params=None):
        if 'flaky' in url:
            raise TimeoutError()
        return {'MediaContainer': {'Metadata': [{'ratingKey': 'ok', 'Guid': [{'id': 'tmdb://42'}]}]}}

    reader = sf.SeasonPlays()
    reader._json = AsyncMock(side_effect=resolve_json)
    with patch.object(sf.SeasonPlays, '_scan', AsyncMock(return_value=(entries, False))), \
         patch('api_service.services.year_recap.RESOLVE_BATCH', 1):
        kept, truncated, cutoff = asyncio.run(reader.read(True, 'http://plex', 'tok', NOW - timedelta(days=30), NOW))
    assert cutoff == NOW - timedelta(days=5)
    assert [(e['tmdb'], e['episode']) for e in kept] == [('42', 1)]  # the later play waits for the next run


# --- progress table ---------------------------------------------------------------------------

def test_progress_is_forward_only_and_last_play_moves_on_rewatches(db):
    db.record_season_progress(KEY, [{'tmdb_id': 1, 'season': 2, 'episode': 4, 'watched_at': NOW - timedelta(days=10)}])
    db.record_season_progress(KEY, [{'tmdb_id': 1, 'season': 1, 'episode': 3, 'watched_at': NOW - timedelta(days=1)}])
    db.record_season_progress(KEY, [{'tmdb_id': 1, 'season': 2, 'episode': 6, 'watched_at': NOW - timedelta(days=20)}])
    [show] = db.season_followup_candidates(KEY, NOW - timedelta(days=30))
    assert (show['season'], show['episode']) == (2, 6)
    assert show['last_watched_at'] == (NOW - timedelta(days=1)).replace(tzinfo=None)
    assert db.season_followup_candidates('other-server', NOW - timedelta(days=30)) == []
    db.mark_season_requested(KEY, 1, 3)
    db.mark_season_requested(KEY, 1, 2)  # never moves back
    assert db.season_followup_candidates(KEY, NOW - timedelta(days=30))[0]['requested_season'] == 3


def test_watermark_round_trip(db):
    assert db.get_scan_watermark(KEY) is None
    db.set_scan_watermark(KEY, NOW)
    db.set_scan_watermark(KEY, NOW)  # an unchanged value must not insert a duplicate key
    db.set_scan_watermark(KEY, NOW + timedelta(hours=6))
    assert db.get_scan_watermark(KEY) == NOW + timedelta(hours=6)


def test_furthest_positions_ignores_specials_and_unknown_numbers():
    rows = sf.furthest_positions([play('5', 1, 9, 3), play('5', 2, 1, 8), play('5', 0, 1, 1),
                                  play('5', None, None, 1), play(None, 3, 3, 1)])
    # The special and the unnumbered play are the newest plays: they keep the show fresh.
    assert rows == [{'tmdb_id': 5, 'season': 2, 'episode': 1, 'watched_at': NOW - timedelta(days=1)}]
    assert sf.furthest_positions([play('6', 0, 1, 2)]) == [
        {'tmdb_id': 6, 'season': None, 'episode': None, 'watched_at': NOW - timedelta(days=2)}]


def test_special_only_play_refreshes_a_tracked_show_but_never_creates_one(db):
    db.record_season_progress(KEY, [{'tmdb_id': 6, 'season': None, 'episode': None, 'watched_at': NOW}])
    assert db.season_followup_candidates(KEY, NOW - timedelta(days=400)) == []
    db.record_season_progress(KEY, [{'tmdb_id': 1, 'season': 2, 'episode': 4, 'watched_at': NOW - timedelta(days=300)}])
    db.record_season_progress(KEY, [{'tmdb_id': 1, 'season': None, 'episode': None, 'watched_at': NOW}])
    [show] = db.season_followup_candidates(KEY, NOW - timedelta(days=10))
    assert (show['season'], show['episode'], show['last_watched_at']) == (2, 4, NOW.replace(tzinfo=None))


# --- the request rule -------------------------------------------------------------------------

@pytest.mark.parametrize('episode, before_end, expected', [(8, 2, 2), (7, 2, None), (10, 0, 2), (9, 0, None)])
def test_threshold(episode, before_end, expected):
    show = {'season': 1, 'episode': episode, 'requested_season': None}
    assert sf.next_season(show, {1: 10, 2: 8}, before_end) == expected


def test_rule_needs_a_known_count_an_existing_next_season_and_no_earlier_request():
    show = {'season': 1, 'episode': 10, 'requested_season': None}
    assert sf.next_season(show, {1: 0, 2: 8}, 2) is None
    assert sf.next_season(show, {1: None, 2: 8}, 2) is None
    assert sf.next_season(show, {1: 10}, 2) is None  # caught up: wait for TMDb
    assert sf.next_season({**show, 'requested_season': 2}, {1: 10, 2: 8}, 2) is None


# --- the job ----------------------------------------------------------------------------------

def run_job(db, env, plays, seasons, deliver=True, now=NOW):
    reader = AsyncMock(return_value=(plays, False, None))
    tmdb = AsyncMock()
    tmdb.get_tv_seasons = AsyncMock(side_effect=lambda tmdb_id: seasons.get(tmdb_id))
    sender = AsyncMock(return_value=deliver) if not isinstance(deliver, AsyncMock) else deliver
    with patch.object(sf.ConfigService, 'get_runtime_config', return_value=env), \
         patch.object(sf.SeasonPlays, 'read', reader), \
         patch.object(sf, '_tmdb_client', return_value=tmdb), \
         patch.object(sf, '_deliver', sender):
        result = asyncio.run(sf.execute_season_followup(now=now))
    return result, reader, sender


def test_disabled_job_does_nothing_and_enabling_needs_no_restart(db):
    result, reader, sender = run_job(db, {**ENV, 'SEASON_FOLLOWUP_ENABLED': False}, [play('1', 1, 9, 1)], {})
    assert result['status'] == 'disabled'
    reader.assert_not_called()
    assert db.get_scan_watermark(KEY) is None
    result, _, sender = run_job(db, ENV, [play('1', 1, 9, 1)], {1: {'tvdb_id': 11, 'seasons': {1: 10, 2: 10}}})
    assert result['requested'] == 1
    sender.assert_awaited_once()
    assert sender.await_args.args[2:5] == (1, 11, 2)


def test_request_is_marked_only_after_success_and_retried(db):
    seasons = {1: {'tvdb_id': None, 'seasons': {1: 10, 2: 10}}}
    result, _, _ = run_job(db, ENV, [play('1', 1, 10, 1)], seasons, deliver=False)
    assert (result['requested'], result['skipped']) == (0, 1)
    result, _, _ = run_job(db, ENV, [], seasons, deliver=AsyncMock(side_effect=RuntimeError('down')))
    assert result['errors'] == 1
    result, _, _ = run_job(db, ENV, [], seasons)
    assert result['requested'] == 1
    result, _, sender = run_job(db, ENV, [], seasons)
    assert result['requested'] == 0
    sender.assert_not_called()


def test_caught_up_show_is_requested_once_tmdb_lists_the_next_season(db):
    run_job(db, ENV, [play('1', 3, 10, 30)], {1: {'tvdb_id': None, 'seasons': {1: 10, 2: 10, 3: 10}}})
    result, _, _ = run_job(db, ENV, [], {1: {'tvdb_id': None, 'seasons': {1: 10, 2: 10, 3: 10, 4: 0}}})
    assert result['requested'] == 1  # no new play needed


def test_window_and_only_suggestarr_filter(db):
    seasons = {1: {'tvdb_id': None, 'seasons': {1: 10, 2: 10}}, 2: {'tvdb_id': None, 'seasons': {1: 10, 2: 10}}}
    result, _, _ = run_job(db, {**ENV, 'SEASON_FOLLOWUP_WINDOW_DAYS': 5}, [play('1', 1, 10, 9)], seasons)
    assert result['shows'] == 0
    db.save_request('tv', '2', 'tmdb-src')
    db.save_requests_batch([{'media': {'mediaType': 'tv', 'tmdbId': 1}}])  # imported from Seer
    result, _, sender = run_job(db, {**ENV, 'SEASON_FOLLOWUP_ONLY_SUGGESTARR': True},
                                [play('1', 1, 10, 1), play('2', 1, 10, 1)], seasons)
    assert [call.args[2] for call in sender.await_args_list] == [2]  # the Seer-imported show 1 is left out


def test_watermark_window_outage_and_server_switch(db):
    _, reader, _ = run_job(db, ENV, [], {})
    assert reader.await_args.args[3] == NOW - timedelta(days=180)  # no row: full window
    later = NOW + timedelta(days=10)  # a 10-day outage is read from the stored watermark
    _, reader, _ = run_job(db, ENV, [], {}, now=later)
    assert reader.await_args.args[3] == NOW - timedelta(days=1)
    _, reader, _ = run_job(db, {**ENV, 'JELLYFIN_API_URL': 'http://jf-new.local'}, [], {}, now=later)
    assert reader.await_args.args[3] == later - timedelta(days=180)
    _, reader, _ = run_job(db, {**ENV, 'SELECTED_SERVICE': 'plex', 'PLEX_API_URL': 'http://plex.local',
                                'PLEX_TOKEN': 't'}, [], {}, now=later)
    assert reader.await_args.args[3] == later - timedelta(days=180)
    assert reader.await_args.args[0] is True


def test_unresolved_cutoff_becomes_the_watermark(db):
    cutoff = NOW - timedelta(days=3)
    reader = AsyncMock(return_value=([], False, cutoff))
    with patch.object(sf.ConfigService, 'get_runtime_config', return_value=ENV), \
         patch.object(sf.SeasonPlays, 'read', reader), patch.object(sf, '_tmdb_client', return_value=AsyncMock()):
        asyncio.run(sf.execute_season_followup(now=NOW))
    assert db.get_scan_watermark(KEY) == cutoff


def test_progress_per_server_never_triggers_from_an_old_server(db):
    db.record_season_progress(sf.server_key('plex', 'http://plex.local'),
                              [{'tmdb_id': 1, 'season': 4, 'episode': 9, 'watched_at': NOW - timedelta(days=50)}])
    result, _, sender = run_job(db, ENV, [play('1', 1, 2, 1)],
                                {1: {'tvdb_id': None, 'seasons': {1: 10, 4: 10, 5: 10}}})
    sender.assert_not_called()


def test_watermark_is_not_moved_when_progress_fails(db):
    with patch.object(type(db), 'record_season_progress', side_effect=RuntimeError('disk')), \
         patch.object(type(db), 'set_scan_watermark') as set_watermark, pytest.raises(RuntimeError):
        run_job(db, ENV, [play('1', 1, 9, 1)], {})
    set_watermark.assert_not_called()


def test_unconfigured_server_is_reported():
    with patch.object(sf.ConfigService, 'get_runtime_config', return_value={**ENV, 'JELLYFIN_TOKEN': ''}):
        assert asyncio.run(sf.execute_season_followup(now=NOW))['status'] == 'not_configured'


# --- delivery -------------------------------------------------------------------------------

def test_seer_posts_only_the_seasons_and_accepts_success_and_duplicate():
    seer = SeerClient('http://seer.local', 'k')

    async def answer(status, response):
        async def post(data):
            seer._last_status = status
            post.payload = data
            return response
        async def make_request(method, endpoint, data=None, **kw):
            assert kw.get('retries') == 1  # one attempt per run
            return await post(data)
        with patch.object(seer, '_make_request', side_effect=make_request), \
             patch.object(seer, '_fetch_server_defaults', AsyncMock()) as defaults:
            result = await seer.request_seasons(5, 77, [3])
        defaults.assert_not_called()  # Seer picks its own server, profile and root folder
        return result, post.payload

    assert asyncio.run(answer(201, {'id': 1})) == (True, {'mediaType': 'tv', 'mediaId': 5, 'seasons': [3], 'tvdbId': 77})
    assert asyncio.run(answer(409, None))[0] is True
    assert asyncio.run(answer(500, None))[0] is False


def test_seer_outage_is_an_error_not_a_skip():
    from api_service.exceptions.api_exceptions import BackendUnavailableError
    seer = SeerClient('http://seer.local', 'k')

    async def post(data):
        seer._transport_failed = True
        return None
    async def make_request(*a, **kw):
        return await post(None)
    with patch.object(seer, '_make_request', side_effect=make_request), pytest.raises(BackendUnavailableError):
        asyncio.run(seer.request_seasons(5, None, [3]))


def test_follow_up_shares_the_automation_lock(db):
    from api_service.jobs.request_expiry import _run_lock
    with _run_lock, patch.object(sf.ConfigService, 'get_runtime_config', return_value=ENV):
        assert asyncio.run(sf.execute_season_followup(now=NOW)) == {'status': 'already_running'}


def sonarr(library, lookup=None, add_status=201):
    client = ArrClient('sonarr', 'http://sonarr.local', 'k')
    calls = []

    async def request(method, path, **kwargs):
        calls.append((method, path, kwargs.get('json')))
        if method == 'GET' and path == 'series':
            return 200, library
        if method == 'GET' and path == 'series/lookup':
            return 200, lookup or []
        if method == 'GET' and path in ('tag', 'qualityprofile', 'rootfolder'):
            return 200, {'tag': [], 'qualityprofile': [{'id': 1}], 'rootfolder': [{'path': '/tv'}]}[path]
        if method == 'POST' and path == 'tag':
            return 201, {'id': 9, 'label': kwargs['json']['label']}
        if method == 'POST' and path == 'series':
            library.append({**kwargs['json'], 'id': 50})
            return add_status, {}
        return 201, {}
    client._request = request
    return client, calls


PROFILE = {'profileId': 1, 'rootFolder': '/tv'}


def test_sonarr_existing_series_monitors_and_searches_the_season():
    series = {'id': 3, 'tmdbId': 5, 'monitored': True, 'seasons': [{'seasonNumber': 1, 'monitored': True},
                                                                    {'seasonNumber': 2, 'monitored': False}]}
    client, calls = sonarr([series])
    assert asyncio.run(client.request_season(5, 2, PROFILE)) is True
    put = next(c for c in calls if c[0] == 'PUT')
    assert put[1] == 'series/3' and put[2]['seasons'][1]['monitored'] is True
    assert calls[-1] == ('POST', 'command', {'name': 'SeasonSearch', 'seriesId': 3, 'seasonNumber': 2})


def test_sonarr_without_the_season_yet_refreshes_and_retries_later():
    client, calls = sonarr([{'id': 3, 'tmdbId': 5, 'monitored': True, 'seasons': [{'seasonNumber': 1}]}])
    assert asyncio.run(client.request_season(5, 2, PROFILE)) is False
    assert ('POST', 'command', {'name': 'RefreshSeries', 'seriesId': 3}) in calls
    assert not any(c[0] == 'PUT' for c in calls)


def test_sonarr_missing_series_is_added_with_only_that_season():
    lookup = [{'tmdbId': 5, 'title': 'Show', 'seasons': [{'seasonNumber': 1}, {'seasonNumber': 2}]}]
    client, calls = sonarr([], lookup)
    assert asyncio.run(client.request_season(5, 2, PROFILE)) is True
    added = next(c[2] for c in calls if c[:2] == ('POST', 'series'))
    assert [s['monitored'] for s in added['seasons']] == [False, True]
    assert (added['qualityProfileId'], added['rootFolderPath']) == (1, '/tv')
    assert not any(c[2] and c[2].get('name') == 'SeasonSearch' for c in calls)  # add already searches


def test_sonarr_missing_series_whose_lookup_lacks_the_season_is_not_added():
    client, calls = sonarr([], [{'tmdbId': 5, 'seasons': [{'seasonNumber': 1}]}])
    assert asyncio.run(client.request_season(5, 2, PROFILE)) is False
    assert not any(c[:2] == ('POST', 'series') for c in calls)


def test_sonarr_add_race_falls_through_to_monitoring():
    lookup = [{'tmdbId': 5, 'seasons': [{'seasonNumber': 1}, {'seasonNumber': 2}]}]
    library = []
    client, calls = sonarr(library, lookup, add_status=409)

    async def run():
        result = await client.request_season(5, 2, PROFILE)
        return result
    # The conflict means someone else added it, with season 2 unmonitored.
    original = client._request

    async def request(method, path, **kwargs):
        if method == 'POST' and path == 'series':
            library.append({'id': 60, 'tmdbId': 5, 'monitored': True,
                            'seasons': [{'seasonNumber': 1, 'monitored': True}, {'seasonNumber': 2, 'monitored': False}]})
            calls.append((method, path, kwargs.get('json')))
            return 409, {}
        return await original(method, path, **kwargs)
    client._request = request
    assert asyncio.run(run()) is True
    assert calls[-1] == ('POST', 'command', {'name': 'SeasonSearch', 'seriesId': 60, 'seasonNumber': 2})


def test_deliver_uses_the_default_sonarr_profile_or_skips():
    env = {**ENV, 'REQUEST_BACKEND': 'arr', 'SONARR_API_URL': 'http://sonarr.local', 'SONARR_TOKEN': 'k'}
    assert asyncio.run(sf._deliver(env, 'arr', 5, None, 2, {})) is False  # no default profile
    profile = {'profileId': 1, 'rootFolder': '/tv'}
    with patch.object(ArrClient, 'request_season', AsyncMock(return_value=True)) as request_season:
        clients = {}
        assert asyncio.run(sf._deliver({**env, 'ARR_PROFILE_CONFIG': {'default_tv': profile}},
                                       'arr', 5, None, 2, clients)) is True
    assert request_season.await_args.args == (5, 2, profile)


@pytest.mark.parametrize('settings', [{'SEASON_FOLLOWUP_ENABLED': 'yes'}, {'SEASON_FOLLOWUP_EPISODES_BEFORE_END': -1},
                                      {'SEASON_FOLLOWUP_WINDOW_DAYS': 0}, {'SEASON_FOLLOWUP_WINDOW_DAYS': 4000}])
def test_invalid_settings_are_rejected(settings):
    from api_service.config.config import validate_season_followup_settings
    with pytest.raises(ValueError):
        validate_season_followup_settings(settings)
    validate_season_followup_settings({})  # defaults are valid


def test_request_lookup_uses_server_placeholders_on_mariadb():
    from api_service.db.components.request_mixin import RequestMixin
    from unittest.mock import MagicMock
    mixin = RequestMixin.__new__(RequestMixin)
    mixin.db_type, mixin.logger = 'mariadb', MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = (1,)
    conn = MagicMock()
    conn.__enter__.return_value.cursor.return_value = cursor
    mixin.get_connection = MagicMock(return_value=conn)
    assert mixin.check_request_exists('tv', '5') is True
    assert '?' not in cursor.execute.call_args.args[0]


class _FakeResponse:
    def __init__(self, status, body):
        self.status, self._body = status, body

    async def json(self, **kwargs):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    def __init__(self, status, body):
        self.answer, self.calls = (status, body), []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs.get('json')))
        return _FakeResponse(*self.answer)


@pytest.mark.parametrize('status, body, expected', [
    (409, {'message': 'Request for this media already exists.'}, True),
    (400, {'message': 'Request for this media already exists.'}, True),
    (500, {'message': 'Internal error'}, False),
])
def test_seer_duplicate_answer_through_the_real_http_path(status, body, expected):
    seer = SeerClient('http://seer.local', 'k')
    session = _FakeSession(status, body)
    with patch.object(seer, '_get_session', AsyncMock(return_value=session)), \
         patch('api_service.services.seer.seer_client.asyncio.sleep', AsyncMock()):
        assert asyncio.run(seer.request_seasons(5, None, [2])) is expected
    assert len(session.calls) == 1  # a single POST: the next run retries
    assert session.calls[0][:2] == ('POST', 'http://seer.local/api/v1/request')
    assert 'profileId' not in session.calls[0][2]


def test_sonarr_add_race_searches_even_an_already_monitored_season():
    lookup = [{'tmdbId': 5, 'seasons': [{'seasonNumber': 1}, {'seasonNumber': 2}]}]
    library = []
    client, calls = sonarr(library, lookup)
    original = client._request

    async def request(method, path, **kwargs):
        if method == 'POST' and path == 'series':
            library.append({'id': 61, 'tmdbId': 5, 'monitored': True,
                            'seasons': [{'seasonNumber': 1, 'monitored': True}, {'seasonNumber': 2, 'monitored': True}]})
            calls.append((method, path, kwargs.get('json')))
            return 409, {}
        return await original(method, path, **kwargs)
    client._request = request
    assert asyncio.run(client.request_season(5, 2, PROFILE)) is True
    assert calls[-1] == ('POST', 'command', {'name': 'SeasonSearch', 'seriesId': 61, 'seasonNumber': 2})
    assert not any(c[0] == 'PUT' for c in calls)


def test_sonarr_fresh_add_whose_own_lookup_drops_the_season_is_completed():
    lookups = [[{'tmdbId': 5, 'seasons': [{'seasonNumber': 1}, {'seasonNumber': 2}]}],
               [{'tmdbId': 5, 'seasons': [{'seasonNumber': 1}]}]]  # add()'s own lookup lacks season 2
    library = []
    client, calls = sonarr(library)
    original = client._request

    async def request(method, path, **kwargs):
        if method == 'GET' and path == 'series/lookup':
            calls.append((method, path, None))
            return 200, lookups.pop(0)
        return await original(method, path, **kwargs)
    client._request = request
    assert asyncio.run(client.request_season(5, 2, PROFILE)) is False  # Sonarr has no season 2 yet
    assert ('POST', 'command', {'name': 'RefreshSeries', 'seriesId': 50}) in calls


def test_a_404_batch_is_retried_item_by_item():
    entries = [play(None, 1, 1, 3, series_id='gone'), play(None, 1, 2, 2, series_id='ok')]

    async def answer(url, headers, params=None):
        if ',' in url or 'gone' in url:
            from api_service.services.arr.arr_client import ArrHTTPError
            raise ArrHTTPError('not found', 404)
        return {'MediaContainer': {'Metadata': [{'ratingKey': 'ok', 'Guid': [{'id': 'tmdb://42'}]}]}}

    reader = sf.SeasonPlays()
    reader._json = AsyncMock(side_effect=answer)
    asyncio.run(reader._resolve(True, 'http://plex', {}, entries))
    assert [(e['tmdb'], e['unresolved']) for e in entries] == [(None, False), ('42', False)]


def test_seer_follow_up_honours_the_request_delay():
    from api_service.jobs import queue_worker
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)
    clients = {'seer': AsyncMock()}
    clients['seer'].request_seasons = AsyncMock(return_value=True)
    with patch.object(sf.asyncio, 'sleep', fake_sleep), patch.object(queue_worker, '_last_seer_send', None):
        env = {**ENV, 'SEER_REQUEST_DELAY': 5}
        asyncio.run(sf._deliver(env, 'seer', 1, None, 2, clients))
        asyncio.run(sf._deliver(env, 'seer', 2, None, 2, clients))
    assert len(sleeps) == 1 and 4 < sleeps[0] <= 5
