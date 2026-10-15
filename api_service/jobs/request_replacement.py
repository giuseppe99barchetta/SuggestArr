"""Observe explicit Seerr rejections and generate at most one alternative each."""
from api_service.config.logger_manager import LoggerManager
from api_service.db.database_manager import DatabaseManager
from api_service.jobs.job_manager import JobManager
from api_service.jobs.request_expiry import _matches_request, _run_lock
from api_service.services.config_service import ConfigService
from api_service.services.seer.seer_client import SeerClient, normalize_seer_url
from api_service.utils.asyncio_loop import run_coroutine_sync

logger = LoggerManager.get_logger('RequestReplacement')


async def execute_request_replacements():
    if not _run_lock.acquire(blocking=False):
        return {'status': 'already_running'}
    try:
        env = ConfigService.get_runtime_config()
        result = dict(status='ok', checked=0, queued=0, exhausted=0, ignored=0, pending=0, errors=0)
        if env.get('REPLACE_REJECTED_REQUESTS') is not True:
            return {**result, 'status': 'disabled'}
        try:
            instance = normalize_seer_url(env.get('SEER_API_URL', ''))
        except (ValueError, AttributeError):
            return {**result, 'status': 'not_configured', 'errors': 1}
        if not env.get('SEER_TOKEN'):
            return {**result, 'status': 'not_configured', 'errors': 1}
        db = DatabaseManager()
        async with SeerClient(instance, env['SEER_TOKEN']) as seer:
            for item in db.get_seer_requests_to_check(instance):
                try:
                    http_status, remote = await seer.request_expiry_action(item['seer_request_id'])
                    if http_status == 404:
                        remote_status, state, reason = -1, 'ignored', 'Request was removed; no explicit rejection'
                    elif http_status != 200:
                        remote_status, state, reason = 1, 'observing', f'Seerr lookup failed (HTTP {http_status})'
                        result['errors'] += 1
                    elif not _matches_request(item, remote):
                        remote_status, state, reason = -1, 'ignored', 'Remote request identity could not be verified'
                    elif type(remote.get('status')) is not int or remote['status'] not in range(1, 6):
                        remote_status, state, reason = 1, 'observing', 'Unrecognized remote request status'
                        result['errors'] += 1
                    else:
                        remote_status = remote['status']
                        if remote_status == 3:
                            automatic = db.was_automatically_declined(item['delivery_id'])
                            state = 'ignored' if automatic else 'pending'
                            reason = 'Automatic expiry decline' if automatic else 'Rejected in Seerr; awaiting an alternative'
                        else:
                            state = 'observing' if remote_status == 1 else 'ignored'
                            reason = 'Awaiting Seerr decision' if remote_status == 1 else 'Request was not rejected'
                    db.record_seer_request_check(item['delivery_id'], remote_status, state, reason)
                    result['checked'] += 1
                    if state == 'ignored':
                        result['ignored'] += 1
                except Exception:
                    logger.warning('Could not check delivery %s', item['delivery_id'], exc_info=True)
                    result['errors'] += 1
        manager = JobManager.get_instance()
        attempts_by_job = {}
        for item in db.get_pending_request_replacements(instance):
            try:
                attempts = attempts_by_job.get(item['job_id'], 0)
                if attempts >= max(1, int(item.get('max_results') or 1)):
                    db.finish_request_replacement(item['delivery_id'], 'pending', 'Waiting for the next check: job request limit')
                    result['pending'] += 1
                    continue
                attempts_by_job[item['job_id']] = attempts + 1
                if db.was_automatically_declined(item['delivery_id']):
                    state, reason = 'ignored', 'Automatic expiry decline'
                else:
                    state, reason = await manager.execute_replacement(item)
                db.finish_request_replacement(item['delivery_id'], state, reason)
                result[state] += 1
            except Exception:
                db.finish_request_replacement(item['delivery_id'], 'pending', 'Alternative generation failed; will retry')
                logger.warning('Replacement failed for delivery %s', item['delivery_id'], exc_info=True)
                result['errors'] += 1
        return result
    finally:
        _run_lock.release()


def run_request_replacements():
    try:
        run_coroutine_sync(execute_request_replacements(), logger)
    except Exception:
        logger.error('Scheduled replacement check failed', exc_info=True)
