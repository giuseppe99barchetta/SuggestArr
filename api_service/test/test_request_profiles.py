"""Tests for the Seer-side request profile check and the messages it lets through."""
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from api_service.utils import request_profiles

PROFILES = {'movie': {'serverId': 1, 'profileId': 4, 'rootFolder': '/movies'}}
CONFIG = {'SEER_API_URL': 'http://seer.internal:5055', 'SEER_TOKEN': 'token'}


def _seer(servers=None, error=None):
    seer = MagicMock(get_radarr_servers=AsyncMock(return_value=servers, side_effect=error))
    seer.__aenter__ = AsyncMock(return_value=seer)
    seer.__aexit__ = AsyncMock(return_value=False)
    return seer


def _check(seer):
    with patch.object(request_profiles.ConfigService, 'get_runtime_config', return_value=CONFIG), \
            patch.object(request_profiles, 'SeerClient', return_value=seer):
        request_profiles.validate_request_profiles_with_seer(PROFILES)


def test_an_unknown_server_is_reported_as_is():
    with pytest.raises(ValueError, match='^Unknown movie server$'):
        _check(_seer(servers=[{'id': 2}]))


def test_client_errors_never_reveal_the_seer_address():
    with pytest.raises(ValueError) as caught:
        _check(_seer(error=aiohttp.InvalidURL(CONFIG['SEER_API_URL'])))
    assert str(caught.value) == 'Could not verify request profiles with Seer'


def test_known_ids_pass():
    _check(_seer(servers=[{'id': 1, 'profiles': [{'id': 4}], 'rootFolders': [{'path': '/movies'}]}]))
