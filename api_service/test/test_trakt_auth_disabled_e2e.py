"""End-to-end: profile-based Trakt augmentation under SUGGESTARR_AUTH_DISABLED=true.

Proves the feature works with zero auth_users rows and resolves Trakt by
profile_id against a real DatabaseManager -- no login-account dependency.
The Trakt network client is stubbed; the DB is real SQLite.
"""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from api_service.db.database_manager import DatabaseManager
from api_service.services.trakt.media_user_augmentor import MediaUserTraktAugmentor


class FakeTraktClient:
    """Stub TraktClient: no network, deterministic recent + watched history."""
    last = None

    def __init__(self, client_id, client_secret, access_token="", refresh_token="",
                 expires_at=None, session=None, db=None, link_id=None,
                 token_source="manual_oauth", **_):
        self.link_id = link_id
        self.token_source = token_source
        self.existing_content = {"movie": [], "tv": []}
        FakeTraktClient.last = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get_recent_items(self, limit=10):
        return [{"tmdb_id": "11", "media_type": "movie", "title": "A", "year": 2001}]

    async def init_existing_content(self):
        self.existing_content = {
            "movie": [{"tmdb_id": "11"}, {"tmdb_id": "22"}],
            "tv": [{"tmdb_id": "33"}],
        }


@pytest.fixture
def auth_disabled_db():
    """Real SQLite DatabaseManager with auth disabled and zero auth_users rows."""
    import api_service.db.database_manager as dm_mod

    dm_mod.DatabaseManager._instance = None
    fd, db_file = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    path_patch = patch.object(dm_mod, "DB_PATH", db_file)
    env_patch = patch(
        "api_service.db.database_manager.load_env_vars",
        return_value={"DB_TYPE": "sqlite"},
    )
    path_patch.start()
    env_patch.start()
    auth_patch = patch.dict(os.environ, {"SUGGESTARR_AUTH_DISABLED": "true"})
    auth_patch.start()

    manager = DatabaseManager()
    try:
        yield manager
    finally:
        dm_mod.DatabaseManager._instance = None
        auth_patch.stop()
        path_patch.stop()
        env_patch.stop()
        try:
            os.unlink(db_file)
        except FileNotFoundError:
            pass


def _auth_users_count(db):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM auth_users")
        return cursor.fetchone()[0]


def _setup_linked_media_user(db):
    """Create a fully linked media user: identity + link + tokens + source."""
    expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
    identity = db.upsert_media_user_identity("jellyfin", "jf-1", "alice")
    link_id = db.upsert_trakt_account_link(
        media_user_identity_id=identity["id"],
        trakt_user_id="trakt-1",
        trakt_username="alice_trakt",
        token_source="manual_oauth",
        status="connected",
    )
    db.upsert_trakt_oauth_tokens(link_id, "acc", "ref", expires_at)
    db.upsert_trakt_source(
        media_user_identity_id=identity["id"],
        source_type="watched_history",
        source_key="watched_history",
        enabled=True,
        use_as_seed=True,
        use_as_exclusion=True,
    )
    return identity["id"]


def test_linked_media_user_augments_with_zero_auth_users(auth_disabled_db):
    db = auth_disabled_db
    assert os.environ.get("SUGGESTARR_AUTH_DISABLED") == "true"
    assert _auth_users_count(db) == 0

    media_user_identity_id = _setup_linked_media_user(db)

    aug = MediaUserTraktAugmentor("cid", "secret", db=db)
    with patch(
        "api_service.services.trakt.media_user_augmentor.TraktClient",
        FakeTraktClient,
    ):
        result = asyncio.run(aug.augment(media_user_identity_id))

    assert result is not None
    assert result.seed_items == [
        {"tmdb_id": "11", "media_type": "movie", "title": "A", "year": 2001}
    ]
    assert result.watched_ids == {"movie": {"11", "22"}, "tv": {"33"}}
    assert FakeTraktClient.last.link_id is not None
    assert FakeTraktClient.last.token_source == "manual_oauth"
    assert _auth_users_count(db) == 0


def test_unlinked_media_user_is_silent_noop(auth_disabled_db):
    db = auth_disabled_db
    assert _auth_users_count(db) == 0

    aug = MediaUserTraktAugmentor("cid", "secret", db=db)
    with patch(
        "api_service.services.trakt.media_user_augmentor.TraktClient",
        FakeTraktClient,
    ):
        result = asyncio.run(aug.augment(999999))

    assert result is None
    assert _auth_users_count(db) == 0
