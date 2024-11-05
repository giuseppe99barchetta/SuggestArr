import os
import subprocess
import platform
import yaml
from croniter import croniter
from api_service.config.logger_manager import LoggerManager

logger = LoggerManager().get_logger(__name__)

# Constants for environment variables
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'config_files', 'config.yaml')

ENV_VARS = {
    'TMDB_API_KEY': 'TMDB_API_KEY',
    'JELLYFIN_API_URL': 'JELLYFIN_API_URL',
    'JELLYFIN_TOKEN': 'JELLYFIN_TOKEN',
    'SEER_API_URL': 'SEER_API_URL',
    'SEER_TOKEN': 'SEER_TOKEN',
    'SEER_USER_NAME': 'SEER_USER_NAME',
    'SEER_USER_PSW': 'SEER_USER_PSW',
    'MAX_SIMILAR_MOVIE': 'MAX_SIMILAR_MOVIE',
    'MAX_SIMILAR_TV': 'MAX_SIMILAR_TV',
    'CRON_TIMES': 'CRON_TIMES',
    'MAX_CONTENT_CHECKS': 'MAX_CONTENT_CHECKS',
    'SEARCH_SIZE': 'SEARCH_SIZE',
    'JELLYFIN_LIBRARIES': 'JELLYFIN_LIBRARIES',
    'SELECTED_SERVICE': 'SELECTED_SERVICE',
    'PLEX_TOKEN': 'PLEX_TOKEN',
    'PLEX_API_URL': 'PLEX_API_URL',
    'PLEX_LIBRARIES': 'PLEX_LIBRARIES',
    'SEER_SESSION_TOKEN': 'SEER_SESSION_TOKEN',
    'FILTER_TMDB_THRESHOLD': 'FILTER_TMDB_THRESHOLD',
    'FILTER_TMDB_MIN_VOTES': 'FILTER_TMDB_MIN_VOTES',
    'FILTER_GENRES_EXCLUDE': 'FILTER_GENRES_EXCLUDE',
    'FILTER_RELEASE_YEAR': 'FILTER_RELEASE_YEAR',
    'HONOR_JELLYSEER_DISCOVERY': 'HONOR_JELLYSEER_DISCOVERY',
    'FILTER_INCLUDE_NO_RATING': 'FILTER_INCLUDE_NO_RATING',
    'FILTER_LANGUAGE':'FILTER_LANGUAGE',
    'FILTER_NUM_SEASONS':'FILTER_NUM_SEASONS',
    'SELECTED_USERS': 'SELECTED_USERS',
}

def load_env_vars():
    """
    Load variables from the config.yaml file and return them as a dictionary.
    """
    if not os.path.exists(CONFIG_PATH):
        logger.warning(f"{CONFIG_PATH} not found. Creating a new one with default values.")
        return get_default_values()

    with open(CONFIG_PATH, 'r', encoding='utf-8') as file:
        config_data = yaml.safe_load(file)
        return {key: config_data.get(key, default_value()) for key, default_value in get_default_values().items()}


def get_default_values():
    """
    Returns a dictionary of default values for the environment variables.
    """
    return {
        ENV_VARS['TMDB_API_KEY']: lambda: '',
        ENV_VARS['JELLYFIN_API_URL']: lambda: '',
        ENV_VARS['JELLYFIN_TOKEN']: lambda: '',
        ENV_VARS['SEER_API_URL']: lambda: '',
        ENV_VARS['SEER_TOKEN']: lambda: '',
        ENV_VARS['SEER_USER_NAME']: lambda: None,
        ENV_VARS['SEER_USER_PSW']: lambda: None,
        ENV_VARS['SEER_SESSION_TOKEN']: lambda: None,
        ENV_VARS['MAX_SIMILAR_MOVIE']: lambda: '5',
        ENV_VARS['MAX_SIMILAR_TV']: lambda: '2',
        ENV_VARS['CRON_TIMES']: lambda: '0 0 * * *',
        ENV_VARS['MAX_CONTENT_CHECKS']: lambda: '10',
        ENV_VARS['SEARCH_SIZE']: lambda: '20',
        ENV_VARS['JELLYFIN_LIBRARIES']: lambda: [],
        ENV_VARS['PLEX_TOKEN']: lambda: '',
        ENV_VARS['PLEX_API_URL']: lambda: '',
        ENV_VARS['PLEX_LIBRARIES']: lambda: [],
        ENV_VARS['SELECTED_SERVICE']: lambda: '',
        ENV_VARS['FILTER_TMDB_THRESHOLD']: lambda: None,
        ENV_VARS['FILTER_TMDB_MIN_VOTES']: lambda: None,
        ENV_VARS['FILTER_GENRES_EXCLUDE']: lambda: [],
        ENV_VARS['HONOR_JELLYSEER_DISCOVERY']: lambda: False,
        ENV_VARS['FILTER_RELEASE_YEAR']: lambda: None,
        ENV_VARS['FILTER_INCLUDE_NO_RATING']: lambda: True,
        ENV_VARS['FILTER_LANGUAGE']: lambda: None,
        ENV_VARS['FILTER_NUM_SEASONS']: lambda: None,
        ENV_VARS['SELECTED_USERS']: lambda: [],
    }


def save_env_vars(config_data):
    """
    Save environment variables from the web interface to the config.yaml file.
    Also validates cron times and updates them if needed.
    """
    cron_times = config_data.get(ENV_VARS['CRON_TIMES'], '0 0 * * *')

    if not croniter.is_valid(cron_times):
        raise ValueError("Invalid cron time provided.")

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

    # Update cron job if on Linux
    if platform.system() == 'Linux':
        update_cron_job(cron_times)


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

def update_cron_job(cron_time):
    """
    Updates the cron job to trigger the Flask API using curl.
    This function is specific to Linux systems.
    """
    try:
        # Command to call the Flask endpoint using curl
        cron_command = "curl -X POST http://localhost:5000/api/automation/force_run >> /var/log/cron.log 2>&1"

        # Create the cron job entry
        cron_entry = f"{cron_time} {cron_command}\n"

        # Path for the cron job configuration file
        cron_file_path = "/etc/cron.d/automation-cron"
        
        # Write the cron entry to the file
        with open(cron_file_path, "w", encoding="utf-8") as cron_file:
            cron_file.write(cron_entry)

        # Set correct permissions and reload cron
        subprocess.run(["chmod", "0644", cron_file_path], check=True)
        subprocess.run(["crontab", cron_file_path], check=True)

        logger.info("Cron job updated with: %s", cron_time)

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to update cron job: {e}")
        raise RuntimeError(f"Failed to update cron job: {e}")
