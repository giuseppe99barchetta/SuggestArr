"""
Config Import - One-time import of YAML config settings into the database.
This provides backwards compatibility for users upgrading from older versions.
After import, all job management is done through the UI/database only.
"""
from typing import Any, Dict

from api_service.config.config import load_env_vars
from api_service.config.logger_manager import LoggerManager
from api_service.db.job_repository import JobRepository


def import_config_to_db() -> Dict[str, Any]:
    """
    One-time import of YAML config settings into the database.

    Only runs if:
    - No jobs exist in the database yet
    - CRON_TIMES is configured in the YAML

    After this import, the YAML is no longer synced - all job management
    happens through the UI/database.

    Returns:
        Dictionary with import result.
    """
    logger = LoggerManager.get_logger("ConfigImport")

    try:
        repository = JobRepository()

        # Check if any jobs already exist - if so, skip import
        existing_jobs = repository.get_all_jobs()
        if existing_jobs and len(existing_jobs) > 0:
            logger.debug("Jobs already exist in database, skipping config import")
            return {'status': 'skipped', 'message': 'Jobs already exist in database'}

        # Load config
        env_vars = load_env_vars()

        # Check if CRON_TIMES is configured
        cron_times = env_vars.get('CRON_TIMES')
        if not cron_times:
            logger.info("No CRON_TIMES in config, skipping import")
            return {'status': 'skipped', 'message': 'No CRON_TIMES configured'}

        logger.info("Importing YAML config settings to database (one-time migration)")

        # Determine schedule type and value
        schedule_type, schedule_value = _parse_cron_config(cron_times)

        # Build filters from config
        filters = _build_filters_from_config(env_vars)

        # Get user IDs from config
        user_ids = _get_user_ids_from_config(env_vars)

        # Build job data - this is a regular job, not a "system" job
        job_data = {
            'name': 'Default Automation',
            'job_type': 'recommendation',
            'enabled': True,
            'media_type': 'both',
            'filters': filters,
            'schedule_type': schedule_type,
            'schedule_value': schedule_value,
            'max_results': 20,
            'user_ids': user_ids
        }

        # Create the job
        job_id = repository.create_job(job_data)

        logger.info(f"Config imported successfully as job ID: {job_id}")
        logger.info("YAML config will no longer be synced. Manage jobs through the UI.")

        return {
            'status': 'success',
            'job_id': job_id,
            'message': 'Config imported to database'
        }

    except Exception as e:
        logger.error(f"Failed to import config: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }


def _parse_cron_config(cron_times: str) -> tuple:
    """
    Parse CRON_TIMES config value to schedule type and value.

    Args:
        cron_times: Cron expression or preset name.

    Returns:
        Tuple of (schedule_type, schedule_value).
    """
    # Check if it's a preset
    presets = ['daily', 'weekly', 'every_12h', 'every_6h', 'every_hour']
    if cron_times.lower() in presets:
        return ('preset', cron_times.lower())

    # Otherwise, treat as cron expression
    return ('cron', cron_times)


def _build_filters_from_config(env_vars: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build job filters from environment config.

    Args:
        env_vars: Environment variables dictionary.

    Returns:
        Filters dictionary.
    """
    filters = {}

    # Similar content settings
    max_similar_movie = env_vars.get('MAX_SIMILAR_MOVIE')
    if max_similar_movie:
        filters['max_similar_movie'] = int(max_similar_movie)

    max_similar_tv = env_vars.get('MAX_SIMILAR_TV')
    if max_similar_tv:
        filters['max_similar_tv'] = int(max_similar_tv)

    max_content = env_vars.get('MAX_CONTENT_CHECKS')
    if max_content:
        filters['max_content'] = int(max_content)

    search_size = env_vars.get('SEARCH_SIZE')
    if search_size:
        filters['search_size'] = int(search_size)

    # TMDb filter settings
    tmdb_threshold = env_vars.get('FILTER_TMDB_THRESHOLD')
    if tmdb_threshold:
        filters['vote_average_gte'] = int(tmdb_threshold) / 10  # Convert 0-100 to 0-10

    tmdb_min_votes = env_vars.get('FILTER_TMDB_MIN_VOTES')
    if tmdb_min_votes:
        filters['vote_count_gte'] = int(tmdb_min_votes)

    filter_release_year = env_vars.get('FILTER_RELEASE_YEAR')
    if filter_release_year:
        filters['release_year_gte'] = int(filter_release_year)

    # Language filter
    filter_language = env_vars.get('FILTER_LANGUAGE')
    if filter_language:
        if isinstance(filter_language, list) and len(filter_language) > 0:
            filters['with_original_language'] = filter_language[0]
        elif isinstance(filter_language, str):
            filters['with_original_language'] = filter_language

    # Genre exclude filter
    filter_genres_exclude = env_vars.get('FILTER_GENRES_EXCLUDE')
    if filter_genres_exclude and isinstance(filter_genres_exclude, list):
        filters['without_genres'] = filter_genres_exclude

    # Include content without rating
    filter_include_no_rating = env_vars.get('FILTER_INCLUDE_NO_RATING')
    if filter_include_no_rating is not None:
        filters['include_no_rating'] = bool(filter_include_no_rating)

    # Number of seasons filter (TV only)
    filter_num_seasons = env_vars.get('FILTER_NUM_SEASONS')
    if filter_num_seasons:
        filters['min_seasons'] = int(filter_num_seasons)

    # Streaming services filter
    filter_streaming = env_vars.get('FILTER_STREAMING_SERVICES')
    if filter_streaming and isinstance(filter_streaming, list):
        filters['with_watch_providers'] = filter_streaming

    # Region for streaming providers
    filter_region = env_vars.get('FILTER_REGION_PROVIDER')
    if filter_region:
        filters['watch_region'] = filter_region

    # Honor Jellyseer discovery settings
    honor_discovery = env_vars.get('HONOR_JELLYSEER_DISCOVERY')
    if honor_discovery is not None:
        filters['honor_jellyseer_discovery'] = bool(honor_discovery)

    # Exclude already downloaded content
    exclude_downloaded = env_vars.get('EXCLUDE_DOWNLOADED')
    if exclude_downloaded is not None:
        filters['exclude_downloaded'] = bool(exclude_downloaded)

    # Exclude already requested content
    exclude_requested = env_vars.get('EXCLUDE_REQUESTED')
    if exclude_requested is not None:
        filters['exclude_requested'] = bool(exclude_requested)

    return filters


def _get_user_ids_from_config(env_vars: Dict[str, Any]) -> list:
    """
    Get user IDs from SELECTED_USERS config.

    Args:
        env_vars: Environment variables dictionary.

    Returns:
        List of user IDs.
    """
    selected_users = env_vars.get('SELECTED_USERS', [])

    if not isinstance(selected_users, list):
        return []

    user_ids = []
    for user in selected_users:
        if isinstance(user, dict) and 'id' in user:
            user_ids.append(user['id'])
        elif isinstance(user, str):
            user_ids.append(user)

    return user_ids


# Keep old function name for backwards compatibility during transition
def sync_system_job_from_config() -> Dict[str, Any]:
    """Deprecated: Use import_config_to_db instead."""
    return import_config_to_db()
