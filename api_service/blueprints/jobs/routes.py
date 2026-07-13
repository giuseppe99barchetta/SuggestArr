""" API routes for managing jobs (discover and recommendation).
Provides CRUD operations and job execution endpoints.
"""
import threading
import traceback
from flask import Blueprint, jsonify, request, g

from api_service.auth.limiter import limiter
from api_service.auth.middleware import require_role
from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.db.job_repository import JobRepository
from api_service.jobs.job_manager import JobManager
from api_service.jobs.discover_automation import DiscoverAutomation, execute_discover_job
from api_service.jobs.recommendation_automation import RecommendationAutomation, execute_recommendation_job
from api_service.jobs.trakt_recommendations_automation import (
    TraktRecommendationsAutomation,
    execute_trakt_recommendations_job,
)
from api_service.utils.asyncio_loop import run_coroutine_sync
from api_service.services.config_service import ConfigService
from api_service.services.seer.seer_client import SeerClient

logger = LoggerManager.get_logger("JobsRoute")
jobs_bp = Blueprint('jobs', __name__)
jobs_bp.strict_slashes = False

_run_all_lock = threading.Lock()
_run_all_running = False


def run_async(coro):
    """
    Run an async coroutine synchronously.
    Drains pending cleanup tasks before closing the per-invocation event loop.
    """
    return run_coroutine_sync(coro, logger)


def _validate_request_profiles(value):
    if value is None:
        return {}
    if not isinstance(value, dict) or any(key not in ('movie', 'tv') for key in value):
        raise ValueError('request_profiles must contain only movie and tv')
    for profile in value.values():
        if not isinstance(profile, dict) or any(key not in ('serverId', 'profileId', 'rootFolder') for key in profile):
            raise ValueError('Invalid request profile')
        if profile.get('serverId') is not None and not isinstance(profile['serverId'], int):
            raise ValueError('serverId must be an integer')
        if profile.get('profileId') is not None and not isinstance(profile['profileId'], int):
            raise ValueError('profileId must be an integer')
        if profile.get('rootFolder') is not None and not isinstance(profile['rootFolder'], str):
            raise ValueError('rootFolder must be a string')
        present = [profile.get(key) is not None for key in ('serverId', 'profileId', 'rootFolder')]
        if any(present) and not all(present):
            raise ValueError('serverId, profileId and rootFolder must be selected together')
    return value


def _validate_request_profiles_with_seer(profiles):
    if not any(profiles.values()):
        return
    env = ConfigService.get_runtime_config()
    async def check():
        async with SeerClient(env.get('SEER_API_URL', ''), env.get('SEER_TOKEN', ''),
                              session_token=env.get('SEER_SESSION_TOKEN')) as seer:
            for media_type, profile in profiles.items():
                if not profile or profile.get('serverId') is None:
                    continue
                servers = await (seer.get_radarr_servers() if media_type == 'movie' else seer.get_sonarr_servers())
                server = next((item for item in servers or [] if item.get('id') == profile['serverId']), None)
                if not server:
                    raise ValueError(f"Unknown {media_type} server")
                if profile.get('profileId') not in {item.get('id') for item in server.get('profiles', [])}:
                    raise ValueError(f"Unknown {media_type} quality profile")
                if profile.get('rootFolder') not in {item.get('path') for item in server.get('rootFolders', [])}:
                    raise ValueError(f"Unknown {media_type} root folder")
    run_async(check())


def get_job_manager() -> JobManager:
    """
    Get the JobManager instance and ensure it's configured.

    Returns:
        Configured JobManager instance.
    """
    manager = JobManager.get_instance()
    # Ensure both executors are registered
    if 'discover' not in manager._job_executors:
        manager.set_job_executor(execute_discover_job, job_type='discover')
    if 'recommendation' not in manager._job_executors:
        manager.set_job_executor(execute_recommendation_job, job_type='recommendation')
    if 'trakt_recommendations' not in manager._job_executors:
        manager.set_job_executor(execute_trakt_recommendations_job, job_type='trakt_recommendations')
    return manager


