"""
Integration tests for DatabaseManager auth/user methods.

Strategy: real SQLite database in a temporary file — no mocking of the DB
layer.  Each test method gets a fresh, isolated database by resetting the
singleton and pointing DB_PATH at a new temp file.

Covers:
  - create_auth_user
  - get_auth_user_by_id / get_auth_user_by_username
  - update_last_login (datetime stored correctly, parseable, not None)
  - update_auth_user (role, is_active)
  - update_auth_user_profile (username, password_hash, unique constraint)
  - delete_auth_user
  - get_admin_count
  - store_refresh_token / get_refresh_token / revoke_refresh_token /
    cleanup_expired_refresh_tokens
"""
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import logging
logging.disable(logging.CRITICAL)


# ---------------------------------------------------------------------------
# Base class — fresh temp SQLite DB per test method
# ---------------------------------------------------------------------------

class _DBBase(unittest.TestCase):
    """
    Reset the DatabaseManager singleton and create an isolated temp-file
    SQLite database before every test.  Tear it all down afterwards.
    """

    def setUp(self):
        import api_service.db.database_manager as dm_mod

        # Reset singleton so __init__ runs fully with the new temp path.
        dm_mod.DatabaseManager._instance = None

        # Fresh temp file for each test — avoids inter-test state leakage.
        fd, self._db_file = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        # Override DB_PATH before __init__ reads it.
        self._path_patch = patch.object(dm_mod, 'DB_PATH', self._db_file)
        self._path_patch.start()

        # Avoid touching real config.yaml.
        self._env_patch = patch(
            'api_service.db.database_manager.load_env_vars',
            return_value={'DB_TYPE': 'sqlite'},
        )
        self._env_patch.start()

        from api_service.db.database_manager import DatabaseManager
        self.db = DatabaseManager()

    def tearDown(self):
        import api_service.db.database_manager as dm_mod
        dm_mod.DatabaseManager._instance = None
        self._path_patch.stop()
        self._env_patch.stop()
        try:
            os.unlink(self._db_file)
        except FileNotFoundError:
            pass

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def _make_user(self, username='alice', role='admin'):
        """Insert a user with a placeholder hash and return the new id."""
        return self.db.create_auth_user(username, 'dummy_hash', role=role)


# ---------------------------------------------------------------------------
# create_auth_user
# ---------------------------------------------------------------------------

class TestCreateAuthUser(_DBBase):

    def test_returns_positive_integer_id(self):
        uid = self._make_user()
        self.assertIsInstance(uid, int)
        self.assertGreater(uid, 0)

    def test_created_user_is_retrievable_by_id(self):
        uid = self._make_user('bob', 'user')
        user = self.db.get_auth_user_by_id(uid)
        self.assertIsNotNone(user)
        self.assertEqual(user['username'], 'bob')
        self.assertEqual(user['role'], 'user')

    def test_password_hash_stored_correctly(self):
        uid = self._make_user()
        user = self.db.get_auth_user_by_id(uid)
        self.assertEqual(user['password_hash'], 'dummy_hash')

    def test_is_active_defaults_to_true(self):
        uid = self._make_user()
        user = self.db.get_auth_user_by_id(uid)
        self.assertTrue(user['is_active'])

    def test_user_count_increments_per_insertion(self):
        self.assertEqual(self.db.get_auth_user_count(), 0)
        self._make_user('u1')
        self.assertEqual(self.db.get_auth_user_count(), 1)
        self._make_user('u2')
        self.assertEqual(self.db.get_auth_user_count(), 2)

    def test_duplicate_username_raises_database_error(self):
        from api_service.exceptions.database_exceptions import DatabaseError
        self._make_user('alice')
        with self.assertRaises(DatabaseError):
            self._make_user('alice')

    def test_sequential_ids_are_unique(self):
        uid1 = self._make_user('u1')
        uid2 = self._make_user('u2')
        self.assertNotEqual(uid1, uid2)


# ---------------------------------------------------------------------------
# get_auth_user_by_id / get_auth_user_by_username
# ---------------------------------------------------------------------------

