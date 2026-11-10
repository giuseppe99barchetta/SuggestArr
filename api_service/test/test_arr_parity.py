"""Seer-only features carried over to direct Radarr/Sonarr delivery (REQUEST_BACKEND=arr).

Every ArrClient call here goes through a fake ``_request``: no test ever reaches a real
Radarr/Sonarr (the operator's config holds real credentials).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api_service.services.arr.arr_client import ArrClient, arr_tag_label
from api_service.services.arr.arr_request_client import ArrRequestClient

RADARR = {'RADARR_API_URL': 'http://radarr:7878', 'RADARR_TOKEN': 'k'}
SONARR = {'SONARR_API_URL': 'http://sonarr:8989', 'SONARR_TOKEN': 'k'}
PROFILES = {'default_movie': {'profileId': 4, 'rootFolder': '/movies', 'tags': [1]},
            'default_tv': {'profileId': 6, 'rootFolder': '/tv'}}
ARR_ENV = {**RADARR, **SONARR, 'ARR_PROFILE_CONFIG': PROFILES, 'REQUEST_BACKEND': 'arr'}


@pytest.fixture(autouse=True)
def no_real_arr(monkeypatch):
    """Fail loudly if a test forgot to fake the Radarr/Sonarr API."""
    async def refuse(self, method, path, **kwargs):
        raise AssertionError(f'unexpected real {method} {path} to {self.api_url}')
    monkeypatch.setattr(ArrClient, '_request', refuse)


class FakeArr:
    """Answers ArrClient._request from a ``{(method, path): (status, data)}`` table and records calls."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    async def __call__(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        answer = self.routes[(method, path)]
        return answer(kwargs) if callable(answer) else answer

    def paths(self, method):
        return [path for m, path, _ in self.calls if m == method]


def _client(service, routes):
    client = ArrClient(service, 'http://arr.test/', 'k')
    client._request = FakeArr(routes)
    return client


LOOKUP = [{'title': 'Inception', 'tmdbId': 27205}]
PAYLOAD = {'mediaType': 'movie', 'mediaId': 27205, 'profileId': 4, 'rootFolder': '/movies', 'tags': [1, 9]}


def _posted_tags(client):
    return next(kwargs['json']['tags'] for m, path, kwargs in client._request.calls if (m, path) == ('POST', 'movie'))


# --- 1. suggestarr tag ---------------------------------------------------------

def test_an_existing_suggestarr_tag_is_reused_and_merged_without_duplicates():
    client = _client('radarr', {('GET', 'tag'): (200, [{'id': 9, 'label': 'SuggestArr'}]),
                                ('GET', 'movie/lookup'): (200, LOOKUP), ('POST', 'movie'): (201, {})})
    assert asyncio.run(client.add(PAYLOAD)) is True
    assert client._request.paths('POST') == ['movie']  # no tag created
    assert _posted_tags(client) == [1, 9]


def test_a_missing_tag_is_created_once_per_client():
    client = _client('radarr', {('GET', 'tag'): (200, []), ('POST', 'tag'): lambda kw: (201, {'id': 12, **kw['json']}),
                                ('GET', 'movie/lookup'): (200, LOOKUP), ('POST', 'movie'): (201, {})})
    asyncio.run(client.add(PAYLOAD, ['suggestarr-user-mario']))
    asyncio.run(client.add(PAYLOAD, ['suggestarr-user-mario']))
    labels = [kw['json']['label'] for m, path, kw in client._request.calls if (m, path) == ('POST', 'tag')]
    assert labels == ['suggestarr', 'suggestarr-user-mario']  # created once, then cached
    assert client._request.paths('GET').count('tag') == 1
    assert _posted_tags(client) == [1, 9, 12]


def test_a_tag_that_cannot_be_created_fails_the_delivery():
    client = _client('radarr', {('GET', 'tag'): (200, []), ('POST', 'tag'): (500, None)})
    with pytest.raises(RuntimeError, match='tag'):
        asyncio.run(client.add(PAYLOAD))
    assert 'movie' not in client._request.paths('POST')


@pytest.mark.parametrize('text,label', [('Mario Rossi!', 'mario-rossi'), ('ÉLodie_99', 'lodie-99'),
                                        ('__', ''), (None, ''), ('a--b', 'a-b')])
