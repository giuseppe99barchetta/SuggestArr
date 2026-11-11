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


# What the instance offers; add() refuses anything else.
OFFERED = {('GET', 'qualityprofile'): (200, [{'id': 4}]), ('GET', 'rootfolder'): (200, [{'path': '/movies'}])}


def _client(service, routes):
    routes = {**OFFERED, **routes}
    client = ArrClient(service, 'http://arr.test/', 'k')
    client._request = FakeArr(routes)
    return client


LOOKUP = [{'title': 'Inception', 'tmdbId': 27205}]
PAYLOAD = {'mediaType': 'movie', 'mediaId': 27205, 'profileId': 4, 'rootFolder': '/movies', 'tags': [9]}


def _posted_tags(client):
    return next(kwargs['json']['tags'] for m, path, kwargs in client._request.calls if (m, path) == ('POST', 'movie'))


# --- 1. suggestarr tag ---------------------------------------------------------

def test_an_existing_suggestarr_tag_is_reused_and_merged_without_duplicates():
    client = _client('radarr', {('GET', 'tag'): (200, [{'id': 9, 'label': 'SuggestArr'}]),
                                ('GET', 'movie/lookup'): (200, LOOKUP), ('POST', 'movie'): (201, {})})
    assert asyncio.run(client.add(PAYLOAD)) is True
    assert client._request.paths('POST') == ['movie']  # no tag created
    assert _posted_tags(client) == [9]


def test_a_missing_tag_is_created_once_per_client():
    client = _client('radarr', {('GET', 'tag'): (200, [{'id': 9, 'label': 'kids'}]),
                                ('POST', 'tag'): lambda kw: (201, {'id': 12, **kw['json']}),
                                ('GET', 'movie/lookup'): (200, LOOKUP), ('POST', 'movie'): (201, {})})
    asyncio.run(client.add(PAYLOAD, ['suggestarr-user-mario']))
    asyncio.run(client.add(PAYLOAD, ['suggestarr-user-mario']))
    labels = [kw['json']['label'] for m, path, kw in client._request.calls if (m, path) == ('POST', 'tag')]
    assert labels == ['suggestarr', 'suggestarr-user-mario']  # created once, then cached
    assert client._request.paths('GET').count('tag') == 1
    assert _posted_tags(client) == [9, 12]


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


@pytest.mark.parametrize('change', [{'profileId': 99}, {'rootFolder': '/etc'}, {'tags': [9, 77]}])
def test_a_profile_the_instance_does_not_offer_is_never_sent(change):
    client = _client('radarr', {('GET', 'tag'): (200, [{'id': 9, 'label': 'suggestarr'}]),
                                ('GET', 'movie/lookup'): (200, LOOKUP), ('POST', 'movie'): (201, {})})
    with pytest.raises(RuntimeError, match='choose them again'):
        asyncio.run(client.add({**PAYLOAD, **change}))
    assert 'movie' not in client._request.paths('POST')


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


# --- 5. per-job profiles in both shapes ----------------------------------------

from api_service.services.seer.seer_client import SeerClient  # noqa: E402
from api_service.utils import request_profiles  # noqa: E402

SEER_PROFILE = {'serverId': 0, 'profileId': 99, 'rootFolder': '/seer', 'is4k': False}
ARR_PROFILE = {'profileId': 7, 'rootFolder': '/movies-4k', 'tags': [5]}


@pytest.mark.parametrize('profiles', [
    {'movie': SEER_PROFILE, 'tv': {'serverId': 1, 'profileId': 2, 'rootFolder': '/tv', 'languageProfileId': 1}},
    {'movie': ARR_PROFILE, 'tv': {'profileId': 2, 'rootFolder': '/tv'}},
    {'movie': SEER_PROFILE, 'tv': {'profileId': 2, 'rootFolder': '/tv', 'tags': []}},
    {'movie': {}, 'tv': {}},
])
def test_both_profile_shapes_are_valid(profiles):
    assert request_profiles.validate_request_profiles(profiles) == profiles


@pytest.mark.parametrize('profile', [
    {'profileId': 7},                                      # Arr shape needs a root folder too
    {'rootFolder': '/x', 'tags': [1]},
    {'tags': [1]},                                         # tags without a profile
    {'profileId': 7, 'rootFolder': '/x', 'is4k': True},    # Seer-only keys without a server
    {'profileId': 7, 'rootFolder': '/x', 'languageProfileId': 1},
    {**SEER_PROFILE, 'tags': [1]},                         # tags are not sent to Seer
    {'profileId': 7, 'rootFolder': '/x', 'tags': ['1']},
    {'profileId': 7, 'rootFolder': '/x', 'tags': 1},
    {'serverId': 0, 'profileId': 7},                       # Seer triple still all-or-nothing
])
def test_mixed_or_partial_profiles_are_refused(profile):
    with pytest.raises(ValueError):
        request_profiles.validate_request_profiles({'movie': profile})


