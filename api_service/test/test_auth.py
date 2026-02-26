"""
Tests for the authentication system.

Covers:
  - AuthService: password hashing, JWT issuance/verification, refresh tokens
  - enforce_authentication middleware: allow/deny, setup-mode, DISABLE_AUTH
  - require_role decorator: role matching, 401/403 responses
  - Auth blueprint endpoints: setup, login, refresh, logout, me, status
  - Timing-safe login (verify_password always called)

Strategy
--------
AuthService tests are pure unit tests with no Flask or database required.

Middleware and blueprint tests use a minimal Flask app with DatabaseManager
patched at every import site so no real DB is touched.  An in-memory
dict simulates the auth_users and refresh_tokens tables.
"""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import logging
logging.disable(logging.CRITICAL)

# Inject a stable test secret so secret_key.py never writes to disk.
TEST_SECRET = "test-secret-for-unit-tests-only-not-for-production"
os.environ['SUGGESTARR_SECRET_KEY'] = TEST_SECRET


# ---------------------------------------------------------------------------
# Helpers shared across test classes
# ---------------------------------------------------------------------------

def _make_valid_token(user_id=1, username="alice", role="admin"):
    """Return a valid JWT for use in test requests."""
    from api_service.auth.auth_service import AuthService
    return AuthService.create_access_token(user_id, username, role)


def _make_expired_token():
    """Return a JWT whose exp is in the past."""
    import jwt as pyjwt
    from api_service.auth.secret_key import load_secret_key
    past = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
    payload = {
        "sub": "1", "username": "alice", "role": "admin",
        "iat": past - timedelta(minutes=16), "exp": past, "jti": "x",
    }
    return pyjwt.encode(payload, load_secret_key(), algorithm="HS256")


# ---------------------------------------------------------------------------
# AuthService — pure unit tests
# ---------------------------------------------------------------------------

class TestAuthService(unittest.TestCase):
    """Cryptographic primitives: no Flask, no DB."""

    def setUp(self):
        from api_service.auth.secret_key import invalidate_cache
        invalidate_cache()
        os.environ['SUGGESTARR_SECRET_KEY'] = TEST_SECRET

    def tearDown(self):
        from api_service.auth.secret_key import invalidate_cache
        invalidate_cache()

    # --- Password hashing ---

    def test_correct_password_verifies(self):
        from api_service.auth.auth_service import AuthService
        h = AuthService.hash_password("hunter2")
        self.assertTrue(AuthService.verify_password("hunter2", h))

    def test_wrong_password_rejected(self):
        from api_service.auth.auth_service import AuthService
        h = AuthService.hash_password("hunter2")
        self.assertFalse(AuthService.verify_password("wrong", h))

    def test_malformed_hash_returns_false(self):
        from api_service.auth.auth_service import AuthService
        self.assertFalse(AuthService.verify_password("anything", "not-a-bcrypt-hash"))

    def test_each_hash_unique_for_same_input(self):
        from api_service.auth.auth_service import AuthService
        h1 = AuthService.hash_password("same")
        h2 = AuthService.hash_password("same")
        self.assertNotEqual(h1, h2)
        self.assertTrue(AuthService.verify_password("same", h1))
        self.assertTrue(AuthService.verify_password("same", h2))

    # --- JWT ---

    def test_valid_token_round_trips(self):
        from api_service.auth.auth_service import AuthService
        token = AuthService.create_access_token(42, "bob", "viewer")
        payload = AuthService.verify_access_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "42")
        self.assertEqual(payload["username"], "bob")
        self.assertEqual(payload["role"], "viewer")

    def test_expired_token_returns_none(self):
        from api_service.auth.auth_service import AuthService
        self.assertIsNone(AuthService.verify_access_token(_make_expired_token()))

    def test_tampered_signature_returns_none(self):
        import jwt as pyjwt
        from api_service.auth.auth_service import AuthService
        now = datetime.now(tz=timezone.utc)
        fake = pyjwt.encode(
            {"sub": "1", "username": "x", "role": "admin",
             "iat": now, "exp": now + timedelta(minutes=15), "jti": "y"},
            "wrong-secret", algorithm="HS256",
        )
        self.assertIsNone(AuthService.verify_access_token(fake))

    def test_garbage_token_returns_none(self):
        from api_service.auth.auth_service import AuthService
        self.assertIsNone(AuthService.verify_access_token("not.a.jwt.at.all"))

    def test_each_token_has_unique_jti(self):
        from api_service.auth.auth_service import AuthService
        p1 = AuthService.verify_access_token(AuthService.create_access_token(1, "a", "admin"))
        p2 = AuthService.verify_access_token(AuthService.create_access_token(1, "a", "admin"))
        self.assertNotEqual(p1["jti"], p2["jti"])

    # --- Refresh tokens ---

    def test_refresh_token_structure(self):
        from api_service.auth.auth_service import AuthService
        raw, digest = AuthService.generate_refresh_token()
        self.assertIsInstance(raw, str)
        self.assertEqual(len(digest), 64)   # SHA-256 hex
        self.assertNotEqual(raw, digest)

    def test_hash_refresh_token_deterministic(self):
        from api_service.auth.auth_service import AuthService
        raw, _ = AuthService.generate_refresh_token()
        self.assertEqual(
            AuthService.hash_refresh_token(raw),
            AuthService.hash_refresh_token(raw),
        )

    def test_refresh_tokens_unique(self):
        from api_service.auth.auth_service import AuthService
        r1, _ = AuthService.generate_refresh_token()
        r2, _ = AuthService.generate_refresh_token()
        self.assertNotEqual(r1, r2)


