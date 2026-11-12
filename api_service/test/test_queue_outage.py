"""A backend outage must not turn queued requests into failures; delivery timing must use consistent clocks."""
import asyncio
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

import api_service.db.database_manager  # noqa: F401  registers the SQLite datetime adapter used in production
from api_service.db.components.request_queue_mixin import RequestQueueMixin
from api_service.db.components.schema_manager import SchemaManager
from api_service.db.components.suggestion_feedback_mixin import SuggestionFeedbackMixin
from api_service.db.components.webhook_mixin import WebhookMixin
from api_service.exceptions.api_exceptions import BackendUnavailableError, is_transport_error
from api_service.jobs import queue_worker
from api_service.jobs.queue_worker import _run_worker
from api_service.services.arr.arr_client import ArrHTTPError
from api_service.services.arr.arr_request_client import ArrRequestClient
from api_service.services.seer.seer_client import SeerClient

ENV = {'REQUEST_BACKEND': 'arr', 'RADARR_API_URL': 'http://radarr:7878', 'RADARR_TOKEN': 'k',
       'SONARR_API_URL': 'http://sonarr:8989', 'SONARR_TOKEN': 'k',
       'SEER_API_URL': 'http://seer:5055', 'SEER_TOKEN': 'k'}


# --- client classification: outage vs rejection -------------------------------------------------

@pytest.mark.parametrize('error', [aiohttp.ClientConnectionError('refused'), asyncio.TimeoutError(),
                                   ArrHTTPError('Radarr answered HTTP 503 for movie', 503)])
def test_arr_outage_is_unavailable_not_a_rejection(error):
    client = ArrRequestClient(ENV)
    fake = MagicMock()
    fake.__aenter__ = AsyncMock(return_value=fake)
    fake.__aexit__ = AsyncMock(return_value=False)
    fake.add = AsyncMock(side_effect=error)
    with patch('api_service.services.arr.arr_request_client.ArrClient', return_value=fake):
        with pytest.raises(BackendUnavailableError):
            asyncio.run(client.submit_queued_request({'mediaType': 'movie', 'mediaId': 1}))


def test_arr_rejection_stays_a_plain_failure():
    client = ArrRequestClient(ENV)
    fake = MagicMock()
    fake.__aenter__ = AsyncMock(return_value=fake)
    fake.__aexit__ = AsyncMock(return_value=False)
    fake.add = AsyncMock(side_effect=ArrHTTPError('Radarr rejected tmdb:1 (HTTP 400)', 400))
    with patch('api_service.services.arr.arr_request_client.ArrClient', return_value=fake):
        assert asyncio.run(client.submit_queued_request({'mediaType': 'movie', 'mediaId': 1})) is False


def _seer():
    return SeerClient('http://seer.local', 'key')


PAYLOAD = {'mediaType': 'movie', 'mediaId': 1, 'profileId': 4, 'rootFolder': '/movies', 'userId': 3}


def test_seer_unreachable_during_submit_is_unavailable():
    client = _seer()

    async def fake_request(*args, **kwargs):
        client._transport_failed = True  # what _make_request records after its retries
        return None

    with patch.object(client, '_make_request', side_effect=fake_request):
        with pytest.raises(BackendUnavailableError):
            asyncio.run(client.submit_queued_request(dict(PAYLOAD)))


def test_seer_rejection_stays_a_plain_failure():
    client = _seer()
    with patch.object(client, '_make_request', AsyncMock(return_value=None)):
        assert asyncio.run(client.submit_queued_request(dict(PAYLOAD))) is False


def test_seer_make_request_records_connection_errors_and_gateway_statuses():
    for status in (502, 503, 504):
        client = _seer()
        response = MagicMock(status=status)
        response.json = AsyncMock(return_value={'message': 'down'})
        response.__aenter__ = AsyncMock(return_value=response)
        response.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.request.return_value = response
        with patch.object(client, '_get_session', AsyncMock(return_value=session)), \
                patch('api_service.services.seer.seer_client.asyncio.sleep', AsyncMock()):
            assert asyncio.run(client._make_request('POST', 'api/v1/request', retries=1)) is None
        assert client._transport_failed is True
    client = _seer()
    session = MagicMock()
    session.request.side_effect = aiohttp.ClientConnectionError('refused')
    with patch.object(client, '_get_session', AsyncMock(return_value=session)), \
            patch('api_service.services.seer.seer_client.asyncio.sleep', AsyncMock()):
        asyncio.run(client._make_request('POST', 'api/v1/request', retries=1))
    assert client._transport_failed is True


