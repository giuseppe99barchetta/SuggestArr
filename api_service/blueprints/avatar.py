"""Shared profile-image response for authenticated account endpoints."""

from flask import make_response

from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.services.config_service import ConfigService
from api_service.services.user_avatar import UserAvatarService
from api_service.utils.asyncio_loop import run_coroutine_sync

logger = LoggerManager.get_logger('AvatarRoute')


async def _fetch_avatar(config, user, links):
    async with UserAvatarService() as service:
        return await service.resolve(config, user, links)


def user_avatar_response(user_id):
    """Proxy an authorised account's image, or return 204 for the local fallback.

    Callers enforce ownership/role checks before invoking this helper.
    Provider credentials and upstream URLs never reach the response.
    """
    avatar = None
    try:
        user_id = int(user_id)
        db = DatabaseManager()
        user = db.get_auth_user_by_id(user_id)
        if user:
            links = db.get_user_media_profiles(user_id)
            avatar = run_coroutine_sync(_fetch_avatar(ConfigService.get_runtime_config(), user, links), logger)
    except Exception:
        logger.debug('Profile image unavailable')
    if avatar:
        content, mime_type, source = avatar
        response = make_response(content, 200)
        response.headers['Content-Type'] = mime_type
        response.headers['X-Avatar-Source'] = source
        response.headers['X-Content-Type-Options'] = 'nosniff'
    else:
        response = make_response('', 204)
    response.headers['Cache-Control'] = 'private, no-store'
    return response