# ---------------------------------------------------------------------------
# Middleware — enforce_authentication
# ---------------------------------------------------------------------------

class TestMiddleware(unittest.TestCase):
    """
    Test enforce_authentication by calling it directly inside a Flask
    request context.  DatabaseManager is replaced with a configurable stub.
    """

    def setUp(self):
        from api_service.auth.secret_key import invalidate_cache
        invalidate_cache()
        from api_service.auth.middleware import invalidate_setup_cache
        invalidate_setup_cache()
        os.environ['SUGGESTARR_SECRET_KEY'] = TEST_SECRET
        os.environ.pop('SUGGESTARR_AUTH_DISABLED', None)

    def tearDown(self):
        from api_service.auth.middleware import invalidate_setup_cache
        invalidate_setup_cache()
        os.environ.pop('SUGGESTARR_AUTH_DISABLED', None)

    def _call_middleware(self, path, headers=None, user_count=1):
        """
        Run enforce_authentication for a synthetic request and return its result.
        Returns None if the middleware allows the request, or a (response, code) tuple.
        """
        from flask import Flask
        from api_service.auth.middleware import enforce_authentication, invalidate_setup_cache

        app = Flask(__name__)
        stub_db = MagicMock()
        stub_db.return_value.get_auth_user_count.return_value = user_count

        invalidate_setup_cache()

        with patch('api_service.auth.middleware.DatabaseManager', stub_db):
            with app.test_request_context(path, headers=headers or {}):
                return enforce_authentication()

    # --- Non-API paths always pass ---

    def test_frontend_root_always_passes(self):
        self.assertIsNone(self._call_middleware('/'))

    def test_frontend_asset_always_passes(self):
        self.assertIsNone(self._call_middleware('/assets/main.js'))

    # --- Explicit public routes ---

    def test_health_live_is_public(self):
        self.assertIsNone(self._call_middleware('/api/health/live'))

    def test_auth_login_is_public(self):
        self.assertIsNone(self._call_middleware('/api/auth/login'))

    def test_auth_refresh_is_public(self):
        self.assertIsNone(self._call_middleware('/api/auth/refresh'))

    def test_auth_setup_is_public(self):
        self.assertIsNone(self._call_middleware('/api/auth/setup'))

    def test_auth_status_is_public(self):
        self.assertIsNone(self._call_middleware('/api/auth/status'))

    # --- Setup mode (no users) opens everything ---

    def test_setup_mode_opens_protected_routes(self):
        result = self._call_middleware('/api/config/fetch', user_count=0)
        self.assertIsNone(result)

    # --- Protected routes require a Bearer token ---

    def test_no_token_returns_401(self):
        result = self._call_middleware('/api/config/fetch', user_count=1)
        self.assertIsNotNone(result)
        _resp, code = result
        self.assertEqual(code, 401)

    def test_invalid_token_returns_401(self):
        result = self._call_middleware(
            '/api/config/fetch',
            headers={"Authorization": "Bearer garbage"},
            user_count=1,
        )
        self.assertIsNotNone(result)
        _, code = result
        self.assertEqual(code, 401)

    def test_expired_token_returns_401(self):
        result = self._call_middleware(
            '/api/config/fetch',
            headers={"Authorization": f"Bearer {_make_expired_token()}"},
            user_count=1,
        )
        self.assertIsNotNone(result)
        _, code = result
        self.assertEqual(code, 401)

    def test_valid_token_passes(self):
        token = _make_valid_token()
        result = self._call_middleware(
            '/api/config/fetch',
            headers={"Authorization": f"Bearer {token}"},
            user_count=1,
        )
        self.assertIsNone(result)

    def test_wrong_scheme_returns_401(self):
        result = self._call_middleware(
            '/api/config/fetch',
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
            user_count=1,
        )
        _, code = result
        self.assertEqual(code, 401)

    # --- DISABLE_AUTH escape hatch ---

    def test_disable_auth_bypasses_protected_routes(self):
        os.environ['SUGGESTARR_AUTH_DISABLED'] = 'true'
        result = self._call_middleware('/api/config/fetch', user_count=1)
        self.assertIsNone(result)

    def test_disable_auth_false_still_enforces(self):
        os.environ['SUGGESTARR_AUTH_DISABLED'] = 'false'
        result = self._call_middleware('/api/config/fetch', user_count=1)
        _, code = result
        self.assertEqual(code, 401)

    # --- Error response must not leak internals ---

    def test_401_body_has_no_debug_info(self):
        result = self._call_middleware('/api/config/fetch', user_count=1)
        resp, _ = result
        data = resp.get_json()
        body = str(data).lower()
        self.assertIn("error", body)
        self.assertNotIn("traceback", body)
        self.assertNotIn("exception", body)
        self.assertNotIn("token", body)