def test_seer_unreachable_while_fetching_missing_defaults_is_unavailable():
    client = _seer()

    async def unreachable(*args, **kwargs):
        client._transport_failed = True  # _make_request after its retries
        return None

    payload = {'mediaType': 'movie', 'mediaId': 1, 'userId': 3}  # no profileId / rootFolder: defaults are fetched
    with patch.object(client, '_make_request', side_effect=unreachable):
        with pytest.raises(BackendUnavailableError):
            asyncio.run(client.submit_queued_request(payload))


def test_seer_without_defaults_and_reachable_is_still_a_rejection():
    client = _seer()
    payload = {'mediaType': 'movie', 'mediaId': 1, 'userId': 3}
    with patch.object(client, '_make_request', AsyncMock(return_value=None)):
        assert asyncio.run(client.submit_queued_request(payload)) is False


@pytest.mark.parametrize('status', [502, 503, 504])
def test_a_gateway_status_during_login_is_unavailable(status):
    client = SeerClient('http://seer.local', 'key', seer_user_name='u', seer_password='p')
    response = MagicMock(status=status, cookies={})
    response.read = AsyncMock(return_value=b'')
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post.return_value = response
    payload = {'mediaType': 'movie', 'mediaId': 1, 'profileId': 4, 'rootFolder': '/m'}  # no userId: logs in first
    with patch.object(client, '_get_session', AsyncMock(return_value=session)):
        with pytest.raises(BackendUnavailableError):
            asyncio.run(client.submit_queued_request(payload))


def test_a_rejected_login_is_not_an_outage():
    client = SeerClient('http://seer.local', 'key', seer_user_name='u', seer_password='bad')
    response = MagicMock(status=401, cookies={})
    response.read = AsyncMock(return_value=b'')
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post.return_value = response
    payload = {'mediaType': 'movie', 'mediaId': 1, 'profileId': 4, 'rootFolder': '/m'}
    with patch.object(client, '_get_session', AsyncMock(return_value=session)):
        assert asyncio.run(client.submit_queued_request(payload)) is False


def test_a_tag_creation_gateway_error_is_an_outage_not_a_rejection():
    from api_service.services.arr.arr_client import ArrClient
    client = ArrClient('radarr', 'http://arr.test/', 'k')
    client._request = AsyncMock(side_effect=[(200, []), (503, None)])  # GET /tag, then POST /tag fails
    with pytest.raises(ArrHTTPError) as caught:
        asyncio.run(client._tag_ids_for(['suggestarr']))
    assert caught.value.status == 503


def test_a_missing_destination_configuration_is_an_outage_until_restored():
    client = ArrRequestClient({'REQUEST_BACKEND': 'arr'})  # no Radarr/Sonarr configured any more
    with pytest.raises(BackendUnavailableError):
        asyncio.run(client.submit_queued_request({'mediaType': 'movie', 'mediaId': 1}))
    fake = MagicMock()
    fake.__aenter__ = AsyncMock(return_value=fake)
    fake.__aexit__ = AsyncMock(return_value=False)
    fake.add = AsyncMock(return_value=True)
    with patch('api_service.services.arr.arr_request_client.ArrClient', return_value=fake):
        assert asyncio.run(ArrRequestClient(ENV).submit_queued_request({'mediaType': 'movie', 'mediaId': 1})) is True


def test_a_real_rejection_after_an_earlier_timeout_is_not_an_outage():
    client = _seer()
    bad = MagicMock(status=400)
    bad.json = AsyncMock(return_value={'message': 'invalid'})
    bad.__aenter__ = AsyncMock(return_value=bad)
    bad.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.request.side_effect = [aiohttp.ClientConnectionError('reset'), bad, bad]
    with patch.object(client, '_get_session', AsyncMock(return_value=session)), \
            patch('api_service.services.seer.seer_client.asyncio.sleep', AsyncMock()):
        assert asyncio.run(client.submit_queued_request(dict(PAYLOAD, userId=None))) is False
    # the transport failure was followed by an answer (400): the row counts a rejection, not an outage