def test_tag_labels_only_keep_lowercase_letters_digits_and_dashes(text, label):
    assert arr_tag_label(text) == label


@pytest.mark.parametrize('enabled,name,expected', [
    (True, 'Mario Rossi', ['suggestarr-user-mario-rossi']),
    (True, None, []),       # name unknown: only the suggestarr tag
    (True, '!!', []),       # nothing usable after normalization
    (False, 'Mario Rossi', []),
])
def test_the_per_user_tag_follows_the_setting_and_the_known_name(enabled, name, expected):
    client = ArrRequestClient({**ARR_ENV, 'ARR_TAG_BY_USER': enabled})
    fake = MagicMock()
    fake.add = AsyncMock(return_value=True)
    with patch('api_service.services.arr.arr_request_client.DatabaseManager') as db, \
            patch('api_service.services.arr.arr_request_client.ArrClient', return_value=fake):
        db.return_value.get_media_user_name.return_value = name
        assert asyncio.run(client.submit_queued_request({'mediaType': 'movie', 'mediaId': 1, '_user_id': 'u1'})) is True
    assert fake.add.await_args.args[1] == expected


def test_the_request_client_reuses_one_arr_client_per_instance_and_closes_it():
    client = ArrRequestClient(ARR_ENV)
    fake = MagicMock()
    fake.add = AsyncMock(return_value=True)
    fake.close = AsyncMock()
    with patch('api_service.services.arr.arr_request_client.ArrClient', return_value=fake) as factory:
        async def deliver_twice():
            async with client:
                await client.submit_queued_request({'mediaType': 'movie', 'mediaId': 1})
                await client.submit_queued_request({'mediaType': 'movie', 'mediaId': 2})
        asyncio.run(deliver_twice())
    factory.assert_called_once_with('radarr', 'http://radarr:7878', 'k')
    fake.close.assert_awaited_once()


# --- 2. availability ---------------------------------------------------------

from api_service.jobs import availability_sync  # noqa: E402


def test_radarr_statuses_follow_the_downloaded_file():
    client = _client('radarr', {('GET', 'movie'): (200, [
        {'tmdbId': 1, 'hasFile': True}, {'tmdbId': 2, 'hasFile': False}, {'title': 'no tmdb id', 'hasFile': True}])})
    assert asyncio.run(client.get_media_statuses()) == {
        ('movie', '1'): {'status': 'available', 'url': None}, ('movie', '2'): {'status': 'processing', 'url': None}}


def test_sonarr_statuses_compare_downloaded_and_monitored_episodes():
    series = [{'tmdbId': 1, 'statistics': {'episodeFileCount': 20, 'episodeCount': 20}},
              {'tmdbId': 2, 'statistics': {'episodeFileCount': 3, 'episodeCount': 20}},
              {'tmdbId': 3, 'statistics': {'episodeFileCount': 0, 'episodeCount': 20}},
              {'tmdbId': 4}]  # statistics missing: nothing downloaded yet
    statuses = asyncio.run(_client('sonarr', {('GET', 'series'): (200, series)}).get_media_statuses())
    assert {key[1]: value['status'] for key, value in statuses.items()} == {
        '1': 'available', '2': 'partial', '3': 'processing', '4': 'processing'}
    assert all(key[0] == 'tv' for key in statuses)


def _sync(env, db, clients):
    """Run sync_availability with fake Radarr/Sonarr clients keyed by service."""
    def build(service, url, token):
        fake = MagicMock()
        fake.__aenter__ = AsyncMock(return_value=fake)
        fake.__aexit__ = AsyncMock(return_value=False)
        answer = clients[service]
        fake.get_media_statuses = AsyncMock(side_effect=answer) if isinstance(answer, Exception) \
            else AsyncMock(return_value=answer)
        return fake
    with patch.object(availability_sync.ConfigService, 'get_runtime_config', return_value=env), \
            patch.object(availability_sync, 'DatabaseManager', return_value=db), \
            patch.object(availability_sync, 'ArrClient', side_effect=build), \
            patch.object(availability_sync, 'SeerClient', side_effect=AssertionError('Seer must not be contacted')):
        return asyncio.run(availability_sync.sync_availability())


def _db(requested, known):
    return MagicMock(get_requested_media_keys=MagicMock(return_value=set(requested)),
                     get_media_availability=MagicMock(return_value=dict(known)),
                     get_title_owner_ids=MagicMock(return_value=[]))


