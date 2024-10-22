"""
This script loads environment variables for connecting to the TMDb, Jellyfin, and Seer APIs.
It uses the dotenv library to load variables from a .env file and validates their presence.
"""
import ast
import os
import subprocess
import platform
from dotenv import load_dotenv
from croniter import croniter
from config.logger_manager import LoggerManager

# Constants for environment variables
TMDB_API_KEY = 'TMDB_API_KEY'
JELLYFIN_API_URL = 'JELLYFIN_API_URL'
JELLYFIN_TOKEN = 'JELLYFIN_TOKEN'
SEER_API_URL = 'SEER_API_URL'
SEER_TOKEN = 'SEER_TOKEN'
SEER_USER_NAME = 'SEER_USER_NAME'
SEER_USER_PSW = 'SEER_USER_PSW'
MAX_SIMILAR_MOVIE = 'MAX_SIMILAR_MOVIE'
MAX_SIMILAR_TV = 'MAX_SIMILAR_TV'
CRON_TIMES = 'CRON_TIMES'
MAX_CONTENT_CHECKS = 'MAX_CONTENT_CHECKS'
JELLYFIN_LIBRARIES = 'JELLYFIN_LIBRARIES'
SELECTED_SERVICE = 'SELECTED_SERVICE'
PLEX_TOKEN = 'PLEX_TOKEN'
PLEX_API_URL = 'PLEX_API_URL'
PLEX_LIBRARIES = 'PLEX_LIBRARIES'

def load_env_vars():
    """
    Load variables from .env file.
    """
    load_dotenv(override=True)

    return {
        TMDB_API_KEY: os.getenv(TMDB_API_KEY, ''),
        JELLYFIN_API_URL: os.getenv(JELLYFIN_API_URL, ''),
        JELLYFIN_TOKEN: os.getenv(JELLYFIN_TOKEN, ''),
        SEER_API_URL: os.getenv(SEER_API_URL, ''),
        SEER_TOKEN: os.getenv(SEER_TOKEN, ''),
        SEER_USER_NAME: os.getenv(SEER_USER_NAME, None),
        SEER_USER_PSW: os.getenv(SEER_USER_PSW, None),
        MAX_SIMILAR_MOVIE: os.getenv(MAX_SIMILAR_MOVIE, '5'),
        MAX_SIMILAR_TV: os.getenv(MAX_SIMILAR_TV, '2'),
        CRON_TIMES: os.getenv(CRON_TIMES, '0 0 * * *'),
        MAX_CONTENT_CHECKS: os.getenv(MAX_CONTENT_CHECKS, '10'),
        JELLYFIN_LIBRARIES: os.getenv(JELLYFIN_LIBRARIES, '[]'),
        PLEX_TOKEN: os.getenv(PLEX_TOKEN, ''),
        PLEX_API_URL: os.getenv(PLEX_API_URL, ''),
        PLEX_LIBRARIES: os.getenv(PLEX_LIBRARIES, '[]'),
        SELECTED_SERVICE: os.getenv(SELECTED_SERVICE, ''),
    }

def save_env_vars(config_data):
    """
    Save environment variables from web interface to .env file.
    """
    cron_times = config_data.get(CRON_TIMES, '0 0 * * *')

    if not croniter.is_valid(cron_times):
        raise ValueError("Invalid cron time provided.")

    # Consolidated environment variables
    env_vars = {
        TMDB_API_KEY: config_data.get(TMDB_API_KEY, ''),
        JELLYFIN_API_URL: config_data.get(JELLYFIN_API_URL, ''),
        JELLYFIN_TOKEN: config_data.get(JELLYFIN_TOKEN, ''),
        SEER_API_URL: config_data.get(SEER_API_URL, ''),
        SEER_TOKEN: config_data.get(SEER_TOKEN, ''),
        SEER_USER_NAME: config_data.get(SEER_USER_NAME, ''),
        SEER_USER_PSW: config_data.get(SEER_USER_PSW, ''),
        MAX_SIMILAR_MOVIE: config_data.get(MAX_SIMILAR_MOVIE, '5'),
        MAX_SIMILAR_TV: config_data.get(MAX_SIMILAR_TV, '2'),
        CRON_TIMES: cron_times,
        MAX_CONTENT_CHECKS: config_data.get(MAX_CONTENT_CHECKS, '10'),
        JELLYFIN_LIBRARIES: config_data.get(JELLYFIN_LIBRARIES, '[]'),
        PLEX_LIBRARIES: config_data.get(PLEX_LIBRARIES, '[]'),
        SELECTED_SERVICE: config_data.get(SELECTED_SERVICE, ''),
        PLEX_TOKEN: config_data.get(PLEX_TOKEN, ''),
        PLEX_API_URL: config_data.get(PLEX_API_URL, ''),
    }

    # Write environment variables to .env file
    with open('.env', 'w', encoding='utf-8') as f:
        for key, value in env_vars.items():
            f.write(f'{key}="{value}"\n')

    # Reload environment variables after saving
    load_env_vars()

    # Update cron job if on Linux
    if platform.system() == 'Linux':
        update_cron_job(cron_times)


def update_cron_job(cron_time):
    """
    Updates the cron job file in the operating system to trigger the Flask API via curl.
    """
    try:
        logger = LoggerManager().get_logger(__name__)

        # Command to call the Flask endpoint using curl
        cron_command = (
            "curl -X POST http://localhost:5000/run_now "
            ">> /var/log/cron.log 2>&1"
        )

        # Create the content of the new cron job
        cron_entry = f"{cron_time} {cron_command}\n"

        # Write the new cron job to the configuration file
        cron_file_path = "/etc/cron.d/automation-cron"
        with open(cron_file_path, "w", encoding="utf-8") as cron_file:
            cron_file.write(cron_entry)

        # Ensure the cron file has the correct permissions on Unix-like systems
        subprocess.run(["chmod", "0644", cron_file_path], check=True)

        # Reload cron
        subprocess.run(["crontab", cron_file_path], check=True)

        logger.info("Cron job updated with: %s", cron_time)

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to update cron job: {e}")