def test_is_transport_error():
    assert is_transport_error(aiohttp.ClientError()) and is_transport_error(asyncio.TimeoutError())
    assert is_transport_error(BackendUnavailableError('x')) and not is_transport_error(ValueError('x'))


# --- worker --------------------------------------------------------------------------------------

class Client:
    def __init__(self, outcome=True, fail_media=()):
        self.outcome, self.fail_media = outcome, set(fail_media)
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def init(self):
        return None

    async def submit_queued_request(self, payload):
        self.calls.append(payload)
        if payload.get('mediaType') in self.fail_media:
            raise BackendUnavailableError('down')
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def row(row_id, media='movie', backend='arr', retry=0, since=None):
    return {'id': row_id, 'tmdb_id': str(row_id), 'media_type': media, 'retry_count': retry, 'job_id': 1,
            'execution_id': None, 'unavailable_since': since,
            'payload': f'{{"mediaType": "{media}", "mediaId": {row_id}, "_backend": "{backend}"}}'}


def work(rows, arr=None, seer=None):
    db = MagicMock()
    db.expire_pending_approvals.return_value = 0
    db.check_request_exists.return_value = False
    db.mark_pending_submitting.return_value = True
    db.get_due_requests.return_value = rows
    with patch('api_service.jobs.queue_worker.DatabaseManager', return_value=db), \
            patch('api_service.jobs.queue_worker.ConfigService.get_runtime_config', return_value=ENV), \
            patch('api_service.jobs.queue_worker.SeerClient', return_value=seer or Client()), \
            patch('api_service.jobs.queue_worker.ArrRequestClient', return_value=arr or Client()):
        asyncio.run(_run_worker())
    return db


def test_unavailable_backend_keeps_the_row_queued_without_spending_a_retry():
    db = work([row(1, retry=2)], arr=Client(BackendUnavailableError('down')))
    db.mark_pending_unavailable.assert_called_once()
    db.increment_pending_retry.assert_not_called()
    db.mark_pending_failed.assert_not_called()
    assert db.mark_pending_unavailable.call_args.args[1] > datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.mark.parametrize('error', [aiohttp.ClientConnectionError('x'), asyncio.TimeoutError()])
def test_raw_transport_errors_from_a_client_are_also_unavailable(error):
    db = work([row(1)], arr=Client(error))
    db.mark_pending_unavailable.assert_called_once()
    db.increment_pending_retry.assert_not_called()


def test_a_rejection_still_counts_and_fails_after_the_last_retry():
    db = work([row(1, retry=queue_worker.MAX_RETRIES - 1)], arr=Client(False))
    db.mark_pending_failed.assert_called_once()
    assert 'rejected' in db.mark_pending_failed.call_args.args[2]
    db.mark_pending_unavailable.assert_not_called()


def test_old_deliverable_row_is_not_failed_by_a_first_brief_outage():
    db = work([row(1, since=None)], arr=Client(BackendUnavailableError('down')))
    db.mark_pending_failed.assert_not_called()
    db.mark_pending_unavailable.assert_called_once()


def test_seven_continuous_days_of_outage_fail_the_row_with_an_accurate_reason():
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7, minutes=1)
    db = work([row(1, since=since)], arr=Client(BackendUnavailableError('down')))
    db.mark_pending_failed.assert_called_once()
    assert 'unreachable' in db.mark_pending_failed.call_args.args[2]
    assert db.enqueue_webhook_event.call_args.args[0] == 'request.failed'
    db.mark_pending_unavailable.assert_not_called()


def test_outage_just_under_seven_days_keeps_waiting():
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=6, hours=23)
    db = work([row(1, since=since.isoformat())], arr=Client(BackendUnavailableError('down')))
    db.mark_pending_failed.assert_not_called()


def test_radarr_down_does_not_hold_back_sonarr_and_the_reverse():
    for broken, healthy in (('movie', 'tv'), ('tv', 'movie')):
        arr = Client(True, fail_media={broken})
        db = work([row(1, broken), row(2, healthy), row(3, broken)], arr=arr)
        delivered = [call['mediaType'] for call in arr.calls]
        assert delivered == [broken, healthy], delivered          # the 2nd broken row is not even tried
        assert db.mark_pending_unavailable.call_count == 2         # both broken rows parked
        db.mark_pending_submitted.assert_called_once()


