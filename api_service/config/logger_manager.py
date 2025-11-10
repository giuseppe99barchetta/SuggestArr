"""
LoggerManager Module

This module provides a centralized way to configure and manage loggers across the application.

Classes:
    - LoggerManager: Configures and returns loggers for use in different parts of the application.

Example:
    logger = LoggerManager.get_logger(__name__)
    logger.info("This is an informational message.")
"""

import os
import logging
import sys
from concurrent_log_handler import ConcurrentRotatingFileHandler

class LoggerManager:
    """
    LoggerManager is responsible for configuring and managing loggers throughout the application.
    It provides a centralized way to set up logging with custom levels, formats, and handlers.
    """

    @staticmethod
    def get_logger(name: str, max_bytes=5 * 1024 * 1024, backup_count=5, log_file=None):
        """
        Returns a logger with the specified name and log level.

        :param name: The name of the logger (usually the module name).
        :param max_bytes: The maximum file size (in bytes) before rotating.
        :param backup_count: The number of backup files to keep.
        :param log_file: The path to the file where logs will be saved.
        :return: Configured logger instance.
        """

        if log_file is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../config/config_files'))
            os.makedirs(base_dir, exist_ok=True)  # Ensure directory exists
            log_file = os.path.join(base_dir, 'app.log')

        logger = logging.getLogger(name)

        # Try to get log level from configuration first, then environment, then default
        try:
            from . import config as config_module
            config_vars = config_module.load_env_vars()
            log_level_str = config_vars.get('LOG_LEVEL', os.getenv('LOG_LEVEL', 'INFO')).upper()
        except Exception:
            # Fallback to environment variable if configuration loading fails
            log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()

        # Map string log levels to logging constants
        log_level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR
        }

        log_level = log_level_map.get(log_level_str, logging.INFO)
        logger.setLevel(log_level)

        # Check if the logger already has handlers to avoid duplicate handlers
        if not logger.handlers:
            # Create a console handler to send logs to stdout
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG)  # Set to DEBUG to capture all levels, let logger filter

            # Create a file handler to save logs to a file
            file_handler = ConcurrentRotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)  # Set to DEBUG to capture all levels, let logger filter

            # Create a logging format
            formatter = logging.Formatter('%(asctime)s - %(name)-20s - %(levelname)-5s - %(message)s')
            console_handler.setFormatter(formatter)
            file_handler.setFormatter(formatter)

            # Add both handlers to the logger
            logger.addHandler(console_handler)
            logger.addHandler(file_handler)
        
        return logger

    @staticmethod
    def set_log_level(level: str):
        """
        Dynamically set the log level for all loggers and save to configuration.

        :param level: The log level to set ('DEBUG', 'INFO', 'WARNING', 'ERROR')
        """
        log_level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR
        }

        if level.upper() not in log_level_map:
            raise ValueError(f"Invalid log level: {level}. Must be one of: DEBUG, INFO, WARNING, ERROR")

        # Set environment variable for future loggers
        os.environ['LOG_LEVEL'] = level.upper()

        # Update existing loggers
        for logger_name in logging.Logger.manager.loggerDict:
            logger = logging.getLogger(logger_name)
            logger.setLevel(log_level_map[level.upper()])

        # Save to configuration file for persistence
        try:
            from . import config as config_module
            config_vars = config_module.load_env_vars()
            config_vars['LOG_LEVEL'] = level.upper()
            config_module.save_env_vars(config_vars)
        except Exception as e:
            # Don't fail the log level change if saving config fails
            print(f"Warning: Could not save log level to configuration: {e}")

    @staticmethod
    def get_current_log_level():
        """
        Get the current log level from configuration or environment.

        :return: Current log level string
        """
        try:
            from . import config as config_module
            config_vars = config_module.load_env_vars()
            return config_vars.get('LOG_LEVEL', os.getenv('LOG_LEVEL', 'INFO')).upper()
        except Exception:
            return os.getenv('LOG_LEVEL', 'INFO').upper()
