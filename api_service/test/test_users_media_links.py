"""
Tests for the media profile linking endpoints in users/routes.py.

Covers endpoints not tested by test_users_routes.py:
  GET    /api/users/me/links                   — list linked media accounts
  POST   /api/users/me/link/jellyfin           — link Jellyfin account
  POST   /api/users/me/link/emby               — link Emby account
  GET    /api/users/me/link/<prov>/users       — list users from provider server
  DELETE /api/users/me/link/<provider>         — unlink account
  GET    /api/users/me/link/plex/oauth-start   — start Plex OAuth PIN flow
  POST   /api/users/me/link/plex/oauth-poll    — poll Plex OAuth PIN status

Strategy
--------
A minimal Flask app registers the users blueprint with DatabaseManager
replaced by an in-memory FakeDB that supports media profile operations.
g.current_user is injected by a before_request hook; SUGGESTARR_AUTH_DISABLED
bypasses JWT enforcement so we don't need real tokens.

External HTTP calls (Plex.tv, Jellyfin) are patched out.
"""
import os
import unittest
from unittest.mock import patch, MagicMock

import logging
logging.disable(logging.CRITICAL)

TEST_SECRET = "test-secret-for-media-link-tests-not-for-production"
os.environ['SUGGESTARR_SECRET_KEY'] = TEST_SECRET


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class _MediaLinkBase(unittest.TestCase):
    """
    Minimal Flask app with users blueprint and a FakeDB that supports
    media profile CRUD (get_user_media_profiles, create_user_media_profile,
    delete_user_media_profile).  The auth_user_count stub is provided so that
    the enforcement middleware doesn't crash when AUTH_DISABLED is checked.
    """

    _CALLER = {"id": "1", "username": "admin", "role": "admin"}

    def setUp(self):
        os.environ['SUGGESTARR_AUTH_DISABLED'] = 'true'
        os.environ['SUGGESTARR_SECRET_KEY'] = TEST_SECRET
        self._caller = dict(self._CALLER)
        self._profiles: list = []
        self._build_fake_db()
        self._setup_app()

    def tearDown(self):
        os.environ.pop('SUGGESTARR_AUTH_DISABLED', None)
        from api_service.auth.middleware import invalidate_setup_cache
        invalidate_setup_cache()
        for p in self._patches:
            p.stop()

    # ------------------------------------------------------------------
    # FakeDB
    # ------------------------------------------------------------------

    def _build_fake_db(self):
        profiles = self._profiles

        class FakeDB:
            def __init__(self_inner):
                pass

            def get_auth_user_count(self_inner):
                return 1  # setup mode guard: pretend there's 1 user

            def get_user_media_profiles(self_inner, user_id):
                return [
                    {k: v for k, v in p.items() if k != 'access_token'}
                    for p in profiles if p['user_id'] == user_id
                ]

            def create_user_media_profile(self_inner, user_id, provider,
                                          external_user_id, external_username,
                                          access_token=None):
                profiles.append({
                    'id': len(profiles) + 1,
                    'user_id': user_id,
                    'provider': provider,
                    'external_user_id': external_user_id,
                    'external_username': external_username,
                    'access_token': access_token,
                    'created_at': '2025-01-01 00:00:00',
                })

            def delete_user_media_profile(self_inner, user_id, provider):
                for i, p in enumerate(profiles):
                    if p['user_id'] == user_id and p['provider'] == provider:
                        del profiles[i]
                        return True
                return False

        self.FakeDB = FakeDB

    # ------------------------------------------------------------------
    # Flask app setup
    # ------------------------------------------------------------------

    def _setup_app(self):
        from flask import Flask, g
        from api_service.blueprints.users.routes import users_bp
        from api_service.auth.middleware import enforce_authentication, invalidate_setup_cache

        invalidate_setup_cache()

        app = Flask(__name__)
        app.config['TESTING'] = True

        caller_ref = self

        @app.before_request
        def inject_caller():
            g.current_user = caller_ref._caller

        self._patches = [
            patch('api_service.blueprints.users.routes.DatabaseManager', self.FakeDB),
            patch('api_service.auth.middleware.DatabaseManager', self.FakeDB),
        ]
        for p in self._patches:
            p.start()

        app.before_request(enforce_authentication)
        app.register_blueprint(users_bp, url_prefix='/api/users')

        self.app = app
        self.client = app.test_client()


# ---------------------------------------------------------------------------
# GET /api/users/me/links
# ---------------------------------------------------------------------------

