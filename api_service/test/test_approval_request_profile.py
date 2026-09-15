"""Choosing a quality profile while approving a suggestion.

Two halves, tested separately because they fail differently: the validation
(which must reject a profile that looks plausible but is not) and the write
into the stored payload (which must hit the right rows and leave the rest
alone).
"""
import json
import sqlite3

import pytest

from api_service.db.components.request_queue_mixin import RequestQueueMixin
from api_service.utils.request_profiles import validate_request_profiles


class Queue(RequestQueueMixin):
    db_type = "sqlite"

    def __init__(self, connection):
        self.connection = connection
        self.webhook_events = []

    def get_connection(self):
        return self.connection

    def enqueue_webhook_event(self, event, payload):
        self.webhook_events.append((event, payload))


def _queue(rows):
    """A queue with the columns decide_suggestions touches.

    Rows are ``(id, media_type, status, owner_id, payload)``.
    """
    connection = sqlite3.connect(":memory:")
    connection.executescript("""
        CREATE TABLE pending_requests (id INTEGER PRIMARY KEY, tmdb_id TEXT, media_type TEXT,
            status TEXT, owner_id INTEGER, payload TEXT, job_id INTEGER, execution_id INTEGER,
            decided_by INTEGER, decided_at TIMESTAMP);
    """)
    connection.executemany(
        "INSERT INTO pending_requests (id,tmdb_id,media_type,status,owner_id,payload) "
        "VALUES (?,?,?,?,?,?)",
        [(row_id, str(row_id * 10), media_type, status, owner_id, payload)
         for row_id, media_type, status, owner_id, payload in rows])
    return Queue(connection), connection


def _approve(queue, ids, owner_id, profiles):
    return queue.decide_suggestions(ids, owner_id, 7, True, profiles=profiles)


def _status(connection, row_id):
    return connection.execute(
        "SELECT status FROM pending_requests WHERE id=?", (row_id,)).fetchone()[0]


def _payload(connection, row_id):
    return json.loads(connection.execute(
        "SELECT payload FROM pending_requests WHERE id=?", (row_id,)).fetchone()[0])


# --- the validation -------------------------------------------------------

def test_a_complete_profile_passes_unchanged():
    profile = {'movie': {'serverId': 1, 'profileId': 7, 'rootFolder': '/movies'}}
    assert validate_request_profiles(profile) == profile


def test_no_profile_is_not_an_error():
    assert validate_request_profiles(None) == {}


@pytest.mark.parametrize('profile', [
    {'film': {'serverId': 1}},
    {'movie': {'unknown': 1}},
    {'movie': {'serverId': '1', 'profileId': 7, 'rootFolder': '/movies'}},
    {'movie': {'profileId': 7}},
    {'movie': {'serverId': 1, 'profileId': 7}},
    {'movie': {'is4k': 'yes'}},
])
def test_a_malformed_profile_is_refused(profile):
    """Each of these would otherwise reach Jellyseerr and fetch something wrong.

    The partial triples matter most: a profileId without its serverId means
    nothing, because profile 7 is a different profile on every server.
    """
    with pytest.raises(ValueError):
        validate_request_profiles(profile)


# --- the write, together with the approval --------------------------------

MOVIE_PROFILE = {'serverId': 1, 'profileId': 7, 'rootFolder': '/movies'}


def test_the_chosen_profile_reaches_the_stored_payload():
    queue, connection = _queue([(1, 'movie', 'awaiting_approval', 7, '{"mediaId": 10}')])
    assert _approve(queue, [1], 7, {'movie': MOVIE_PROFILE}) == 1
    assert _payload(connection, 1) == {
        'mediaId': 10, 'serverId': 1, 'profileId': 7, 'rootFolder': '/movies'}
    assert _status(connection, 1) == 'queued'


def test_each_row_gets_the_profile_of_its_own_media_type():
    """A bulk approval may mix movies and series, and profile 7 in Radarr is not
    profile 7 in Sonarr — so the media type decides per row, not per call."""
    queue, connection = _queue([
        (1, 'movie', 'awaiting_approval', 7, '{}'),
        (2, 'tv', 'awaiting_approval', 7, '{}'),
    ])
    assert _approve(queue, [1, 2], 7, {
        'movie': MOVIE_PROFILE,
        'tv': {'serverId': 2, 'profileId': 4, 'rootFolder': '/series'},
    }) == 2
    assert _payload(connection, 1)['profileId'] == 7
    assert _payload(connection, 2)['profileId'] == 4
    assert _payload(connection, 2)['rootFolder'] == '/series'


