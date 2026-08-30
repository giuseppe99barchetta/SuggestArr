import sqlite3
from unittest.mock import MagicMock

from flask import Flask, g

from api_service.auth.limiter import limiter
from api_service.blueprints.automation import routes as automation_routes
from api_service.db.components.request_queue_mixin import RequestQueueMixin
from api_service.db.components.suggestion_feedback_mixin import SuggestionFeedbackMixin


class Queue(RequestQueueMixin, SuggestionFeedbackMixin):
    db_type = 'sqlite'

    def __init__(self, connection):
        self.connection = connection

    def get_connection(self):
        return self.connection


def _queue():
    connection = sqlite3.connect(':memory:')
    connection.executescript("""
        CREATE TABLE discover_jobs (
            id INTEGER PRIMARY KEY,
            owner_id INTEGER,
            max_requests_per_user INTEGER NOT NULL DEFAULT 0,
            request_limit_window_hours INTEGER NOT NULL DEFAULT 24
        );
        CREATE TABLE pending_requests (
            id INTEGER PRIMARY KEY,
            tmdb_id TEXT NOT NULL,
            media_type TEXT NOT NULL,
            user_id TEXT,
            payload TEXT,
            owner_id INTEGER,
            job_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE suggestion_feedback (
            user_id INTEGER NOT NULL,
            media_user_id TEXT NOT NULL DEFAULT '',
            tmdb_id TEXT NOT NULL,
            media_type TEXT NOT NULL,
            feedback TEXT NOT NULL,
            reason_type TEXT,
            reason_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, media_user_id, tmdb_id, media_type)
        );
    """)
    return Queue(connection), connection


def test_feedback_is_scoped_to_internal_user_and_media_profile():
    queue, connection = _queue()
    connection.execute(
        "INSERT INTO pending_requests(id,tmdb_id,media_type,user_id,payload,owner_id) "
        "VALUES (1,'42','movie','plex-a','{\"_user_id\": \"plex-a\"}',7)"
    )
    connection.commit()

    saved = queue.set_suggestion_feedback(1, 7, 7, 'not_interested', 'genre', 'Not horror')
    assert saved['media_user_id'] == 'plex-a'
    assert queue.get_suggestion_feedback(connection.cursor(), 7, '42', 'movie', 'plex-a')['feedback'] == 'not_interested'
    assert queue.get_suggestion_feedback(connection.cursor(), 8, '42', 'movie', 'plex-a') is None
    assert queue.get_suggestion_feedback(connection.cursor(), 7, '42', 'movie', 'plex-b') is None


def test_negative_feedback_blocks_only_matching_automated_job_owner_and_profile():
    queue, connection = _queue()
    connection.executescript("""
        INSERT INTO discover_jobs VALUES (1, 7, 0, 24);
        INSERT INTO pending_requests(id,tmdb_id,media_type,user_id,payload,owner_id)
        VALUES (1,'42','movie','plex-a','{}',7);
    """)
    queue.set_suggestion_feedback(1, 7, 7, 'already_seen')

    assert queue._automated_submission_skip_reason(1, 7, '42', 'movie', 'plex-a')
    assert queue._automated_submission_skip_reason(1, 7, '42', 'movie', 'plex-b') is None
    assert queue._automated_submission_skip_reason(None, 7, '42', 'movie', 'plex-a') is None


def test_rolling_limit_applies_per_job_and_media_user():
    queue, connection = _queue()
    connection.executescript("""
        INSERT INTO discover_jobs VALUES (1, 7, 2, 24);
        INSERT INTO pending_requests(id,tmdb_id,media_type,user_id,payload,owner_id,job_id,created_at)
        VALUES
            (1,'11','movie','plex-a','{}',7,1,CURRENT_TIMESTAMP),
            (2,'12','movie','plex-a','{}',7,1,CURRENT_TIMESTAMP),
            (3,'13','movie','plex-b','{}',7,1,CURRENT_TIMESTAMP),
            (4,'14','movie','plex-a','{}',7,2,CURRENT_TIMESTAMP);
    """)

    assert 'limit of 2' in queue._automated_submission_skip_reason(1, 7, '99', 'movie', 'plex-a')
    assert queue._automated_submission_skip_reason(1, 7, '99', 'movie', 'plex-b') is None


def test_feedback_route_validates_and_scopes_to_current_user(monkeypatch):
    db = MagicMock()
    db.set_suggestion_feedback.return_value = {
        'feedback': 'too_similar', 'reason_type': 'genre', 'reason_text': None,
        'media_user_id': 'plex-a',
    }
    monkeypatch.setattr(automation_routes, 'DatabaseManager', MagicMock(return_value=db))
    app = Flask(__name__)
    app.config.update(TESTING=True, RATELIMIT_ENABLED=False)
    app.secret_key = 'test-secret'

    @app.before_request
    def authenticate():
        g.current_user = {'id': '7', 'role': 'admin'}

    limiter.init_app(app)
    app.register_blueprint(automation_routes.automation_bp, url_prefix='/api/automation')
    client = app.test_client()

    invalid = client.put('/api/automation/requests/workflow/5/feedback', json={'feedback': 'nope'})
    assert invalid.status_code == 400
    db.set_suggestion_feedback.assert_not_called()

    response = client.put(
        '/api/automation/requests/workflow/5/feedback',
        json={'feedback': 'too_similar', 'reason_type': 'genre'},
    )
    assert response.status_code == 200
    db.set_suggestion_feedback.assert_called_once_with(5, None, 7, 'too_similar', 'genre', None, None)