def test_direct_sync_stores_changes_and_announces_titles_that_became_available():
    known = {('movie', '1'): {'status': 'processing', 'url': None}, ('tv', '5'): {'status': 'processing', 'url': None}}
    db = _db(known, known)
    result = _sync(ARR_ENV, db, {'radarr': {('movie', '1'): {'status': 'available', 'url': None}},
                                 'sonarr': {('tv', '5'): {'status': 'partial', 'url': None}}})
    assert result == {'status': 'ok', 'changed': 2, 'available': 1}
    db.save_media_availability.assert_called_once_with({('movie', '1'): {'status': 'available', 'url': None},
                                                        ('tv', '5'): {'status': 'partial', 'url': None}})
    db.enqueue_webhook_event.assert_called_once_with('request.available', {'tmdb_id': '1', 'media_type': 'movie'})


def test_one_unreadable_instance_updates_nothing():
    db = _db({('movie', '1'), ('tv', '5')}, {('movie', '1'): {'status': 'processing', 'url': None}})
    result = _sync(ARR_ENV, db, {'radarr': {('movie', '1'): {'status': 'available', 'url': None}},
                                 'sonarr': RuntimeError('down')})
    assert result['status'] == 'unavailable'
    db.save_media_availability.assert_not_called()
    db.enqueue_webhook_event.assert_not_called()


def test_a_type_without_an_instance_keeps_its_stored_states():
    known = {('movie', '1'): {'status': 'processing', 'url': None}, ('tv', '5'): {'status': 'available', 'url': 'http://jf/5'}}
    db = _db(known, known)
    env = {**RADARR, 'ARR_PROFILE_CONFIG': PROFILES, 'REQUEST_BACKEND': 'arr'}  # no Sonarr
    _sync(env, db, {'radarr': {('movie', '1'): {'status': 'available', 'url': None}}})
    db.save_media_availability.assert_called_once_with({('movie', '1'): {'status': 'available', 'url': None}})


def test_direct_sync_without_any_instance_is_not_configured():
    assert _sync({'REQUEST_BACKEND': 'arr'}, _db([], {}), {})['status'] == 'not_configured'


# --- 3. replace rejected -------------------------------------------------------

import json  # noqa: E402

from api_service.jobs import request_replacement  # noqa: E402
from api_service.test.test_request_replacement import MemoryDB, make_manager  # noqa: E402
from api_service.db.components.schema_manager import SchemaManager  # noqa: E402


@pytest.fixture
def memdb():
    database = MemoryDB()
    SchemaManager(database).initialize_db()
    yield database
    database.connection.close()


def _awaiting(db, row_id, backend='arr', job_id=1):
    db.connection.execute(
        'INSERT INTO pending_requests(id,tmdb_id,media_type,payload,status,job_id,owner_id,user_id) '
        "VALUES(?,?,'movie',?,'awaiting_approval',?,7,'u1')",
        (row_id, str(row_id + 100), json.dumps({'_backend': backend} if backend else {}), job_id))
    db.connection.commit()


def _replacements(db):
    return dict(db.connection.execute('SELECT delivery_id,status FROM request_replacements').fetchall())


@pytest.mark.parametrize('blacklist', [False, True])
def test_rejecting_a_direct_suggestion_opens_one_pending_replacement(memdb, blacklist):
    _awaiting(memdb, 1)
    _awaiting(memdb, 2, backend='seer')   # Seer rows are replaced from Seer's own decision
    _awaiting(memdb, 3, backend=None)     # rows queued before _backend existed are Seer's
    _awaiting(memdb, 4, job_id=None)      # not from a job: nothing to generate an alternative with
    assert memdb.decide_suggestions([1, 2, 3, 4], None, 9, False, blacklist, replace_rejected=True) == 4
    assert _replacements(memdb) == {1: 'pending'}
    assert memdb.get_pending_request_replacements(None)[0]['delivery_id'] == 1
    assert memdb.get_pending_request_replacements('http://seer.local') == []


def test_no_replacement_without_the_setting_or_on_approval(memdb):
    _awaiting(memdb, 1)
    memdb.decide_suggestions([1], None, 9, False, replace_rejected=False)
    _awaiting(memdb, 2)
    memdb.decide_suggestions([2], None, 9, True, replace_rejected=True)
    assert _replacements(memdb) == {}