def test_a_media_type_without_a_profile_is_approved_unchanged():
    queue, connection = _queue([
        (1, 'movie', 'awaiting_approval', 7, '{}'),
        (2, 'tv', 'awaiting_approval', 7, '{"mediaId": 20}'),
    ])
    assert _approve(queue, [1, 2], 7, {'movie': MOVIE_PROFILE}) == 2
    assert _payload(connection, 2) == {'mediaId': 20}
    assert _status(connection, 2) == 'queued'


def test_someone_elses_suggestion_is_neither_rewritten_nor_approved():
    queue, connection = _queue([
        (1, 'movie', 'awaiting_approval', 7, '{}'),
        (2, 'movie', 'awaiting_approval', 8, '{}'),
    ])
    assert _approve(queue, [1, 2], 7, {'movie': MOVIE_PROFILE}) == 1
    assert _payload(connection, 2) == {}
    assert _status(connection, 2) == 'awaiting_approval'


def test_an_admin_may_approve_any_owner_with_a_profile():
    queue, connection = _queue([
        (1, 'movie', 'awaiting_approval', 7, '{}'),
        (2, 'movie', 'awaiting_approval', 8, '{}'),
    ])
    assert _approve(queue, [1, 2], None, {'movie': MOVIE_PROFILE}) == 2
    assert _payload(connection, 2)['profileId'] == 7


def test_a_decided_row_is_left_alone():
    """Only rows still awaiting approval are ours to change — a queued row may
    already have been picked up by the worker, and a rejected one must not
    carry a profile that a later request-again would reuse."""
    queue, connection = _queue([
        (1, 'movie', 'queued', 7, '{}'),
        (2, 'movie', 'rejected', 7, '{}'),
    ])
    assert _approve(queue, [1, 2], 7, {'movie': MOVIE_PROFILE}) == 0
    assert _payload(connection, 1) == {}
    assert _payload(connection, 2) == {}


def test_an_empty_profile_writes_nothing():
    queue, connection = _queue([
        (1, 'movie', 'awaiting_approval', 7, '{"mediaId": 10}'),
        (2, 'movie', 'awaiting_approval', 7, '{"mediaId": 20}'),
    ])
    assert _approve(queue, [1], 7, {}) == 1
    assert _approve(queue, [2], 7, {'movie': {}}) == 1
    assert _payload(connection, 1) == {'mediaId': 10}
    assert _payload(connection, 2) == {'mediaId': 20}


def test_a_rejection_ignores_a_profile():
    queue, connection = _queue([(1, 'movie', 'awaiting_approval', 7, '{}')])
    assert queue.decide_suggestions([1], 7, 7, False, profiles={'movie': MOVIE_PROFILE}) == 1
    assert _payload(connection, 1) == {}
    assert _status(connection, 1) == 'rejected'


def test_an_unreadable_payload_is_skipped_not_replaced():
    """Losing the rest of a payload would be worse than not setting a profile."""
    queue, connection = _queue([
        (1, 'movie', 'awaiting_approval', 7, 'not json'),
        (2, 'movie', 'awaiting_approval', 7, '{}'),
    ])
    assert _approve(queue, [1, 2], 7, {'movie': MOVIE_PROFILE}) == 2
    assert connection.execute(
        "SELECT payload FROM pending_requests WHERE id=1").fetchone()[0] == 'not json'
    assert _payload(connection, 2)['profileId'] == 7


class _FailingStatusChange:
    """A connection whose status update fails after the payloads were written."""

    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        self.connection.__enter__()
        return self

    def __exit__(self, *exc):
        return self.connection.__exit__(*exc)

    def cursor(self):
        cursor = self.connection.cursor()
        execute = cursor.execute

        class Cursor:
            rowcount = 0

            def execute(self, sql, params=()):
                if 'SET status=' in sql:
                    raise sqlite3.OperationalError('database is locked')
                result = execute(sql, params)
                self.rowcount = cursor.rowcount
                return result

            def fetchall(self):
                return cursor.fetchall()

        return Cursor()

    def commit(self):
        self.connection.commit()


def test_a_failed_status_change_leaves_no_profile_behind():
    """The profile and the approval are one transaction.

    Otherwise a row could stay rejected or awaiting approval while carrying
    the profile, and a later request-again would fetch with it.
    """
    queue, connection = _queue([(1, 'movie', 'awaiting_approval', 7, '{"mediaId": 10}')])
    connection.commit()
    queue.get_connection = lambda: _FailingStatusChange(connection)
    with pytest.raises(sqlite3.OperationalError):
        _approve(queue, [1], 7, {'movie': MOVIE_PROFILE})
    assert _payload(connection, 1) == {'mediaId': 10}
    assert _status(connection, 1) == 'awaiting_approval'
