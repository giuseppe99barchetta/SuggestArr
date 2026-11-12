"""Two runs refreshing one Trakt or Simkl link: the one that loses uses the tokens the winner saved."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from api_service.services.simkl.simkl_client import SimklClient
from api_service.services.trakt.trakt_client import TraktClient

NEWER = {'access_token': 'new-access', 'refresh_token': 'new-refresh', 'expires_at': 4_000_000_000}
OLD = {'access_token': 'old-access', 'refresh_token': 'old-refresh', 'expires_at': 1}


def trakt(db):
    return TraktClient('cid', access_token='old-access', refresh_token='old-refresh', expires_at=1, db=db, link_id=7)


def simkl(db):
    return SimklClient('cid', access_token='old-access', refresh_token='old-refresh', expires_at=1, db=db, link_id=7)


CLIENTS = [(trakt, 'get_trakt_oauth_tokens'), (simkl, 'get_simkl_oauth_tokens')]


@pytest.mark.asyncio
@pytest.mark.parametrize('make, getter', CLIENTS)
async def test_tokens_saved_by_another_run_are_used_without_a_second_refresh(make, getter):
    db = MagicMock()
    getattr(db, getter).return_value = dict(NEWER)
    client = make(db)
    client._request = AsyncMock()
    await client.refresh_access_token()
    client._request.assert_not_called()  # the old refresh token is already spent
    assert (client.access_token, client.refresh_token) == ('new-access', 'new-refresh')


@pytest.mark.asyncio
@pytest.mark.parametrize('make, getter', CLIENTS)
async def test_a_refused_refresh_is_forgiven_when_the_winner_saved_tokens_meanwhile(make, getter):
    db = MagicMock()
    getattr(db, getter).side_effect = [dict(OLD), dict(NEWER)]
    client = make(db)
    client._request = AsyncMock(side_effect=RuntimeError('invalid_grant'))
    await client.refresh_access_token()
    assert client.refresh_token == 'new-refresh'


@pytest.mark.asyncio
@pytest.mark.parametrize('make, getter', CLIENTS)
async def test_a_genuine_refusal_still_fails(make, getter):
    db = MagicMock()
    getattr(db, getter).return_value = dict(OLD)
    client = make(db)
    client._request = AsyncMock(side_effect=RuntimeError('invalid_grant'))
    with pytest.raises(RuntimeError):
        await client.refresh_access_token()
