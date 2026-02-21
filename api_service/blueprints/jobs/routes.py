"""
API routes for managing jobs (discover and recommendation).
Provides CRUD operations and job execution endpoints.
"""
import asyncio
import traceback
from flask import Blueprint, jsonify, request

from api_service.config.logger_manager import LoggerManager
from api_service.db.job_repository import JobRepository
from api_service.jobs.job_manager import JobManager
from api_service.jobs.discover_automation import execute_discover_job
from api_service.jobs.recommendation_automation import execute_recommendation_job

logger = LoggerManager.get_logger("JobsRoute")
jobs_bp = Blueprint('jobs', __name__)
jobs_bp.strict_slashes = False


def run_async(coro):
    """
    Run an async coroutine synchronously.
    Creates a new event loop if none exists.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running (e.g., in async context), create a new one
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


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
    return manager


@jobs_bp.route('', methods=['GET'])
def get_jobs():
    """
    Get all discover jobs.

    Returns:
        JSON list of all jobs.
    """
    try:
        repository = JobRepository()
        jobs = repository.get_all_jobs()

        # Add next run time from scheduler
        manager = get_job_manager()
        scheduled = {j['id']: j['next_run'] for j in manager.get_scheduled_jobs()}

        for job in jobs:
            scheduler_id = f"discover_job_{job['id']}"
            job['next_run'] = scheduled.get(scheduler_id)

        return jsonify({'status': 'success', 'jobs': jobs}), 200
    except Exception as e:
        logger.error(f"Error retrieving jobs: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@jobs_bp.route('/<int:job_id>', methods=['GET'])
def get_job(job_id: int):
    """
    Get a single discover job by ID.

    Args:
        job_id: ID of the job to retrieve.

    Returns:
        JSON job object or 404 if not found.
    """
    try:
        repository = JobRepository()
        job = repository.get_job(job_id)

        if not job:
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
        logger.error(f"Error retrieving job {job_id}: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@jobs_bp.route('', methods=['POST'])
def create_job():
    """
    Create a new job (discover or recommendation).

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
        if job_type not in ['discover', 'recommendation']:
            return jsonify({
                'status': 'error',
                'message': 'job_type must be "discover" or "recommendation"'
            }), 400
        data['job_type'] = job_type

        # Validate media_type
        valid_media_types = ['movie', 'tv'] if job_type == 'discover' else ['movie', 'tv', 'both']
        if data['media_type'] not in valid_media_types:
            return jsonify({
                'status': 'error',
                'message': f'media_type must be one of: {", ".join(valid_media_types)}'
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
        logger.error(f"Error creating job: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@jobs_bp.route('/<int:job_id>', methods=['PUT'])
def update_job(job_id: int):
    """
    Update an existing discover job.

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

        # Validate media_type if provided
        job_type = data.get('job_type', existing.get('job_type', 'discover'))
        valid_media_types = ['movie', 'tv'] if job_type == 'discover' else ['movie', 'tv', 'both']
        if 'media_type' in data and data['media_type'] not in valid_media_types:
            return jsonify({
                'status': 'error',
                'message': f'media_type must be one of: {", ".join(valid_media_types)}'
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
        logger.error(f"Error updating job {job_id}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@jobs_bp.route('/<int:job_id>', methods=['DELETE'])
def delete_job(job_id: int):
    """
    Delete a discover job.

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
        logger.error(f"Error deleting job {job_id}: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@jobs_bp.route('/<int:job_id>/toggle', methods=['POST'])
def toggle_job(job_id: int):
    """
    Toggle a discover job's enabled status.

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
        logger.error(f"Error toggling job {job_id}: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@jobs_bp.route('/<int:job_id>/run', methods=['POST'])
def run_job_now(job_id: int):
    """
    Execute a job immediately.

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

        job_type = job.get('job_type', 'discover')
        logger.info(f"Running {job_type} job {job_id} immediately")

        # Execute job based on type (async function called synchronously)
        if job_type == 'recommendation':
            result = run_async(execute_recommendation_job(job_id))
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
        error_msg = str(e) if str(e) else type(e).__name__
        logger.error(f"Error running job {job_id}: {error_msg}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': error_msg}), 500


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

        limit = request.args.get('limit', 50, type=int)
        history = repository.get_job_history(job_id, limit)

        return jsonify({
            'status': 'success',
            'job_name': job['name'],
            'history': history
        }), 200

    except Exception as e:
        logger.error(f"Error retrieving history for job {job_id}: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


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

        return jsonify({'status': 'success', 'history': history}), 200

    except Exception as e:
        logger.error(f"Error retrieving history: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


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
        tmdb = TMDbDiscover(env_vars['TMDB_API_KEY'])

        if media_type == 'both':
            # Combine movie and TV genres, removing duplicates
            movie_genres = run_async(tmdb.get_genres('movie'))
            tv_genres = run_async(tmdb.get_genres('tv'))
            # Merge by id, keeping unique genres
            genres_dict = {g['id']: g for g in movie_genres}
            for g in tv_genres:
                if g['id'] not in genres_dict:
                    genres_dict[g['id']] = g
            genres = sorted(genres_dict.values(), key=lambda x: x['name'])
        else:
            genres = run_async(tmdb.get_genres(media_type))

        return jsonify({'status': 'success', 'genres': genres}), 200

    except Exception as e:
        logger.error(f"Error retrieving genres: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


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
        tmdb = TMDbDiscover(env_vars['TMDB_API_KEY'])
        languages = run_async(tmdb.get_languages())

        return jsonify({'status': 'success', 'languages': languages}), 200

    except Exception as e:
        logger.error(f"Error retrieving languages: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


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
        return jsonify({'status': 'success', 'configured': client is not None}), 200
    except Exception as e:
        logger.error(f"Error checking LLM status: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@jobs_bp.route('/import-config', methods=['POST'])
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
        logger.error(f"Error importing config: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