class TestGetMyLinks(_MediaLinkBase):

    def test_returns_empty_list_initially(self):
        resp = self.client.get('/api/users/me/links')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), [])

    def test_returns_linked_profiles(self):
        self._profiles.append({
            'id': 1, 'user_id': 1, 'provider': 'jellyfin',
            'external_user_id': 'jf-123', 'external_username': 'alice',
            'access_token': None, 'created_at': '2025-01-01 00:00:00',
        })
        resp = self.client.get('/api/users/me/links')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['provider'], 'jellyfin')
        self.assertEqual(data[0]['external_username'], 'alice')

    def test_excludes_access_token_from_response(self):
        self._profiles.append({
            'id': 1, 'user_id': 1, 'provider': 'plex',
            'external_user_id': 'plex-456', 'external_username': 'alice',
            'access_token': 'super-secret-token', 'created_at': '2025-01-01 00:00:00',
        })
        resp = self.client.get('/api/users/me/links')
        data = resp.get_json()
        for item in data:
            self.assertNotIn('access_token', item)

    def test_only_returns_current_user_profiles(self):
        # Profile for user 1 (current caller)
        self._profiles.append({
            'id': 1, 'user_id': 1, 'provider': 'jellyfin',
            'external_user_id': 'jf-1', 'external_username': 'alice',
            'access_token': None, 'created_at': '2025-01-01 00:00:00',
        })
        # Profile for a different user
        self._profiles.append({
            'id': 2, 'user_id': 99, 'provider': 'jellyfin',
            'external_user_id': 'jf-99', 'external_username': 'other',
            'access_token': None, 'created_at': '2025-01-01 00:00:00',
        })
        resp = self.client.get('/api/users/me/links')
        data = resp.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['external_username'], 'alice')


# ---------------------------------------------------------------------------
# POST /api/users/me/link/jellyfin
# ---------------------------------------------------------------------------

