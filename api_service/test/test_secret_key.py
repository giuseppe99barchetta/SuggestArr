"""
Tests for api_service/auth/secret_key.py.

Covers:
  - load_secret_key: env-var priority (valid key, short key, empty string)
  - load_secret_key: file loading from disk
  - load_secret_key: key generation when neither env var nor file exist
  - load_secret_key: empty file triggers key generation
  - _generate_and_save: key length (≥32 bytes) and persistence to disk
  - Cache: second call returns the same cached value
  - invalidate_cache: allows load_secret_key to re-read from the source

Strategy
--------
All tests that touch the filesystem use temporary directories/files to
avoid writing to the real config path.  Module-level _cached_key is reset
via invalidate_cache() in setUp/tearDown.
"""
import os
import tempfile
import unittest
from unittest.mock import patch

import logging
logging.disable(logging.CRITICAL)


class _SecretKeyBase(unittest.TestCase):
    """Clear the in-process cache and env var before and after every test."""

    def setUp(self):
        from api_service.auth.secret_key import invalidate_cache
        invalidate_cache()
        os.environ.pop('SUGGESTARR_SECRET_KEY', None)

    def tearDown(self):
        from api_service.auth.secret_key import invalidate_cache
        invalidate_cache()
        os.environ.pop('SUGGESTARR_SECRET_KEY', None)


# ---------------------------------------------------------------------------
# Env-var loading
# ---------------------------------------------------------------------------

class TestLoadSecretKeyFromEnvVar(_SecretKeyBase):

    def test_env_var_key_is_returned_unchanged(self):
        """A key set in the env var must be returned as-is."""
        secret = 'a' * 44  # 44 chars, comfortably ≥32 bytes
        os.environ['SUGGESTARR_SECRET_KEY'] = secret
        from api_service.auth.secret_key import load_secret_key
        self.assertEqual(load_secret_key(), secret)

    def test_env_var_takes_priority_over_file(self):
        """Env var must be preferred even when a key file exists on disk."""
        env_secret = 'env-secret-key-long-enough-for-hs256-in-tests'
        os.environ['SUGGESTARR_SECRET_KEY'] = env_secret

        import api_service.auth.secret_key as sk_mod
        with tempfile.NamedTemporaryFile(mode='w', suffix='.key',
                                        delete=False) as fh:
            fh.write('file-secret-that-must-be-ignored')
            file_path = fh.name
        try:
            with patch.object(sk_mod, '_SECRET_KEY_PATH', file_path):
                from api_service.auth.secret_key import load_secret_key
                result = load_secret_key()
            self.assertEqual(result, env_secret)
        finally:
            os.unlink(file_path)

    def test_short_env_key_returned_without_length_enforcement(self):
        """
        secret_key.py does not enforce a minimum length on the env var.
        That validation belongs to the caller (JWT signing).
        A short value must still be returned so the caller can decide.
        """
        short = 'tooshort'
        os.environ['SUGGESTARR_SECRET_KEY'] = short
        from api_service.auth.secret_key import load_secret_key
        self.assertEqual(load_secret_key(), short)

    def test_empty_env_var_treated_as_absent(self):
        """
        An empty SUGGESTARR_SECRET_KEY must be ignored and the loader must
        fall through to the file/generation path.
        """
        os.environ['SUGGESTARR_SECRET_KEY'] = '   '  # blank / whitespace only

        import api_service.auth.secret_key as sk_mod
        disk_key = 'disk-fallback-key-long-enough-for-the-test'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.key',
                                        delete=False) as fh:
            fh.write(disk_key)
            file_path = fh.name
        try:
            with patch.object(sk_mod, '_SECRET_KEY_PATH', file_path):
                from api_service.auth.secret_key import load_secret_key
                result = load_secret_key()
            self.assertEqual(result, disk_key,
                             "Whitespace-only env var must not be used as the key")
        finally:
            os.unlink(file_path)


# ---------------------------------------------------------------------------
# File-based loading
# ---------------------------------------------------------------------------

class TestLoadSecretKeyFromFile(_SecretKeyBase):

    def test_key_loaded_from_file_when_env_absent(self):
        """Key on disk is returned when no env var is set."""
        disk_key = 'disk-only-secret-long-enough-for-hs256-algorithm'
        import api_service.auth.secret_key as sk_mod
        with tempfile.NamedTemporaryFile(mode='w', suffix='.key',
                                        delete=False) as fh:
            fh.write(disk_key)
            file_path = fh.name
        try:
            with patch.object(sk_mod, '_SECRET_KEY_PATH', file_path):
                from api_service.auth.secret_key import load_secret_key
                result = load_secret_key()
            self.assertEqual(result, disk_key)
        finally:
            os.unlink(file_path)

    def test_empty_file_triggers_key_generation(self):
        """
        An empty secret.key file must not be treated as valid.
        load_secret_key must call _generate_and_save instead.
        """
        import api_service.auth.secret_key as sk_mod
        with tempfile.NamedTemporaryFile(mode='w', suffix='.key',
                                        delete=False) as fh:
            fh.write('')   # intentionally empty
            file_path = fh.name
        try:
            with patch.object(sk_mod, '_SECRET_KEY_PATH', file_path):
                with patch.object(sk_mod, '_generate_and_save',
                                  return_value='generated-key') as mock_gen:
                    from api_service.auth.secret_key import load_secret_key
                    result = load_secret_key()
            mock_gen.assert_called_once()
            self.assertEqual(result, 'generated-key')
        finally:
            try:
                os.unlink(file_path)
            except FileNotFoundError:
                pass

    def test_whitespace_only_file_treated_as_empty(self):
        """A file containing only whitespace is equivalent to an empty file."""
        import api_service.auth.secret_key as sk_mod
        with tempfile.NamedTemporaryFile(mode='w', suffix='.key',
                                        delete=False) as fh:
            fh.write('   \n  ')
            file_path = fh.name
        try:
            with patch.object(sk_mod, '_SECRET_KEY_PATH', file_path):
                with patch.object(sk_mod, '_generate_and_save',
                                  return_value='generated-key') as mock_gen:
                    from api_service.auth.secret_key import load_secret_key
                    result = load_secret_key()
            mock_gen.assert_called_once()
        finally:
            try:
                os.unlink(file_path)
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------

