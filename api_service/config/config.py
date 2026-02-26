import os
import yaml
import json
from croniter import croniter
from api_service.config.logger_manager import LoggerManager

logger = LoggerManager.get_logger("Config")

# Constants for environment variables
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'config_files', 'config.yaml')

def _parse_json_fields(config_data):
    """
    Parse JSON string fields into proper Python objects.
    Some fields might be stored as JSON strings and need to be parsed.

    Args:
        config_data (dict): Configuration dictionary

    Returns:
        dict: Configuration with parsed JSON fields
    """
    # Fields that should be lists/dicts but might be stored as JSON strings
    json_fields = [
        'SELECTED_USERS',
        'JELLYFIN_LIBRARIES',
        'PLEX_LIBRARIES',
        'FILTER_LANGUAGE',
        'FILTER_GENRES_EXCLUDE',
        'FILTER_STREAMING_SERVICES',
        'SEER_ANIME_PROFILE_CONFIG'
    ]

    for field in json_fields:
        if field in config_data and isinstance(config_data[field], str):
            try:
                # Try to parse as JSON
                parsed_value = json.loads(config_data[field])
                config_data[field] = parsed_value
                logger.debug(f"Parsed {field} from JSON string to {type(parsed_value).__name__}")
            except (json.JSONDecodeError, TypeError):
                # If parsing fails, check if it should be an empty list based on defaults
                default_value = get_default_values().get(field, lambda: None)()
                if isinstance(default_value, list):
                    config_data[field] = []
                    logger.warning(f"Failed to parse {field}, setting to empty list")

    return config_data

def load_env_vars():
    """
    Load variables from the config.yaml file and return them as a dictionary.
    """
    logger.debug("Loading environment variables from config.yaml")
    if not os.path.exists(CONFIG_PATH):
        logger.warning(f"{CONFIG_PATH} not found. Creating a new one with default values.")
        return get_config_values()

    with open(CONFIG_PATH, 'r', encoding='utf-8') as file:
        config_data = yaml.safe_load(file)
        logger.debug("Correctly loaded stored config.yaml")
        resolved_config = {key: config_data.get(key, default_value()) for key, default_value in get_default_values().items()}
        # Parse JSON string fields
        resolved_config = _parse_json_fields(resolved_config)
        return resolved_config


def get_default_values():
    """
    Returns a dictionary of default values for the environment variables.
    """
    logger.debug("Getting default values for environment variables")
    return {
        'TMDB_API_KEY': lambda: '',
        'JELLYFIN_API_URL': lambda: '',
        'JELLYFIN_TOKEN': lambda: '',
        'SEER_API_URL': lambda: '',
        'SEER_TOKEN': lambda: '',
        'SEER_USER_NAME': lambda: None,
        'SEER_USER_PSW': lambda: None,
        'SEER_SESSION_TOKEN': lambda: None,
        'MAX_SIMILAR_MOVIE': lambda: '5',
        'MAX_SIMILAR_TV': lambda: '2',
        'CRON_TIMES': lambda: '0 0 * * *',
        'MAX_CONTENT_CHECKS': lambda: '10',
        'SEARCH_SIZE': lambda: '20',
        'JELLYFIN_LIBRARIES': lambda: [],
        'PLEX_TOKEN': lambda: '',
        'PLEX_API_URL': lambda: '',
        'PLEX_LIBRARIES': lambda: [],
        'SELECTED_SERVICE': lambda: '',
        'FILTER_TMDB_THRESHOLD': lambda: None,
        'FILTER_TMDB_MIN_VOTES': lambda: None,
        'FILTER_GENRES_EXCLUDE': lambda: [],
        'HONOR_JELLYSEER_DISCOVERY': lambda: False,
        'FILTER_RELEASE_YEAR': lambda: None,
        'FILTER_INCLUDE_NO_RATING': lambda: True,
        'FILTER_LANGUAGE': lambda: None,
        'FILTER_NUM_SEASONS': lambda: None,
        'SELECTED_USERS': lambda: [],
        'FILTER_STREAMING_SERVICES': lambda: [],
        'FILTER_REGION_PROVIDER': lambda: None,
        'FILTER_MIN_RUNTIME': lambda: None,
        # Include pay-per-view availability (rent/buy) in streaming checks
        # Default: false (only subscription-based flatrate providers are considered)
        'FILTER_INCLUDE_TVOD': lambda: False,
        'SUBPATH': lambda: None,
        'DB_TYPE': lambda: 'sqlite',
        'DB_HOST': lambda: None,
        'DB_PORT': lambda: None,
        'DB_USER': lambda: None,
        'DB_PASSWORD': lambda: None,
        'DB_NAME': lambda: None,
        'EXCLUDE_DOWNLOADED': lambda: True,
        'EXCLUDE_REQUESTED': lambda: True,
        'SETUP_COMPLETED': lambda: False,
        'LOG_LEVEL': lambda: 'INFO',
        'ENABLE_BETA_FEATURES': lambda: False,
        'ENABLE_ADVANCED_ALGORITHM': lambda: False,
        'ENABLE_SOCIAL_FEATURES': lambda: False,
        'ENABLE_DEBUG_MODE': lambda: False,
        'ENABLE_PERFORMANCE_MONITORING': lambda: False,
        'ENABLE_VISUAL_EFFECTS': lambda: True,
        'ENABLE_STATIC_BACKGROUND': lambda: False,
        'STATIC_BACKGROUND_COLOR': lambda: '#2E3440',
        'OMDB_API_KEY': lambda: '',
        'FILTER_RATING_SOURCE': lambda: 'tmdb',
        'FILTER_IMDB_THRESHOLD': lambda: None,
        'FILTER_IMDB_MIN_VOTES': lambda: None,
        'OPENAI_API_KEY': lambda: '',
        'OPENAI_BASE_URL': lambda: '',
        'LLM_MODEL': lambda: 'gpt-4o-mini',
        'CACHE_TTL': lambda: 24,
        'MAX_CACHE_SIZE': lambda: 100,
        'API_TIMEOUT': lambda: 30,
        'API_RETRIES': lambda: 3,
        'ENABLE_API_CACHING': lambda: True,
        # Database connection pool settings
        'DB_MIN_CONNECTIONS': lambda: '2',
        'DB_MAX_CONNECTIONS': lambda: '10',
        'DB_MAX_IDLE_TIME': lambda: '300',
        'DB_MAX_LIFETIME': lambda: '3600',
        'DB_CONNECTION_TIMEOUT': lambda: '30',
        'DB_RETRY_ATTEMPTS': lambda: '3',
        'DB_RETRY_DELAY': lambda: '1.0',
        'SEER_ANIME_PROFILE_CONFIG': lambda: {},
        'SEER_REQUEST_DELAY': lambda: 2,
    }