class TestLinkJellyfin(_MediaLinkBase):

    def test_link_success_returns_200(self):
        resp = self.client.post('/api/users/me/link/jellyfin',
                                json={"external_user_id": "jf-123",
                                      "external_username": "alice"})
        self.assertEqual(resp.status_code, 200)

    def test_link_success_response_contains_expected_fields(self):
        resp = self.client.post('/api/users/me/link/jellyfin',
                                json={"external_user_id": "jf-123",
                                      "external_username": "alice"})
        data = resp.get_json()
        self.assertIn('message', data)
        self.assertIn('external_username', data)
        self.assertEqual(data['external_username'], 'alice')

    def test_link_stores_profile_in_db(self):
        self.client.post('/api/users/me/link/jellyfin',
                         json={"external_user_id": "jf-123",
                               "external_username": "alice"})
        self.assertEqual(len(self._profiles), 1)
        self.assertEqual(self._profiles[0]['provider'], 'jellyfin')
        self.assertEqual(self._profiles[0]['external_user_id'], 'jf-123')

    def test_missing_external_user_id_returns_400(self):
        resp = self.client.post('/api/users/me/link/jellyfin',
                                json={"external_username": "alice"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.get_json())

    def test_missing_external_username_returns_400(self):
        resp = self.client.post('/api/users/me/link/jellyfin',
                                json={"external_user_id": "jf-123"})
        self.assertEqual(resp.status_code, 400)

    def test_empty_body_returns_400(self):
        resp = self.client.post('/api/users/me/link/jellyfin', json={})
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# POST /api/users/me/link/emby
# ---------------------------------------------------------------------------

class TestLinkEmby(_MediaLinkBase):

    def test_link_emby_success(self):
        resp = self.client.post('/api/users/me/link/emby',
                                json={"external_user_id": "emby-789",
                                      "external_username": "alice"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('Emby', data.get('message', ''))
        self.assertEqual(data['external_username'], 'alice')

    def test_link_emby_stores_provider_correctly(self):
        self.client.post('/api/users/me/link/emby',
                         json={"external_user_id": "emby-789",
                               "external_username": "alice"})
        self.assertEqual(self._profiles[0]['provider'], 'emby')

    def test_link_emby_missing_fields_returns_400(self):
        resp = self.client.post('/api/users/me/link/emby', json={})
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# DELETE /api/users/me/link/<provider>
# ---------------------------------------------------------------------------

class TestUnlinkProvider(_MediaLinkBase):

    def setUp(self):
        super().setUp()
        self._profiles.append({
            'id': 1, 'user_id': 1, 'provider': 'jellyfin',
            'external_user_id': 'jf-123', 'external_username': 'alice',
            'access_token': None, 'created_at': '2025-01-01 00:00:00',
        })

    def test_unlink_existing_provider_returns_200(self):
        resp = self.client.delete('/api/users/me/link/jellyfin')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('message', data)

    def test_unlink_removes_profile_from_db(self):
        self.client.delete('/api/users/me/link/jellyfin')
        self.assertEqual(len(self._profiles), 0)

    def test_unlink_nonexistent_provider_returns_404(self):
        resp = self.client.delete('/api/users/me/link/plex')
        self.assertEqual(resp.status_code, 404)
        self.assertIn('error', resp.get_json())

    def test_invalid_provider_name_returns_400(self):
        resp = self.client.delete('/api/users/me/link/invalid_provider')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.get_json())

    def test_plex_provider_is_valid(self):
        """Plex is a valid provider; 404 when not linked (not 400)."""
        resp = self.client.delete('/api/users/me/link/plex')
        self.assertEqual(resp.status_code, 404)

    def test_emby_provider_is_valid(self):
        """Emby is a valid provider; 404 when not linked (not 400)."""
        resp = self.client.delete('/api/users/me/link/emby')
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# GET /api/users/me/link/<provider>/users
# ---------------------------------------------------------------------------

class TestListProviderUsers(_MediaLinkBase):

    def test_unsupported_provider_plex_returns_400(self):
        resp = self.client.get('/api/users/me/link/plex/users')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.get_json())

    def test_unsupported_provider_trakt_returns_400(self):
        resp = self.client.get('/api/users/me/link/trakt/users')
        self.assertEqual(resp.status_code, 400)

    def test_not_configured_returns_503(self):
        with patch('api_service.services.config_service.ConfigService.get_runtime_config',
                   return_value={}):
            resp = self.client.get('/api/users/me/link/jellyfin/users')
        self.assertEqual(resp.status_code, 503)
        self.assertIn('error', resp.get_json())

    def test_missing_token_returns_503(self):
        with patch('api_service.services.config_service.ConfigService.get_runtime_config',
                   return_value={'JELLYFIN_API_URL': 'http://jf.local',
                                 'JELLYFIN_TOKEN': ''}):
            resp = self.client.get('/api/users/me/link/jellyfin/users')
        self.assertEqual(resp.status_code, 503)

    def test_http_error_returns_502(self):
        with patch('api_service.services.config_service.ConfigService.get_runtime_config',
                   return_value={'JELLYFIN_API_URL': 'http://jf.local',
                                 'JELLYFIN_TOKEN': 'token123'}):
            with patch('api_service.blueprints.users.routes.http_requests.get',
                       side_effect=Exception("connection refused")):
                resp = self.client.get('/api/users/me/link/jellyfin/users')
        self.assertEqual(resp.status_code, 502)

    def test_success_returns_user_list(self):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"Id": "user1", "Name": "Alice"},
            {"Id": "user2", "Name": "Bob"},
        ]
        mock_response.raise_for_status.return_value = None

        with patch('api_service.services.config_service.ConfigService.get_runtime_config',
                   return_value={'JELLYFIN_API_URL': 'http://jf.local',
                                 'JELLYFIN_TOKEN': 'token123'}):
            with patch('api_service.blueprints.users.routes.http_requests.get',
                       return_value=mock_response):
                resp = self.client.get('/api/users/me/link/jellyfin/users')

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['id'], 'user1')
        self.assertEqual(data[1]['name'], 'Bob')

    def test_emby_provider_also_supported(self):
        mock_response = MagicMock()
        mock_response.json.return_value = [{"Id": "e1", "Name": "Carol"}]
        mock_response.raise_for_status.return_value = None

        with patch('api_service.services.config_service.ConfigService.get_runtime_config',
                   return_value={'JELLYFIN_API_URL': 'http://emby.local',
                                 'JELLYFIN_TOKEN': 'token456'}):
            with patch('api_service.blueprints.users.routes.http_requests.get',
                       return_value=mock_response):
                resp = self.client.get('/api/users/me/link/emby/users')

        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# GET /api/users/me/link/plex/oauth-start
# ---------------------------------------------------------------------------

