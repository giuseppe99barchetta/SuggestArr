"""
Tests for the users management blueprint (/api/users).

Covers admin-only CRUD endpoints and the 403 responses for non-admin users.

Strategy
--------
A minimal Flask app registers the users blueprint with DatabaseManager
replaced by an in-memory FakeDB.  g.current_user is injected by a
before_request hook so require_role can inspect it without running the JWT
middleware.  The caller role can be changed per-test via self._caller.

Endpoints tested:
  GET    /api/users              — list all users (admin only)
  POST   /api/users              — create user (admin only)
  PATCH  /api/users/<id>         — update role / active (admin only)
  DELETE /api/users/<id>         — delete user (admin only)

Role guards tested:
  - Non-admin → 403
  - Admin cannot modify/delete their own account → 403
  - Last active admin guard → 403
"""
import os
import unittest
from unittest.mock import patch

import logging
logging.disable(logging.CRITICAL)

# Stable test secret so secret_key.py never writes to disk.
TEST_SECRET = "test-secret-for-users-blueprint-tests-only-not-for-production"
os.environ['SUGGESTARR_SECRET_KEY'] = TEST_SECRET


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class _UsersBlueprintBase(unittest.TestCase):
    """
    Set up a minimal Flask app with:
      - users blueprint registered at /api/users
      - DatabaseManager replaced by an in-memory FakeDB
      - g.current_user set from self._caller before every request
    """

    # Default caller: admin user with id=1.
    _ADMIN_CALLER = {"id": "1", "username": "admin", "role": "admin"}

    def setUp(self):
        os.environ['SUGGESTARR_SECRET_KEY'] = TEST_SECRET
        os.environ['SUGGESTARR_AUTH_DISABLED'] = 'true'  # bypass middleware

        # Caller identity used by the before_request hook.
        self._caller = dict(self._ADMIN_CALLER)

        # In-memory user store: username → row dict.
        self._users: dict = {}
        self._uid_seq = iter(range(1, 10_000))

        self._build_fake_db()
        self._setup_app()

    def tearDown(self):
        os.environ.pop('SUGGESTARR_AUTH_DISABLED', None)
        for p in self._patches:
            p.stop()

    # ------------------------------------------------------------------
    # FakeDB construction
    # ------------------------------------------------------------------

    def _build_fake_db(self):
        users = self._users
        uid_seq = self._uid_seq

        class FakeDB:
            def __init__(self_inner):
                pass

            # --- auth user CRUD ---

            def create_auth_user(self_inner, username, password_hash,
                                 role='user'):
                if username in users:
                    raise Exception("UNIQUE constraint failed: auth_users.username")
                uid = next(uid_seq)
                users[username] = {
                    "id": uid, "username": username,
                    "password_hash": password_hash, "role": role,
                    "is_active": True, "last_login": None,
                    "created_at": "2025-01-01 00:00:00",
                }
                return uid

            def get_auth_user_by_id(self_inner, user_id):
                for u in users.values():
                    if u["id"] == user_id:
                        return u
                return None

            def get_all_auth_users(self_inner):
                return [
                    {k: v for k, v in u.items() if k != 'password_hash'}
                    for u in users.values()
                ]

            def update_auth_user(self_inner, user_id, updates):
                for u in users.values():
                    if u["id"] == user_id:
                        u.update(updates)
                        return True
                return False

            def delete_auth_user(self_inner, user_id):
                for username, u in list(users.items()):
                    if u["id"] == user_id:
                        del users[username]
                        return True
                return False

            def get_admin_count(self_inner):
                return sum(
                    1 for u in users.values()
                    if u.get('role') == 'admin' and u.get('is_active', True)
                )

        self.FakeDB = FakeDB

    # ------------------------------------------------------------------
    # Flask app setup
    # ------------------------------------------------------------------

    def _setup_app(self):
        from flask import Flask, g
        from api_service.blueprints.users.routes import users_bp
        from api_service.auth.middleware import enforce_authentication

        app = Flask(__name__)
        app.config['TESTING'] = True

        caller_ref = self  # closure

        @app.before_request
        def inject_caller():
            g.current_user = caller_ref._caller

        self._patches = [
            patch('api_service.blueprints.users.routes.DatabaseManager',
                  self.FakeDB),
            patch('api_service.auth.middleware.DatabaseManager', self.FakeDB),
        ]
        for p in self._patches:
            p.start()

        app.before_request(enforce_authentication)
        app.register_blueprint(users_bp, url_prefix='/api/users')

        self.app = app
        self.client = app.test_client()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_admin(self, username='admin', uid_override=None):
        """Insert an admin user and return their id."""
        from api_service.auth.auth_service import AuthService
        db = self.FakeDB()
        uid = db.create_auth_user(username,
                                  AuthService.hash_password('StrongPass1!'),
                                  role='admin')
        return uid

    def _make_user(self, username='bob', role='user'):
        """Insert a regular user and return their id."""
        from api_service.auth.auth_service import AuthService
        db = self.FakeDB()
        uid = db.create_auth_user(username,
                                  AuthService.hash_password('StrongPass1!'),
                                  role=role)
        return uid

    def _set_caller(self, uid, username, role):
        """Change the identity presented to require_role for this test."""
        self._caller = {"id": str(uid), "username": username, "role": role}


