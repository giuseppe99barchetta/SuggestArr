"""
Utility functions for managing environment and worker processes.
"""

import os
import psutil
from dotenv import load_dotenv
from config.logger_manager import LoggerManager

logger = LoggerManager.get_logger(__name__)

class AppUtils:
    """
    A utility class for application-level tasks such as environment loading
    and worker process identification.
    """

    @staticmethod
    def is_last_worker():
        """
        Check if the current process is the last worker based on the highest PID.
        """
        current_pid = os.getpid()
        pids = [p.pid for p in psutil.process_iter()]
        max_pid = max(pids)
        return current_pid == max_pid

    @staticmethod
    def load_environment():
        """
        Reload environment variables from the .env file.
        """
        load_dotenv(override=True)
        logger.debug("Environment variables reloaded.")

    @staticmethod
    def print_welcome_message():
        """
        Log the welcome message.
        """
        welcome_message = """
        
        =====================================================================================
        |   Welcome to the SuggestArr Application!                                          |
        |   Manage your settings through the web interface at: http://localhost:5000        |
        |   Fill in the input fields with your data and let the cron job handle the rest!   |
        |   To run the automation process immediately, click the 'Force Run' button.        |
        |   The 'Force Run' button will appear only after you save your settings.           |
        |   To leave feedback visit: https://github.com/giuseppe99barchetta/SuggestArr      |
        =====================================================================================
        """
        logger.info(welcome_message)
