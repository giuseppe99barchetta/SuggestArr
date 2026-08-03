from contextlib import contextmanager
from unittest.mock import patch

from flask import Flask, g

from api_service.api.v1.blueprint import public_api_v1_bp


class _StatsCursor:
    def __init__(self):
        self._one = None
        self._many = []

    def execute(self, query, _params=()):
        if 'FROM pending_requests' in query:
            self._many = [('awaiting_approval', 1), ('queued', 3), ('submitted', 4)]
        elif 'FROM job_execution_history' in query:
            self._many = [('completed', 6), ('failed', 1)]
        elif "DATE(requested_at) = DATE('now')" in query:
            self._one = (2,)
        elif "strftime('%w', 'now')" in query:
            self._one = (5,)
        elif "strftime('%Y-%m', requested_at)" in query:
            self._one = (9,)
        elif 'FROM requests' in query:
            self._one = (20,)

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class _StatsDatabase:
    db_type = 'sqlite'

    @contextmanager
    def get_connection(self):
        yield _StatsConnection()


class _StatsConnection:
    def cursor(self):
        return _StatsCursor()


class _StatsJobs:
    def get_all_jobs(self):
        return [
            {'job_type': 'discover', 'enabled': 1, 'is_system': 1},
            {'job_type': 'recommendation', 'enabled': 0, 'is_system': 0},
        ]


def _client_as(role):
    app = Flask(__name__)
    app.config['TESTING'] = True

    @app.before_request
    def authenticate_test_request():
        g.current_user = {'id': 1, 'username': 'tester', 'role': role}
        g.auth_method = 'test'
        g.api_key_id = None
        g.api_key_name = None

    app.register_blueprint(public_api_v1_bp, url_prefix='/api/v1')
    return app.test_client()


def test_installation_stats_returns_complete_admin_snapshot():
    with patch('api_service.api.v1.blueprint.DatabaseManager', return_value=_StatsDatabase()), \
            patch('api_service.api.v1.blueprint.JobRepository', return_value=_StatsJobs()):
        response = _client_as('admin').get('/api/v1/installation/stats')

    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['requests'] == {'total': 20, 'today': 2, 'this_week': 5, 'this_month': 9}
    assert data['jobs'] == {
        'total': 2, 'enabled': 1, 'disabled': 1, 'system': 1,
        'by_type': {'discover': 1, 'recommendation': 1, 'trakt_recommendations': 0},
    }
    assert data['runs'] == {
        'total': 7,
        'by_status': {'queued': 0, 'running': 0, 'completed': 6, 'failed': 1, 'skipped': 0},
    }
    assert data['queue'] == {
        'queued': 3, 'submitting': 0, 'submitted': 4, 'failed': 0,
        'total_pending': 3, 'total': 8,
    }


def test_installation_stats_requires_admin_role():
    response = _client_as('user').get('/api/v1/installation/stats')

    assert response.status_code == 403