def get_config_values():
    """
    Executes the lambdas and returns the actual values for JSON serialization.
    """
    logger.debug("Resolving default values for configuration")
    default_values = get_default_values()
    resolved_values = {key: value() if callable(value) else value for key, value in default_values.items()}
    logger.debug(f"Resolved configuration values: {resolved_values}")
    return resolved_values

def save_env_vars(config_data):
    """
    Save environment variables from the web interface to the config.yaml file.
    Also validates cron times and updates them if needed.
    """
    logger.debug("Saving environment variables to config.yaml")
    cron_times = config_data.get('CRON_TIMES', '0 0 * * *')

    valid_presets = {'daily', 'weekly', 'every_12h', 'every_6h', 'every_hour'}
    if cron_times not in valid_presets and not croniter.is_valid(cron_times):
        logger.error("Invalid cron time provided.")
        raise ValueError("Invalid cron time provided.")

    try:
        # Prepare environment variables to be saved
        env_vars = {
            key: value for key, value in {
                key: config_data.get(key, default_value()) for key, default_value in get_default_values().items()
            }.items() if value not in [None, '']
        }

        # Create config.yaml file if it does not exist
        if not os.path.exists(CONFIG_PATH):
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            logger.info(f'Creating new file for config at {CONFIG_PATH}')
            open(CONFIG_PATH, 'w').close()  # Create an empty file

        # Write environment variables to the config.yaml file
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            yaml.safe_dump(env_vars, f)
            logger.debug(f"Environment variables saved: {env_vars}")

    except Exception as e:
        logger.error(f"Error saving environment variables: {e}")
        raise


def clear_env_vars():
    """
    Remove environment variables from memory and delete the config.yaml file if it exists.
    """
    logger.debug("Clearing environment variables and deleting config.yaml if it exists")
    # Delete the config.yaml file if it exists
    if os.path.exists(CONFIG_PATH):
        try:
            os.remove(CONFIG_PATH)
            logger.info("Configuration cleared successfully.")
        except OSError as e:
            logger.error(f"Error deleting {CONFIG_PATH}: {e}")

def save_session_token(token):
    """Save session token of Seer client."""
    logger.debug("Saving session token")
    with open(CONFIG_PATH, 'r+', encoding='utf-8') as file:
        config_data = yaml.safe_load(file) or {}
        config_data['SEER_SESSION_TOKEN'] = token
        file.seek(0)
        yaml.dump(config_data, file)
        file.truncate()
        logger.debug("Session token saved successfully")

