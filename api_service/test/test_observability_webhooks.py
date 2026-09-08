import asyncio
import json
import sqlite3
from unittest.mock import MagicMock, patch

from flask import Flask, g

from api_service.api.v1.blueprint import public_api_v1_bp
from api_service.jobs.job_manager import JobManager
from api_service.jobs.webhook_worker import run_webhook_worker
from api_service.jobs.queue_worker import _run_worker
from api_service.db.components.webhook_mixin import WebhookMixin


class _WebhookDb(WebhookMixin):
    db_type = 'sqlite'

    def __init__(self):
        self.connection = sqlite3.connect(':memory:')
        self.config = {'items': [{'id': 'hook-1', 'url': 'https://hooks.example.test', 'secret': 'a' * 16,
                                  'events': ['suggestion.created']}]}
        self.connection.execute('''CREATE TABLE webhook_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT, webhook_id TEXT,
            event_type TEXT, url TEXT, secret TEXT, allow_private INTEGER, payload TEXT,
            status TEXT DEFAULT 'queued', retry_count INTEGER DEFAULT 0,
            next_attempt_at TIMESTAMP, last_error TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)''')

    def get_connection(self):
        return self.connection

    def get_integration(self, _service):
        return self.config

    def set_integration(self, _service, config):
        self.config = config


def _client(db):
    app = Flask(__name__)
    app.config['TESTING'] = True

    @app.before_request
    def admin():
        g.current_user = {'id': 1, 'username': 'admin', 'role': 'admin'}
        g.auth_method = 'test'
        g.api_key_id = None
        g.api_key_name = None

    app.register_blueprint(public_api_v1_bp, url_prefix='/api/v1')
    return app.test_client(), patch('api_service.api.v1.blueprint.DatabaseManager', return_value=db)


def test_metrics_requires_admin_and_returns_prometheus_text():
    db = MagicMock()
    client, db_patch = _client(db)
    with db_patch, patch('api_service.api.v1.blueprint.render_metrics', return_value=(b'metric 1\n', 'text/plain')):
        response = client.get('/api/v1/metrics')
    assert response.status_code == 200
    assert response.get_data() == b'metric 1\n'
    assert response.content_type.startswith('text/plain')


def test_webhooks_create_list_and_delete_without_returning_secret():
    db = MagicMock()
    db.create_webhook.return_value = {'id': 'hook-1', 'name': 'n8n', 'url': 'https://hooks.example.test',
                                      'events': ['run.failed'], 'enabled': True, 'allow_private': False}
    db.list_webhooks.return_value = [db.create_webhook.return_value]
    db.delete_webhook.return_value = True
    client, db_patch = _client(db)
    payload = {'name': 'n8n', 'url': 'https://hooks.example.test', 'secret': 'a' * 16, 'events': ['run.failed']}
    with db_patch, patch('api_service.api.v1.blueprint.validate_url') as validate:
        created = client.post('/api/v1/webhooks', json=payload)
        listed = client.get('/api/v1/webhooks')
        deleted = client.delete('/api/v1/webhooks/hook-1')
    assert created.status_code == 201
    assert 'secret' not in created.get_json()['data']
    validate.assert_called_once_with(payload['url'], allow_private=False)
    assert listed.get_json()['data'][0]['id'] == 'hook-1'
    assert deleted.status_code == 204


def test_webhook_allowlist_rejects_unlisted_destinations_and_preserves_it_on_delete():
    db = _WebhookDb()
    db.set_webhook_allowed_hosts(['hooks.example.test'])
    assert db.is_webhook_destination_allowed('https://hooks.example.test/anything')
    assert not db.is_webhook_destination_allowed('https://other.example.test')
    assert db.delete_webhook('hook-1')
    assert db.get_webhook_allowed_hosts() == ['hooks.example.test']

    client, db_patch = _client(db)
    payload = {'name': 'other', 'url': 'https://other.example.test', 'secret': 'a' * 16,
               'events': ['suggestion.created']}
    with db_patch, patch('api_service.api.v1.blueprint.validate_url'):
        response = client.post('/api/v1/webhooks', json=payload)
    assert response.status_code == 400