class TestGetAuthUser(_DBBase):

    def setUp(self):
        super().setUp()
        self._uid = self._make_user('alice', 'admin')

    def test_get_by_id_returns_correct_user(self):
        user = self.db.get_auth_user_by_id(self._uid)
        self.assertEqual(user['id'], self._uid)
        self.assertEqual(user['username'], 'alice')

    def test_get_by_id_returns_all_expected_keys(self):
        user = self.db.get_auth_user_by_id(self._uid)
        for key in ('id', 'username', 'password_hash', 'role', 'is_active', 'last_login'):
            self.assertIn(key, user)

    def test_get_by_username_returns_correct_user(self):
        user = self.db.get_auth_user_by_username('alice')
        self.assertIsNotNone(user)
        self.assertEqual(user['id'], self._uid)
        self.assertEqual(user['role'], 'admin')

    def test_get_by_id_nonexistent_returns_none(self):
        self.assertIsNone(self.db.get_auth_user_by_id(99999))

    def test_get_by_username_nonexistent_returns_none(self):
        self.assertIsNone(self.db.get_auth_user_by_username('nobody'))

    def test_last_login_initially_none(self):
        user = self.db.get_auth_user_by_id(self._uid)
        self.assertIsNone(user['last_login'])

    def test_multiple_users_isolated(self):
        uid2 = self._make_user('bob', 'user')
        alice = self.db.get_auth_user_by_username('alice')
        bob = self.db.get_auth_user_by_id(uid2)
        self.assertEqual(alice['role'], 'admin')
        self.assertEqual(bob['role'], 'user')
        self.assertNotEqual(alice['id'], bob['id'])


# ---------------------------------------------------------------------------
# update_last_login
# ---------------------------------------------------------------------------

class TestUpdateLastLogin(_DBBase):
    """
    Verify update_last_login persists a valid datetime value.

    SQLite stores TIMESTAMP columns as ISO 8601 strings.  The important
    invariant is that the value can be parsed back as a datetime and is
    recent (within a few seconds of 'now').
    """

    def setUp(self):
        super().setUp()
        self._uid = self._make_user()

    def test_last_login_transitions_from_none_to_non_none(self):
        user_before = self.db.get_auth_user_by_id(self._uid)
        self.assertIsNone(user_before['last_login'])

        self.db.update_last_login(self._uid)

        user_after = self.db.get_auth_user_by_id(self._uid)
        self.assertIsNotNone(user_after['last_login'])

    def test_last_login_value_is_recent(self):
        """The stored timestamp must be close to the moment the call was made."""
        before = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=2)
        self.db.update_last_login(self._uid)
        user = self.db.get_auth_user_by_id(self._uid)

        stored = user['last_login']
        # SQLite returns TIMESTAMP as a string; parse it.
        if isinstance(stored, str):
            # SQLite format: 'YYYY-MM-DD HH:MM:SS.ffffff' or 'YYYY-MM-DDTHH:MM:SS'
            stored_dt = datetime.fromisoformat(stored.replace(' ', 'T'))
        else:
            stored_dt = stored

        # Normalise to naive UTC for comparison.
        if stored_dt.tzinfo is not None:
            stored_dt = stored_dt.astimezone(timezone.utc).replace(tzinfo=None)

        after = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=2)
        self.assertGreaterEqual(stored_dt, before,
                                "last_login should be after the start of the test")
        self.assertLessEqual(stored_dt, after,
                             "last_login should not be in the future")

    def test_last_login_can_be_called_repeatedly(self):
        self.db.update_last_login(self._uid)
        first_val = self.db.get_auth_user_by_id(self._uid)['last_login']
        self.db.update_last_login(self._uid)
        second_val = self.db.get_auth_user_by_id(self._uid)['last_login']
        # Both calls must produce a non-None value.
        self.assertIsNotNone(first_val)
        self.assertIsNotNone(second_val)


# ---------------------------------------------------------------------------
# update_auth_user (role / is_active)
# ---------------------------------------------------------------------------

class TestUpdateAuthUser(_DBBase):

    def setUp(self):
        super().setUp()
        self._uid = self._make_user('alice', 'admin')

    def test_change_role_to_user(self):
        result = self.db.update_auth_user(self._uid, {'role': 'user'})
        self.assertTrue(result)
        user = self.db.get_auth_user_by_id(self._uid)
        self.assertEqual(user['role'], 'user')

    def test_deactivate_user(self):
        result = self.db.update_auth_user(self._uid, {'is_active': 0})
        self.assertTrue(result)
        user = self.db.get_auth_user_by_id(self._uid)
        self.assertFalse(user['is_active'])

    def test_reactivate_user(self):
        self.db.update_auth_user(self._uid, {'is_active': 0})
        self.db.update_auth_user(self._uid, {'is_active': 1})
        user = self.db.get_auth_user_by_id(self._uid)
        self.assertTrue(user['is_active'])

    def test_update_nonexistent_user_returns_false(self):
        result = self.db.update_auth_user(99999, {'role': 'user'})
        self.assertFalse(result)

    def test_empty_updates_returns_false(self):
        result = self.db.update_auth_user(self._uid, {})
        self.assertFalse(result)

    def test_disallowed_field_silently_ignored(self):
        """Fields not in {'role', 'is_active'} must not be persisted."""
        result = self.db.update_auth_user(self._uid, {'username': 'evil'})
        # Returns False because no allowed fields were found.
        self.assertFalse(result)
        user = self.db.get_auth_user_by_id(self._uid)
        self.assertEqual(user['username'], 'alice')

    def test_combined_role_and_active_update(self):
        result = self.db.update_auth_user(self._uid, {'role': 'user', 'is_active': 0})
        self.assertTrue(result)
        user = self.db.get_auth_user_by_id(self._uid)
        self.assertEqual(user['role'], 'user')
        self.assertFalse(user['is_active'])


