"""A suggestion belongs to the person whose watch history produced it.

The default automation has no owner, so its suggestions used to have
``owner_id`` NULL: nobody but an admin could see or approve them, and an admin
saw everybody's.  Now the owner is resolved when a suggestion is queued —
through a *verified* media link only — and stored.
"""
import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, g

from api_service.auth.limiter import limiter
from api_service.blueprints.automation import routes as automation_routes
from api_service.db.components.request_queue_mixin import RequestQueueMixin
from api_service.db.components.schema_manager import SchemaManager
from api_service.db.components.suggestion_feedback_mixin import SuggestionFeedbackMixin
from api_service.db.components.suggestion_ownership import ownership_clause
from api_service.test.test_db_users import _DBBase
from api_service.utils import request_scope


class Queue(RequestQueueMixin, SuggestionFeedbackMixin):
    db_type = "sqlite"

    def __init__(self, connection):
        self.connection = connection

    def get_connection(self):
        return self.connection

    def enqueue_webhook_event(self, event, payload):
        pass


ACHIM_ID, ROBERT_ID, ADMIN_ID = 7, 9, 1
ACHIM, ROBERT, NOBODY = 'jf-achim', 'jf-robert', 'jf-nobody'


def _queue():
    connection = sqlite3.connect(":memory:")
    connection.executescript("""
        CREATE TABLE pending_requests (id INTEGER PRIMARY KEY, tmdb_id TEXT, media_type TEXT, user_id TEXT,
            payload TEXT, status TEXT, retry_count INTEGER DEFAULT 0, last_attempt_at TIMESTAMP,
            next_attempt_at TIMESTAMP, job_id INTEGER, execution_id INTEGER, owner_id INTEGER,
            decided_at TIMESTAMP, decided_by INTEGER, last_error TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE metadata (media_id TEXT, media_type TEXT, title TEXT, poster_path TEXT, overview TEXT,
            rating REAL, release_date TEXT, logo_path TEXT, backdrop_path TEXT);
        CREATE TABLE discover_jobs (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE users (user_id TEXT, user_name TEXT);
        CREATE TABLE media_user_identities (external_user_id TEXT, external_username TEXT);
        CREATE TABLE user_media_profiles (external_user_id TEXT, external_username TEXT);
        CREATE TABLE suggestion_blacklist (tmdb_id TEXT, media_type TEXT, created_by INTEGER,
            PRIMARY KEY (tmdb_id, media_type));
    """)
    rows = [
        # id, tmdb, status, owner (as stored when queued), _user_id
        (1, '10', 'awaiting_approval', ACHIM_ID, ACHIM),    # resolved to Achim
        (2, '20', 'awaiting_approval', ROBERT_ID, ROBERT),  # resolved to Robert
        (3, '30', 'awaiting_approval', None, NOBODY),       # nobody verified: unassigned
        (4, '40', 'awaiting_approval', ACHIM_ID, ROBERT),   # Achim's own job, on Robert's history
        (5, '50', 'failed', ACHIM_ID, ACHIM),
        (6, '60', 'failed', ROBERT_ID, ROBERT),
        (7, '70', 'failed', None, NOBODY),
        (8, '80', 'rejected', ACHIM_ID, ACHIM),
        (9, '90', 'rejected', ROBERT_ID, ROBERT),
        (10, '100', 'rejected', None, NOBODY),
    ]
    for row_id, tmdb, status, owner, media_user in rows:
        connection.execute(
            "INSERT INTO pending_requests (id,tmdb_id,media_type,user_id,payload,status,job_id,owner_id) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (row_id, tmdb, 'movie', media_user, json.dumps({'_user_id': media_user}), status, 1, owner),
        )
    connection.commit()
    return connection, Queue(connection)


def _status(connection, row_id):
    return connection.execute("SELECT status FROM pending_requests WHERE id=?", (row_id,)).fetchone()[0]


# --- the SQL rule ---------------------------------------------------------

def test_no_owner_means_no_restriction():
    assert ownership_clause('sqlite', None) == ('', [])
    assert ownership_clause('sqlite', None, True) == ('', [])


def test_an_owner_matches_only_their_rows():
    assert ownership_clause('sqlite', 7) == (' AND owner_id=?', [7])


def test_unassigned_rows_can_be_included():
    assert ownership_clause('sqlite', 7, True, 'p.') == (' AND (p.owner_id=? OR p.owner_id IS NULL)', [7])


@pytest.mark.parametrize('db_type', ['postgres', 'mysql', 'mariadb'])
def test_other_databases_get_their_own_placeholders(db_type):
    clause, params = ownership_clause(db_type, 7, True, 'p.')
    assert '?' not in clause and clause.count('%s') == 1
    assert params == [7]