def get_config_sections():
    """
    Returns a dictionary of configuration sections and their associated keys.
    """
    return {
        'services': ['TMDB_API_KEY', 'OMDB_API_KEY', 'SELECTED_SERVICE', 'PLEX_TOKEN', 'PLEX_API_URL',
                    'PLEX_LIBRARIES', 'JELLYFIN_API_URL', 'JELLYFIN_TOKEN', 'JELLYFIN_LIBRARIES',
                    'SEER_API_URL', 'SEER_TOKEN', 'SEER_USER_NAME', 'SEER_USER_PSW',
                    'SEER_SESSION_TOKEN', 'SEER_ANIME_PROFILE_CONFIG', 'SEER_REQUEST_DELAY',
                    'SELECTED_USERS'],
        'database': ['DB_TYPE', 'DB_HOST', 'DB_PORT', 'DB_USER', 'DB_PASSWORD', 'DB_NAME',
                    'DB_MIN_CONNECTIONS', 'DB_MAX_CONNECTIONS', 'DB_MAX_IDLE_TIME', 
                    'DB_MAX_LIFETIME', 'DB_CONNECTION_TIMEOUT', 'DB_RETRY_ATTEMPTS', 'DB_RETRY_DELAY'],
        'content_filters': ['FILTER_RATING_SOURCE', 'FILTER_TMDB_THRESHOLD', 'FILTER_TMDB_MIN_VOTES',
                           'FILTER_IMDB_THRESHOLD', 'FILTER_IMDB_MIN_VOTES', 'FILTER_GENRES_EXCLUDE',
                           'HONOR_JELLYSEER_DISCOVERY', 'FILTER_RELEASE_YEAR', 'FILTER_INCLUDE_NO_RATING',
                           'FILTER_LANGUAGE', 'FILTER_NUM_SEASONS', 'FILTER_STREAMING_SERVICES',
                           'FILTER_REGION_PROVIDER', 'EXCLUDE_DOWNLOADED', 'EXCLUDE_REQUESTED',
                           'FILTER_MIN_RUNTIME', 'FILTER_INCLUDE_TVOD'],
        'advanced': ['SELECTED_USERS', 'LOG_LEVEL', 'ENABLE_BETA_FEATURES',
                     'ENABLE_ADVANCED_ALGORITHM', 'ENABLE_SOCIAL_FEATURES',
                     'ENABLE_DEBUG_MODE', 'ENABLE_PERFORMANCE_MONITORING', 'ENABLE_VISUAL_EFFECTS',
                     'ENABLE_STATIC_BACKGROUND', 'STATIC_BACKGROUND_COLOR',
                     'CACHE_TTL', 'MAX_CACHE_SIZE', 'API_TIMEOUT', 'API_RETRIES',
                     'ENABLE_API_CACHING', 'OPENAI_API_KEY', 'OPENAI_BASE_URL',
                     'LLM_MODEL', 'SUBPATH']
    }

def get_config_section(section_name):
    """
    Retrieve a specific configuration section.

    Args:
        section_name (str): Name of the section to retrieve

    Returns:
        dict: Configuration values for the requested section
    """
    sections = get_config_sections()
    if section_name not in sections:
        raise ValueError(f"Unknown configuration section: {section_name}")

    config = load_env_vars()
    section_keys = sections[section_name]

    return {key: config.get(key) for key in section_keys}

def save_config_section(section_name, section_data):
    """
    Save a specific configuration section.

    Args:
        section_name (str): Name of the section to save
        section_data (dict): Configuration values for the section
    """
    sections = get_config_sections()
    if section_name not in sections:
        raise ValueError(f"Unknown configuration section: {section_name}")

    # Load current configuration
    current_config = load_env_vars()

    # Update only the section-specific keys
    section_keys = sections[section_name]
    for key in section_keys:
        if key in section_data:
            current_config[key] = section_data[key]

    # Special handling for setup completion
    if section_name in ['services', 'database']:
        # Check if essential setup is completed
        if is_setup_complete(current_config):
            current_config['SETUP_COMPLETED'] = True

    # Save the updated configuration
    save_env_vars(current_config)

def is_setup_complete(config_data=None):
    """
    Check if essential setup configuration is complete.

    Args:
        config_data (dict, optional): Configuration data to check. If None, loads from file.

    Returns:
        bool: True if essential setup is complete
    """
    if config_data is None:
        config_data = load_env_vars()

    # Check essential configurations
    essential_checks = [
        config_data.get('TMDB_API_KEY'),  # TMDB API key is required
        config_data.get('SELECTED_SERVICE'),  # Media service selection
    ]

    # Service-specific checks
    service = config_data.get('SELECTED_SERVICE')
    if service == 'plex':
        essential_checks.extend([
            config_data.get('PLEX_TOKEN'),
            config_data.get('PLEX_API_URL'),
        ])
    elif service in ('jellyfin', 'emby'):
        essential_checks.extend([
            config_data.get('JELLYFIN_API_URL'),
            config_data.get('JELLYFIN_TOKEN'),
        ])

    # Database check (always required)
    db_type = config_data.get('DB_TYPE', 'sqlite')
    if db_type != 'sqlite':
        essential_checks.extend([
            config_data.get('DB_HOST'),
            config_data.get('DB_PORT'),
            config_data.get('DB_USER'),
            config_data.get('DB_PASSWORD'),
            config_data.get('DB_NAME')
        ])

    # Consider setup complete if all essential fields are filled
    return all(essential_checks)