# ---------------------------------------------------------------------------
# update_auth_user_profile (username / password_hash)
# ---------------------------------------------------------------------------

class TestUpdateAuthUserProfile(_DBBase):

    def setUp(self):
        super().setUp()
        self._uid = self._make_user('alice', 'admin')

    def test_change_username(self):
        result = self.db.update_auth_user_profile(self._uid, {'username': 'alice2'})
        self.assertTrue(result)
        user = self.db.get_auth_user_by_id(self._uid)
        self.assertEqual(user['username'], 'alice2')

    def test_change_password_hash(self):
        result = self.db.update_auth_user_profile(self._uid, {'password_hash': 'new_bcrypt_hash'})
        self.assertTrue(result)
        user = self.db.get_auth_user_by_id(self._uid)
        self.assertEqual(user['password_hash'], 'new_bcrypt_hash')

    def test_duplicate_username_raises(self):
        """Unique constraint must propagate so the route can return 409."""
        self._make_user('bob', 'user')
        with self.assertRaises(Exception):
            self.db.update_auth_user_profile(self._uid, {'username': 'bob'})

    def test_nonexistent_user_returns_false(self):
        result = self.db.update_auth_user_profile(99999, {'username': 'ghost'})
        self.assertFalse(result)

    def test_empty_updates_returns_false(self):
        result = self.db.update_auth_user_profile(self._uid, {})
        self.assertFalse(result)

    def test_disallowed_field_silently_ignored(self):
        result = self.db.update_auth_user_profile(self._uid, {'role': 'god'})
        self.assertFalse(result)
        user = self.db.get_auth_user_by_id(self._uid)
        self.assertEqual(user['role'], 'admin')


# ---------------------------------------------------------------------------
# delete_auth_user
# ---------------------------------------------------------------------------

class TestDeleteAuthUser(_DBBase):

    def setUp(self):
        super().setUp()
        self._uid = self._make_user('alice', 'admin')

    def test_delete_existing_user_returns_true(self):
        result = self.db.delete_auth_user(self._uid)
        self.assertTrue(result)

    def test_deleted_user_not_retrievable_by_id(self):
        self.db.delete_auth_user(self._uid)
        self.assertIsNone(self.db.get_auth_user_by_id(self._uid))

    def test_deleted_user_not_retrievable_by_username(self):
        self.db.delete_auth_user(self._uid)
        self.assertIsNone(self.db.get_auth_user_by_username('alice'))

    def test_delete_nonexistent_user_returns_false(self):
        result = self.db.delete_auth_user(99999)
        self.assertFalse(result)

    def test_count_decrements_after_delete(self):
        self.assertEqual(self.db.get_auth_user_count(), 1)
        self.db.delete_auth_user(self._uid)
        self.assertEqual(self.db.get_auth_user_count(), 0)

    def test_second_delete_returns_false(self):
        self.db.delete_auth_user(self._uid)
        result = self.db.delete_auth_user(self._uid)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# get_admin_count
# ---------------------------------------------------------------------------

class TestGetAllAuthUsers(_DBBase):

    def test_returns_empty_list_when_no_users(self):
        result = self.db.get_all_auth_users()
        self.assertEqual(result, [])

    def test_returns_all_users(self):
        self._make_user('alice', 'admin')
        self._make_user('bob', 'user')
        result = self.db.get_all_auth_users()
        self.assertEqual(len(result), 2)

    def test_response_excludes_password_hash(self):
        self._make_user('alice', 'admin')
        result = self.db.get_all_auth_users()
        for user in result:
            self.assertNotIn('password_hash', user)

    def test_response_includes_expected_keys(self):
        self._make_user('alice', 'admin')
        result = self.db.get_all_auth_users()
        user = result[0]
        for key in ('id', 'username', 'role', 'is_active', 'created_at', 'last_login'):
            self.assertIn(key, user)

    def test_ordered_by_id(self):
        self._make_user('alice', 'admin')
        self._make_user('bob', 'user')
        result = self.db.get_all_auth_users()
        ids = [u['id'] for u in result]
        self.assertEqual(ids, sorted(ids))