class TestPlexOAuthStart(_MediaLinkBase):

    def test_start_success_returns_pin_and_url(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 12345, "code": "ABCD"}
        mock_response.raise_for_status.return_value = None

        with patch('api_service.blueprints.users.routes.http_requests.post',
                   return_value=mock_response):
            resp = self.client.get('/api/users/me/link/plex/oauth-start')

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('pin_id', data)
        self.assertIn('auth_url', data)
        self.assertEqual(data['pin_id'], 12345)
        self.assertIn('ABCD', data['auth_url'])

    def test_start_http_error_returns_502(self):
        with patch('api_service.blueprints.users.routes.http_requests.post',
                   side_effect=Exception("timeout")):
            resp = self.client.get('/api/users/me/link/plex/oauth-start')

        self.assertEqual(resp.status_code, 502)
        self.assertIn('error', resp.get_json())


# ---------------------------------------------------------------------------
# POST /api/users/me/link/plex/oauth-poll
# ---------------------------------------------------------------------------

class TestPlexOAuthPoll(_MediaLinkBase):

    def test_missing_pin_id_returns_400(self):
        resp = self.client.post('/api/users/me/link/plex/oauth-poll', json={})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.get_json())

    def test_null_pin_id_returns_400(self):
        resp = self.client.post('/api/users/me/link/plex/oauth-poll',
                                json={"pin_id": None})
        self.assertEqual(resp.status_code, 400)

    def test_pending_when_no_auth_token(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"authToken": None}
        mock_response.raise_for_status.return_value = None

        with patch('api_service.blueprints.users.routes.http_requests.get',
                   return_value=mock_response):
            resp = self.client.post('/api/users/me/link/plex/oauth-poll',
                                    json={"pin_id": 12345})

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'pending')

    def test_http_error_on_pin_poll_returns_502(self):
        with patch('api_service.blueprints.users.routes.http_requests.get',
                   side_effect=Exception("timeout")):
            resp = self.client.post('/api/users/me/link/plex/oauth-poll',
                                    json={"pin_id": 12345})

        self.assertEqual(resp.status_code, 502)

    def test_linked_when_auth_token_present(self):
        poll_response = MagicMock()
        poll_response.json.return_value = {"authToken": "plex-token-abc"}
        poll_response.raise_for_status.return_value = None

        user_response = MagicMock()
        user_response.json.return_value = {
            "id": 67890, "username": "plexuser", "email": "plex@example.com"
        }
        user_response.raise_for_status.return_value = None

        with patch('api_service.blueprints.users.routes.http_requests.get',
                   side_effect=[poll_response, user_response]):
            resp = self.client.post('/api/users/me/link/plex/oauth-poll',
                                    json={"pin_id": 12345})

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'linked')
        self.assertEqual(data['external_username'], 'plexuser')

    def test_linked_stores_profile_with_token(self):
        poll_response = MagicMock()
        poll_response.json.return_value = {"authToken": "plex-token-abc"}
        poll_response.raise_for_status.return_value = None

        user_response = MagicMock()
        user_response.json.return_value = {"id": 67890, "username": "plexuser"}
        user_response.raise_for_status.return_value = None

        with patch('api_service.blueprints.users.routes.http_requests.get',
                   side_effect=[poll_response, user_response]):
            self.client.post('/api/users/me/link/plex/oauth-poll',
                             json={"pin_id": 12345})

        self.assertEqual(len(self._profiles), 1)
        stored = self._profiles[0]
        self.assertEqual(stored['provider'], 'plex')
        self.assertEqual(stored['access_token'], 'plex-token-abc')
        self.assertEqual(stored['external_username'], 'plexuser')

    def test_user_info_error_returns_502(self):
        poll_response = MagicMock()
        poll_response.json.return_value = {"authToken": "plex-token-abc"}
        poll_response.raise_for_status.return_value = None

        with patch('api_service.blueprints.users.routes.http_requests.get',
                   side_effect=[poll_response, Exception("user info failed")]):
            resp = self.client.post('/api/users/me/link/plex/oauth-poll',
                                    json={"pin_id": 12345})

        self.assertEqual(resp.status_code, 502)

    def test_linked_uses_email_when_username_absent(self):
        """username fallback: use email if username field is absent."""
        poll_response = MagicMock()
        poll_response.json.return_value = {"authToken": "tok"}
        poll_response.raise_for_status.return_value = None

        user_response = MagicMock()
        user_response.json.return_value = {"id": 1, "email": "user@plex.tv"}
        user_response.raise_for_status.return_value = None

        with patch('api_service.blueprints.users.routes.http_requests.get',
                   side_effect=[poll_response, user_response]):
            resp = self.client.post('/api/users/me/link/plex/oauth-poll',
                                    json={"pin_id": 99})

        data = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(data['external_username'], 'user@plex.tv')


if __name__ == '__main__':
    unittest.main()