# ---------------------------------------------------------------------------
# GET /api/users — list users
# ---------------------------------------------------------------------------

class TestListUsers(_UsersBlueprintBase):

    def test_admin_can_list_users(self):
        self._make_admin('admin')
        self._make_user('bob')
        resp = self.client.get('/api/users')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)

    def test_list_response_excludes_password_hash(self):
        self._make_admin('admin')
        resp = self.client.get('/api/users')
        data = resp.get_json()
        for user in data:
            self.assertNotIn('password_hash', user)

    def test_non_admin_gets_403(self):
        uid = self._make_user('viewer', 'user')
        self._set_caller(uid, 'viewer', 'user')
        resp = self.client.get('/api/users')
        self.assertEqual(resp.status_code, 403)

    def test_empty_user_list_returns_empty_array(self):
        resp = self.client.get('/api/users')
        data = resp.get_json()
        self.assertEqual(data, [])


# ---------------------------------------------------------------------------
# POST /api/users — admin create user
# ---------------------------------------------------------------------------

class TestCreateUser(_UsersBlueprintBase):

    def test_admin_can_create_user(self):
        resp = self.client.post('/api/users',
                                json={"username": "newuser",
                                      "password": "StrongPass1!",
                                      "role": "user"})
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertIn("id", data)
        self.assertEqual(data["username"], "newuser")
        self.assertEqual(data["role"], "user")

    def test_admin_can_create_admin(self):
        resp = self.client.post('/api/users',
                                json={"username": "admin2",
                                      "password": "StrongPass1!",
                                      "role": "admin"})
        self.assertEqual(resp.status_code, 201)

    def test_non_admin_gets_403(self):
        uid = self._make_user('viewer', 'user')
        self._set_caller(uid, 'viewer', 'user')
        resp = self.client.post('/api/users',
                                json={"username": "hacker",
                                      "password": "StrongPass1!"})
        self.assertEqual(resp.status_code, 403)

    def test_duplicate_username_returns_409(self):
        self._make_user('existing')
        resp = self.client.post('/api/users',
                                json={"username": "existing",
                                      "password": "StrongPass1!"})
        self.assertEqual(resp.status_code, 409)

    def test_invalid_role_returns_400(self):
        resp = self.client.post('/api/users',
                                json={"username": "u",
                                      "password": "StrongPass1!",
                                      "role": "superuser"})
        self.assertEqual(resp.status_code, 400)

    def test_missing_fields_returns_400(self):
        resp = self.client.post('/api/users', json={})
        self.assertEqual(resp.status_code, 400)

    def test_short_password_returns_400(self):
        from api_service.auth.auth_service import MIN_PASSWORD_LENGTH
        resp = self.client.post('/api/users',
                                json={"username": "u",
                                      "password": "x" * (MIN_PASSWORD_LENGTH - 1)})
        self.assertEqual(resp.status_code, 400)

    def test_too_long_username_returns_400(self):
        resp = self.client.post('/api/users',
                                json={"username": "a" * 65,
                                      "password": "StrongPass1!"})
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# PATCH /api/users/<id> — update role / active
# ---------------------------------------------------------------------------