def test_a_backend_that_cannot_be_built_parks_its_rows_and_never_blocks_the_other():
    arr = Client(True)
    db = MagicMock()
    db.expire_pending_approvals.return_value = 0
    db.check_request_exists.return_value = False
    db.mark_pending_submitting.return_value = True
    db.get_due_requests.return_value = [row(1, backend='seer'), row(2, backend='arr')]
    with patch('api_service.jobs.queue_worker.DatabaseManager', return_value=db), \
            patch('api_service.jobs.queue_worker.ConfigService.get_runtime_config', return_value=ENV), \
            patch('api_service.jobs.queue_worker.SeerClient', MagicMock(side_effect=ValueError('no url'))), \
            patch('api_service.jobs.queue_worker.ArrRequestClient', return_value=arr):
        asyncio.run(_run_worker())
    db.mark_pending_unavailable.assert_called_once()
    db.increment_pending_retry.assert_not_called()
    db.mark_pending_submitted.assert_called_once()


def test_a_row_cancelled_while_the_backend_is_down_is_left_cancelled():
    # mark_pending_unavailable reports False when the row is no longer queued/sending: nothing else happens.
    arr = Client(BackendUnavailableError('down'))
    db = MagicMock()
    db.expire_pending_approvals.return_value = 0
    db.check_request_exists.return_value = False
    db.mark_pending_submitting.return_value = True
    db.mark_pending_unavailable.return_value = False
    db.get_due_requests.return_value = [row(1)]
    with patch('api_service.jobs.queue_worker.DatabaseManager', return_value=db), \
            patch('api_service.jobs.queue_worker.ConfigService.get_runtime_config', return_value=ENV), \
            patch('api_service.jobs.queue_worker.SeerClient', return_value=Client()), \
            patch('api_service.jobs.queue_worker.ArrRequestClient', return_value=arr):
        asyncio.run(_run_worker())
    db.mark_pending_failed.assert_not_called()
    db.enqueue_webhook_event.assert_not_called()


def test_an_expired_outage_row_cancelled_meanwhile_is_neither_failed_nor_announced():
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=8)
    arr = Client(BackendUnavailableError('down'))
    db = MagicMock()
    db.expire_pending_approvals.return_value = 0
    db.check_request_exists.return_value = False
    db.mark_pending_submitting.return_value = False  # cancelled after it was read: the claim fails
    db.get_due_requests.return_value = [row(1, since=since)]
    with patch('api_service.jobs.queue_worker.DatabaseManager', return_value=db), \
            patch('api_service.jobs.queue_worker.ConfigService.get_runtime_config', return_value=ENV), \
            patch('api_service.jobs.queue_worker.SeerClient', return_value=Client()), \
            patch('api_service.jobs.queue_worker.ArrRequestClient', return_value=arr):
        asyncio.run(_run_worker())
    db.mark_pending_failed.assert_not_called()
    db.enqueue_webhook_event.assert_not_called()


def test_a_destination_marked_down_does_not_revive_a_cancelled_row_either():
    arr = Client(True, fail_media={'movie'})
    db = MagicMock()
    db.expire_pending_approvals.return_value = 0
    db.check_request_exists.return_value = False
    db.mark_pending_submitting.return_value = True
    db.mark_pending_unavailable.side_effect = [True, False]  # 2nd row was cancelled meanwhile
    db.get_due_requests.return_value = [row(1), row(2)]
    with patch('api_service.jobs.queue_worker.DatabaseManager', return_value=db), \
            patch('api_service.jobs.queue_worker.ConfigService.get_runtime_config', return_value=ENV), \
            patch('api_service.jobs.queue_worker.SeerClient', return_value=Client()), \
            patch('api_service.jobs.queue_worker.ArrRequestClient', return_value=arr):
        asyncio.run(_run_worker())
    assert len(arr.calls) == 1
    db.mark_pending_failed.assert_not_called()


# --- database: real SQLite -----------------------------------------------------------------------