def test_seer_ignores_a_radarr_profile_and_direct_delivery_ignores_a_seer_profile():
    assert SeerClient._job_profile_overrides({'request_profiles': {'movie': ARR_PROFILE}}, 'movie') == {}
    assert SeerClient._job_profile_overrides({'request_profiles': {'movie': SEER_PROFILE}}, 'movie') == SEER_PROFILE
    assert ArrRequestClient._job_profile_overrides({'request_profiles': {'movie': SEER_PROFILE}}, 'movie') == {}
    assert ArrRequestClient._job_profile_overrides({'request_profiles': {'movie': ARR_PROFILE}}, 'movie') == ARR_PROFILE
    assert ArrRequestClient._job_profile_overrides({'request_profiles': {'movie': {'profileId': 7}}}, 'movie') == {}


def test_a_job_radarr_profile_replaces_the_default_at_enqueue():
    client = ArrRequestClient(ARR_ENV, queue_context={'job_id': 1, 'request_profiles': {'movie': ARR_PROFILE}})
    with patch('api_service.services.seer.seer_client.DatabaseManager') as manager, \
            patch('api_service.services.seer.seer_client.load_env_vars', return_value=ARR_ENV):
        db = manager.return_value
        db.check_request_exists.return_value = False
        db.enqueue_request.return_value = True
        assert asyncio.run(client.request_media('movie', {'id': 27205, 'title': 'Inception'})) is True
    payload = db.enqueue_request.call_args.args[3]
    assert (payload['profileId'], payload['rootFolder'], payload['tags']) == (7, '/movies-4k', [5])


OPTIONS = {'profiles': [{'id': 7, 'name': 'UHD'}], 'rootFolders': [{'path': '/movies-4k'}], 'tags': [{'id': 5, 'label': 'kids'}]}


def _validate_with_arr(profiles, env=ARR_ENV, options=OPTIONS):
    fake = MagicMock(get_options=AsyncMock(side_effect=options) if isinstance(options, Exception)
                     else AsyncMock(return_value=options))
    fake.__aenter__ = AsyncMock(return_value=fake)
    fake.__aexit__ = AsyncMock(return_value=False)
    with patch('api_service.services.arr.arr_client.ArrClient', return_value=fake) as factory:
        request_profiles.validate_request_profiles_with_arr(profiles, env)
    return factory


def test_radarr_profiles_are_checked_against_the_instance_and_seer_profiles_skipped():
    factory = _validate_with_arr({'movie': ARR_PROFILE, 'tv': SEER_PROFILE})
    factory.assert_called_once_with('radarr', 'http://radarr:7878', 'k')
    assert _validate_with_arr({'movie': SEER_PROFILE, 'tv': {}}).call_count == 0


@pytest.mark.parametrize('profile', [{**ARR_PROFILE, 'profileId': 8}, {**ARR_PROFILE, 'rootFolder': '/other'},
                                     {**ARR_PROFILE, 'tags': [5, 6]}])
def test_an_unknown_radarr_id_is_refused(profile):
    with pytest.raises(request_profiles.UnknownSeerProfileError):
        _validate_with_arr({'movie': profile})


@pytest.mark.parametrize('env,options', [(ARR_ENV, RuntimeError('down')), ({'REQUEST_BACKEND': 'arr'}, OPTIONS)])
def test_a_radarr_profile_that_cannot_be_verified_is_refused(env, options):
    with pytest.raises(ValueError):
        _validate_with_arr({'movie': ARR_PROFILE}, env=env, options=options)


# --- 6. pause while Radarr/Sonarr still downloads ---------------------------------

from api_service.jobs.job_manager import JobManager  # noqa: E402


@pytest.mark.parametrize('total,busy', [(0, False), (3, True)])
def test_the_queue_is_busy_when_it_holds_records(total, busy):
    client = _client('radarr', {('GET', 'queue'): (200, {'page': 1, 'pageSize': 1, 'totalRecords': total, 'records': []})})
    assert asyncio.run(client.queue_busy()) is busy
    assert client._request.calls[0][2]['params'] == {'page': 1, 'pageSize': 1}


