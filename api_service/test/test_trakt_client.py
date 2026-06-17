import time
from unittest.mock import MagicMock

import pytest

from api_service.services.trakt.trakt_client import (
    TraktClient,
    TraktDeviceDenied,
    TraktDeviceExpired,
    TraktDevicePending,
)


class FakeResponse:
    def __init__(self, status, payload=None, headers=None):
        self.status = status
        self._payload = payload or {}
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self._payload

    async def text(self):
        return str(self._payload)


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.responses.pop(0)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_request_device_code_posts_client_id():
    session = FakeSession([
        FakeResponse(200, {
            "device_code": "dev-1",
            "user_code": "ABCD-EFGH",
            "verification_url": "https://trakt.tv/activate",
            "expires_in": 600,
            "interval": 5,
        })
    ])
    client = TraktClient("cid", "secret", session=session)

    result = await client.request_device_code()

    assert result["device_code"] == "dev-1"
    assert session.calls[0][0] == "POST"
    assert session.calls[0][1] == "https://api.trakt.tv/oauth/device/code"
    assert session.calls[0][2]["json"] == {"client_id": "cid"}


@pytest.mark.asyncio
async def test_poll_for_token_updates_instance_without_db_persist_when_no_link_id():
    session = FakeSession([
        FakeResponse(200, {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 7200,
        })
    ])
    db = MagicMock()
    db.get_integration.return_value = {"client_id": "cid", "client_secret": "secret"}
    client = TraktClient("cid", "secret", session=session, db=db)

    result = await client.poll_for_token("device-code")

    assert result["access_token"] == "access"
    assert client.access_token == "access"
    assert client.refresh_token == "refresh"
    assert client.expires_at > int(time.time())
    db.set_integration.assert_not_called()
    db.update_trakt_oauth_tokens.assert_not_called()


@pytest.mark.asyncio
async def test_poll_for_token_returns_tokens_on_success():
    session = FakeSession([
        FakeResponse(200, {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 7200,
        })
    ])
    client = TraktClient("cid", "secret", session=session)

    result = await client.poll_for_token("device-code")

    assert result["access_token"] == "access"
    assert client.access_token == "access"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 429])
async def test_poll_for_token_raises_pending_on_400_and_429(status):
    session = FakeSession([FakeResponse(status)])
    client = TraktClient("cid", "secret", session=session)

    with pytest.raises(TraktDevicePending):
        await client.poll_for_token("device-code")


@pytest.mark.asyncio
async def test_poll_for_token_raises_expired_on_410():
    session = FakeSession([FakeResponse(410)])
    client = TraktClient("cid", "secret", session=session)

    with pytest.raises(TraktDeviceExpired):
        await client.poll_for_token("device-code")


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [418, 409])
async def test_poll_for_token_raises_denied_on_418_and_409(status):
    session = FakeSession([FakeResponse(status)])
    client = TraktClient("cid", "secret", session=session)

    with pytest.raises(TraktDeviceDenied):
        await client.poll_for_token("device-code")


@pytest.mark.asyncio
async def test_refresh_persists_tokens_via_update_trakt_oauth_tokens():
    session = FakeSession([
        FakeResponse(200, {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 7200,
        })
    ])
    db = MagicMock()
    client = TraktClient(
        "cid",
        "secret",
        "old-access",
        "old-refresh",
        expires_at=int(time.time()) - 10,
        session=session,
        db=db,
        link_id=1,
        token_source="manual_oauth",
    )

    result = await client.refresh_access_token()

    assert result["access_token"] == "new-access"
    db.update_trakt_oauth_tokens.assert_called_once()
    assert db.update_trakt_oauth_tokens.call_args.args[:3] == (1, "new-access", "new-refresh")
    assert db.update_trakt_oauth_tokens.call_args.args[3] > int(time.time())
    db.set_integration.assert_not_called()


@pytest.mark.asyncio
async def test_poll_for_token_persists_tokens_via_link_id():
    """poll_for_token calls _apply_and_persist_tokens which persists when link_id is set."""
    session = FakeSession([
        FakeResponse(200, {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 7200,
        })
    ])
    db = MagicMock()
    client = TraktClient(
        "cid", "secret", session=session, db=db,
        link_id=1, token_source="manual_oauth",
    )

    result = await client.poll_for_token("device-code")

    assert result["access_token"] == "access"
    db.update_trakt_oauth_tokens.assert_called_once_with(1, "access", "refresh", client.expires_at)


@pytest.mark.asyncio
async def test_get_user_settings_normalizes_trakt_user_payload():
    session = FakeSession([
        FakeResponse(200, {
            "user": {
                "username": "trakt_name",
                "ids": {"slug": "trakt-slug", "uuid": "uuid-1"},
            }
        })
    ])
    client = TraktClient(
        "cid",
        "secret",
        "access",
        "refresh",
        expires_at=int(time.time()) + 3600,
        session=session,
    )

    result = await client.get_user_settings()

    assert result["trakt_username"] == "trakt_name"
    assert result["trakt_user_id"] == "uuid-1"
    assert session.calls[0][1] == "https://api.trakt.tv/users/settings"


