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
    def get_logger(name: str, log_file='app.log', max_bytes=5 * 1024 * 1024, backup_count=5):
        """
        Returns a logger with the specified name and log level.
        
        :param name: The name of the logger (usually the module name).
        :param level: The logging level (e.g., logging.INFO, logging.DEBUG).
        :param log_file: The path to the file where logs will be saved.
        :param max_bytes: The maximum file size (in bytes) before rotating.
        :param backup_count: The number of backup files to keep.
        :return: Configured logger instance.
        """
        logger = logging.getLogger(name)
        log_level = os.getenv('LOG_LEVEL', 'info').upper()
        logger.setLevel(log_level)

        # Check if the logger already has handlers to avoid duplicate handlers
        if not logger.handlers:
            # Create a console handler to send logs to stdout
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)

            # Create a file handler to save logs to a file
            file_handler = ConcurrentRotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8')
            file_handler.setLevel(log_level)

            # Create a logging format
            formatter = logging.Formatter('%(asctime)s - %(name)-20s - %(levelname)-5s - %(message)s')
            console_handler.setFormatter(formatter)
            file_handler.setFormatter(formatter)

            # Add both handlers to the logger
            logger.addHandler(console_handler)
            logger.addHandler(file_handler)
        
        return logger