class TestUpdateUser(_UsersBlueprintBase):

    def setUp(self):
        super().setUp()
        # Admin caller has id=1, target user has id=2.
        self._admin_uid = self._make_admin('admin')
        self._set_caller(self._admin_uid, 'admin', 'admin')
        self._target_uid = self._make_user('bob', 'user')

    def test_admin_can_change_role(self):
        resp = self.client.patch(f'/api/users/{self._target_uid}',
                                 json={"role": "admin"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._users["bob"]["role"], "admin")

    def test_admin_can_deactivate_user(self):
        resp = self.client.patch(f'/api/users/{self._target_uid}',
                                 json={"is_active": False})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(self._users["bob"]["is_active"])

    def test_admin_cannot_modify_own_account(self):
        resp = self.client.patch(f'/api/users/{self._admin_uid}',
                                 json={"role": "user"})
        self.assertEqual(resp.status_code, 403)

    def test_nonexistent_user_returns_404(self):
        resp = self.client.patch('/api/users/99999', json={"role": "user"})
        self.assertEqual(resp.status_code, 404)

    def test_no_valid_fields_returns_400(self):
        resp = self.client.patch(f'/api/users/{self._target_uid}', json={})
        self.assertEqual(resp.status_code, 400)

    def test_invalid_role_value_returns_400(self):
        resp = self.client.patch(f'/api/users/{self._target_uid}',
                                 json={"role": "god"})
        self.assertEqual(resp.status_code, 400)

    def test_non_admin_gets_403(self):
        uid = self._make_user('viewer', 'user')
        self._set_caller(uid, 'viewer', 'user')
        resp = self.client.patch(f'/api/users/{self._target_uid}',
                                 json={"role": "admin"})
        self.assertEqual(resp.status_code, 403)

    def test_cannot_demote_last_active_admin(self):
        """Demoting the only admin must be blocked to prevent lock-out."""
        # Make bob an admin; admin is the only other admin.
        self._users["bob"]["role"] = "admin"
        # Now demote bob (admin is the other admin, so count=2 initially).
        # Remove admin to simulate it being the only admin.
        del self._users["admin"]
        # Now bob is the only admin — demoting him must be rejected.
        resp = self.client.patch(f'/api/users/{self._target_uid}',
                                 json={"role": "user"})
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# DELETE /api/users/<id>
# ---------------------------------------------------------------------------

class TestDeleteUser(_UsersBlueprintBase):

    def setUp(self):
        super().setUp()
        self._admin_uid = self._make_admin('admin')
        self._set_caller(self._admin_uid, 'admin', 'admin')
        self._target_uid = self._make_user('bob', 'user')

    def test_admin_can_delete_user(self):
        resp = self.client.delete(f'/api/users/{self._target_uid}')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('bob', self._users)

    def test_admin_cannot_delete_own_account(self):
        resp = self.client.delete(f'/api/users/{self._admin_uid}')
        self.assertEqual(resp.status_code, 403)
        self.assertIn('admin', self._users)

    def test_nonexistent_user_returns_404(self):
        resp = self.client.delete('/api/users/99999')
        self.assertEqual(resp.status_code, 404)

    def test_non_admin_gets_403(self):
        uid = self._make_user('viewer', 'user')
        self._set_caller(uid, 'viewer', 'user')
        resp = self.client.delete(f'/api/users/{self._target_uid}')
        self.assertEqual(resp.status_code, 403)

    def test_cannot_delete_last_active_admin(self):
        """Deleting the sole active admin must be blocked."""
        # Make bob an admin and remove the other admin from the store so that
        # bob becomes the last admin.  Then try to delete him.
        self._users["bob"]["role"] = "admin"
        del self._users["admin"]
        resp = self.client.delete(f'/api/users/{self._target_uid}')
        self.assertEqual(resp.status_code, 403)
        self.assertIn('bob', self._users)

    def test_delete_response_contains_message(self):
        resp = self.client.delete(f'/api/users/{self._target_uid}')
        data = resp.get_json()
        self.assertIn("message", data)


if __name__ == '__main__':
    unittest.main()
