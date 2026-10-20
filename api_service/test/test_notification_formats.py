"""Tests for Discord, ntfy and Telegram notifications built on the webhook queue."""
import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, g

from api_service.api.v1.blueprint import public_api_v1_bp
from api_service.db.components.webhook_mixin import WebhookMixin
from api_service.services.notification_formats import (
    describe_event,
    notification_target_error,
    render_notification,
)


class _NotifyDb(WebhookMixin):
    db_type = 'sqlite'

    def __init__(self, hooks):
        self.connection = sqlite3.connect(':memory:')
        self.config = {'items': hooks}
        self.connection.execute('''CREATE TABLE webhook_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT, webhook_id TEXT,
            event_type TEXT, url TEXT, secret TEXT, allow_private INTEGER, payload TEXT,
            status TEXT DEFAULT 'queued', retry_count INTEGER DEFAULT 0,
            next_attempt_at TIMESTAMP, last_error TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)''')
        self.connection.execute('CREATE TABLE discover_jobs (id INTEGER PRIMARY KEY, name TEXT)')
        self.connection.execute("INSERT INTO discover_jobs VALUES (4, 'Weekend picks')")

    def get_connection(self):
        return self.connection

    def get_integration(self, _service):
        return self.config

    def get_metadata(self, media_id, media_type):
        return {'title': 'Dune'} if (media_id, media_type) == ('438631', 'movie') else None

    def deliveries(self):
        rows = self.connection.execute('SELECT webhook_id, url, payload FROM webhook_deliveries ORDER BY id').fetchall()
        return {hook: (url, json.loads(payload)) for hook, url, payload in rows}


def _hook(hook_id, fmt, url):
    return {'id': hook_id, 'url': url, 'secret': 'a' * 16, 'events': ['request.submitted', 'run.failed'], 'format': fmt}


def test_event_text_names_the_title_or_job_and_falls_back_to_ids():
    assert describe_event('request.submitted', {'tmdb_id': '1', 'media_type': 'movie'}, title='Dune') == 'Requested in Seer: Dune'
    assert describe_event('request.failed', {'tmdb_id': '1', 'media_type': 'tv'}) == 'Request failed: tv 1'
    assert describe_event('run.failed', {'job_id': 4, 'reason': 'timeout'}, job_name='Daily') == 'Job run failed: Daily (timeout)'
    assert describe_event('job.completed', {'job_id': 4}) == 'Job finished: #4'


def test_each_service_gets_its_own_body_and_url():
    assert render_notification('discord', 'https://discord.com/api/webhooks/1/x', 'Hi') == (
        'https://discord.com/api/webhooks/1/x', json.dumps({'content': 'Hi', 'username': 'SuggestArr'}))
    url, body = render_notification('ntfy', 'https://ntfy.example.test/sub/alerts', 'Hi')
    assert url == 'https://ntfy.example.test/sub/'
    assert json.loads(body) == {'topic': 'alerts', 'title': 'SuggestArr', 'message': 'Hi'}
    url, body = render_notification('telegram', 'https://api.telegram.org/botT/sendMessage?chat_id=-100', 'Hi')
    assert json.loads(body) == {'chat_id': '-100', 'text': 'Hi'}


def test_urls_missing_the_ntfy_topic_or_telegram_chat_are_explained():
    assert notification_target_error('ntfy', 'https://ntfy.sh/') is not None
    assert notification_target_error('ntfy', 'https://ntfy.sh/topic') is None
    assert notification_target_error('telegram', 'https://api.telegram.org/botT/sendMessage') is not None
    assert notification_target_error('discord', 'https://discord.com/api/webhooks/1/x') is None


def test_enqueued_events_are_rendered_per_destination_format():
    legacy = _hook('legacy', 'json', 'https://legacy.example.test')
    del legacy['format']  # saved before formats existed
    db = _NotifyDb([
        _hook('signed', 'json', 'https://hooks.example.test'),
        _hook('discord', 'discord', 'https://discord.com/api/webhooks/1/x'),
        _hook('ntfy', 'ntfy', 'https://ntfy.sh/alerts'),
        legacy,
    ])

    assert db.enqueue_webhook_event('request.submitted', {'tmdb_id': '438631', 'media_type': 'movie', 'job_id': 4}) == 4

    sent = db.deliveries()
    assert sent['signed'][1]['event'] == 'request.submitted'
    assert sent['legacy'][1]['data']['tmdb_id'] == '438631'
    assert sent['discord'][1]['content'] == 'Requested in Seer: Dune'
    assert sent['ntfy'] == ('https://ntfy.sh/', {'topic': 'alerts', 'title': 'SuggestArr', 'message': 'Requested in Seer: Dune'})


def test_job_events_use_the_job_name():
    db = _NotifyDb([_hook('discord', 'discord', 'https://discord.com/api/webhooks/1/x')])
    db.enqueue_webhook_event('run.failed', {'job_id': 4, 'job_type': 'discover', 'reason': 'Seer down'})
    assert db.deliveries()['discord'][1]['content'] == 'Job run failed: Weekend picks (Seer down)'


def _client(db):
    app = Flask(__name__)

    @app.before_request
    def admin():
        g.current_user = {'id': 1, 'username': 'admin', 'role': 'admin'}
        g.auth_method = 'test'
        g.api_key_id = None
        g.api_key_name = None

    app.register_blueprint(public_api_v1_bp, url_prefix='/api/v1')
    return app.test_client(), patch('api_service.api.v1.blueprint.DatabaseManager', return_value=db)


@pytest.mark.parametrize('payload, message', [
    ({'format': 'slack'}, 'format must be one of'),
    ({'format': 'telegram', 'url': 'https://api.telegram.org/botT/sendMessage'}, 'chat_id'),
])
def test_create_rejects_unknown_formats_and_unusable_urls(payload, message):
    db = MagicMock()
    client, db_patch = _client(db)
    body = {'name': 'Chat', 'url': 'https://discord.com/api/webhooks/1/x', 'events': ['run.failed'], **payload}
    with db_patch, patch('api_service.api.v1.blueprint.validate_url'):
        response = client.post('/api/v1/webhooks', json=body)
    assert response.status_code == 400
    assert message in response.get_json()['error']['message']
    db.create_webhook.assert_not_called()


def test_chat_formats_need_no_secret_but_signed_json_still_does():
    db = MagicMock()
    db.is_webhook_destination_allowed.return_value = True
    db.create_webhook.return_value = {'id': 'hook-1'}
    client, db_patch = _client(db)
    base = {'name': 'Chat', 'url': 'https://discord.com/api/webhooks/1/x', 'events': ['run.failed']}
    with db_patch, patch('api_service.api.v1.blueprint.validate_url'):
        created = client.post('/api/v1/webhooks', json={**base, 'format': 'discord'})
        unsigned = client.post('/api/v1/webhooks', json=base)
    assert created.status_code == 201
    saved = db.create_webhook.call_args.args[0]
    assert saved['format'] == 'discord' and len(saved['secret']) >= 16
    assert unsigned.status_code == 400