def test_webhook_allowlist_settings_are_normalized():
    db = _WebhookDb()
    client, db_patch = _client(db)
    with db_patch:
        response = client.put('/api/v1/webhooks/settings', json={
            'allowed_hosts': ['HOOKS.example.test', 'hooks.example.test'],
        })
    assert response.status_code == 200
    assert response.get_json()['data']['allowed_hosts'] == ['hooks.example.test']


def test_webhook_delivery_status_and_manual_retry_are_admin_only():
    db = MagicMock()
    db.list_webhook_deliveries.return_value = [{'id': 4, 'status': 'failed', 'event_type': 'run.failed'}]
    db.retry_webhook_delivery.return_value = True
    client, db_patch = _client(db)
    with db_patch:
        listed = client.get('/api/v1/webhooks/deliveries')
        retried = client.post('/api/v1/webhooks/deliveries/4/retry')
    assert listed.get_json()['data'] == db.list_webhook_deliveries.return_value
    assert retried.get_json()['data'] == {'id': 4, 'status': 'queued'}
    db.retry_webhook_delivery.assert_called_once_with(4)


def test_webhook_worker_signs_and_marks_successful_delivery():
    db = MagicMock()
    db.get_due_webhook_deliveries.return_value = [{
        'id': 1, 'event_id': 'event-1', 'event_type': 'run.failed', 'url': 'https://hooks.example.test',
        'secret': 'a' * 16, 'allow_private': 0, 'payload': '{"job_id":7}', 'retry_count': 0,
    }]
    response = MagicMock(status_code=204)
    with patch('api_service.jobs.webhook_worker.DatabaseManager', return_value=db), \
            patch('api_service.jobs.webhook_worker.validate_url'), \
            patch('api_service.jobs.webhook_worker.requests.post', return_value=response) as post:
        run_webhook_worker()
    assert post.call_args.kwargs['headers']['X-SuggestArr-Signature'].startswith('sha256=')
    db.update_webhook_delivery.assert_called_once_with(1, 'delivered', 0)


def test_webhook_worker_retries_a_failed_delivery():
    db = MagicMock()
    db.get_due_webhook_deliveries.return_value = [{
        'id': 1, 'event_id': 'event-1', 'event_type': 'run.failed', 'url': 'https://hooks.example.test',
        'secret': 'a' * 16, 'allow_private': 0, 'payload': '{}', 'retry_count': 0,
    }]
    response = MagicMock(status_code=503)
    with patch('api_service.jobs.webhook_worker.DatabaseManager', return_value=db), \
            patch('api_service.jobs.webhook_worker.validate_url'), \
            patch('api_service.jobs.webhook_worker.requests.post', return_value=response):
        run_webhook_worker()
    assert db.update_webhook_delivery.call_args.args[:3] == (1, 'queued', 1)


def test_webhook_worker_retries_timeout_and_ssrf_rejection_without_posting():
    item = {
        'id': 1, 'event_id': 'event-1', 'event_type': 'run.failed', 'url': 'https://hooks.example.test',
        'secret': 'a' * 16, 'allow_private': 0, 'payload': '{}', 'retry_count': 0,
    }
    db = MagicMock()
    db.get_due_webhook_deliveries.return_value = [item]
    with patch('api_service.jobs.webhook_worker.DatabaseManager', return_value=db), \
            patch('api_service.jobs.webhook_worker.validate_url'), \
            patch('api_service.jobs.webhook_worker.requests.post', side_effect=__import__('requests').Timeout):
        run_webhook_worker()
    assert db.update_webhook_delivery.call_args.args[:3] == (1, 'queued', 1)

    db.reset_mock()
    db.get_due_webhook_deliveries.return_value = [item]
    with patch('api_service.jobs.webhook_worker.DatabaseManager', return_value=db), \
            patch('api_service.jobs.webhook_worker.validate_url', side_effect=ValueError('blocked')), \
            patch('api_service.jobs.webhook_worker.requests.post') as post:
        run_webhook_worker()
    post.assert_not_called()
    assert db.update_webhook_delivery.call_args.args[:3] == (1, 'queued', 1)


