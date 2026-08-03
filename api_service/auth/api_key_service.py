"""Generation and verification of high-entropy SuggestArr API keys."""
import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from api_service.db.api_key_repository import ApiKeyRepository

MAX_RAW_KEY_LENGTH = 256


class ApiKeyService:
    def __init__(self, database):
        self.db = database
        self.repository = ApiKeyRepository(database)

    def create_key(self, user_id, name, expires_at=None):
        # The underscore is the wire-format delimiter, so keep it out of parts.
        key_id = secrets.token_urlsafe(12).replace('_', '')
        secret = secrets.token_urlsafe(32).replace('_', '')
        raw_key = f"sarr_{key_id}_{secret}"
        prefix = f"sarr_{key_id}_..."
        row_id = self.repository.create_key(user_id, name, key_id, self._hash(secret), prefix, expires_at)
        return {'id': row_id, 'name': name, 'key': raw_key, 'prefix': prefix,
                'created_at': datetime.now(timezone.utc), 'expires_at': expires_at}

    def resolve(self, raw_key):
        if not isinstance(raw_key, str) or len(raw_key) > MAX_RAW_KEY_LENGTH:
            return None
        parts = raw_key.split('_')
        if len(parts) != 3 or parts[0] != 'sarr' or not parts[1] or not parts[2]:
            return None
        record = self.repository.get_key_by_public_id(parts[1])
        if not record or record['revoked_at'] or self._expired(record['expires_at']):
            return None
        if not hmac.compare_digest(record['secret_hash'], self._hash(parts[2])):
            return None
        user = self.db.get_auth_user_by_id(record['user_id'])
        if not user or not user.get('is_active', True):
            return None
        self.repository.touch_last_used(record['id'])
        return {'user': user, 'api_key_id': record['id'], 'api_key_name': record['name']}

    @staticmethod
    def _hash(secret):
        return hashlib.sha256(secret.encode('utf-8')).hexdigest()

    @staticmethod
    def _expired(value):
        if not value:
            return False
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value <= datetime.now(timezone.utc)