class TestGetAdminCount(_DBBase):

    def test_zero_when_no_users(self):
        self.assertEqual(self.db.get_admin_count(), 0)

    def test_counts_active_admins(self):
        self._make_user('admin1', 'admin')
        self._make_user('admin2', 'admin')
        self._make_user('regular', 'user')
        self.assertEqual(self.db.get_admin_count(), 2)

    def test_deactivated_admin_not_counted(self):
        uid = self._make_user('admin1', 'admin')
        self.db.update_auth_user(uid, {'is_active': 0})
        self.assertEqual(self.db.get_admin_count(), 0)

    def test_user_role_not_counted(self):
        self._make_user('u', 'user')
        self.assertEqual(self.db.get_admin_count(), 0)

    def test_mixed_roles_count_only_active_admins(self):
        uid_a = self._make_user('admin', 'admin')
        self._make_user('user1', 'user')
        self._make_user('user2', 'user')
        self.assertEqual(self.db.get_admin_count(), 1)
        self.db.update_auth_user(uid_a, {'is_active': 0})
        self.assertEqual(self.db.get_admin_count(), 0)


# ---------------------------------------------------------------------------
# Refresh token methods
# ---------------------------------------------------------------------------

class TestRefreshTokenMethods(_DBBase):

    def setUp(self):
        super().setUp()
        self._uid = self._make_user()

    def _future(self, days=7):
        return datetime.now(timezone.utc) + timedelta(days=days)

    def _past(self, days=1):
        return datetime.now(timezone.utc) - timedelta(days=days)

    def test_store_and_retrieve(self):
        self.db.store_refresh_token(self._uid, 'hash1', self._future())
        record = self.db.get_refresh_token('hash1')
        self.assertIsNotNone(record)
        self.assertEqual(record['user_id'], self._uid)

    def test_retrieved_record_has_expected_keys(self):
        self.db.store_refresh_token(self._uid, 'hash2', self._future())
        record = self.db.get_refresh_token('hash2')
        for key in ('id', 'user_id', 'expires_at'):
            self.assertIn(key, record)

    def test_revoked_token_not_returned(self):
        self.db.store_refresh_token(self._uid, 'hash3', self._future())
        self.db.revoke_refresh_token('hash3')
        self.assertIsNone(self.db.get_refresh_token('hash3'))

    def test_nonexistent_token_returns_none(self):
        self.assertIsNone(self.db.get_refresh_token('does_not_exist'))

    def test_revoke_nonexistent_token_is_safe(self):
        """Revoking a token that doesn't exist must not raise."""
        try:
            self.db.revoke_refresh_token('ghost_hash')
        except Exception as exc:
            self.fail(f"revoke_refresh_token raised unexpectedly: {exc}")

    def test_cleanup_removes_expired_and_revoked_tokens(self):
        # Insert: 1 expired, 1 revoked, 1 valid.
        self.db.store_refresh_token(self._uid, 'expired_h', self._past())
        self.db.store_refresh_token(self._uid, 'revoked_h', self._future())
        self.db.revoke_refresh_token('revoked_h')
        self.db.store_refresh_token(self._uid, 'valid_h', self._future())

        deleted = self.db.cleanup_expired_refresh_tokens()
        self.assertEqual(deleted, 2)

    def test_cleanup_preserves_valid_tokens(self):
        self.db.store_refresh_token(self._uid, 'expired_h', self._past())
        self.db.store_refresh_token(self._uid, 'valid_h', self._future())
        self.db.cleanup_expired_refresh_tokens()
        self.assertIsNotNone(self.db.get_refresh_token('valid_h'))

    def test_cleanup_returns_zero_when_nothing_to_clean(self):
        self.db.store_refresh_token(self._uid, 'valid_h', self._future())
        deleted = self.db.cleanup_expired_refresh_tokens()
        self.assertEqual(deleted, 0)

    def test_timezone_aware_expires_at_accepted(self):
        """store_refresh_token must accept a tz-aware datetime without raising."""
        aware_dt = datetime.now(timezone.utc) + timedelta(days=7)
        try:
            self.db.store_refresh_token(self._uid, 'aware_h', aware_dt)
        except Exception as exc:
            self.fail(f"store_refresh_token raised with tz-aware datetime: {exc}")
        self.assertIsNotNone(self.db.get_refresh_token('aware_h'))


if __name__ == '__main__':
    unittest.main()
