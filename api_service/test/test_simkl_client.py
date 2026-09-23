"""Tests for the Simkl API client.

Response shapes here were captured from the live Simkl API rather than written
from the docs, because several of them contradict what the docs imply.
"""
import asyncio
from unittest.mock import patch

import pytest

from api_service.services.simkl.simkl_client import (
    SimklAuthError,
    SimklClient,
    SimklClientIdError,
    SimklError,
    SimklPinExpired,
    SimklPinFlowError,
    SimklPinPending,
)


class FakeResponse:
    def __init__(self, status=200, payload=None, text=""):
        self.status = status
        self._payload = payload if payload is not None else {}
        self._text = text

    async def json(self, content_type=None):
        return self._payload

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class FakeSession:
    """Records every request so call ordering and parameters can be asserted."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.closed = False

    def _respond(self, method, url, headers=None, params=None):
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "params": params or {}})
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def get(self, url, **kwargs):
        return self._respond("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._respond("POST", url, **kwargs)

    async def close(self):
        self.closed = True


def make_client(responses, **kwargs):
    session = FakeSession(responses)
    client = SimklClient("cid", session=session, **kwargs)
    return client, session


async def _no_sleep(_seconds):
    """Collapse retry backoff so the retry tests stay fast."""
    return None


# ---- Required request shape --------------------------------------------------

def test_every_request_carries_the_required_app_params_and_user_agent():
    client, session = make_client([FakeResponse(payload={})])
    asyncio.run(client.get_activities())

    call = session.calls[0]
    assert call["params"]["client_id"] == "cid"
    assert call["params"]["app-name"] == "suggestarr"
    assert call["params"]["app-version"]
    assert call["headers"]["User-Agent"].startswith("suggestarr/")


def test_authenticated_requests_send_the_bearer_token_and_anonymous_ones_do_not():
    client, session = make_client(
        [FakeResponse(payload={}), FakeResponse(payload={"user_code": "X"})],
        access_token="tok",
    )
    asyncio.run(client.get_activities())
    asyncio.run(client.request_pin_code())

    assert session.calls[0]["headers"]["Authorization"] == "Bearer tok"
    assert "Authorization" not in session.calls[1]["headers"]


# ---- PIN flow ----------------------------------------------------------------

def test_request_pin_code_normalizes_the_live_payload():
    client, _ = make_client([FakeResponse(payload={
        "result": "OK",
        "device_code": "DEVICE_CODE",
        "user_code": "8CCE9",
        "verification_url": "https://simkl.com/pin",
        "verification_uri": "https://simkl.com/pin",
        "expires_in": 900,
        "interval": 5,
    })])
    result = asyncio.run(client.request_pin_code())

    assert result == {
        "user_code": "8CCE9",
        "verification_uri": "https://simkl.com/pin",
        "expires_in": 900,
        "interval": 5,
    }


def test_pending_pin_raises_pending():
    client, _ = make_client([FakeResponse(payload={"result": "KO", "message": "Authorization pending"})])
    with pytest.raises(SimklPinPending):
        asyncio.run(client.poll_for_token("8CCE9"))


def test_pin_is_expired_when_the_response_offers_a_new_device_code():
    """Simkl answers a dead PIN by handing back a fresh code payload.

    The signal is the presence of device_code, not its value: Simkl sends the
    literal placeholder string "DEVICE_CODE" there.
    """
    client, _ = make_client([FakeResponse(payload={
        "result": "OK", "device_code": "DEVICE_CODE", "user_code": "NEW11",
    })])
    with pytest.raises(SimklPinExpired):
        asyncio.run(client.poll_for_token("DEAD1"))


def test_authorized_pin_returns_and_stores_the_token():
    client, _ = make_client([FakeResponse(payload={"result": "OK", "access_token": "tok-123"})])
    token = asyncio.run(client.poll_for_token("8CCE9"))

    assert token == "tok-123"
    assert client.access_token == "tok-123"


def test_unrecognized_pin_response_raises_rather_than_looping():
    client, _ = make_client([FakeResponse(payload={"something": "else"})])
    with pytest.raises(SimklPinFlowError):
        asyncio.run(client.poll_for_token("8CCE9"))


def test_polling_without_a_code_never_reaches_the_network():
    client, session = make_client([])
    with pytest.raises(SimklPinFlowError):
        asyncio.run(client.poll_for_token("  "))
    assert session.calls == []


def test_user_code_is_url_encoded_into_the_path():
    """A code is interpolated into the URL, so it must not be able to escape it."""
    client, session = make_client([FakeResponse(payload={"access_token": "t"})])
    asyncio.run(client.poll_for_token("../../sync/activities"))

    assert "/oauth/pin/..%2F..%2Fsync%2Factivities" in session.calls[0]["url"]


# ---- Error mapping -----------------------------------------------------------

def test_401_raises_auth_error_without_retrying():
    client, session = make_client([FakeResponse(status=401)], access_token="stale")
    with pytest.raises(SimklAuthError):
        asyncio.run(client.get_activities())
    assert len(session.calls) == 1


def test_412_raises_client_id_error_without_retrying():
    client, session = make_client([FakeResponse(status=412)])
    with pytest.raises(SimklClientIdError):
        asyncio.run(client.get_activities())
    assert len(session.calls) == 1


@pytest.mark.parametrize("status", [400, 403, 404, 409])
def test_deterministic_4xx_statuses_are_not_retried(status):
    """Simkl warns that retrying a 4xx just burns quota and induces a 429."""
    client, session = make_client([FakeResponse(status=status)])
    with pytest.raises(SimklError):
        asyncio.run(client.get_activities())
    assert len(session.calls) == 1


def test_429_is_retried_and_succeeds():
    client, session = make_client([
        FakeResponse(status=429),
        FakeResponse(payload={"all": "2026-01-01T00:00:00Z"}),
    ])
    with patch("asyncio.sleep", _no_sleep):
        result = asyncio.run(client.get_activities())

    assert result == {"all": "2026-01-01T00:00:00Z"}
    assert len(session.calls) == 2


def test_retries_give_up_after_the_maximum():
    client, session = make_client([FakeResponse(status=503)] * SimklClient.MAX_RETRIES)
    with patch("asyncio.sleep", _no_sleep):
        with pytest.raises(SimklError):
            asyncio.run(client.get_activities())
    assert len(session.calls) == SimklClient.MAX_RETRIES


# ---- all-items ---------------------------------------------------------------

def test_get_all_items_unwraps_the_type_keyed_response():
    entries = [{"status": "watching", "show": {"title": "A", "ids": {"simkl": 1}}}]
    client, _ = make_client([FakeResponse(payload={"shows": entries})])
    assert asyncio.run(client.get_all_items("shows", "watching")) == entries


def test_get_all_items_tolerates_the_empty_object_simkl_returns_for_empty_buckets():
    """An empty bucket comes back as {} rather than {"shows": []}."""
    client, _ = make_client([FakeResponse(payload={})])
    assert asyncio.run(client.get_all_items("movies", "completed")) == []


def test_get_all_items_passes_date_from_and_ids_only_through():
    client, session = make_client([FakeResponse(payload={})])
    asyncio.run(client.get_all_items(
        "shows", "completed", date_from="2026-01-01T00:00:00Z", ids_only=True,
    ))
    params = session.calls[0]["params"]
    assert params["date_from"] == "2026-01-01T00:00:00Z"
    assert params["extended"] == "ids_only"


def test_get_all_items_omits_optional_params_when_unset():
    client, session = make_client([FakeResponse(payload={})])
    asyncio.run(client.get_all_items("shows", "completed"))
    params = session.calls[0]["params"]
    assert "date_from" not in params
    assert "extended" not in params


def test_get_all_items_rejects_an_unknown_media_type():
    client, _ = make_client([])
    with pytest.raises(ValueError):
        asyncio.run(client.get_all_items("books", "completed"))


def test_a_non_object_body_raises_rather_than_reading_as_an_empty_bucket():
    """An empty list is a claim the removal sweep acts on by deleting rows.

    A body we cannot parse must not be able to make that claim, so it fails
    loudly and the sync falls back to the cache it already has.
    """
    client, _ = make_client([FakeResponse(payload=["not", "an", "object"])])
    with pytest.raises(SimklError):
        asyncio.run(client.get_all_items("shows", "completed"))


def test_status_matrix_matches_what_simkl_actually_exposes():
    """Movies have no watching or hold bucket; asking for one silently returns {}."""
    assert SimklClient.STATUSES_BY_TYPE["movies"] == ("completed", "dropped")
    for media_type in ("shows", "anime"):
        assert SimklClient.STATUSES_BY_TYPE[media_type] == (
            "watching", "completed", "hold", "dropped",
        )


def test_activities_key_for_tv_differs_from_its_url_path_segment():
    assert SimklClient.ACTIVITIES_KEY_BY_TYPE["shows"] == "tv_shows"
    assert SimklClient.ACTIVITIES_KEY_BY_TYPE["anime"] == "anime"
    assert SimklClient.ACTIVITIES_KEY_BY_TYPE["movies"] == "movies"


# ---- Settings normalization --------------------------------------------------

def test_user_settings_keeps_only_the_identity_fields_and_drops_pii():
    client, _ = make_client([FakeResponse(payload={
        "user": {
            "name": "Wire", "age": "35", "gender": "male",
            "bio": "private", "loc": "somewhere", "avatar": "http://x",
        },
        "account": {"id": 8307044, "type": "free", "timezone": "UTC"},
    })])
    result = asyncio.run(client.get_user_settings())

    assert result == {"simkl_user_id": "8307044", "simkl_username": "Wire"}
    for leaked in ("age", "gender", "bio", "loc", "avatar"):
        assert leaked not in result


def test_user_settings_survives_a_payload_with_neither_block():
    client, _ = make_client([FakeResponse(payload={})])
    assert asyncio.run(client.get_user_settings()) == {
        "simkl_user_id": "", "simkl_username": "",
    }
