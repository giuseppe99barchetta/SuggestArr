import asyncio
from unittest.mock import MagicMock, patch

from api_service.services.trakt.media_user_augmentor import MediaUserTraktAugmentor


class FakeTraktClient:
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


def _db_with_link_and_tokens(status="connected"):
    db = MagicMock()
    db.get_trakt_account_link.return_value = {
        "id": 1,
        "media_user_identity_id": 1, "connected": True,
        "status": status,
        "token_source": "manual_oauth",
    }
    db.get_trakt_oauth_tokens.return_value = {
        "access_token": "acc", "refresh_token": "ref", "expires_at": 999,
    }
    db.get_enabled_trakt_sources.return_value = [
        {"source_type": "watched_history", "use_as_seed": True, "use_as_exclusion": True},
    ]
    return db


def test_augment_returns_seeds_and_watched_ids():
    db = _db_with_link_and_tokens()
    aug = MediaUserTraktAugmentor("cid", "secret", db=db)
    with patch("api_service.services.trakt.media_user_augmentor.TraktClient", FakeTraktClient):
        result = asyncio.run(aug.augment(1))
    assert result is not None
    assert result.seed_items == [{"tmdb_id": "11", "media_type": "movie", "title": "A", "year": 2001}]
    assert result.watched_ids == {"movie": {"11", "22"}, "tv": {"33"}}
    assert FakeTraktClient.last.link_id == 1
    assert FakeTraktClient.last.token_source == "manual_oauth"


def test_augment_no_account_returns_none():
    db = MagicMock()
    db.get_trakt_account_link.return_value = None
    aug = MediaUserTraktAugmentor("cid", "secret", db=db)
    with patch("api_service.services.trakt.media_user_augmentor.TraktClient", FakeTraktClient):
        assert asyncio.run(aug.augment(1)) is None


def test_augment_skips_revoked_and_errored():
    aug = MediaUserTraktAugmentor("cid", "secret", db=_db_with_link_and_tokens(status="revoked"))
    with patch("api_service.services.trakt.media_user_augmentor.TraktClient", FakeTraktClient):
        assert asyncio.run(aug.augment(1)) is None


def test_augment_get_recent_items_failure_returns_watched_ids():
    """get_recent_items fails internally (returns []) but watched_ids still succeed."""
    db = _db_with_link_and_tokens()

    class Boom(FakeTraktClient):
        async def get_recent_items(self, limit=10):
            raise RuntimeError("trakt 401")

    aug = MediaUserTraktAugmentor("cid", "secret", db=db)
    with patch("api_service.services.trakt.media_user_augmentor.TraktClient", Boom):
        result = asyncio.run(aug.augment(1))
    assert result is not None
    assert result.seed_items == []
    assert result.watched_ids == {"movie": {"11", "22"}, "tv": {"33"}}
    db.mark_trakt_account_link_error.assert_not_called()


def test_augment_disabled_without_credentials():
    aug = MediaUserTraktAugmentor("", "", db=_db_with_link_and_tokens())
    assert aug.enabled is False
    assert asyncio.run(aug.augment(1)) is None


@patch("api_service.services.trakt.media_user_augmentor.DatabaseManager")
def test_from_env_returns_none_without_credentials(_db):
    assert MediaUserTraktAugmentor.from_env({}) is None
    assert MediaUserTraktAugmentor.from_env({"TRAKT_CLIENT_ID": "", "TRAKT_CLIENT_SECRET": ""}) is None


@patch("api_service.services.trakt.media_user_augmentor.DatabaseManager")
def test_from_env_builds_enabled_augmentor(_db):
    aug = MediaUserTraktAugmentor.from_env({"TRAKT_CLIENT_ID": "cid", "TRAKT_CLIENT_SECRET": "secret"})
    assert aug is not None
    assert aug.enabled is True


@patch("api_service.services.trakt.media_user_augmentor.DatabaseManager")
def test_from_env_falls_back_to_integrations_block(_db):
    env = {"integrations": {"trakt": {"client_id": "cid", "client_secret": "secret"}}}
    aug = MediaUserTraktAugmentor.from_env(env)
    assert aug is not None
    assert aug.enabled is True