# ---------------------------------------------------------------------------
# require_role decorator
# ---------------------------------------------------------------------------

class TestRequireRole(unittest.TestCase):
    """Test the require_role decorator in isolation via a minimal Flask app."""

    def _app_with_route(self, route_roles, current_user):
        from flask import Flask, g
        from api_service.auth.middleware import require_role

        app = Flask(__name__)

        @app.route('/test')
        @require_role(*route_roles)
        def protected():
            return "ok", 200

        @app.before_request
        def set_user():
            g.current_user = current_user

        return app

    def test_matching_role_allowed(self):
        app = self._app_with_route(["admin"], {"id": "1", "username": "a", "role": "admin"})
        resp = app.test_client().get('/test')
        self.assertEqual(resp.status_code, 200)

    def test_wrong_role_returns_403(self):
        app = self._app_with_route(["admin"], {"id": "2", "username": "b", "role": "viewer"})
        resp = app.test_client().get('/test')
        self.assertEqual(resp.status_code, 403)
        self.assertIn("error", resp.get_json())

    def test_no_current_user_returns_401(self):
        from flask import Flask
        from api_service.auth.middleware import require_role

        app = Flask(__name__)

        @app.route('/test')
        @require_role("admin")
        def protected():
            return "ok", 200

        # No before_request sets g.current_user
        resp = app.test_client().get('/test')
        self.assertEqual(resp.status_code, 401)

    def test_multiple_roles_any_match(self):
        app = self._app_with_route(
            ["admin", "viewer"],
            {"id": "3", "username": "c", "role": "viewer"},
        )
        resp = app.test_client().get('/test')
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# Auth blueprint — endpoint-level tests
# ---------------------------------------------------------------------------