@pytest.mark.asyncio
async def test_recent_history_collapses_episodes_to_unique_parent_shows():
    session = FakeSession([
        FakeResponse(200, [
            {"type": "episode", "show": {"title": "Severance", "year": 2022, "ids": {"tmdb": 95396}}},
            {"type": "episode", "show": {"title": "Severance", "year": 2022, "ids": {"tmdb": 95396}}},
            {"type": "movie", "movie": {"title": "Inception", "year": 2010, "ids": {"tmdb": 27205}}},
        ])
    ])
    client = TraktClient("cid", "secret", "access", "refresh", expires_at=int(time.time()) + 3600, session=session)

    result = await client.get_recent_items(limit=10)

    assert result == [
        {"tmdb_id": "95396", "media_type": "tv", "title": "Severance", "year": 2022, "watched_at": 0},
        {"tmdb_id": "27205", "media_type": "movie", "title": "Inception", "year": 2010, "watched_at": 0},
    ]


@pytest.mark.asyncio
async def test_existing_content_uses_watched_movies_and_shows_tmdb_ids():
    session = FakeSession([
        FakeResponse(200, [{"movie": {"title": "Heat", "year": 1995, "ids": {"tmdb": 949}}}]),
        FakeResponse(200, [{"show": {"title": "Dark", "year": 2017, "ids": {"tmdb": 70523}}}]),
    ])
    client = TraktClient("cid", "secret", "access", "refresh", expires_at=int(time.time()) + 3600, session=session)

    await client.init_existing_content()

    assert client.existing_content == {
        "movie": [{"tmdb_id": "949", "title": "Heat", "year": 1995}],
        "tv": [{"tmdb_id": "70523", "title": "Dark", "year": 2017}],
    }


def test_normalize_watched_items_includes_year():
    payload = [
        {"movie": {"title": "Heat", "year": 1995, "ids": {"tmdb": 949}}},
        {"movie": {"title": "No Year", "ids": {"tmdb": 27205}}},
    ]

    normalized = TraktClient._normalize_watched_items(payload, "movie")

    assert normalized == [
        {"tmdb_id": "949", "title": "Heat", "year": 1995},
        {"tmdb_id": "27205", "title": "No Year", "year": None},
    ]


def test_normalize_recommendation_items_deduplicates_by_tmdb_id():
    client = TraktClient("cid", "secret")
    payload = [
        {"title": "Inception", "year": 2010, "ids": {"tmdb": 27205}},
        {"title": "Duplicate", "year": 2010, "ids": {"tmdb": 27205}},
        {"title": "No TMDB"},
    ]

    normalized = client._normalize_recommendation_items(payload, "movie")

    assert normalized == [{
        "tmdb_id": "27205",
        "media_type": "movie",
        "title": "Inception",
        "year": 2010,
    }]


@pytest.mark.asyncio
async def test_get_recommendations_requests_trakt_endpoint():
    session = FakeSession([
        FakeResponse(200, [
            {"title": "Arrival", "year": 2016, "ids": {"tmdb": 329865}},
        ]),
    ])
    client = TraktClient("cid", "secret", "access", session=session)

    result = await client.get_recommendations(
        "movie",
        limit=15,
        ignore_collected=True,
        ignore_watched=True,
    )

    assert result[0]["tmdb_id"] == "329865"
    assert session.calls[0][0] == "GET"
    assert session.calls[0][1] == "https://api.trakt.tv/recommendations/movies"
    assert session.calls[0][2]["params"] == {
        "limit": 15,
        "extended": "min",
        "ignore_collected": "true",
        "ignore_watched": "true",
    }


@pytest.mark.asyncio
async def test_401_refreshes_once_and_retries():
    session = FakeSession([
        FakeResponse(401, {"error": "expired"}),
        FakeResponse(200, {"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 7200}),
        FakeResponse(200, []),
    ])
    db = MagicMock()
    db.get_integration.return_value = {
        "client_id": "cid",
        "client_secret": "secret",
        "access_token": "old",
        "refresh_token": "refresh",
    }
    client = TraktClient("cid", "secret", "old", "refresh", expires_at=int(time.time()) + 3600, session=session, db=db)

    result = await client.get_recent_items(limit=10)

    assert result == []
    assert session.calls[0][0] == "GET"
    assert session.calls[1][0] == "POST"
    assert session.calls[2][0] == "GET"
    assert client.access_token == "new-access"
    db.update_trakt_oauth_tokens.assert_not_called()
    db.set_integration.assert_not_called()