@jobs_bp.route('', methods=['GET'])
def get_jobs():
    """
    Get all discover jobs.
    
    Admin users see all jobs.
    Normal users only see jobs they own (where owner_id matches their user ID).

    Returns:
        JSON list of all jobs.
    """
    try:
        repository = JobRepository()
        jobs = repository.get_all_jobs()
        
        # Apply RBAC: non-admin users only see their own jobs
        current_user = getattr(g, 'current_user', None)
        if current_user and current_user.get('role') != 'admin':
            user_id = int(current_user['id'])
            jobs = [job for job in jobs if job.get('owner_id') == user_id]

        # Add next run time from scheduler
        manager = get_job_manager()
        scheduled = {j['id']: j['next_run'] for j in manager.get_scheduled_jobs()}

        for job in jobs:
            scheduler_id = f"discover_job_{job['id']}"
            job['next_run'] = scheduled.get(scheduler_id)

        return jsonify({
            'status': 'success',
            'jobs': jobs,
            'request_approval_default': load_env_vars().get('REQUIRE_REQUEST_APPROVAL', False),
        }), 200
    except Exception as e:
        logger.error(f"Error retrieving jobs: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@jobs_bp.route('/suggestions', methods=['GET'])
def get_suggestions():
    user = g.current_user
    owner_id = None if user.get('role') == 'admin' else int(user['id'])
    status = request.args.get('status', 'awaiting_approval')
    if status not in ('awaiting_approval', 'queued', 'submitting', 'submitted', 'rejected', 'failed'):
        return jsonify({'status': 'error', 'message': 'Invalid status'}), 400
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 24))))
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid pagination'}), 400
    items, total = JobRepository().db.list_suggestions(
        owner_id, status, request.args.get('search', '').strip()[:100], page, per_page)
    return jsonify({'status': 'success', 'items': items, 'total': total,
                    'page': page, 'pages': max(1, (total + per_page - 1) // per_page)}), 200


@jobs_bp.route('/suggestions/approve', methods=['POST'])
@limiter.limit("20 per minute")
def approve_suggestions():
    return _decide_suggestions(True)


@jobs_bp.route('/suggestions/blacklist', methods=['POST'])
@limiter.limit("20 per minute")
def blacklist_suggestions():
    return _decide_suggestions(False, blacklist=True)


@jobs_bp.route('/suggestions/reject', methods=['POST'])
@limiter.limit("20 per minute")
def reject_suggestions():
    return _decide_suggestions(False)


@jobs_bp.route('/suggestions/retry', methods=['POST'])
@limiter.limit("20 per minute")
def retry_suggestions():
    data = request.get_json(silent=True) or {}
    ids = data.get('ids')
    if not isinstance(ids, list) or not ids or len(ids) > 100 or any(not isinstance(item, int) for item in ids):
        return jsonify({'status': 'error', 'message': 'ids must contain 1 to 100 integers'}), 400
    user = g.current_user
    owner_id = None if user.get('role') == 'admin' else int(user['id'])
    changed = JobRepository().db.retry_suggestions(ids, owner_id)
    return jsonify({'status': 'success', 'updated': changed}), 200


@jobs_bp.route('/suggestions/blacklist', methods=['GET'])
@require_role('admin')
def get_suggestion_blacklist():
    return jsonify({'status': 'success', 'items': JobRepository().db.list_blacklist()}), 200


@jobs_bp.route('/suggestions/blacklist/<media_type>/<tmdb_id>', methods=['DELETE'])
@require_role('admin')
def restore_blacklisted_suggestion(media_type, tmdb_id):
    if media_type not in ('movie', 'tv'):
        return jsonify({'status': 'error', 'message': 'Invalid media type'}), 400
    removed = JobRepository().db.remove_blacklist(tmdb_id, media_type)
    return jsonify({'status': 'success', 'removed': removed}), 200


def _decide_suggestions(approve, blacklist=False):
    data = request.get_json(silent=True) or {}
    ids = data.get('ids')
    if not isinstance(ids, list) or not ids or len(ids) > 100 or any(not isinstance(item, int) for item in ids):
        return jsonify({'status': 'error', 'message': 'ids must contain 1 to 100 integers'}), 400
    user = g.current_user
    owner_id = None if user.get('role') == 'admin' else int(user['id'])
    changed = JobRepository().db.decide_suggestions(ids, owner_id, int(user['id']), approve, blacklist)
    return jsonify({'status': 'success', 'updated': changed}), 200


@jobs_bp.route('/<int:job_id>', methods=['GET'])
def get_job(job_id: int):
    """
    Get a single discover job by ID.
    
    Admin users can view any job.
    Normal users can only view jobs they own.

    Args:
        job_id: ID of the job to retrieve.

    Returns:
        JSON job object or 404 if not found (or not owned by current user).
    """
    try:
        repository = JobRepository()
        job = repository.get_job(job_id)

        if not job:
            return jsonify({'status': 'error', 'message': 'Job not found'}), 404
        
        # Apply RBAC: non-admin users can only see their own jobs
        current_user = getattr(g, 'current_user', None)
        if current_user and current_user.get('role') != 'admin':
            user_id = int(current_user['id'])
            if job.get('owner_id') != user_id:
                # Return 404 to avoid leaking existence of jobs
                return jsonify({'status': 'error', 'message': 'Job not found'}), 404

        # Add next run time from scheduler
        manager = get_job_manager()
        scheduled = manager.get_scheduled_jobs()
        scheduler_id = f"discover_job_{job_id}"

        for s in scheduled:
            if s['id'] == scheduler_id:
                job['next_run'] = s['next_run']
                break

        return jsonify({'status': 'success', 'job': job}), 200
    except Exception as e:
        logger.error(f"Error retrieving job {job_id}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@jobs_bp.route('', methods=['POST'])
def create_job():
    """
    Create a new job (discover or recommendation) for the authenticated user.

    Ownership model:
        - owner_id is always set from g.current_user['id'].
        - Clients cannot choose or override owner_id.
        - Admin users can still manage any job after creation.

    Request body:
        - name: Job name (required)
        - job_type: 'discover' or 'recommendation' (optional, default 'discover')
        - media_type: 'movie', 'tv', or 'both' (required)
        - filters: Dictionary of filters (required)
        - schedule_type: 'preset' or 'cron' (required)
        - schedule_value: Schedule value (required)
        - max_results: Maximum results (optional, default 20)
        - user_ids: List of user IDs for recommendation jobs (optional)
        - enabled: Whether job is enabled (optional, default true)

    Returns:
        JSON with created job ID.
    """
    try:
        data = request.get_json()

        # Validate required fields
        required = ['name', 'media_type', 'filters', 'schedule_type', 'schedule_value']
        missing = [f for f in required if f not in data]
        if missing:
            return jsonify({
                'status': 'error',
                'message': f'Missing required fields: {", ".join(missing)}'
            }), 400

        # Set default job_type
        job_type = data.get('job_type', 'discover')
        if job_type not in ['discover', 'recommendation', 'trakt_recommendations']:
            return jsonify({
                'status': 'error',
                'message': 'job_type must be one of: discover, recommendation, trakt_recommendations'
            }), 400
        data['job_type'] = job_type
        delivery_mode = data.get('delivery_mode', 'inherit')
        if delivery_mode not in ('inherit', 'automatic', 'manual'):
            return jsonify({'status': 'error', 'message': 'delivery_mode must be inherit, automatic or manual'}), 400
        data['delivery_mode'] = delivery_mode
        approval_pause_mode = data.get('approval_pause_mode', 'inherit')
        if approval_pause_mode not in ('inherit', 'always', 'never'):
            return jsonify({'status': 'error', 'message': 'approval_pause_mode must be inherit, always or never'}), 400
        data['approval_pause_mode'] = approval_pause_mode
        try:
            data['request_profiles'] = _validate_request_profiles(data.get('request_profiles'))
            _validate_request_profiles_with_seer(data['request_profiles'])
        except ValueError as exc:
            return jsonify({'status': 'error', 'message': str(exc)}), 400
        identity_mode = data.get('seer_identity_mode', 'technical_user')
        if identity_mode not in ('matching_user', 'technical_user', 'admin_user'):
            return jsonify({'status': 'error', 'message': 'Invalid seer_identity_mode'}), 400
        if identity_mode == 'admin_user' and getattr(g, 'current_user', {}).get('role') != 'admin':
            return jsonify({'status': 'error', 'message': 'admin_user identity requires an admin job owner'}), 403
        try:
            data['unwatched_suggestion_days'] = int(data.get('unwatched_suggestion_days', 7))
            if data['unwatched_suggestion_days'] < 1:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({'status': 'error', 'message': 'unwatched_suggestion_days must be a positive integer'}), 400
        
        # Set owner_id from current user - never allow client to override
        current_user = getattr(g, 'current_user', None)
        if current_user:
            data['owner_id'] = int(current_user['id'])
        else:
            # Fallback: should not happen on protected routes
            data['owner_id'] = None

        # Validate media_type
        valid_media_types = ['movie', 'tv'] if job_type == 'discover' else ['movie', 'tv', 'both']
        if data['media_type'] not in valid_media_types:
            return jsonify({
                'status': 'error',
                'message': f'media_type must be one of: {", ".join(valid_media_types)}'
            }), 400

        if job_type == 'trakt_recommendations' and len(data.get('user_ids') or []) != 1:
            return jsonify({
                'status': 'error',
                'message': 'Trakt recommendations jobs require exactly one linked media user'
            }), 400

        # Validate schedule_type
        if data['schedule_type'] not in ['preset', 'cron']:
            return jsonify({
                'status': 'error',
                'message': 'schedule_type must be "preset" or "cron"'
            }), 400

        # Create job
        repository = JobRepository()
        job_id = repository.create_job(data)

        # Schedule job if enabled
        if data.get('enabled', True):
            job = repository.get_job(job_id)
            manager = get_job_manager()
            manager.start()
            manager.schedule_job(job)

        logger.info(f"Created {job_type} job: {data['name']} (ID: {job_id})")
        return jsonify({'status': 'success', 'job_id': job_id}), 201

    except Exception as e:
        logger.error(f"Error creating job: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@jobs_bp.route('/<int:job_id>', methods=['PUT'])
def update_job(job_id: int):
    """
    Update an existing discover job.
    
    Admin users can update any job.
    Normal users can only update jobs they own.

    Args:
        job_id: ID of the job to update.

    Request body:
        Any job fields to update.

    Returns:
        JSON success status.
    """
    try:
        data = request.get_json()
        repository = JobRepository()

        # Check job exists
        existing = repository.get_job(job_id)
        if not existing:
            return jsonify({'status': 'error', 'message': 'Job not found'}), 404
        
        # Apply RBAC: non-admin users can only update their own jobs
        current_user = getattr(g, 'current_user', None)
        if current_user and current_user.get('role') != 'admin':
            user_id = int(current_user['id'])
            if existing.get('owner_id') != user_id:
                return jsonify({'status': 'error', 'message': 'Insufficient permissions'}), 403

        # Validate job_type if provided
        job_type = data.get('job_type', existing.get('job_type', 'discover'))
        if 'request_profiles' in data:
            try:
                data['request_profiles'] = _validate_request_profiles(data['request_profiles'])
                _validate_request_profiles_with_seer(data['request_profiles'])
            except ValueError as exc:
                return jsonify({'status': 'error', 'message': str(exc)}), 400
        if 'delivery_mode' in data and data['delivery_mode'] not in ('inherit', 'automatic', 'manual'):
            return jsonify({'status': 'error', 'message': 'delivery_mode must be inherit, automatic or manual'}), 400
        if 'approval_pause_mode' in data and data['approval_pause_mode'] not in ('inherit', 'always', 'never'):
            return jsonify({'status': 'error', 'message': 'approval_pause_mode must be inherit, always or never'}), 400
        if 'seer_identity_mode' in data:
            if data['seer_identity_mode'] not in ('matching_user', 'technical_user', 'admin_user'):
                return jsonify({'status': 'error', 'message': 'Invalid seer_identity_mode'}), 400
            if data['seer_identity_mode'] == 'admin_user' and current_user.get('role') != 'admin':
                return jsonify({'status': 'error', 'message': 'admin_user identity requires an admin job owner'}), 403
        if 'unwatched_suggestion_days' in data:
            try:
                data['unwatched_suggestion_days'] = int(data['unwatched_suggestion_days'])
                if data['unwatched_suggestion_days'] < 1:
                    raise ValueError
            except (TypeError, ValueError):
                return jsonify({'status': 'error', 'message': 'unwatched_suggestion_days must be a positive integer'}), 400
        if 'job_type' in data and job_type not in ['discover', 'recommendation', 'trakt_recommendations']:
            return jsonify({
                'status': 'error',
                'message': 'job_type must be one of: discover, recommendation, trakt_recommendations'
            }), 400

        # Validate media_type if provided
        valid_media_types = ['movie', 'tv'] if job_type == 'discover' else ['movie', 'tv', 'both']
        if 'media_type' in data and data['media_type'] not in valid_media_types:
            return jsonify({
                'status': 'error',
                'message': f'media_type must be one of: {", ".join(valid_media_types)}'
            }), 400

        if job_type == 'trakt_recommendations':
            user_ids = data.get('user_ids', existing.get('user_ids') or [])
            if len(user_ids) != 1:
                return jsonify({
                    'status': 'error',
                    'message': 'Trakt recommendations jobs require exactly one linked media user'
                }), 400

        # Validate schedule_type if provided
        if 'schedule_type' in data and data['schedule_type'] not in ['preset', 'cron']:
            return jsonify({
                'status': 'error',
                'message': 'schedule_type must be "preset" or "cron"'
            }), 400

        # Update job
        updated = repository.update_job(job_id, data)

        if updated:
            # Reschedule job
            job = repository.get_job(job_id)
            manager = get_job_manager()
            manager.start()

            if job['enabled']:
                manager.schedule_job(job)
            else:
                manager.unschedule_job(job_id)

            logger.info(f"Updated job: {job_id}")
            return jsonify({'status': 'success', 'message': 'Job updated'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Update failed'}), 500

    except Exception as e:
        logger.error(f"Error updating job {job_id}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@jobs_bp.route('/<int:job_id>', methods=['DELETE'])
def delete_job(job_id: int):
    """
    Delete a discover job.
    
    Admin users can delete any job.
    Normal users can only delete jobs they own.

    Args:
        job_id: ID of the job to delete.

    Returns:
        JSON success status.
    """
    try:
        repository = JobRepository()

        # Check job exists
        existing = repository.get_job(job_id)
        if not existing:
            return jsonify({'status': 'error', 'message': 'Job not found'}), 404
        
        # Apply RBAC: non-admin users can only delete their own jobs
        current_user = getattr(g, 'current_user', None)
        if current_user and current_user.get('role') != 'admin':
            user_id = int(current_user['id'])
            if existing.get('owner_id') != user_id:
                return jsonify({'status': 'error', 'message': 'Insufficient permissions'}), 403

        # Unschedule first
        manager = get_job_manager()
        manager.unschedule_job(job_id)

        # Delete job (history is deleted via CASCADE)
        deleted = repository.delete_job(job_id)

        if deleted:
            logger.info(f"Deleted discover job: {job_id}")
            return jsonify({'status': 'success', 'message': 'Job deleted'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Delete failed'}), 500

    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@jobs_bp.route('/<int:job_id>/toggle', methods=['POST'])
def toggle_job(job_id: int):
    """
    Toggle a discover job's enabled status.
    
    Admin users can toggle any job.
    Normal users can only toggle jobs they own.

    Args:
        job_id: ID of the job to toggle.

    Returns:
        JSON with new enabled status.
    """
    try:
        repository = JobRepository()

        # Check job exists
        job = repository.get_job(job_id)
        if not job:
            return jsonify({'status': 'error', 'message': 'Job not found'}), 404
        
        # Apply RBAC: non-admin users can only toggle their own jobs
        current_user = getattr(g, 'current_user', None)
        if current_user and current_user.get('role') != 'admin':
            user_id = int(current_user['id'])
            if job.get('owner_id') != user_id:
                return jsonify({'status': 'error', 'message': 'Insufficient permissions'}), 403

        # Toggle enabled status
        new_enabled = not job['enabled']
        repository.toggle_job(job_id, new_enabled)

        # Update scheduler
        manager = get_job_manager()
        manager.start()

        if new_enabled:
            job['enabled'] = True
            manager.schedule_job(job)
        else:
            manager.unschedule_job(job_id)

        logger.info(f"Toggled job {job_id} to enabled={new_enabled}")
        return jsonify({
            'status': 'success',
            'enabled': new_enabled,
            'message': f'Job {"enabled" if new_enabled else "disabled"}'
        }), 200

    except Exception as e:
        logger.error(f"Error toggling job {job_id}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@jobs_bp.route('/<int:job_id>/run', methods=['POST'])
@limiter.limit("5 per minute")
def run_job_now(job_id: int):
    """
    Execute a job immediately.
    
    Admin users can run any job.
    Normal users can only run jobs they own.

    Args:
        job_id: ID of the job to run.

    Returns:
        JSON with execution result.
    """
    try:
        repository = JobRepository()

        # Check job exists
        job = repository.get_job(job_id)
        if not job:
            return jsonify({'status': 'error', 'message': 'Job not found'}), 404
        
        # Apply RBAC: non-admin users can only run their own jobs
        current_user = getattr(g, 'current_user', None)
        if current_user and current_user.get('role') != 'admin':
            user_id = int(current_user['id'])
            if job.get('owner_id') != user_id:
                return jsonify({'status': 'error', 'message': 'Insufficient permissions'}), 403

        job_type = job.get('job_type', 'discover')
        logger.info(f"Running {job_type} job {job_id} immediately")

        manager = get_job_manager()
        if run_async(manager._should_pause_for_pending_requests(job)):
            exec_id = repository.log_execution_start(job_id)
            repository.log_execution_end(
                exec_id=exec_id,
                status='skipped',
                results_count=0,
                requested_count=0,
                error_message='Paused: Seer has pending requests awaiting approval or denial.'
            )
            return jsonify({
                'status': 'paused',
                'message': 'Job paused because Seer has pending requests awaiting approval or denial.',
                'results_count': 0,
                'requested_count': 0
            }), 200

        # Execute job based on type (async function called synchronously)
        if job_type == 'recommendation':
            result = run_async(execute_recommendation_job(job_id))
        elif job_type == 'trakt_recommendations':
            result = run_async(execute_trakt_recommendations_job(job_id))
        else:
            result = run_async(execute_discover_job(job_id))

        if result.success:
            return jsonify({
                'status': 'success',
                'message': 'Job executed successfully',
                'results_count': result.results_count,
                'requested_count': result.requested_count
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result.error_message or 'Job execution failed'
            }), 500

    except Exception as e:
        logger.error(f"Error running job {job_id}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@jobs_bp.route('/<int:job_id>/dry-run', methods=['POST'])
@limiter.limit("10 per minute")
def dry_run_job(job_id: int):
    """
    Simulate job execution without making actual requests to download clients.

    Runs the full pipeline — provider checks, TMDb discovery/recommendations,
    all configured filters — but skips enqueueing to Seer. No history entry
    is written.
    
    Admin users can dry-run any job.
    Normal users can only dry-run jobs they own.

    Args:
        job_id: ID of the job to preview.

    Returns:
        JSON with the list of media items that would have been requested.
    """
    try:
        repository = JobRepository()

        job = repository.get_job(job_id)
        if not job:
            return jsonify({'status': 'error', 'message': 'Job not found'}), 404
        
        # Apply RBAC: non-admin users can only dry-run their own jobs
        current_user = getattr(g, 'current_user', None)
        if current_user and current_user.get('role') != 'admin':
            user_id = int(current_user['id'])
            if job.get('owner_id') != user_id:
                return jsonify({'status': 'error', 'message': 'Insufficient permissions'}), 403

        job_type = job.get('job_type', 'discover')
        logger.info(f"Dry-run for {job_type} job {job_id} ({job.get('name', '')})")

        async def _run():
            if job_type == 'recommendation':
                automation = await RecommendationAutomation.create(job_id, dry_run=True)
            elif job_type == 'trakt_recommendations':
                automation = await TraktRecommendationsAutomation.create(job_id, dry_run=True)
            else:
                automation = await DiscoverAutomation.create(job_id)
            return await automation.run(dry_run=True)

        result = run_async(_run())

        if result.success:
            return jsonify({
                'status': 'success',
                'dry_run': True,
                'items_count': result.results_count,
                'items': result.dry_run_items or [],
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result.error_message or 'Dry run failed',
            }), 500

    except Exception as e:
        logger.error(f"Error during dry-run for job {job_id}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


def _run_all_jobs_in_background():
    """
    Run all enabled jobs sequentially in a background thread.
    Each job is executed with its own event loop to avoid conflicts.
    """
    global _run_all_running
    try:
        repository = JobRepository()
        jobs = [j for j in repository.get_all_jobs() if j.get('enabled', True)]
        logger.info(f"Force run all: executing {len(jobs)} job(s)")

        for job in jobs:
            job_id = job['id']
            job_type = job.get('job_type', 'discover')
            try:
                logger.info(f"Force run all: starting {job_type} job {job_id} ({job.get('name', '')})")
                manager = get_job_manager()
                if run_async(manager._should_pause_for_pending_requests(job)):
                    exec_id = repository.log_execution_start(job_id)
                    repository.log_execution_end(
                        exec_id=exec_id,
                        status='skipped',
                        results_count=0,
                        requested_count=0,
                        error_message='Paused: Seer has pending requests awaiting approval or denial.'
                    )
                    logger.info(
                        "Force run all: paused job %s because Seer has pending requests.",
                        job_id,
                    )
                    continue
                if job_type == 'recommendation':
                    run_async(execute_recommendation_job(job_id))
                elif job_type == 'trakt_recommendations':
                    run_async(execute_trakt_recommendations_job(job_id))
                else:
                    run_async(execute_discover_job(job_id))
                logger.info(f"Force run all: job {job_id} completed")
            except Exception as e:
                logger.error(f"Force run all: error in job {job_id}: {e}", exc_info=True)

        logger.info("Force run all: finished")
    finally:
        with _run_all_lock:
            _run_all_running = False


@jobs_bp.route('/run-all', methods=['POST'])
@require_role('admin')
@limiter.limit("5 per minute")
def run_all_jobs():
    """
    Execute all enabled jobs immediately in a background thread.
    Returns immediately (202) while jobs run asynchronously.

    Returns:
        JSON with status and number of jobs started, or 409 if already running,
        or 404 if no enabled jobs exist.
    """
    global _run_all_running
    with _run_all_lock:
        if _run_all_running:
            return jsonify({'status': 'busy', 'message': 'A force run is already in progress.'}), 409
        _run_all_running = True

    repository = JobRepository()
    jobs = [j for j in repository.get_all_jobs() if j.get('enabled', True)]

    if not jobs:
        with _run_all_lock:
            _run_all_running = False
        return jsonify({'status': 'error', 'message': 'No enabled jobs found.'}), 404

    thread = threading.Thread(target=_run_all_jobs_in_background, daemon=True)
    thread.start()

    return jsonify({
        'status': 'success',
        'message': f'Running {len(jobs)} job(s) in the background.',
        'jobs_count': len(jobs)
    }), 202


@jobs_bp.route('/<int:job_id>/history', methods=['GET'])
def get_job_history(job_id: int):
    """
    Get execution history for a specific job.

    Args:
        job_id: ID of the job.

    Query params:
        - limit: Maximum records to return (default 50).

    Returns:
        JSON list of execution history records.
    """
    try:
        repository = JobRepository()

        # Check job exists
        job = repository.get_job(job_id)
        if not job:
            return jsonify({'status': 'error', 'message': 'Job not found'}), 404

        current_user = getattr(g, 'current_user', None)
        if current_user and current_user.get('role') != 'admin':
            user_id = int(current_user['id'])
            if job.get('owner_id') != user_id:
                return jsonify({'status': 'error', 'message': 'Job not found'}), 404

        limit = request.args.get('limit', 50, type=int)
        history = repository.get_job_history(job_id, limit)

        return jsonify({
            'status': 'success',
            'job_name': job['name'],
            'history': history
        }), 200

    except Exception as e:
        logger.error(f"Error retrieving history for job {job_id}: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@jobs_bp.route('/history', methods=['GET'])
def get_all_history():
    """
    Get recent execution history across all jobs.

    Query params:
        - limit: Maximum records to return (default 100).

    Returns:
        JSON list of execution history records.
    """
    try:
        repository = JobRepository()
        limit = request.args.get('limit', 100, type=int)
        history = repository.get_recent_history(limit)

        current_user = getattr(g, 'current_user', None)
        if current_user and current_user.get('role') != 'admin':
            user_id = int(current_user['id'])
            owned_job_ids = {
                job['id']
                for job in repository.get_all_jobs()
                if job.get('owner_id') == user_id
            }
            history = [
                item for item in history
                if item.get('job_id') in owned_job_ids
            ]

        return jsonify({'status': 'success', 'history': history}), 200

    except Exception as e:
        logger.error(f"Error retrieving history: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@jobs_bp.route('/genres/<media_type>', methods=['GET'])
def get_genres(media_type: str):
    """
    Get available genres for a media type.

    Args:
        media_type: 'movie', 'tv', or 'both'.

    Returns:
        JSON list of genres.
    """
    try:
        if media_type not in ['movie', 'tv', 'both']:
            return jsonify({
                'status': 'error',
                'message': 'media_type must be "movie", "tv", or "both"'
            }), 400

        from api_service.config.config import load_env_vars
        from api_service.services.tmdb.tmdb_discover import TMDbDiscover

        env_vars = load_env_vars()

        async def fetch_genres():
            async with TMDbDiscover(env_vars['TMDB_API_KEY']) as tmdb:
                if media_type == 'both':
                    # Combine movie and TV genres, removing duplicates
                    movie_genres = await tmdb.get_genres('movie')
                    tv_genres = await tmdb.get_genres('tv')
                    # Merge by id, keeping unique genres
                    genres_dict = {g['id']: g for g in movie_genres}
                    for g in tv_genres:
                        if g['id'] not in genres_dict:
                            genres_dict[g['id']] = g
                    return sorted(genres_dict.values(), key=lambda x: x['name'])
                else:
                    return await tmdb.get_genres(media_type)

        genres = run_async(fetch_genres())

        return jsonify({'status': 'success', 'genres': genres}), 200

    except Exception as e:
        logger.error(f"Error retrieving genres: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@jobs_bp.route('/languages', methods=['GET'])
def get_languages():
    """
    Get available languages from TMDb.

    Returns:
        JSON list of languages.
    """
    try:
        from api_service.config.config import load_env_vars
        from api_service.services.tmdb.tmdb_discover import TMDbDiscover

        env_vars = load_env_vars()

        async def fetch_languages():
            async with TMDbDiscover(env_vars['TMDB_API_KEY']) as tmdb:
                return await tmdb.get_languages()

        languages = run_async(fetch_languages())

        return jsonify({'status': 'success', 'languages': languages}), 200

    except Exception as e:
        logger.error(f"Error retrieving languages: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@jobs_bp.route('/watch-regions', methods=['GET'])
def get_watch_regions():
    """
    Get available watch provider regions from TMDb.

    Returns:
        JSON list of regions with iso_3166_1 and english_name.
    """
    try:
        from api_service.config.config import load_env_vars
        from api_service.services.tmdb.tmdb_discover import TMDbDiscover

        env_vars = load_env_vars()

        async def fetch_regions():
            async with TMDbDiscover(env_vars['TMDB_API_KEY']) as tmdb:
                return await tmdb.get_watch_regions()

        regions = run_async(fetch_regions())

        return jsonify({'status': 'success', 'regions': regions}), 200

    except Exception as e:
        logger.error(f"Error retrieving watch regions: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@jobs_bp.route('/watch-providers', methods=['GET'])
def get_watch_providers():
    """
    Get available streaming providers for a region from TMDb.

    Query params:
        region: ISO 3166-1 region code (e.g. 'IT').

    Returns:
        JSON list of providers with provider_id and provider_name.
    """
    try:
        region = request.args.get('region', '').upper()
        if not region:
            return jsonify({'status': 'error', 'message': 'region query parameter is required'}), 400

        from api_service.config.config import load_env_vars
        from api_service.services.tmdb.tmdb_discover import TMDbDiscover

        env_vars = load_env_vars()

        async def fetch_providers():
            async with TMDbDiscover(env_vars['TMDB_API_KEY']) as tmdb:
                return await tmdb.get_streaming_providers(region)

        providers = run_async(fetch_providers())

        return jsonify({'status': 'success', 'providers': providers}), 200

    except Exception as e:
        logger.error(f"Error retrieving watch providers: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@jobs_bp.route('/defaults', methods=['GET'])
def get_job_defaults():
    """
    Return default filter values for new jobs, derived from the global content-filter config.

    The frontend uses these to pre-populate new job forms so that they match
    the thresholds configured in the wizard instead of starting from zero.

    Returns:
        JSON with default filter values:
            - vote_average_gte: global FILTER_TMDB_THRESHOLD / 10, or 6.0 if not set
            - vote_count_gte: global FILTER_TMDB_MIN_VOTES, or None
    """
    try:
        config = load_env_vars()

        tmdb_threshold = config.get('FILTER_TMDB_THRESHOLD')
        if tmdb_threshold is not None:
            try:
                vote_average_gte = float(tmdb_threshold) / 10
            except (ValueError, TypeError):
                vote_average_gte = 6.0
        else:
            vote_average_gte = 6.0

        tmdb_min_votes = config.get('FILTER_TMDB_MIN_VOTES')
        vote_count_gte = int(tmdb_min_votes) if tmdb_min_votes is not None else None
        request_first_season_only = config.get('REQUEST_FIRST_SEASON_ONLY', False)
        if not isinstance(request_first_season_only, bool):
            request_first_season_only = (
                str(request_first_season_only).strip().lower() in {'1', 'true', 'yes', 'on'}
            )

        return jsonify({
            'status': 'success',
            'defaults': {
                'vote_average_gte': vote_average_gte,
                'vote_count_gte': vote_count_gte,
                'request_first_season_only': request_first_season_only,
            }
        }), 200
    except Exception as e:
        logger.error(f"Error fetching job defaults: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@jobs_bp.route('/queue-status', methods=['GET'])
def get_queue_status():
    """
    Return the current Seer delivery queue status.

    Counts rows in pending_requests by status so the frontend can show a
    persistent banner while items are waiting to be sent to Seer.

    Returns:
        JSON with:
          - queued:     items waiting to be picked up by the worker
          - submitting: items currently being submitted
          - submitted:  items successfully delivered this session
          - failed:     items that exhausted retries
          - total_pending: queued + submitting (items not yet delivered)
    """
    try:
        from api_service.db.database_manager import DatabaseManager
        db = DatabaseManager()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status, COUNT(*) FROM pending_requests GROUP BY status"
            )
            rows = cursor.fetchall()

        counts = {row[0]: row[1] for row in rows}
        queued = counts.get('queued', 0)
        submitting = counts.get('submitting', 0)
        submitted = counts.get('submitted', 0)
        failed = counts.get('failed', 0)

        return jsonify({
            'status': 'success',
            'queued': queued,
            'submitting': submitting,
            'submitted': submitted,
            'failed': failed,
            'total_pending': queued + submitting,
        }), 200
    except Exception as e:
        logger.error(f"Error retrieving queue status: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@jobs_bp.route('/llm-status', methods=['GET'])
def get_llm_status():
    """
    Check if LLM is configured and available for AI-enhanced recommendations.

    Returns:
        JSON with configured status boolean.
    """
    try:
        from api_service.services.llm.llm_service import get_llm_client
        client = get_llm_client()
        config = load_env_vars()
        advanced_enabled = config.get('ENABLE_ADVANCED_ALGORITHM', False) is True
        return jsonify({
            'status': 'success',
            'configured': client is not None,
            'advanced_algorithm_enabled': advanced_enabled
        }), 200
    except Exception as e:
        logger.error(f"Error checking LLM status: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@jobs_bp.route('/sync-ai-setting', methods=['POST'])
@require_role('admin')
def sync_ai_setting():
    """
    Sync the use_llm flag across all recommendation jobs based on ENABLE_ADVANCED_ALGORITHM config.

    When ENABLE_ADVANCED_ALGORITHM is True and LLM is configured, sets use_llm=True on all
    recommendation jobs. Otherwise sets use_llm=False.

    Returns:
        JSON with sync result and number of updated jobs.
    """
    try:
        from api_service.services.llm.llm_service import get_llm_client

        config = load_env_vars()
        advanced_enabled = config.get('ENABLE_ADVANCED_ALGORITHM', False) is True
        llm_configured = advanced_enabled and get_llm_client() is not None
        new_use_llm = advanced_enabled and llm_configured

        repository = JobRepository()
        jobs = repository.get_all_jobs()
        updated = 0

        for job in jobs:
            if job.get('job_type') == 'recommendation':
                filters = job.get('filters') or {}
                if filters.get('use_llm') != new_use_llm:
                    filters['use_llm'] = new_use_llm
                    repository.update_job(job['id'], {'filters': filters})
                    updated += 1

        logger.info(
            "Synced AI setting to recommendation jobs: use_llm=%s, updated=%d", new_use_llm, updated
        )
        return jsonify({
            'status': 'success',
            'use_llm': new_use_llm,
            'updated_jobs': updated
        }), 200
    except Exception as e:
        logger.error(f"Error syncing AI setting: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500


@jobs_bp.route('/llm-test', methods=['POST'])
@require_role('admin')
@limiter.limit("5 per minute")
def test_llm_connection():
    """
    Test the LLM connection by making a real API call with the provided configuration.

    Accepts OPENAI_API_KEY, OPENAI_BASE_URL, and LLM_MODEL in the request body.
    Returns success or a descriptive error message.
    """
    try:
        from openai import OpenAI

        data = request.get_json() or {}
        api_key = (data.get('OPENAI_API_KEY') or '').strip()
        base_url = (data.get('OPENAI_BASE_URL') or '').strip() or None
        model = (data.get('LLM_MODEL') or 'gpt-4o-mini').strip()

        if not api_key:
            if base_url:
                # Local providers like Ollama don't need a real key
                api_key = 'ollama'
            else:
                return jsonify({'status': 'error', 'message': 'API Key is required for cloud providers.'}), 400

        client_kwargs = {'api_key': api_key}
        if base_url:
            client_kwargs['base_url'] = base_url

        client = OpenAI(**client_kwargs)

        # Make a minimal completion to verify the connection and credentials.
        # max_completion_tokens is used instead of the deprecated max_tokens to
        # support current OpenAI models (o-series, gpt-4.1-*, gpt-5.x) which
        # reject max_tokens with a 400 error. Some OpenAI-compatible gateways
        # reject values below 16, so we keep a safe minimum of 16.
        client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': 'Hi'}],
            max_completion_tokens=16,
        )

        return jsonify({'status': 'success', 'message': 'Connection successful!'}), 200

    except Exception as e:
        logger.error(f"LLM connection test failed: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'LLM connection test failed. Check logs for details.'}), 400


@jobs_bp.route('/import-config', methods=['POST'])
@require_role('admin')
def import_config():
    """
    One-time import of YAML config settings into the database.
    Only imports if no jobs exist yet and CRON_TIMES is configured.

    Returns:
        JSON with import result.
    """
    try:
        from api_service.jobs.system_job_sync import import_config_to_db

        result = import_config_to_db()

        if result['status'] == 'success':
            # Schedule the newly created job
            repository = JobRepository()
            job = repository.get_job(result['job_id'])
            if job and job['enabled']:
                manager = get_job_manager()
                manager.start()
                manager.schedule_job(job)

            return jsonify({
                'status': 'success',
                'job_id': result.get('job_id'),
                'message': 'Config imported to database'
            }), 200
        elif result['status'] == 'skipped':
            return jsonify({
                'status': 'success',
                'message': result.get('message', 'Import skipped')
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': result.get('message', 'Import failed')
            }), 500

    except Exception as e:
        logger.error(f"Error importing config: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'An internal error occurred'}), 500
