import os
import sys
import types
import unittest
from unittest.mock import patch

from flask import Flask, g

from api_service.auth.limiter import limiter
from api_service.blueprints.jobs.routes import jobs_bp
from api_service.utils.asyncio_loop import run_coroutine_sync


class TestLlmConnectionRoute(unittest.TestCase):
    def setUp(self):
        os.environ['SUGGESTARR_AUTH_DISABLED'] = 'true'

        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.config['RATELIMIT_ENABLED'] = False
        self.app.secret_key = 'test-secret'

        @self.app.before_request
        def inject_admin():
            g.current_user = {"id": "1", "username": "admin", "role": "admin"}

        limiter.init_app(self.app)
        self.app.register_blueprint(jobs_bp, url_prefix='/api/jobs')
        self.client = self.app.test_client()

    def tearDown(self):
        os.environ.pop('SUGGESTARR_AUTH_DISABLED', None)

    def test_llm_connection_uses_provider_safe_minimum_tokens(self):
        calls = []

        class FakeCompletions:
            def create(self, **kwargs):
                calls.append(kwargs)
                return object()

        class FakeOpenAI:
            def __init__(self, **kwargs):
                self.chat = types.SimpleNamespace(
                    completions=FakeCompletions()
                )

        fake_openai_module = types.SimpleNamespace(OpenAI=FakeOpenAI)

        with patch.dict(sys.modules, {'openai': fake_openai_module}):
            response = self.client.post('/api/jobs/llm-test', json={
                'OPENAI_API_KEY': 'test-key',
                'OPENAI_BASE_URL': 'https://openrouter.ai/api/v1',
                'LLM_MODEL': 'test-model',
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls[0]['max_tokens'], 16)


class TestAsyncLoopCleanup(unittest.TestCase):
    def test_run_coroutine_sync_drains_pending_cleanup_task(self):
        state = {"closed": False}

        async def cleanup():
            state["closed"] = True

        async def main():
            import asyncio
            asyncio.create_task(cleanup())
            return "ok"

        self.assertEqual(run_coroutine_sync(main()), "ok")
        self.assertTrue(state["closed"])


class TestHealthLlmCheck(unittest.TestCase):
    def test_health_llm_check_does_not_create_async_client(self):
        from api_service.blueprints.health import routes as health_routes

        with patch(
            'api_service.services.llm.llm_service.is_llm_configured',
            return_value=True,
        ) as configured, patch(
            'api_service.services.llm.llm_service.get_llm_client',
            side_effect=AssertionError("should not create client"),
        ):
            self.assertEqual(health_routes._check_llm(), "ok")

        configured.assert_called_once()