class _AuthBlueprintBase(unittest.TestCase):
    """
    Base for blueprint tests.

    Creates a minimal Flask app with the auth blueprint registered and
    DatabaseManager replaced by an in-memory dict store.
    """

    def setUp(self):
        from api_service.auth.secret_key import invalidate_cache
        invalidate_cache()
        from api_service.auth.middleware import invalidate_setup_cache
        invalidate_setup_cache()
        os.environ['SUGGESTARR_SECRET_KEY'] = TEST_SECRET
        os.environ['SUGGESTARR_AUTH_DISABLED'] = 'true'   # bypass middleware for blueprint tests

        # In-memory stores
        self._users: dict = {}     # username → row dict
        self._user_id_seq = iter(range(1, 10000))
        self._refresh_tokens: dict = {}   # hash → row dict

        self._build_fake_db()
        self._setup_app()

    def tearDown(self):
        os.environ.pop('SUGGESTARR_AUTH_DISABLED', None)
        from api_service.auth.middleware import invalidate_setup_cache
        invalidate_setup_cache()
        from api_service.auth.secret_key import invalidate_cache
        invalidate_cache()
        for p in self._patches:
            p.stop()

    def _build_fake_db(self):
        """Create a FakeDB class closed over this test's in-memory dicts."""
        users = self._users
        uid_seq = self._user_id_seq
        tokens = self._refresh_tokens

        class FakeDB:
            def __init__(self_inner):
                pass

            def get_auth_user_count(self_inner):
                return len(users)

            def create_auth_user(self_inner, username, password_hash, role='viewer'):
                uid = next(uid_seq)
                users[username] = {
                    "id": uid, "username": username,
                    "password_hash": password_hash, "role": role,
                    "is_active": True, "last_login": None,
                }
                return uid

            def get_auth_user_by_username(self_inner, username):
                return users.get(username)

            def get_auth_user_by_id(self_inner, user_id):
                for u in users.values():
                    if u["id"] == user_id:
                        return u
                return None

            def update_last_login(self_inner, user_id):
                for u in users.values():
                    if u["id"] == user_id:
                        u["last_login"] = datetime.utcnow().isoformat()

            def store_refresh_token(self_inner, user_id, token_hash, expires_at):
                tokens[token_hash] = {
                    "id": len(tokens) + 1,
                    "user_id": user_id,
                    "expires_at": expires_at,
                    "revoked": False,
                }

            def get_refresh_token(self_inner, token_hash):
                row = tokens.get(token_hash)
                if row is None or row["revoked"]:
                    return None
                return {"id": row["id"], "user_id": row["user_id"], "expires_at": row["expires_at"]}

            def revoke_refresh_token(self_inner, token_hash):
                if token_hash in tokens:
                    tokens[token_hash]["revoked"] = True

        self.FakeDB = FakeDB

    def _setup_app(self):
        from flask import Flask, jsonify
        from api_service.blueprints.auth.routes import auth_bp
        from api_service.auth.middleware import enforce_authentication
        from api_service.auth.limiter import limiter

        app = Flask(__name__)
        app.config['TESTING'] = True

        # Patch DatabaseManager in every module that imports it
        self._patches = [
            patch('api_service.blueprints.auth.routes.DatabaseManager', self.FakeDB),
            patch('api_service.auth.middleware.DatabaseManager', self.FakeDB),
            patch('api_service.blueprints.auth.routes.load_env_vars',
                  return_value={'SETUP_COMPLETED': False}),
            # Disable limiter in tests to avoid rate-limit interference
            patch('api_service.blueprints.auth.routes.limiter.limit',
                  side_effect=lambda *a, **kw: (lambda f: f)),
        ]
        for p in self._patches:
            p.start()

        app.before_request(enforce_authentication)
        app.register_blueprint(auth_bp, url_prefix='/api/auth')

        @app.errorhandler(429)
        def handle_429(exc):
            return jsonify({"error": "Too many requests"}), 429

        self.app = app
        self.client = app.test_client()

    # --- Helpers ---

    def _create_user(self, username="alice", password="StrongPass1!", role="admin"):
        from api_service.auth.auth_service import AuthService
        db = self.FakeDB()
        pw_hash = AuthService.hash_password(password)
        return db.create_auth_user(username, pw_hash, role)

    def _login(self, username="alice", password="StrongPass1!"):
        return self.client.post('/api/auth/login',
                                json={"username": username, "password": password})


