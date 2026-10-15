"""Expire only verified, tracked SuggestArr requests still pending in Seer."""
import threading
from datetime import datetime, timedelta, timezone

from api_service.config.config import validate_seer_expiry_settings
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.services.config_service import ConfigService
from api_service.services.seer.seer_client import SeerClient, normalize_seer_url, parse_seer_timestamp
from api_service.utils.asyncio_loop import run_coroutine_sync

_run_lock = threading.Lock()
logger = LoggerManager.get_logger('RequestExpiry')


def _matches_request(item, remote):
    if not isinstance(remote, dict):
        return False
    media = remote.get('media')
    if not isinstance(media, dict):
        return False
    try:
        return (
            type(remote.get('id')) is int and remote['id'] == item['seer_request_id']
            and str(media.get('tmdbId')) == str(item['tmdb_id'])
            and remote.get('type') == item['media_type']
            and parse_seer_timestamp(remote['createdAt']) == parse_seer_timestamp(item['seer_created_at'])
        )
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return False


async def execute_request_expiry(*, dry_run=None):
    """Manual and scheduled executions share the same lock and enabled gate."""
    if not _run_lock.acquire(blocking=False):
        return {'status': 'already_running'}
    try:
        env = ConfigService.get_runtime_config()
        validate_seer_expiry_settings(env)
        days = env.get('SEER_AUTO_DECLINE_DAYS', 0)
        dry_run = env.get('SEER_AUTO_DECLINE_DRY_RUN', True) if dry_run is None else dry_run
        result = dict(status='ok', dry_run=dry_run, candidates=0, simulated=0, declined=0, skipped=0, errors=0)
        if days == 0:
            return {**result, 'status': 'disabled'}
        try:
            instance = normalize_seer_url(env.get('SEER_API_URL', ''))
        except (ValueError, AttributeError):
            return {**result, 'status': 'not_configured', 'errors': 1}
        if not env.get('SEER_TOKEN'):
            return {**result, 'status': 'not_configured', 'errors': 1}
        db = DatabaseManager()
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        items = db.get_expiring_seer_requests(cutoff, instance)
        result['candidates'] = len(items)
        async with SeerClient(instance, env['SEER_TOKEN']) as seer:
            for item in items:
                action, reason = 'error', 'Seer request could not be verified'
                try:
                    status, remote = await seer.request_expiry_action(item['seer_request_id'])
                    if status == 404:
                        action, reason = 'skipped', 'Request no longer exists in Seer'
                    elif status != 200:
                        reason = f'Seer lookup failed (HTTP {status})'
                    elif not _matches_request(item, remote):
                        action, reason = 'skipped', 'Remote request identity could not be verified'
                    elif not seer._is_pending_request(remote):
                        action, reason = 'skipped', 'Request is no longer pending approval'
                    elif dry_run:
                        action, reason = 'simulated', f'Would decline: pending for more than {days} days'
                    else:
                        status, remote = await seer.request_expiry_action(item['seer_request_id'], decline=True)
                        if status == 200 and _matches_request(item, remote) and remote.get('status') in (3, '3'):
                            action, reason = 'declined', f'Automatically declined after {days} days'
                        elif status in (404, 409):
                            action, reason = 'skipped', 'Request removed or already decided during expiry'
                        else:
                            reason = f'Seer decline failed or was not confirmed (HTTP {status})'
                except Exception:
                    logger.warning('Expiry failed for delivery %s', item['delivery_id'])
                db.add_request_expiry_log(item, action, reason, dry_run)
                result['errors' if action == 'error' else action] += 1
        logger.info('Request expiry finished: %s', result)
        return result
    finally:
        _run_lock.release()


def run_request_expiry():
    try:
        run_coroutine_sync(execute_request_expiry(), logger)
    except Exception:
        logger.error('Scheduled request expiry failed', exc_info=True)