def test_requesting_a_rejected_title_again_cancels_its_pending_alternative(memdb):
    _awaiting(memdb, 1)
    memdb.decide_suggestions([1], None, 9, False, replace_rejected=True)
    assert memdb.request_rejected([1], None) == 1
    assert _replacements(memdb) == {1: 'ignored'}
    assert memdb.get_pending_request_replacements(None) == []


def _run_replacements(db, manager, env):
    with patch.object(request_replacement, 'DatabaseManager', return_value=db), \
            patch.object(request_replacement.ConfigService, 'get_runtime_config', return_value=env), \
            patch.object(request_replacement, 'SeerClient', side_effect=AssertionError('Seer must not be contacted')), \
            patch.object(request_replacement.JobManager, 'get_instance', return_value=manager):
        return asyncio.run(request_replacement.execute_request_replacements())


def test_direct_mode_generates_the_alternative_without_seer(memdb):
    _awaiting(memdb, 1)
    memdb.decide_suggestions([1], None, 9, False, replace_rejected=True)
    manager, _, executor = make_manager(memdb)
    result = _run_replacements(memdb, manager, {**ARR_ENV, 'REPLACE_REJECTED_REQUESTS': True})
    assert result['status'] == 'ok' and result['queued'] == 1
    executor.assert_awaited_once()
    assert executor.await_args.kwargs['overrides']['_replacement_for'] == 1
    assert _replacements(memdb)[1] == 'queued'
    # one alternative per rejection: a second run generates nothing
    _run_replacements(memdb, manager, {**ARR_ENV, 'REPLACE_REJECTED_REQUESTS': True})
    executor.assert_awaited_once()


def test_direct_replacements_wait_while_seer_is_the_backend(memdb):
    _awaiting(memdb, 1)
    memdb.decide_suggestions([1], None, 9, False, replace_rejected=True)
    manager, _, executor = make_manager(memdb)
    seer = MagicMock(request_expiry_action=AsyncMock())
    seer.__aenter__ = AsyncMock(return_value=seer)
    seer.__aexit__ = AsyncMock(return_value=False)
    with patch.object(request_replacement, 'DatabaseManager', return_value=memdb), \
            patch.object(request_replacement.ConfigService, 'get_runtime_config', return_value={
                'REPLACE_REJECTED_REQUESTS': True, 'SEER_API_URL': 'http://seer.local/', 'SEER_TOKEN': 'k'}), \
            patch.object(request_replacement, 'SeerClient', return_value=seer), \
            patch.object(request_replacement.JobManager, 'get_instance', return_value=manager):
        asyncio.run(request_replacement.execute_request_replacements())
    executor.assert_not_awaited()
    assert _replacements(memdb) == {1: 'pending'}


# --- 4. cleanup only of titles tagged suggestarr ---------------------------

from api_service.jobs import cleanup_automation  # noqa: E402

LIBRARY = [{'id': 11, 'tmdbId': 1, 'tags': [9]},        # added by SuggestArr
           {'id': 12, 'tmdbId': 2, 'tags': [3]},        # added by hand
           {'id': 13, 'tmdbId': 3}]                     # no tags at all


def _library_client(service='radarr', tags=((9, 'suggestarr'),), delete_status=200):
    endpoint = 'movie' if service == 'radarr' else 'series'
    routes = {('GET', endpoint): (200, LIBRARY), ('GET', 'tag'): (200, [{'id': i, 'label': l} for i, l in tags])}
    routes.update({('DELETE', f'{endpoint}/{item["id"]}'): (delete_status, None) for item in LIBRARY})
    return _client(service, routes)


def test_only_a_tagged_title_is_deleted_with_its_files():
    client = _library_client()
    assert asyncio.run(client.delete(1)) == 'deleted'
    assert [(p, kw['params']) for m, p, kw in client._request.calls if m == 'DELETE'] == [('movie/11', {'deleteFiles': 'true'})]
    assert asyncio.run(client.delete(1)) == 'not_found'  # gone from the cached library
    assert client._request.paths('GET').count('movie') == 1


@pytest.mark.parametrize('tmdb_id', [2, 3])
def test_a_title_without_the_suggestarr_tag_is_never_deleted(tmdb_id):
    client = _library_client('sonarr')
    assert asyncio.run(client.delete(tmdb_id)) == 'not_tagged'
    assert client._request.paths('DELETE') == []