class TestAuthSetupEndpoint(_AuthBlueprintBase):

    def test_setup_creates_first_admin(self):
        resp = self.client.post('/api/auth/setup',
                                json={"username": "admin", "password": "StrongPass1!"})
        self.assertEqual(resp.status_code, 201)

    def test_setup_blocked_after_first_user(self):
        self._create_user()
        resp = self.client.post('/api/auth/setup',
                                json={"username": "hacker", "password": "StrongPass1!"})
        self.assertEqual(resp.status_code, 403)

    def test_setup_requires_both_fields(self):
        resp = self.client.post('/api/auth/setup', json={})
        self.assertEqual(resp.status_code, 400)

    def test_setup_enforces_min_password_length(self):
        from api_service.auth.auth_service import MIN_PASSWORD_LENGTH
        resp = self.client.post('/api/auth/setup',
                                json={"username": "admin",
                                      "password": "x" * (MIN_PASSWORD_LENGTH - 1)})
        self.assertEqual(resp.status_code, 400)


class TestAuthLoginEndpoint(_AuthBlueprintBase):

    def test_valid_login_returns_token(self):
        self._create_user("alice", "StrongPass1!")
        resp = self._login("alice", "StrongPass1!")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("access_token", data)
        self.assertIn("role", data)
        self.assertIn("username", data)

    def test_valid_login_sets_refresh_cookie(self):
        self._create_user("alice", "StrongPass1!")
        resp = self._login("alice", "StrongPass1!")
        self.assertIn("suggestarr_refresh", resp.headers.get("Set-Cookie", ""))

    def test_wrong_password_returns_401(self):
        self._create_user("alice", "StrongPass1!")
        resp = self._login("alice", "WrongPassword!")
        self.assertEqual(resp.status_code, 401)

    def test_nonexistent_user_returns_401(self):
        resp = self._login("nobody", "StrongPass1!")
        self.assertEqual(resp.status_code, 401)

    def test_missing_fields_returns_400(self):
        resp = self.client.post('/api/auth/login', json={})
        self.assertEqual(resp.status_code, 400)

    def test_verify_password_called_for_missing_user(self):
        """Timing safety: verify_password must be called even when username is absent."""
        from api_service.auth.auth_service import AuthService
        calls = []
        original = AuthService.verify_password.__func__ if hasattr(AuthService.verify_password, '__func__') else AuthService.verify_password

        with patch.object(AuthService, 'verify_password',
                          staticmethod(lambda pw, h: calls.append(1) or False)):
            self._login("no_such_user", "AnyPassword!")

        self.assertGreaterEqual(len(calls), 1,
            "verify_password must always be called to prevent timing-based username enumeration")

    def test_error_response_does_not_leak_hash(self):
        self._create_user("alice", "StrongPass1!")
        resp = self._login("alice", "WrongPassword!")
        body = str(resp.get_json()).lower()
        self.assertNotIn("hash", body)
        self.assertNotIn("bcrypt", body)
        self.assertNotIn("password", body)