# --- the queue ------------------------------------------------------------

def test_a_user_decides_only_what_they_own():
    """The media account a row came from grants nothing by itself: row 2 is
    Robert's, row 3 is nobody's, and neither is Achim's to decide."""
    connection, queue = _queue()
    assert queue.decide_suggestions([1, 2, 3, 4], ACHIM_ID, ACHIM_ID, True) == 2
    assert _status(connection, 1) == 'queued'
    assert _status(connection, 4) == 'queued'
    assert _status(connection, 2) == 'awaiting_approval'
    assert _status(connection, 3) == 'awaiting_approval'


def test_an_admin_limited_to_their_own_still_reaches_unassigned_rows():
    """Otherwise an unassigned suggestion could never be approved by anyone,
    and with PAUSE_JOBS_WITH_PENDING_APPROVALS its job would never run again."""
    connection, queue = _queue()
    assert queue.decide_suggestions([1, 2, 3], ADMIN_ID, ADMIN_ID, True, include_unassigned=True) == 1
    assert _status(connection, 3) == 'queued'
    assert _status(connection, 1) == 'awaiting_approval'
    assert _status(connection, 2) == 'awaiting_approval'


def test_the_list_follows_the_same_rule():
    _, queue = _queue()
    items, total = queue.list_suggestions(ACHIM_ID, 'awaiting_approval')
    assert (total, sorted(item['id'] for item in items)) == (2, [1, 4])
    items, total = queue.list_suggestions(ADMIN_ID, 'awaiting_approval', include_unassigned=True)
    assert (total, [item['id'] for item in items]) == (1, [3])


def test_an_unrestricted_admin_still_sees_everything():
    _, queue = _queue()
    _, total = queue.list_suggestions(None, 'awaiting_approval')
    assert total == 4


def test_the_profile_is_written_only_into_rows_the_caller_may_decide():
    connection, queue = _queue()
    profile = {'movie': {'serverId': 0, 'profileId': 4, 'rootFolder': '/movies'}}
    assert queue.decide_suggestions([1, 2], ACHIM_ID, ACHIM_ID, True, profiles=profile) == 1
    payloads = dict(connection.execute("SELECT id, payload FROM pending_requests WHERE id IN (1,2)").fetchall())
    assert json.loads(payloads[1])['profileId'] == 4
    assert 'profileId' not in json.loads(payloads[2])


def test_retry_and_request_again_follow_the_same_rule():
    connection, queue = _queue()
    assert queue.retry_suggestions([5, 6, 7], ACHIM_ID) == 1
    assert (_status(connection, 5), _status(connection, 6), _status(connection, 7)) == ('queued', 'failed', 'failed')
    assert queue.request_rejected([8, 9, 10], ADMIN_ID, False, True) == 1
    assert (_status(connection, 8), _status(connection, 9), _status(connection, 10)) == ('rejected', 'rejected', 'queued')


def test_feedback_follows_the_same_rule():
    _, queue = _queue()
    cursor = queue.connection.cursor()
    assert queue._feedback_suggestion(cursor, 1, ACHIM_ID) == ('10', 'movie', ACHIM)
    assert queue._feedback_suggestion(cursor, 2, ACHIM_ID) is None
    assert queue._feedback_suggestion(cursor, 3, ACHIM_ID) is None
    assert queue._feedback_suggestion(cursor, 3, ADMIN_ID, None, True) == ('30', 'movie', NOBODY)


# --- who owns a new suggestion --------------------------------------------

