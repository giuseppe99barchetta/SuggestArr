import os
import subprocess
import yaml
from croniter import croniter
from api_service.config.logger_manager import LoggerManager
from api_service.config.cron_jobs import start_cron_job

logger = LoggerManager().get_logger("Config")

# Constants for environment variables
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'config_files', 'config.yaml')

def load_env_vars():
    """
    Load variables from the config.yaml file and return them as a dictionary.
    """
    if not os.path.exists(CONFIG_PATH):
        logger.warning(f"{CONFIG_PATH} not found. Creating a new one with default values.")
        return get_config_values()

    with open(CONFIG_PATH, 'r', encoding='utf-8') as file:
        config_data = yaml.safe_load(file)
        logger.debug("Correctly loaded stored config.yaml")
        return {key: config_data.get(key, default_value()) for key, default_value in get_default_values().items()}


def get_default_values():
    """
    Returns a dictionary of default values for the environment variables.
    """
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
        'SUBPATH': lambda: None,
        'DB_TYPE': lambda: 'sqlite',
        'DB_HOST': lambda: None,
        'DB_PORT': lambda: None,
        'DB_USER': lambda: None,
        'DB_PASSWORD': lambda: None,
        'DB_NAME': lambda: None,
    }

def get_config_values():
    """
    Executes the lambdas and returns the actual values for JSON serialization.
    """
    default_values = get_default_values()
    resolved_values = {key: value() if callable(value) else value for key, value in default_values.items()}
    return resolved_values

def save_env_vars(config_data):
    """
    Save environment variables from the web interface to the config.yaml file.
    Also validates cron times and updates them if needed.
    """
    cron_times = config_data.get('CRON_TIMES', '0 0 * * *')

    if not croniter.is_valid(cron_times):
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

        # Reload environment variables after saving
        load_env_vars()
        
        # Update the cron job
        start_cron_job(env_vars)
        
    except Exception as e:
        logger.error(f"Error saving environment variables: {e}")
        raise


def clear_env_vars():
    """
    Remove environment variables from memory and delete the config.yaml file if it exists.
    """
    # Delete the config.yaml file if it exists
    if os.path.exists(CONFIG_PATH):
        try:
            os.remove(CONFIG_PATH)
            logger.info("Configuration cleared successfully.")
        except OSError as e:
            logger.error(f"Error deleting {CONFIG_PATH}: {e}")

def save_session_token(token):
    """Save session token of Seer client."""
    with open(CONFIG_PATH, 'r+', encoding='utf-8') as file:
        config_data = yaml.safe_load(file) or {}
        config_data['SEER_SESSION_TOKEN'] = token
        file.seek(0)
        yaml.dump(config_data, file)
        file.truncate()

