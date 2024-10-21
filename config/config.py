"""
This script loads environment variables for connecting to the TMDb, Jellyfin, and Jellyseer APIs.
It uses the dotenv library to load variables from a .env file and validates their presence.
"""
import ast
import os
import subprocess
import platform
from dotenv import load_dotenv

from croniter import croniter
from config.logger_manager import LoggerManager

TMDB_API_KEY = 'TMDB_API_KEY'
JELLYFIN_API_URL = 'JELLYFIN_API_URL'
JELLYFIN_TOKEN = 'JELLYFIN_TOKEN'
JELLYSEER_API_URL = 'JELLYSEER_API_URL'
JELLYSEER_TOKEN = 'JELLYSEER_TOKEN'
MAX_SIMILAR_MOVIE = 'MAX_SIMILAR_MOVIE'
MAX_SIMILAR_TV = 'MAX_SIMILAR_TV'
CRON_TIMES = 'CRON_TIMES'
JELLYSEER_USER_NAME = 'JELLYSEER_USER_NAME'
JELLYSEER_USER_PSW = 'JELLYSEER_USER_PSW'
MAX_CONTENT_CHECKS = 'MAX_CONTENT_CHECKS'
JELLYFIN_LIBRARIES = 'JELLYFIN_LIBRARIES'

def load_env_vars():
    """
    Load variables from .env file
    """
    load_dotenv(override=True)

    jellyfin_libraries = os.getenv('JELLYFIN_LIBRARIES', '[]')
    try:
        jellyfin_libraries = ast.literal_eval(jellyfin_libraries)
        if not isinstance(jellyfin_libraries, list):
            jellyfin_libraries = []
    except (ValueError, SyntaxError):
        jellyfin_libraries = []

    return {
        TMDB_API_KEY: os.getenv(TMDB_API_KEY, ''),
        JELLYFIN_API_URL: os.getenv(JELLYFIN_API_URL, ''),
        JELLYFIN_TOKEN: os.getenv(JELLYFIN_TOKEN, ''),
        JELLYSEER_API_URL: os.getenv(JELLYSEER_API_URL, ''),
        JELLYSEER_TOKEN: os.getenv(JELLYSEER_TOKEN, ''),
        MAX_SIMILAR_MOVIE: os.getenv(MAX_SIMILAR_MOVIE, '5'),
        MAX_SIMILAR_TV: os.getenv(MAX_SIMILAR_TV, '2'),
        CRON_TIMES: os.getenv(CRON_TIMES, '0 0 * * *'),
        JELLYSEER_USER_NAME: os.getenv(JELLYSEER_USER_NAME, None),
        JELLYSEER_USER_PSW: os.getenv(JELLYSEER_USER_PSW, None),
        MAX_CONTENT_CHECKS: os.getenv(MAX_CONTENT_CHECKS, '10'),
        JELLYFIN_LIBRARIES: jellyfin_libraries
    }

def save_env_vars(config_data):
    """
    Save environment variables from web interface.
    """
    cron_times = config_data.get('CRON_TIMES', '0 0 * * *')
    
    print(config_data.get(JELLYFIN_LIBRARIES, ''))

    if not croniter.is_valid(cron_times):
        raise ValueError("Invalid cron time provided.")

    env_vars = {
        TMDB_API_KEY: config_data.get('TMDB_API_KEY', ''),
        JELLYFIN_API_URL: config_data.get('JELLYFIN_API_URL', ''),
        JELLYFIN_TOKEN: config_data.get('JELLYFIN_TOKEN', ''),
        JELLYSEER_API_URL: config_data.get('JELLYSEER_API_URL', ''),
        JELLYSEER_TOKEN: config_data.get('JELLYSEER_TOKEN', ''),
        MAX_SIMILAR_MOVIE: config_data.get('MAX_SIMILAR_MOVIE', '5'),
        MAX_SIMILAR_TV: config_data.get('MAX_SIMILAR_TV', '2'),
        CRON_TIMES: cron_times,
        JELLYSEER_USER_PSW: config_data.get('JELLYSEER_USER_PSW', ''),
        JELLYSEER_USER_NAME: config_data.get('JELLYSEER_USER_NAME', ''),
        MAX_CONTENT_CHECKS: config_data.get('MAX_CONTENT_CHECKS', '10'),
        JELLYFIN_LIBRARIES: config_data.get(JELLYFIN_LIBRARIES, ''),
    }

    with open('.env', 'w', encoding='utf-8') as f:
        for key, value in env_vars.items():
            f.write(f'{key}="{value}"\n')

    load_env_vars()

    # Update cron only in linux system
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