class MemoryDB(RequestQueueMixin, WebhookMixin, SuggestionFeedbackMixin):
    db_type = 'sqlite'
    logger = MagicMock()

    def __init__(self):
        self.connection = sqlite3.connect(':memory:', detect_types=sqlite3.PARSE_DECLTYPES)
        self.connection.row_factory = sqlite3.Row
        SchemaManager(self).initialize_db()

    @contextmanager
    def get_connection(self):
        yield self.connection

    @staticmethod
    def _utc_naive(value):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value

    def add(self, tmdb_id, **columns):
        row = {'tmdb_id': str(tmdb_id), 'media_type': 'movie', 'payload': '{}', 'status': 'queued', **columns}
        names, values = list(row), list(row.values())
        self.connection.execute(f"INSERT INTO pending_requests ({','.join(names)}) VALUES ({','.join('?' * len(names))})", values)
        self.connection.commit()


@pytest.fixture
def db():
    memory = MemoryDB()
    yield memory
    memory.connection.close()


def naive_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_mark_unavailable_sets_since_once_and_keeps_the_retry_count(db):
    db.add(1, retry_count=2)
    row_id = db.connection.execute('SELECT id FROM pending_requests').fetchone()[0]
    db.mark_pending_unavailable(row_id, naive_now() + timedelta(minutes=5), 'down')
    first = db.connection.execute('SELECT * FROM pending_requests').fetchone()
    db.mark_pending_unavailable(row_id, naive_now() + timedelta(minutes=5), 'still down')
    second = db.connection.execute('SELECT * FROM pending_requests').fetchone()
    assert first['unavailable_since'] is not None and first['unavailable_since'] == second['unavailable_since']
    assert second['retry_count'] == 2 and second['status'] == 'queued' and second['last_error'] == 'still down'


def test_any_other_state_change_clears_unavailable_since(db):
    db.add(1)
    row_id = db.connection.execute('SELECT id FROM pending_requests').fetchone()[0]
    db.mark_pending_unavailable(row_id, naive_now(), 'down')
    db.mark_pending_submitted(row_id, 0)
    assert db.connection.execute('SELECT unavailable_since FROM pending_requests').fetchone()[0] is None


def test_manual_retry_clears_unavailable_since(db):
    db.add(1, status='failed', unavailable_since=naive_now() - timedelta(days=8))
    row_id = db.connection.execute('SELECT id FROM pending_requests').fetchone()[0]
    db.retry_suggestions([row_id], owner_id=None, include_unassigned=True)
    assert db.connection.execute('SELECT unavailable_since FROM pending_requests').fetchone()[0] is None


def test_unavailable_rows_cannot_starve_later_rows_of_a_working_backend(db):
    attempted = naive_now() - timedelta(minutes=10)
    for tmdb in range(1, 121):  # more than two batches of old rows whose backend is down
        db.add(tmdb, last_attempt_at=attempted, next_attempt_at=naive_now() - timedelta(minutes=1),
               created_at='2026-01-01 00:00:00')
    db.add(999, created_at='2026-11-01 00:00:00')  # newest row, never attempted, for a working backend
    due = db.get_due_requests(max_items=50)
    assert due[0]['tmdb_id'] == '999'
    assert 'unavailable_since' in due[0]


def test_unavailable_rows_are_not_due_before_their_five_minute_pause(db):
    db.add(1, next_attempt_at=naive_now() + timedelta(minutes=5), last_attempt_at=naive_now())
    assert db.get_due_requests() == []


def test_schema_migration_adds_the_column_and_is_repeatable():
    connection = sqlite3.connect(':memory:')
    connection.execute('CREATE TABLE pending_requests(id INTEGER, status TEXT)')

    class Db:
        db_type = 'sqlite'
        logger = MagicMock()

        @contextmanager
        def get_connection(self):
            yield connection

    manager = SchemaManager(Db())
    manager._migrate_queue_outage()
    manager._migrate_queue_outage()
    columns = [r[1] for r in connection.execute('PRAGMA table_info(pending_requests)')]
    assert columns.count('unavailable_since') == 1


def test_marking_unavailable_leaves_a_cancelled_row_untouched(db):
    db.add(1, status='rejected', last_error='Cancelled')
    row_id = db.connection.execute('SELECT id FROM pending_requests').fetchone()[0]
    assert db.mark_pending_unavailable(row_id, naive_now(), 'down') is False
    record = db.connection.execute('SELECT * FROM pending_requests').fetchone()
    assert record['status'] == 'rejected' and record['unavailable_since'] is None and record['last_error'] == 'Cancelled'


