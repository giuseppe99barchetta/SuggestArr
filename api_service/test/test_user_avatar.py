"""Profile image resolution and the authenticated image boundary (no real network)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from flask import Flask

from api_service.services.user_avatar import MAX_IMAGE_BYTES, UserAvatarService


def linked(provider='jellyfin', external_id='user-42', verified=True):
    return {'provider': provider, 'external_user_id': external_id, 'verified': verified}


def resolve(service, config=None, user=None, links=None):
    return asyncio.run(service.resolve(config or {}, user or {}, links or []))


def test_seer_takes_priority_over_media_server():
    service = UserAvatarService()
    service._seer = AsyncMock(return_value=(b'image', 'image/png'))
    service._jellyfin = AsyncMock()
    result = resolve(service, {'SELECTED_SERVICE': 'jellyfin'}, {'seer_user_id': 7}, [linked()])
    assert result == (b'image', 'image/png', 'seer')
    service._seer.assert_awaited_once_with({'SELECTED_SERVICE': 'jellyfin'}, 7)
    service._jellyfin.assert_not_awaited()


@pytest.mark.parametrize('seer_result', [None, TimeoutError(), ValueError('invalid metadata')])
def test_missing_or_offline_seer_uses_linked_account(seer_result):
    service = UserAvatarService()
    service._seer = AsyncMock()
    if isinstance(seer_result, Exception):
        service._seer.side_effect = seer_result
    else:
        service._seer.return_value = seer_result
    service._jellyfin = AsyncMock(return_value=(b'image', 'image/jpeg'))
    config = {'SELECTED_SERVICE': 'jellyfin'}
    assert resolve(service, config, {'seer_user_id': 7}, [linked()]) == (b'image', 'image/jpeg', 'jellyfin')
    service._jellyfin.assert_awaited_once_with(config, 'user-42')


@pytest.mark.parametrize('links', [[], [linked(verified=False)], [linked('plex')], [linked(external_id='')]])
def test_no_guessing_identity_or_using_another_server(links):
    service = UserAvatarService()
    service._seer = AsyncMock()
    service._jellyfin = AsyncMock()
    service._plex = AsyncMock()
    assert resolve(service, {'SELECTED_SERVICE': 'jellyfin'}, links=links) is None
    service._seer.assert_not_awaited()
    service._jellyfin.assert_not_awaited()
    service._plex.assert_not_awaited()


def test_emby_image_uses_configured_server_and_header_auth():
    service = UserAvatarService()
    service._read = AsyncMock(return_value=(b'image', 'image/png'))
    config = {'SELECTED_SERVICE': 'emby', 'JELLYFIN_API_URL': 'http://media/emby/', 'JELLYFIN_TOKEN': 'test-only'}
    assert resolve(service, config, links=[linked('emby')]) == (b'image', 'image/png', 'emby')
    service._read.assert_awaited_once_with(
        'http://media/emby/Users/user-42/Images/Primary?maxWidth=128&maxHeight=128',
        {'X-Emby-Token': 'test-only'},
    )


def test_seer_relative_avatar_keeps_key_on_configured_origin():
    service = UserAvatarService()
    service._json = AsyncMock(return_value={'avatar': '/avatarproxy/7'})
    service._image = AsyncMock(return_value=(b'image', 'image/png'))
    result = asyncio.run(service._seer({'SEER_API_URL': 'http://seer', 'SEER_TOKEN': 'test-only'}, 7))
    assert result == (b'image', 'image/png')
    service._image.assert_awaited_once_with('http://seer/avatarproxy/7', {'X-Api-Key': 'test-only'})


def test_public_cdn_receives_no_provider_credentials():
    service = UserAvatarService()
    service._image = AsyncMock(return_value=(b'image', 'image/png'))
    with patch('api_service.services.user_avatar.validate_url') as validate:
        asyncio.run(service._remote_image('https://cdn.example/avatar.png', 'http://seer', {'X-Api-Key': 'test-only'}))
    validate.assert_called_once_with('https://cdn.example/avatar.png')
    service._image.assert_awaited_once_with('https://cdn.example/avatar.png', None)


def test_explicit_default_port_is_the_same_configured_origin():
    service = UserAvatarService()
    service._image = AsyncMock(return_value=(b'image', 'image/png'))
    with patch('api_service.services.user_avatar.validate_url') as validate:
        asyncio.run(service._remote_image('http://seer:80/avatarproxy/7', 'http://seer', {'X-Api-Key': 'test-only'}))
    validate.assert_not_called()
    service._image.assert_awaited_once_with('http://seer:80/avatarproxy/7', {'X-Api-Key': 'test-only'})


def test_private_upstream_avatar_is_rejected():
    service = UserAvatarService()
    service._json = AsyncMock(return_value={'avatar': 'http://127.0.0.1/internal'})
    service._image = AsyncMock()
    config = {'SEER_API_URL': 'http://seer', 'SEER_TOKEN': 'test-only'}
    with patch('api_service.services.user_avatar.validate_url', side_effect=ValueError('private address')):
        assert resolve(service, config, {'seer_user_id': 7}) is None
    service._image.assert_not_awaited()


@pytest.mark.parametrize('value', ['file:///etc/passwd', 'https://name:password@cdn.example/a', '', None])
def test_invalid_avatar_urls_are_not_fetched(value):
    service = UserAvatarService()
    service._image = AsyncMock()
    assert asyncio.run(service._remote_image(value, 'http://seer', {})) is None
    service._image.assert_not_awaited()


@pytest.mark.parametrize('mime', ['text/html', 'image/svg+xml', 'application/json'])
def test_active_or_non_image_content_is_not_proxied(mime):
    service = UserAvatarService()
    service._read = AsyncMock(return_value=(b'not an image', mime))
    assert asyncio.run(service._image('http://seer/avatar')) is None


def test_plex_owner_image_matches_linked_id():
    service = UserAvatarService()
    service._json = AsyncMock(return_value={'id': 42, 'thumb': 'https://cdn.example/owner.png'})
    service._remote_image = AsyncMock(return_value=(b'owner', 'image/png'))
    assert resolve(service, {'SELECTED_SERVICE': 'plex', 'PLEX_TOKEN': 'test-only'}, links=[linked('plex', '42')]) == (b'owner', 'image/png', 'plex')


def test_plex_shared_or_managed_account_does_not_get_owner_photo():
    service = UserAvatarService()
    service._json = AsyncMock(return_value={'id': 1, 'thumb': 'https://cdn.example/owner.png'})
    service._read = AsyncMock(return_value=(b'<MediaContainer><User id="42" thumb="https://cdn.example/linked.png" /></MediaContainer>', 'application/xml'))
    service._remote_image = AsyncMock(return_value=(b'linked', 'image/png'))
    result = resolve(service, {'SELECTED_SERVICE': 'plex', 'PLEX_TOKEN': 'test-only'}, links=[linked('plex', '42')])
    assert result == (b'linked', 'image/png', 'plex')
    assert service._remote_image.await_args.args[0] == 'https://cdn.example/linked.png'


@pytest.mark.parametrize('status,size,body_size', [(302, 0, 0), (200, MAX_IMAGE_BYTES + 1, 0), (200, None, MAX_IMAGE_BYTES + 1)])
def test_redirects_and_oversized_downloads_are_rejected(status, size, body_size):
    async def chunks(_size):
        yield b'x' * body_size

    response = MagicMock(status=status, content_length=size)
    response.content.iter_chunked = chunks
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    service = UserAvatarService()
    session = MagicMock()
    session.get.return_value = context
    assert asyncio.run(service._read_image(session, 'http://seer/avatar', None)) is None
    assert session.get.call_args.kwargs['allow_redirects'] is False


@pytest.fixture
def avatar_client(monkeypatch):
    from api_service.auth.limiter import limiter
    from api_service.auth.middleware import enforce_authentication, invalidate_setup_cache
    from api_service.blueprints.auth.routes import auth_bp

    monkeypatch.setenv('SUGGESTARR_AUTH_DISABLED', 'false')
    monkeypatch.setenv('AUTH_MODE', 'enabled')
    db = MagicMock()
    db.get_auth_user_count.return_value = 1
    db.get_auth_user_by_id.return_value = {'id': 3, 'username': 'alice', 'role': 'user', 'is_active': True, 'seer_user_id': 8}
    db.get_user_media_profiles.return_value = [linked()]
    monkeypatch.setattr('api_service.auth.middleware.DatabaseManager', lambda: db)
    monkeypatch.setattr('api_service.blueprints.auth.routes.DatabaseManager', lambda: db)
    monkeypatch.setattr('api_service.auth.middleware.load_env_vars', lambda: {'AUTH_MODE': 'enabled'})
    monkeypatch.setattr('api_service.blueprints.auth.routes.ConfigService.get_runtime_config', lambda: {'SELECTED_SERVICE': 'jellyfin'})
    monkeypatch.setattr('api_service.auth.middleware.AuthService.verify_access_token', lambda token: {'sub': '3', 'username': 'alice', 'role': 'user'})
    monkeypatch.setattr(limiter, 'enabled', False)
    invalidate_setup_cache()
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.before_request(enforce_authentication)
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    yield app.test_client(), db
    invalidate_setup_cache()


def test_avatar_requires_authentication(avatar_client):
    client, _db = avatar_client
    with patch.object(UserAvatarService, 'resolve', new_callable=AsyncMock) as fetch:
        assert client.get('/api/auth/me/avatar').status_code == 401
    fetch.assert_not_awaited()


def test_avatar_only_loads_caller_links_and_returns_private_image(avatar_client):
    client, db = avatar_client
    with patch.object(UserAvatarService, 'resolve', new_callable=AsyncMock, return_value=(b'photo', 'image/png', 'seer')) as fetch:
        response = client.get('/api/auth/me/avatar?user_id=99', headers={'Authorization': 'Bearer test-only'})
    assert response.status_code == 200
    assert response.data == b'photo'
    assert response.content_type == 'image/png'
    assert response.headers['Cache-Control'] == 'private, no-store'
    assert response.headers['X-Avatar-Source'] == 'seer'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    db.get_user_media_profiles.assert_called_once_with(3)
    assert fetch.await_args.args[1]['seer_user_id'] == 8


@pytest.mark.parametrize('failure', [False, True])
def test_no_photo_or_provider_failure_selects_local_fallback(avatar_client, failure):
    client, _db = avatar_client
    with patch.object(UserAvatarService, 'resolve', new_callable=AsyncMock, return_value=None) as fetch:
        if failure:
            fetch.side_effect = RuntimeError('private upstream details')
        response = client.get('/api/auth/me/avatar', headers={'Authorization': 'Bearer test-only'})
    assert response.status_code == 204
    assert response.data == b''
    assert response.headers['Cache-Control'] == 'private, no-store'
