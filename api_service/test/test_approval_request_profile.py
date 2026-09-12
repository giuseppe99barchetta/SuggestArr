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
    """A queue with the columns apply_profile_to_pending touches."""
    connection = sqlite3.connect(":memory:")
    connection.executescript("""
        CREATE TABLE pending_requests (id INTEGER PRIMARY KEY, media_type TEXT,
            status TEXT, owner_id INTEGER, payload TEXT);
    """)
    connection.executemany(
        "INSERT INTO pending_requests (id,media_type,status,owner_id,payload) VALUES (?,?,?,?,?)",
        rows)
    return Queue(connection), connection


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


# --- the write ------------------------------------------------------------

def test_the_chosen_profile_reaches_the_stored_payload():
    queue, connection = _queue([(1, 'movie', 'awaiting_approval', 7, '{"mediaId": 10}')])
    written = queue.apply_profile_to_pending(
        [1], 7, {'movie': {'serverId': 1, 'profileId': 7, 'rootFolder': '/movies'}})
    assert written == 1
    assert _payload(connection, 1) == {
        'mediaId': 10, 'serverId': 1, 'profileId': 7, 'rootFolder': '/movies'}


def test_each_row_gets_the_profile_of_its_own_media_type():
    """A bulk approval may mix films and series, and profile 7 in Radarr is not
    profile 7 in Sonarr — so the media type decides per row, not per call."""
    queue, connection = _queue([
        (1, 'movie', 'awaiting_approval', 7, '{}'),
        (2, 'tv', 'awaiting_approval', 7, '{}'),
    ])
    written = queue.apply_profile_to_pending([1, 2], 7, {
        'movie': {'serverId': 1, 'profileId': 7, 'rootFolder': '/movies'},
        'tv': {'serverId': 2, 'profileId': 4, 'rootFolder': '/series'},
    })
    assert written == 2
    assert _payload(connection, 1)['profileId'] == 7
    assert _payload(connection, 2)['profileId'] == 4
    assert _payload(connection, 2)['rootFolder'] == '/series'


def test_a_media_type_without_a_profile_stays_untouched():
    queue, connection = _queue([
        (1, 'movie', 'awaiting_approval', 7, '{}'),
        (2, 'tv', 'awaiting_approval', 7, '{"mediaId": 20}'),
    ])
    written = queue.apply_profile_to_pending(
        [1, 2], 7, {'movie': {'serverId': 1, 'profileId': 7, 'rootFolder': '/movies'}})
    assert written == 1
    assert _payload(connection, 2) == {'mediaId': 20}


def test_someone_elses_suggestion_is_not_rewritten():
    queue, connection = _queue([
        (1, 'movie', 'awaiting_approval', 7, '{}'),
        (2, 'movie', 'awaiting_approval', 8, '{}'),
    ])
    written = queue.apply_profile_to_pending(
        [1, 2], 7, {'movie': {'serverId': 1, 'profileId': 7, 'rootFolder': '/movies'}})
    assert written == 1
    assert _payload(connection, 2) == {}


def test_an_admin_may_rewrite_any_owner():
    queue, connection = _queue([
        (1, 'movie', 'awaiting_approval', 7, '{}'),
        (2, 'movie', 'awaiting_approval', 8, '{}'),
    ])
    assert queue.apply_profile_to_pending(
        [1, 2], None, {'movie': {'serverId': 1, 'profileId': 7, 'rootFolder': '/movies'}}) == 2


def test_a_decided_row_is_left_alone():
    """Only rows still awaiting approval are ours to change — a queued row may
    already have been picked up by the worker."""
    queue, connection = _queue([(1, 'movie', 'queued', 7, '{}')])
    assert queue.apply_profile_to_pending(
        [1], 7, {'movie': {'serverId': 1, 'profileId': 7, 'rootFolder': '/movies'}}) == 0
    assert _payload(connection, 1) == {}


def test_an_empty_profile_writes_nothing():
    queue, connection = _queue([(1, 'movie', 'awaiting_approval', 7, '{"mediaId": 10}')])
    assert queue.apply_profile_to_pending([1], 7, {}) == 0
    assert queue.apply_profile_to_pending([1], 7, {'movie': {}}) == 0
    assert _payload(connection, 1) == {'mediaId': 10}


def test_an_unreadable_payload_is_skipped_not_replaced():
    """Losing the rest of a payload would be worse than not setting a profile."""
    queue, connection = _queue([
        (1, 'movie', 'awaiting_approval', 7, 'not json'),
        (2, 'movie', 'awaiting_approval', 7, '{}'),
    ])
    assert queue.apply_profile_to_pending(
        [1, 2], 7, {'movie': {'serverId': 1, 'profileId': 7, 'rootFolder': '/movies'}}) == 1
    assert connection.execute(
        "SELECT payload FROM pending_requests WHERE id=1").fetchone()[0] == 'not json'