class TestAuthRefreshEndpoint(_AuthBlueprintBase):

    def test_refresh_with_valid_cookie_returns_new_token(self):
        self._create_user("alice", "StrongPass1!")
        login_resp = self._login("alice", "StrongPass1!")
        self.assertEqual(login_resp.status_code, 200)

        refresh_resp = self.client.post('/api/auth/refresh')
        self.assertEqual(refresh_resp.status_code, 200)
        data = refresh_resp.get_json()
        self.assertIn("access_token", data)

    def test_refresh_without_cookie_returns_401(self):
        resp = self.client.post('/api/auth/refresh')
        self.assertEqual(resp.status_code, 401)

    def test_refresh_with_expired_token_returns_401(self):
        self._create_user("alice", "StrongPass1!")
        from api_service.auth.auth_service import AuthService
        raw = "test-raw-token-for-expiry"
        token_hash = AuthService.hash_refresh_token(raw)
        past = datetime.now(tz=timezone.utc) - timedelta(days=1)
        self.FakeDB().store_refresh_token(1, token_hash, past)

        self.client.set_cookie('suggestarr_refresh', raw, path='/api/auth/refresh')
        resp = self.client.post('/api/auth/refresh')
        self.assertEqual(resp.status_code, 401)


class TestAuthLogoutEndpoint(_AuthBlueprintBase):

    def test_logout_returns_200(self):
        self._create_user("alice", "StrongPass1!")
        self._login("alice", "StrongPass1!")
        resp = self.client.post('/api/auth/logout')
        self.assertEqual(resp.status_code, 200)

    def test_logout_clears_cookie(self):
        self._create_user("alice", "StrongPass1!")
        self._login("alice", "StrongPass1!")
        resp = self.client.post('/api/auth/logout')
        # Cookie should be cleared (expired)
        self.assertIn("suggestarr_refresh", resp.headers.get("Set-Cookie", ""))

    def test_refresh_after_logout_returns_401(self):
        self._create_user("alice", "StrongPass1!")
        self._login("alice", "StrongPass1!")
        self.client.post('/api/auth/logout')
        resp = self.client.post('/api/auth/refresh')
        self.assertEqual(resp.status_code, 401)

    def test_logout_without_cookie_is_safe(self):
        """Calling logout with no cookie must not crash."""
        resp = self.client.post('/api/auth/logout')
        self.assertEqual(resp.status_code, 200)


class TestAuthMeEndpoint(_AuthBlueprintBase):

    def test_me_returns_current_user(self):
        self._create_user("alice", "StrongPass1!", role="admin")
        from api_service.auth.middleware import invalidate_setup_cache
        invalidate_setup_cache()
        # Disable DISABLE_AUTH so middleware runs properly
        os.environ.pop('SUGGESTARR_AUTH_DISABLED', None)

        token = _make_valid_token(user_id=1, username="alice", role="admin")
        resp = self.client.get('/api/auth/me',
                               headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["username"], "alice")
        self.assertEqual(data["role"], "admin")

    def test_me_without_token_returns_401(self):
        self._create_user("alice", "StrongPass1!")
        from api_service.auth.middleware import invalidate_setup_cache
        invalidate_setup_cache()
        os.environ.pop('SUGGESTARR_AUTH_DISABLED', None)

        resp = self.client.get('/api/auth/me')
        self.assertEqual(resp.status_code, 401)


class TestAuthStatusEndpoint(_AuthBlueprintBase):

    def test_status_no_users(self):
        resp = self.client.get('/api/auth/status')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertFalse(data["auth_setup_complete"])

    def test_status_after_user_created(self):
        self._create_user()
        resp = self.client.get('/api/auth/status')
        data = resp.get_json()
        self.assertTrue(data["auth_setup_complete"])


if __name__ == '__main__':
    unittest.main()
