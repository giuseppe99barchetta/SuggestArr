from unittest.mock import MagicMock, patch
import asyncio

from flask import Flask, g

from api_service.api.v1.blueprint import public_api_v1_bp
from api_service.jobs.webhook_worker import run_webhook_worker
from api_service.jobs.queue_worker import _run_worker


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
        'request.submitted', {'tmdb_id': '42', 'media_type': 'movie', 'job_id': 3}
    )
