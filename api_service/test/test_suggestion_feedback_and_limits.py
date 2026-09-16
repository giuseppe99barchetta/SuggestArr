import sqlite3
from unittest.mock import MagicMock

from flask import Flask, g

from api_service.auth.limiter import limiter
from api_service.blueprints.automation import routes as automation_routes
from api_service.db.components.request_queue_mixin import RequestQueueMixin
from api_service.db.components.suggestion_feedback_mixin import SuggestionFeedbackMixin
from api_service.handler.base_handler import BaseMediaHandler


class Queue(RequestQueueMixin, SuggestionFeedbackMixin):
    db_type = 'sqlite'

    def __init__(self, connection):
        self.connection = connection

    def get_connection(self):
        return self.connection


class FeedbackHandler(BaseMediaHandler):
    def _populate_existing_content_sets(self):
        pass

    async def _request_llm_recommendation(self, media, item_type, source_obj, user=None):
        pass


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
            title TEXT,
            year INTEGER,
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
    assert queue.get_suggestion_feedback_signals(7, 'plex-a', 'movie') == {'42': 'not_interested'}
    assert queue.get_suggestion_feedback_signals(7, 'plex-b', 'movie') == {}


def test_feedback_ranking_is_local_per_profile_and_fails_open():
    repository = MagicMock()
    repository.get_suggestion_feedback_signals.return_value = {
        '2': 'interested',
        '3': 'already_seen',
    }
    handler = FeedbackHandler(
        None, None, MagicMock(), 3, 2, use_llm=False,
        feedback_repository=repository, feedback_owner_id=7,
    )

    ranked = handler._apply_feedback_ranking(
        [{'id': 1}, {'id': 2}, {'id': 3}], 'movie', {'id': 'plex-a'},
    )

    assert [item['id'] for item in ranked] == [2, 1]
    repository.get_suggestion_feedback_signals.assert_called_once_with(7, 'plex-a', 'movie')

    failing_repository = MagicMock()
    failing_repository.get_suggestion_feedback_signals.side_effect = RuntimeError('database unavailable')
    fallback = FeedbackHandler(
        None, None, MagicMock(), 3, 2, use_llm=False,
        feedback_repository=failing_repository, feedback_owner_id=7,
    )
    assert fallback._apply_feedback_ranking([{'id': 1}], 'movie', 'plex-a') == [{'id': 1}]


def test_dry_run_explains_feedback_exclusion():
    repository = MagicMock()
    repository.get_suggestion_feedback_signals.return_value = {'3': 'too_similar'}
    handler = FeedbackHandler(
        None, None, MagicMock(), 3, 2, use_llm=False, dry_run=True,
        feedback_repository=repository, feedback_owner_id=7,
    )

    ranked = handler._apply_feedback_ranking([{'id': 3}], 'tv', 'jellyfin-a')

    result = ranked[0]['filter_results']
    assert result['passed'] is False
    assert result['personal_feedback']['reason'] == 'too similar'


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
    db.set_suggestion_feedback.assert_called_once_with(5, None, 7, 'too_similar', 'genre', None, None, False,
                                                       None, None)

    db.has_visible_suggestarr_request.return_value = True
    db.set_media_feedback.return_value = {
        'feedback': 'interested', 'reason_type': None, 'reason_text': None,
        'media_user_id': 'plex-a',
    }
    sent = client.put(
        '/api/automation/requests/media/movie/42/feedback',
        json={'feedback': 'interested', 'media_user_id': 'plex-a'},
    )
    assert sent.status_code == 200
    db.has_visible_suggestarr_request.assert_called_once_with('42', 'movie', 'plex-a', None)
    db.set_media_feedback.assert_called_once_with(7, 'plex-a', '42', 'movie', 'interested', None, None,
                                                  None, None)

    db.has_visible_suggestarr_request.return_value = False
    hidden = client.put(
        '/api/automation/requests/media/movie/99/feedback',
        json={'feedback': 'interested', 'media_user_id': 'plex-b'},
    )
    assert hidden.status_code == 404


def test_taste_profile_splits_likes_from_dislikes_and_skips_neutral_marks():
    queue, connection = _queue()
    rows = [
        (7, '', '1', 'movie', 'interested', 'Arrival', 2016),
        (7, '', '2', 'movie', 'not_interested', 'Hot Tub Time Machine', 2010),
        (7, '', '3', 'movie', 'save_for_later', 'Dune', 2021),
        # Watching something is not a verdict on it, so it must not colour the profile.
        (7, '', '4', 'movie', 'already_seen', 'Knives Out', 2019),
    ]
    connection.executemany(
        "INSERT INTO suggestion_feedback(user_id,media_user_id,tmdb_id,media_type,feedback,title,year) "
        "VALUES (?,?,?,?,?,?,?)", rows,
    )
    connection.commit()

    profile = queue.get_taste_profile(7, '', 'movie')
    assert {entry['title'] for entry in profile['liked']} == {'Arrival', 'Dune'}
    assert [entry['title'] for entry in profile['disliked']] == ['Hot Tub Time Machine']
    assert profile['liked'][0]['year'] in (2016, 2021)


def test_taste_profile_is_scoped_and_bounded():
    queue, connection = _queue()
    connection.executemany(
        "INSERT INTO suggestion_feedback(user_id,media_user_id,tmdb_id,media_type,feedback,title,year) "
        "VALUES (?,?,?,?,?,?,?)",
        [(7, '', str(i), 'movie', 'interested', f'Film {i}', 2000 + i) for i in range(30)]
        + [(7, '', '900', 'tv', 'interested', 'Other Media Type', 2020)]
        + [(8, '', '901', 'movie', 'interested', "Another User's Film", 2020)],
    )
    connection.commit()

    profile = queue.get_taste_profile(7, '', 'movie')
    titles = [entry['title'] for entry in profile['liked']]
    assert len(titles) <= queue.TASTE_PROFILE_LIMIT
    assert 'Other Media Type' not in titles
    assert "Another User's Film" not in titles


def test_taste_profile_ignores_ratings_saved_without_a_title():
    queue, connection = _queue()
    connection.execute(
        "INSERT INTO suggestion_feedback(user_id,media_user_id,tmdb_id,media_type,feedback) "
        "VALUES (7,'','5','movie','interested')"
    )
    connection.commit()

    # Rows predating the title column would otherwise reach the prompt as a bare id.
    assert queue.get_taste_profile(7, '', 'movie') == {'liked': [], 'disliked': []}


def test_taste_profile_is_empty_without_an_owner():
    queue, _ = _queue()
    assert queue.get_taste_profile(None, '', 'movie') == {'liked': [], 'disliked': []}


def test_saving_a_rating_keeps_a_title_a_later_rating_omits():
    queue, connection = _queue()
    connection.execute(
        "INSERT INTO pending_requests(id,tmdb_id,media_type,user_id,payload,owner_id) "
        "VALUES (1,'42','movie','plex-a','{\"_user_id\": \"plex-a\"}',7)"
    )
    connection.commit()

    queue.set_suggestion_feedback(1, 7, 7, 'interested', None, None, None, False, 'Arrival', 2016)
    queue.set_suggestion_feedback(1, 7, 7, 'not_interested', None, None, None, False)

    stored = connection.execute(
        "SELECT feedback, title, year FROM suggestion_feedback WHERE tmdb_id='42'"
    ).fetchone()
    assert stored == ('not_interested', 'Arrival', 2016)
