"""
Secret key management for JWT signing.

Load order (first match wins):
  1. SUGGESTARR_SECRET_KEY env var  — for Docker secrets / K8s secrets / CI injection
  2. /config/config_files/secret.key on disk — auto-generated on first boot

The file is created with mode 0o600 (owner-read-only) on Unix.
On Windows the mode is a best-effort; NTFS ACLs are not modified.

Security note: the key is 32 bytes of CSPRNG output (256-bit security).
Losing the file invalidates all active sessions; users must log in again.
"""
import os
import secrets

from api_service.config.logger_manager import LoggerManager

logger = LoggerManager.get_logger("SecretKey")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_SECRET_KEY_PATH = os.path.join(BASE_DIR, 'config', 'config_files', 'secret.key')

# Module-level cache so the key is read from disk only once per process.
_cached_key: str | None = None


def load_secret_key() -> str:
    """
    Return the application secret key used to sign JWTs.

    Reads from env var first, then from disk, generating the file on first
    boot if absent.  Result is cached in-process after the first call.

    Returns:
        str: A URL-safe base64 secret key string (≥32 random bytes).
    """
    global _cached_key
    if _cached_key is not None:
        return _cached_key

    # 1. Env-var injection (highest priority — no disk I/O needed)
    env_key = os.environ.get('SUGGESTARR_SECRET_KEY', '').strip()
    if env_key:
        _cached_key = env_key
        logger.debug("Secret key loaded from SUGGESTARR_SECRET_KEY env var")
        return _cached_key

    # 2. Persistent file on disk
    if os.path.exists(_SECRET_KEY_PATH):
        with open(_SECRET_KEY_PATH, 'r', encoding='ascii') as fh:
            key = fh.read().strip()
        if key:
            _cached_key = key
            logger.debug("Secret key loaded from %s", _SECRET_KEY_PATH)
            return _cached_key
        logger.warning("secret.key file is empty — regenerating")

    # 3. Generate a new key and persist it
    _cached_key = _generate_and_save()
    return _cached_key


def _generate_and_save() -> str:
    """
    Generate a new 32-byte CSPRNG key, save it to disk with restrictive
    permissions, and return it.

    Returns:
        str: The newly generated key.
    """
    key = secrets.token_urlsafe(32)
    os.makedirs(os.path.dirname(_SECRET_KEY_PATH), exist_ok=True)

    # O_WRONLY | O_CREAT | O_TRUNC + mode 0o600 creates the file with
    # owner-read-only permissions atomically on POSIX systems.
    # On Windows, os.open accepts the mode but does not enforce ACLs;
    # the resulting file is still readable only to the process owner
    # in most default configurations.
    fd = os.open(_SECRET_KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='ascii') as fh:
        fh.write(key)

    logger.info("Generated new secret key at %s", _SECRET_KEY_PATH)
    return key


def invalidate_cache() -> None:
    """
    Clear the in-process key cache.

    Only needed in tests where the env var or file changes between calls.
    """
    global _cached_key
    _cached_key = None