class TestResolveSuggestionOwner(_DBBase):
    """Real SQLite: the schema, the upsert and the resolver together."""

    def setUp(self):
        super().setUp()
        self.achim = self._make_user('achim', 'admin')
        self.robert = self._make_user('robert', 'user')

    def test_a_verified_link_makes_its_user_the_owner(self):
        self.db.create_user_media_profile(self.robert, 'jellyfin', ROBERT, 'robert', verified=True)
        self.assertEqual(self.db.resolve_suggestion_owner('jellyfin', ROBERT), self.robert)

    def test_a_self_picked_link_grants_nothing(self):
        """The case from the review: anyone may pick another person's account
        from the server's user list."""
        self.db.create_user_media_profile(self.robert, 'jellyfin', ACHIM, 'achim')
        self.assertIsNone(self.db.resolve_suggestion_owner('jellyfin', ACHIM))

    def test_relinking_without_proof_drops_the_verification(self):
        self.db.create_user_media_profile(self.robert, 'jellyfin', ROBERT, 'robert', verified=True)
        self.db.create_user_media_profile(self.robert, 'jellyfin', ROBERT, 'robert')
        self.assertIsNone(self.db.resolve_suggestion_owner('jellyfin', ROBERT))
        self.assertFalse(self.db.get_user_media_profiles(self.robert)[0]['verified'])

    def test_two_verified_users_leave_it_unassigned(self):
        self.db.create_user_media_profile(self.achim, 'jellyfin', ROBERT, 'robert', verified=True)
        self.db.create_user_media_profile(self.robert, 'jellyfin', ROBERT, 'robert', verified=True)
        self.assertIsNone(self.db.resolve_suggestion_owner('jellyfin', ROBERT))

    def test_a_deactivated_user_owns_nothing_new(self):
        self.db.create_user_media_profile(self.robert, 'jellyfin', ROBERT, 'robert', verified=True)
        self.db.update_auth_user(self.robert, {'is_active': False})
        self.assertIsNone(self.db.resolve_suggestion_owner('jellyfin', ROBERT))

    def test_the_link_must_belong_to_the_configured_media_server(self):
        """A Plex id means nothing on Jellyfin — and the OpenAI settings are
        stored in the same table with the SuggestArr id as external id."""
        self.db.create_user_media_profile(self.robert, 'plex', ROBERT, 'robert', verified=True)
        self.db.create_user_media_profile(self.achim, 'openai', str(self.robert), 'achim', access_token='{}')
        self.assertIsNone(self.db.resolve_suggestion_owner('jellyfin', ROBERT))
        self.assertIsNone(self.db.resolve_suggestion_owner('plex', str(self.robert)))
        self.assertEqual(self.db.resolve_suggestion_owner('plex', ROBERT), self.robert)

    def test_jellyfin_and_emby_links_point_at_the_same_server(self):
        self.db.create_user_media_profile(self.robert, 'emby', ROBERT, 'robert', verified=True)
        self.assertEqual(self.db.resolve_suggestion_owner('jellyfin', ROBERT), self.robert)

    def test_no_media_user_or_service_resolves_to_nobody(self):
        self.db.create_user_media_profile(self.robert, 'jellyfin', ROBERT, 'robert', verified=True)
        self.assertIsNone(self.db.resolve_suggestion_owner('jellyfin', None))
        self.assertIsNone(self.db.resolve_suggestion_owner('', ROBERT))

    def test_an_existing_database_gains_the_column_unverified(self):
        with self.db.get_connection() as conn:
            conn.executescript("""
                DROP TABLE user_media_profiles;
                CREATE TABLE user_media_profiles (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL, provider TEXT NOT NULL, external_user_id TEXT NOT NULL,
                    external_username TEXT NOT NULL, access_token TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE (user_id, provider));
            """)
            conn.execute("INSERT INTO user_media_profiles (user_id, provider, external_user_id, external_username) "
                         "VALUES (?, 'jellyfin', ?, 'robert')", (self.robert, ROBERT))
            conn.commit()
        SchemaManager(self.db).add_missing_columns()
        self.assertFalse(self.db.get_user_media_profiles(self.robert)[0]['verified'])
        self.assertIsNone(self.db.resolve_suggestion_owner('jellyfin', ROBERT))


def _request_media(context, resolved_owner):
    """Queue one suggestion through SeerClient and return enqueue_request's kwargs."""
    import asyncio
    from api_service.services.seer.seer_client import SeerClient

    client = SeerClient('http://seer.local', 'token', exclude_downloaded=False, exclude_watched=False)
    client.queue_context = context
    with patch('api_service.services.seer.seer_client.DatabaseManager') as manager, \
            patch('api_service.services.seer.seer_client.load_env_vars',
                  return_value={'SELECTED_SERVICE': 'jellyfin'}):
        db = manager.return_value
        db.resolve_suggestion_owner.return_value = resolved_owner
        db.enqueue_request.return_value = True
        asyncio.run(client.request_media('movie', {'id': 10}, user={'id': ROBERT, 'name': 'robert'}))
    return db


def test_a_suggestion_of_an_ownerless_job_is_stored_with_the_resolved_owner():
    db = _request_media({'job_id': 3, 'owner_id': None}, ROBERT_ID)
    db.resolve_suggestion_owner.assert_called_once_with('jellyfin', ROBERT)
    assert db.enqueue_request.call_args.kwargs['owner_id'] == ROBERT_ID


def test_an_unresolved_suggestion_is_stored_unassigned():
    db = _request_media({'job_id': 3, 'owner_id': None}, None)
    assert db.enqueue_request.call_args.kwargs['owner_id'] is None