def test_marking_unavailable_works_for_queued_and_submitting_rows(db):
    for state in ('queued', 'submitting'):
        db.connection.execute('DELETE FROM pending_requests')
        db.add(1, status=state)
        row_id = db.connection.execute('SELECT id FROM pending_requests').fetchone()[0]
        assert db.mark_pending_unavailable(row_id, naive_now(), 'down') is True
        assert db.connection.execute('SELECT status FROM pending_requests').fetchone()[0] == 'queued'


def test_requeueing_a_rejected_suggestion_clears_the_old_outage(db):
    db.add(1, status='rejected', unavailable_since=naive_now() - timedelta(days=8))
    row_id = db.connection.execute('SELECT id FROM pending_requests').fetchone()[0]
    assert db.request_rejected([row_id], owner_id=None, remove_blacklist=False, include_unassigned=True) == 1
    record = db.connection.execute('SELECT * FROM pending_requests').fetchone()
    assert record['status'] == 'queued' and record['unavailable_since'] is None


# --- same-day datetime boundaries (SQLite stores 'T' text, CURRENT_TIMESTAMP writes a space) ------

def test_webhook_retry_scheduled_for_later_today_becomes_due_on_time(db):
    # next_attempt_at is written by Python (ISO 'T'); 'due' must follow the clock, not the calendar date.
    now = naive_now()
    for event, when in (('past', now - timedelta(minutes=1)), ('future', now + timedelta(minutes=30))):
        db.connection.execute(
            "INSERT INTO webhook_deliveries (event_id, webhook_id, event_type, url, secret, payload, status, "
            "next_attempt_at) VALUES (?, 'w', 'e', 'http://x', 's', '{}', 'queued', ?)", (event, when))
    db.connection.commit()
    assert [d['event_id'] for d in db.get_due_webhook_deliveries()] == ['past']


class _Clock:
    """Freeze the 'now' seen by request_queue_mixin so a cutoff and the rows around it share a calendar day."""

    def __init__(self, fixed):
        class Fixed(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed if tz else fixed.replace(tzinfo=None)
        self.patch = patch('api_service.db.components.request_queue_mixin.datetime', Fixed)

    def __enter__(self):
        return self.patch.__enter__()

    def __exit__(self, *exc):
        return self.patch.__exit__(*exc)


NOW = datetime(2026, 11, 12, 15, 0, 0, tzinfo=timezone.utc)


def test_approval_expiry_respects_the_cutoff_within_the_same_day(db):
    # cutoff = now - 1 day = 2026-11-11 15:00; CURRENT_TIMESTAMP writes space-separated text.
    db.add(1, status='awaiting_approval', created_at='2026-11-11 14:55:00')   # before the cutoff -> expires
    db.add(2, status='awaiting_approval', created_at='2026-11-11 15:05:00')   # after the cutoff -> stays
    with _Clock(NOW):
        assert db.expire_pending_approvals(1) == 1
    rows = dict(db.connection.execute('SELECT tmdb_id, status FROM pending_requests').fetchall())
    assert rows == {'1': 'rejected', '2': 'awaiting_approval'}


def test_rate_limit_window_counts_rows_after_the_cutoff_on_the_same_day(db):
    db.connection.execute(
        "INSERT INTO discover_jobs (id, name, media_type, filters, schedule_type, schedule_value, "
        "max_requests_per_user, request_limit_window_hours) VALUES (7, 'j', 'movie', '{}', 'preset', 'daily', 1, 24)")
    db.add(1, job_id=7, user_id='u', created_at='2026-11-11 14:55:00')  # outside the 24h window
    db.add(2, job_id=7, user_id='u', created_at='2026-11-11 15:05:00')  # inside it: the limit of 1 is reached
    db.connection.commit()
    with _Clock(NOW):
        reason = db._automated_submission_skip_reason(7, None, '3', 'movie', 'u')
    assert reason and 'limit' in reason.lower()


def test_rate_limit_window_ignores_rows_before_the_cutoff(db):
    db.connection.execute(
        "INSERT INTO discover_jobs (id, name, media_type, filters, schedule_type, schedule_value, "
        "max_requests_per_user, request_limit_window_hours) VALUES (7, 'j', 'movie', '{}', 'preset', 'daily', 1, 24)")
    db.add(1, job_id=7, user_id='u', created_at='2026-11-11 14:55:00')  # only an old row
    db.connection.commit()
    with _Clock(NOW):
        assert db._automated_submission_skip_reason(7, None, '3', 'movie', 'u') is None