def test_without_a_suggestarr_tag_on_the_instance_nothing_is_deleted():
    client = _library_client(tags=((3, 'other'),))
    assert [asyncio.run(client.delete(i)) for i in (1, 2, 3, 99)] == ['not_tagged'] * 3 + ['not_found']
    assert client._request.paths('DELETE') == []
    assert client._request.paths('POST') == []  # the tag is never created by cleanup
    assert client._request.paths('GET').count('tag') == 1


def test_a_refused_deletion_raises():
    with pytest.raises(RuntimeError):
        asyncio.run(_library_client(delete_status=500).delete(1))


class CleanupDB:
    def __init__(self, candidates, dry_run):
        self.settings = {'enabled': True, 'dry_run': dry_run, 'grace_days': 7}
        self.candidates = candidates
        self.logs, self.deleted_rows, self.updates = [], [], []

    def get_cleanup_settings(self):
        return self.settings

    def get_suggestarr_requests_older_than(self, cutoff):
        return self.candidates

    def update_cleanup_settings(self, **kwargs):
        self.updates.append(kwargs)

    def add_cleanup_log(self, **kwargs):
        self.logs.append(kwargs)

    def delete_request_row(self, tmdb_id, media_type):
        self.deleted_rows.append((tmdb_id, media_type))


def _cleanup(dry_run, env=None, favorites=None):
    candidates = [{'tmdb_id': str(i), 'media_type': 'movie', 'title': f'm{i}'} for i in (1, 2, 4)] + \
                 [{'tmdb_id': '1', 'media_type': 'tv', 'title': 'no sonarr'}]
    db = CleanupDB(candidates, dry_run)
    favorites = favorites or {('movie', '1'): 0.0, ('movie', '2'): 0.0, ('movie', '4'): 10.0, ('tv', '1'): 0.0}
    radarr = _library_client()
    env = env or {**RADARR, 'ARR_PROFILE_CONFIG': PROFILES, 'REQUEST_BACKEND': 'arr',
                  'SELECTED_SERVICE': 'jellyfin', 'JELLYFIN_API_URL': 'http://jf', 'JELLYFIN_TOKEN': 't'}
    with patch.object(cleanup_automation, 'DatabaseManager', return_value=db), \
            patch.object(cleanup_automation.ConfigService, 'get_runtime_config', return_value=env), \
            patch.object(cleanup_automation, '_build_favorite_map', AsyncMock(return_value=favorites)), \
            patch.object(cleanup_automation, 'ArrClient', return_value=radarr), \
            patch.object(cleanup_automation, 'SeerClient', side_effect=AssertionError('Seer must not be contacted')):
        result = asyncio.run(cleanup_automation.execute_cleanup_job())
    return result, db, radarr


def test_direct_cleanup_deletes_only_tagged_unfavorited_titles():
    result, db, radarr = _cleanup(dry_run=False)
    actions = {(log['media_type'], log['tmdb_id']): log['action'] for log in db.logs}
    assert actions == {('movie', '1'): 'deleted', ('movie', '2'): 'skipped_not_tagged',
                       ('movie', '4'): 'kept_favorited', ('tv', '1'): 'skipped_not_in_arr'}
    assert radarr._request.paths('DELETE') == ['movie/11']
    assert db.deleted_rows == [('1', 'movie')]
    assert result['status'] == 'ok' and 'not_tagged=1' in result['summary']


def test_direct_dry_run_reports_what_a_real_run_would_delete_without_deleting():
    result, db, radarr = _cleanup(dry_run=True)
    actions = {(log['media_type'], log['tmdb_id']): log['action'] for log in db.logs}
    assert actions[('movie', '1')] == 'would_delete' and actions[('movie', '2')] == 'skipped_not_tagged'
    assert radarr._request.paths('DELETE') == [] and db.deleted_rows == []
    assert all(log['was_dry_run'] for log in db.logs)


def test_direct_cleanup_without_an_instance_is_not_configured():
    env = {'REQUEST_BACKEND': 'arr', 'SELECTED_SERVICE': 'jellyfin', 'JELLYFIN_API_URL': 'http://jf', 'JELLYFIN_TOKEN': 't'}
    result, db, radarr = _cleanup(dry_run=False, env=env)
    assert result['status'] == 'not_configured' and radarr._request.calls == []