def test_a_job_owner_keeps_their_suggestions():
    db = _request_media({'job_id': 3, 'owner_id': ACHIM_ID}, ROBERT_ID)
    db.resolve_suggestion_owner.assert_not_called()
    assert db.enqueue_request.call_args.kwargs['owner_id'] == ACHIM_ID


# --- who is restricted ----------------------------------------------------

ADMIN = {'id': str(ADMIN_ID), 'role': 'admin'}
USER = {'id': str(ROBERT_ID), 'role': 'user'}


def _db(linked):
    db = MagicMock()
    db.get_user_media_profiles.return_value = [{'external_user_id': value} for value in linked]
    return db


@pytest.mark.parametrize('mode, admin_restricted, user_restricted', [
    ('all', False, False),
    ('own', False, True),
    ('own_all', True, True),
    ('something-else', False, False),
])
def test_visibility_modes(mode, admin_restricted, user_restricted):
    env = {'REQUEST_VISIBILITY': mode}
    assert request_scope.is_restricted(ADMIN, env) is admin_restricted
    assert request_scope.is_restricted(USER, env) is user_restricted


def test_own_all_scopes_an_admin_by_ownership_plus_unassigned():
    env = {'REQUEST_VISIBILITY': 'own_all'}
    db = _db([ACHIM])
    assert request_scope.suggestion_scope(db, ADMIN, env) == request_scope.SuggestionScope(ADMIN_ID, True, None)
    assert request_scope.suggestion_scope(db, ADMIN, env, NOBODY).media_user_ids == [NOBODY]
    # Sent requests are not suggestions; there the linked accounts still decide.
    assert request_scope.visible_request_user_ids(db, ADMIN, env) == [ACHIM]


@pytest.mark.parametrize('mode', ['all', 'own'])
def test_otherwise_an_admin_is_unrestricted(mode):
    scope = request_scope.suggestion_scope(_db([ACHIM]), ADMIN, {'REQUEST_VISIBILITY': mode})
    assert scope == request_scope.SuggestionScope(None, False, None)


def test_a_regular_user_owns_only_their_rows_in_every_mode():
    db = _db([ROBERT])
    for mode, media_users in (('all', None), ('own', [ROBERT]), ('own_all', [ROBERT])):
        scope = request_scope.suggestion_scope(db, USER, {'REQUEST_VISIBILITY': mode})
        assert scope == request_scope.SuggestionScope(ROBERT_ID, False, media_users)


# --- the route the dashboard and the Requests page use --------------------

def _client(monkeypatch, user, mode, db):
    monkeypatch.setattr(automation_routes, 'DatabaseManager', MagicMock(return_value=db))
    monkeypatch.setattr(automation_routes, 'load_env_vars', lambda: {'REQUEST_VISIBILITY': mode})
    monkeypatch.setattr(automation_routes, 'validate_request_profiles_with_seer', lambda profile: None)
    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=False)

    @app.before_request
    def authenticate():
        g.current_user = user

    limiter.init_app(app)
    app.register_blueprint(automation_routes.automation_bp, url_prefix='/api/automation')
    return app.test_client()


def test_an_admin_under_own_all_approves_their_own_and_unassigned(monkeypatch):
    db = _db([ACHIM])
    db.decide_suggestions.return_value = 1
    client = _client(monkeypatch, ADMIN, 'own_all', db)
    profile = {'movie': {'serverId': 0, 'profileId': 4, 'rootFolder': '/movies'}}
    response = client.post('/api/automation/requests/workflow/approve', json={'ids': [1, 3], 'profile': profile})
    assert response.status_code == 200
    db.decide_suggestions.assert_called_once_with(
        [1, 3], ADMIN_ID, ADMIN_ID, True, False, profiles=profile, include_unassigned=True)


def test_an_admin_under_own_all_lists_their_own_and_unassigned(monkeypatch):
    db = _db([ACHIM])
    db.list_suggestions.return_value = ([], 0)
    client = _client(monkeypatch, ADMIN, 'own_all', db)
    assert client.get('/api/automation/requests/workflow').status_code == 200
    args = db.list_suggestions.call_args[0]
    assert args[0] == ADMIN_ID     # owner
    assert args[6] is None         # no media-user filter: ownership decides
    assert args[8] is True         # unassigned included


def test_a_regular_user_approves_only_what_they_own(monkeypatch):
    db = _db([ROBERT])
    db.decide_suggestions.return_value = 1
    client = _client(monkeypatch, USER, 'own', db)
    assert client.post('/api/automation/requests/workflow/approve', json={'ids': [2]}).status_code == 200
    db.decide_suggestions.assert_called_once_with(
        [2], ROBERT_ID, ROBERT_ID, True, False, profiles={}, include_unassigned=False)
