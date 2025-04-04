"""Logging configuration for AccessiWeather application.

This module sets up logging for the application with both console and file
output.
"""

import logging
import logging.handlers
import sys
from pathlib import Path


def setup_logging(log_level=logging.INFO):
    """Set up logging for the application.

    Args:
        log_level: Logging level (default: INFO)
    """
    # Create logs directory if it doesn't exist
    log_dir = Path.home() / "AccessiWeather_logs"
    log_dir.mkdir(exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to avoid duplicates when reloading
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create formatters
    console_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    file_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - " "%(filename)s:%(lineno)d - %(message)s"
    )

    # Console handler - less verbose for normal use
    console = logging.StreamHandler(stream=sys.stdout)
    console.setLevel(log_level)
    console.setFormatter(console_format)
    root_logger.addHandler(console)

    # File handler - more verbose for debugging
    log_file = log_dir / "accessiweather.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3  # 5 MB
    )
    file_handler.setLevel(min(log_level, logging.DEBUG))  # Always include DEBUG in file
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)

    # Log startup information
    logging.info(f"Logging initialized at level {logging.getLevelName(log_level)}")
    logging.info(f"Log file: {log_file}")

    return log_dir