class TestLoadSecretKeyGeneration(_SecretKeyBase):

    def test_generates_key_when_file_absent(self):
        """
        When neither env var nor file exist, _generate_and_save must be called
        and its return value used as the secret key.
        """
        import api_service.auth.secret_key as sk_mod
        non_existent = '/tmp/does_not_exist_suggestarr_secret_test_xyz.key'
        with patch.object(sk_mod, '_SECRET_KEY_PATH', non_existent):
            with patch.object(sk_mod, '_generate_and_save',
                              return_value='freshly-generated') as mock_gen:
                from api_service.auth.secret_key import load_secret_key
                result = load_secret_key()
        mock_gen.assert_called_once()
        self.assertEqual(result, 'freshly-generated')

    def test_generated_key_is_at_least_32_bytes(self):
        """
        _generate_and_save uses secrets.token_urlsafe(32) which produces a
        URL-safe base64 string of at least 43 characters (ceil(32 * 4 / 3)).
        """
        import api_service.auth.secret_key as sk_mod
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_key_path = os.path.join(tmpdir, 'secret.key')
            with patch.object(sk_mod, '_SECRET_KEY_PATH', tmp_key_path):
                from api_service.auth.secret_key import _generate_and_save
                key = _generate_and_save()
        self.assertIsInstance(key, str)
        self.assertGreaterEqual(len(key), 32)

    def test_generated_key_written_to_disk(self):
        """_generate_and_save must persist the key so it survives restarts."""
        import api_service.auth.secret_key as sk_mod
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_key_path = os.path.join(tmpdir, 'secret.key')
            with patch.object(sk_mod, '_SECRET_KEY_PATH', tmp_key_path):
                from api_service.auth.secret_key import _generate_and_save
                key = _generate_and_save()
            with open(tmp_key_path, 'r') as fh:
                persisted = fh.read().strip()
        self.assertEqual(key, persisted)

    def test_two_generation_calls_produce_different_keys(self):
        """
        Each _generate_and_save call must generate a fresh random key
        (i.e. no static seed is used).
        """
        import api_service.auth.secret_key as sk_mod
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = os.path.join(tmpdir, 'k1.key')
            p2 = os.path.join(tmpdir, 'k2.key')
            with patch.object(sk_mod, '_SECRET_KEY_PATH', p1):
                from api_service.auth.secret_key import _generate_and_save
                k1 = _generate_and_save()
            sk_mod.invalidate_cache()
            with patch.object(sk_mod, '_SECRET_KEY_PATH', p2):
                k2 = _generate_and_save()
        self.assertNotEqual(k1, k2)


# ---------------------------------------------------------------------------
# Cache behavior
# ---------------------------------------------------------------------------

class TestSecretKeyCache(_SecretKeyBase):

    def test_second_call_returns_cached_value(self):
        """load_secret_key must return the identical string on repeat calls."""
        os.environ['SUGGESTARR_SECRET_KEY'] = 'stable-secret-for-cache-test-abc123'
        from api_service.auth.secret_key import load_secret_key
        first = load_secret_key()
        second = load_secret_key()
        # Same object identity — cached, no re-read.
        self.assertIs(first, second)

    def test_invalidate_cache_allows_reading_new_value(self):
        """After invalidate_cache the next call re-reads from the source."""
        os.environ['SUGGESTARR_SECRET_KEY'] = 'first-secret-value-long-enough'
        from api_service.auth.secret_key import load_secret_key, invalidate_cache
        first = load_secret_key()

        invalidate_cache()
        os.environ['SUGGESTARR_SECRET_KEY'] = 'second-secret-value-long-enough'
        second = load_secret_key()

        self.assertEqual(first, 'first-secret-value-long-enough')
        self.assertEqual(second, 'second-secret-value-long-enough')
        self.assertNotEqual(first, second)

    def test_cache_not_populated_before_first_call(self):
        """invalidate_cache resets state; module _cached_key must be None."""
        import api_service.auth.secret_key as sk_mod
        from api_service.auth.secret_key import invalidate_cache
        invalidate_cache()
        self.assertIsNone(sk_mod._cached_key)

    def test_cache_populated_after_first_call(self):
        """After load_secret_key, _cached_key must be set to a non-None value."""
        os.environ['SUGGESTARR_SECRET_KEY'] = 'populated-cache-test-key-long'
        import api_service.auth.secret_key as sk_mod
        from api_service.auth.secret_key import load_secret_key
        load_secret_key()
        self.assertIsNotNone(sk_mod._cached_key)


if __name__ == '__main__':
    unittest.main()