@pytest.mark.parametrize('radarr,sonarr,expected', [
    (False, False, False),
    (False, True, True),
    (RuntimeError('down'), False, False),   # unreachable counts as idle
    (RuntimeError('down'), True, True),
])
def test_pending_requests_means_any_instance_still_downloading(radarr, sonarr, expected):
    answers = {'radarr': radarr, 'sonarr': sonarr}

    def build(service, url, token):
        fake = MagicMock(service=service)
        answer = answers[service]
        fake.queue_busy = AsyncMock(side_effect=answer) if isinstance(answer, Exception) else AsyncMock(return_value=answer)
        return fake
    with patch('api_service.services.arr.arr_request_client.ArrClient', side_effect=build):
        assert asyncio.run(ArrRequestClient(ARR_ENV).has_pending_requests()) is expected


def test_without_instances_nothing_is_pending():
    assert asyncio.run(ArrRequestClient({'REQUEST_BACKEND': 'arr'}).has_pending_requests()) is False


@pytest.mark.parametrize('busy', [True, False])
def test_a_job_pauses_while_radarr_still_downloads(busy):
    manager = object.__new__(JobManager)
    manager.logger = MagicMock()
    with patch('api_service.jobs.job_manager.ConfigService.get_runtime_config', return_value=ARR_ENV), \
            patch('api_service.services.arr.arr_client.ArrClient.queue_busy', AsyncMock(return_value=busy)), \
            patch('api_service.jobs.job_manager.SeerClient', side_effect=AssertionError('Seer must not be contacted')):
        assert asyncio.run(manager._should_pause_for_pending_requests({'pause_if_pending_requests': True})) is busy
        assert asyncio.run(manager._should_pause_for_pending_requests({})) is False
        assert JobManager._pending_reason() == 'Radarr/Sonarr still has downloads in the queue'


@pytest.mark.parametrize('approvals,busy,message', [
    (True, True, 'Paused: suggestions are awaiting approval in SuggestArr.'),
    (False, True, 'Paused: Radarr/Sonarr still has downloads in the queue.'),
])
def test_the_skip_message_names_the_check_that_paused_the_job(approvals, busy, message):
    manager = object.__new__(JobManager)
    manager.logger = MagicMock()
    manager.repository = MagicMock()
    manager.repository.get_job.return_value = {'id': 1, 'name': 'Weekly', 'job_type': 'discover'}
    manager._job_executors = {'discover': AsyncMock()}
    with patch('api_service.jobs.job_manager.ConfigService.get_runtime_config', return_value=ARR_ENV), \
            patch.object(JobManager, '_should_pause_for_suggestarr_approvals', return_value=approvals), \
            patch.object(JobManager, '_should_pause_for_pending_requests', AsyncMock(return_value=busy)), \
            patch.object(JobManager, '_queue_webhook') as webhook:
        manager._execute_job(1)
    assert manager.repository.log_execution_end.call_args.kwargs['error_message'] == message
    assert webhook.call_args.args[-1] == 'pending_requests_awaiting_approval'  # reason code unchanged
    manager._job_executors['discover'].assert_not_awaited()


def _status(db, row_id):
    return db.connection.execute('SELECT status FROM pending_requests WHERE id=?', (row_id,)).fetchone()[0]


@pytest.mark.parametrize('alternative_status,cancelled', [
    ('awaiting_approval', True), ('queued', True), ('submitting', False), ('submitted', False)])
def test_requesting_the_original_again_cancels_an_alternative_not_yet_sent(memdb, alternative_status, cancelled):
    _awaiting(memdb, 1)
    memdb.decide_suggestions([1], None, 9, False, replace_rejected=True)
    manager, _, _ = make_manager(memdb)
    _run_replacements(memdb, manager, {**ARR_ENV, 'REPLACE_REJECTED_REQUESTS': True})
    alternative = memdb.connection.execute('SELECT replacement_delivery_id FROM request_replacements').fetchone()[0]
    memdb.connection.execute('UPDATE pending_requests SET status=? WHERE id=?', (alternative_status, alternative))
    memdb.connection.commit()

    assert memdb.request_rejected([1], None) == 1
    assert _status(memdb, 1) == 'queued'
    assert _status(memdb, alternative) == ('rejected' if cancelled else alternative_status)
    assert _replacements(memdb)[1] == ('ignored' if cancelled else 'queued')


@pytest.mark.parametrize('answer', [(200, None), (200, {'error': 'proxy'})])
def test_a_library_answer_that_is_not_a_list_is_an_error_not_an_empty_library(answer):
    with pytest.raises(RuntimeError, match='without a list'):
        asyncio.run(_client('radarr', {('GET', 'movie'): answer}).get_media_statuses())
    with pytest.raises(RuntimeError, match='without a list'):
        asyncio.run(_client('sonarr', {('GET', 'series'): answer}).find_owned(1))