def test_webhook_events_are_versioned_and_manual_retry_only_requeues_failures():
    db = _WebhookDb()
    assert db.enqueue_webhook_event('suggestion.created', {'tmdb_id': '42'}) == 1
    row = db.connection.execute('SELECT id, event_id, payload FROM webhook_deliveries').fetchone()
    assert json.loads(row[2]) == {'version': 1, 'event': 'suggestion.created', 'data': {'tmdb_id': '42'}}
    assert not db.retry_webhook_delivery(row[0])
    db.update_webhook_delivery(row[0], 'failed', retry_count=5, error='timeout')
    assert db.retry_webhook_delivery(row[0])
    assert db.connection.execute('SELECT event_id FROM webhook_deliveries WHERE id = ?', (row[0],)).fetchone()[0] == row[1]
    delivery = db.list_webhook_deliveries()[0]
    assert delivery['id'] == row[0]
    assert delivery['status'] == 'queued'
    assert delivery['retry_count'] == 0
    assert 'secret' not in delivery and 'payload' not in delivery


def test_job_completion_and_skip_events_are_queued():
    manager = object.__new__(JobManager)
    manager.logger = MagicMock()
    manager.repository = MagicMock()
    manager.repository.get_job.return_value = {'name': 'Test', 'job_type': 'discover'}

    async def executor(*_args, **_kwargs):
        return None

    manager._job_executors = {'discover': executor}
    manager._should_pause_for_suggestarr_approvals = lambda _job: False

    async def no_pause(_job):
        return False

    manager._should_pause_for_pending_requests = no_pause
    with patch('api_service.jobs.job_manager.observe_job'):
        manager._execute_job(7, 9)
    manager.repository.db.enqueue_webhook_event.assert_called_with(
        'job.completed', {'job_id': 7, 'job_type': 'discover', 'execution_id': 9},
    )

    manager.repository.db.enqueue_webhook_event.reset_mock()

    async def pause(_job):
        return True

    manager._should_pause_for_pending_requests = pause
    with patch('api_service.jobs.job_manager.observe_job'):
        manager._execute_job(7, 9)
    manager.repository.db.enqueue_webhook_event.assert_called_with(
        'job.skipped', {
            'job_id': 7, 'job_type': 'discover', 'execution_id': 9,
            'reason': 'pending_requests_awaiting_approval',
        },
    )


def test_successful_seer_submission_queues_webhook_event():
    class Seer:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def init(self):
            return None

        async def submit_queued_request(self, _payload):
            return True

    db = MagicMock()
    db.expire_pending_approvals.return_value = 0
    db.check_request_exists.return_value = False
    db.get_due_requests.return_value = [{
        'id': 7, 'tmdb_id': '42', 'media_type': 'movie', 'retry_count': 0,
        'job_id': 3, 'payload': '{}',
    }]
    with patch('api_service.jobs.queue_worker.DatabaseManager', return_value=db), \
            patch('api_service.jobs.queue_worker.ConfigService.get_runtime_config', return_value={}), \
            patch('api_service.jobs.queue_worker.SeerClient', return_value=Seer()):
        assert asyncio.run(_run_worker()) == 1
    db.enqueue_webhook_event.assert_called_once_with(
        'request.submitted', {
            'tmdb_id': '42', 'media_type': 'movie', 'job_id': 3,
            'execution_id': None, 'delivery_id': 7,
        }
    )
