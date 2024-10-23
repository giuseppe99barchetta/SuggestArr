"""
This script loads and saves environment variables for connecting to TMDb, Jellyfin, Plex, and Seer APIs.
It uses the dotenv library to load variables from a .env file and ensures that valid cron expressions are provided.
"""

import ast
import os
import subprocess
import platform
from dotenv import load_dotenv
from croniter import croniter
from config.logger_manager import LoggerManager

# Constants for environment variables
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
    'JELLYFIN_LIBRARIES': 'JELLYFIN_LIBRARIES',
    'SELECTED_SERVICE': 'SELECTED_SERVICE',
    'PLEX_TOKEN': 'PLEX_TOKEN',
    'PLEX_API_URL': 'PLEX_API_URL',
    'PLEX_LIBRARIES': 'PLEX_LIBRARIES',
}

def load_env_vars():
    """
    Load variables from the .env file, if it exists, and return them as a dictionary.
    """
    load_dotenv(override=True)

    return {key: os.getenv(key, default_value()) for key, default_value in get_default_values().items()}

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
        ENV_VARS['MAX_SIMILAR_MOVIE']: lambda: '5',
        ENV_VARS['MAX_SIMILAR_TV']: lambda: '2',
        ENV_VARS['CRON_TIMES']: lambda: '0 0 * * *',
        ENV_VARS['MAX_CONTENT_CHECKS']: lambda: '10',
        ENV_VARS['JELLYFIN_LIBRARIES']: lambda: '[]',
        ENV_VARS['PLEX_TOKEN']: lambda: '',
        ENV_VARS['PLEX_API_URL']: lambda: '',
        ENV_VARS['PLEX_LIBRARIES']: lambda: '[]',
        ENV_VARS['SELECTED_SERVICE']: lambda: '',
    }

def save_env_vars(config_data):
    """
    Save environment variables from the web interface to the .env file. 
    Also validates cron times and updates them if needed.
    """
    cron_times = config_data.get(ENV_VARS['CRON_TIMES'], '0 0 * * *')

    if not croniter.is_valid(cron_times):
        raise ValueError("Invalid cron time provided.")

    # Prepare environment variables to be saved
    env_vars = {key: config_data.get(key, default_value()) for key, default_value in get_default_values().items()}
    
    # Write environment variables to the .env file
    with open('.env', 'w', encoding='utf-8') as f:
        for key, value in env_vars.items():
            f.write(f'{key}="{value}"\n')

    # Reload environment variables after saving
    load_env_vars()

    # Update cron job if on Linux
    if platform.system() == 'Linux':
        update_cron_job(cron_times)


def clear_env_vars():
    """
    Remove environment variables from memory and delete the .env file if it exists.
    """
    # List of environment variables to remove
    env_vars_to_remove = list(ENV_VARS.values())

    # Remove environment variables from memory
    for var in env_vars_to_remove:
        if var in os.environ:
            os.environ.pop(var, None)  # Remove variable if exists, no error if missing

    # Delete the .env file if it exists
    env_file_path = '.env'
    if os.path.exists(env_file_path):
        try:
            os.remove(env_file_path)
        except OSError as e:
            print(f"Error deleting {env_file_path}: {e}")
        
def update_cron_job(cron_time):
    """
    Updates the cron job to trigger the Flask API using curl. 
    This function is specific to Linux systems.
    """
    try:
        logger = LoggerManager().get_logger(__name__)

        # Command to call the Flask endpoint using curl
        cron_command = "curl -X POST http://localhost:5000/run_now >> /var/log/cron.log 2>&1"

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
        logger = LoggerManager().get_logger(__name__)
        logger.error(f"Failed to update cron job: {e}")
        raise RuntimeError(f"Failed to update cron job: {e}")