def test_a_malformed_library_answer_makes_the_sync_write_nothing():
    known = {('movie', '1'): {'status': 'available', 'url': None}}
    db = _db(known, known)
    radarr = _client('radarr', {('GET', 'movie'): (200, None)})  # e.g. a proxy's HTML page: JSON decoding gives None
    env = {**RADARR, 'ARR_PROFILE_CONFIG': PROFILES, 'REQUEST_BACKEND': 'arr'}
    with patch.object(availability_sync.ConfigService, 'get_runtime_config', return_value=env), \
            patch.object(availability_sync, 'DatabaseManager', return_value=db), \
            patch.object(availability_sync, 'ArrClient', return_value=radarr):
        assert asyncio.run(availability_sync.sync_availability())['status'] == 'unavailable'
    db.save_media_availability.assert_not_called()


def test_a_row_cancelled_after_the_worker_read_it_is_never_claimed(memdb):
    memdb.connection.execute("INSERT INTO pending_requests(id,tmdb_id,media_type,payload,status) "
                             "VALUES(5,'105','movie','{}','queued')")
    memdb.connection.commit()
    assert memdb.mark_pending_submitting(5, 0) is True
    assert _status(memdb, 5) == 'submitting'
    assert memdb.mark_pending_submitting(5, 0) is False  # a second worker loses the claim
    memdb.connection.execute("UPDATE pending_requests SET status='rejected' WHERE id=5")
    memdb.connection.commit()
    assert memdb.mark_pending_submitting(5, 0) is False  # cancelled meanwhile: stays rejected
    assert _status(memdb, 5) == 'rejected'


def test_the_worker_does_not_deliver_a_row_it_could_not_claim():
    from api_service.jobs import queue_worker
    db = MagicMock()
    db.expire_pending_approvals.return_value = 0
    db.get_due_requests.return_value = [{'id': 5, 'tmdb_id': '105', 'media_type': 'movie', 'retry_count': 0,
                                         'payload': json.dumps({'_backend': 'arr', 'mediaType': 'movie'})}]
    db.check_request_exists.return_value = False
    db.mark_pending_submitting.return_value = False
    client = MagicMock(submit_queued_request=AsyncMock(return_value=True), init=AsyncMock())
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch.object(queue_worker, 'DatabaseManager', return_value=db), \
            patch.object(queue_worker.ConfigService, 'get_runtime_config', return_value=ARR_ENV), \
            patch.object(queue_worker, 'ArrRequestClient', return_value=client):
        assert asyncio.run(queue_worker._run_worker()) == 0
    client.submit_queued_request.assert_not_awaited()
    db.mark_pending_submitted.assert_not_called()


def test_rejecting_again_after_requesting_again_reopens_one_replacement(memdb):
    _awaiting(memdb, 1)
    memdb.decide_suggestions([1], None, 9, False, replace_rejected=True)
    manager, _, executor = make_manager(memdb)
    _run_replacements(memdb, manager, {**ARR_ENV, 'REPLACE_REJECTED_REQUESTS': True})
    alternative = memdb.connection.execute('SELECT replacement_delivery_id FROM request_replacements').fetchone()[0]
    memdb.request_rejected([1], None)                  # alternative cancelled, slot ignored
    memdb.connection.execute("UPDATE pending_requests SET status='awaiting_approval' WHERE id=1")
    memdb.connection.commit()
    memdb.decide_suggestions([1], None, 9, False, replace_rejected=True)
    assert _replacements(memdb)[1] == 'pending'
    assert memdb.connection.execute(
        'SELECT replacement_delivery_id FROM request_replacements WHERE delivery_id=1').fetchone()[0] is None
    assert _status(memdb, alternative) == 'rejected'   # the cancelled alternative stays cancelled


def test_a_slot_whose_alternative_was_delivered_is_not_reopened(memdb):
    _awaiting(memdb, 1)
    memdb.decide_suggestions([1], None, 9, False, replace_rejected=True)
    memdb.connection.execute("UPDATE request_replacements SET status='queued',replacement_delivery_id=99 WHERE delivery_id=1")
    memdb.connection.execute("UPDATE pending_requests SET status='awaiting_approval' WHERE id=1")
    memdb.connection.commit()
    memdb.decide_suggestions([1], None, 9, False, replace_rejected=True)
    assert _replacements(memdb)[1] == 'queued'


def test_a_failed_tag_read_is_retried_not_taken_for_no_tags():
    answers = iter([(500, None), (200, [{'id': 9, 'label': 'suggestarr'}])])
    client = _client('radarr', {('GET', 'movie'): (200, LIBRARY), ('GET', 'tag'): lambda kw: next(answers)})
    with pytest.raises(RuntimeError):
        asyncio.run(client.find_owned(1))          # first candidate: the tag read fails, reported as an error
    assert asyncio.run(client.find_owned(1))[0] == 'ok'   # next candidate reads the tags again
