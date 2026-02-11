"""
Logging configuration for AccessiWeather application.

This module sets up logging for the application with both console and file output.
Logs are saved to a 'logs' subfolder within the AccessiWeather config directory.
"""

import contextlib
import logging
import logging.handlers
import os
import sys
from pathlib import Path

from accessiweather.config_utils import get_config_dir


def setup_logging(log_level=logging.INFO):
    r"""
    Set up logging for the application.

    Logs are saved to {config_dir}/logs/accessiweather.log where config_dir is:
    - Windows: %APPDATA%\.accessiweather
    - Linux/macOS: ~/.accessiweather
    - Portable mode: {app_dir}/config

    Args:
    ----
        log_level: Logging level (default: INFO)

    """
    # Get config directory and create logs subfolder
    config_dir = Path(get_config_dir())
    log_dir = config_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    # Secure log directory permissions: owner-only access (rwx------)
    with contextlib.suppress(OSError):
        log_dir.chmod(0o700)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to avoid duplicates when reloading
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create formatters
    console_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s", datefmt="%H:%M:%S"
    )
    file_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s"
    )

    # Console handler - less verbose for normal use
    console = logging.StreamHandler(stream=sys.stdout)
    console.setLevel(log_level)
    console.setFormatter(console_format)
    root_logger.addHandler(console)

    # File handler - more verbose for debugging
    log_file = log_dir / "accessiweather.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,  # 5 MB
    )
    file_handler.setLevel(log_level)  # Match configured level — don't force DEBUG to file
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)

    # Configure performance logger
    perf_logger = logging.getLogger("performance")
    perf_mode = os.environ.get("ACCESSIWEATHER_PERFORMANCE", "").lower() in ("1", "true", "yes")
    if perf_mode or log_level <= logging.DEBUG:
        perf_logger.setLevel(logging.INFO)
        logging.info("Performance monitoring enabled")
    else:
        perf_logger.setLevel(logging.WARNING)

    # Log startup information
    logging.info(f"Logging initialized at level {logging.getLevelName(log_level)}")
    logging.info(f"Log file: {log_file}")

    return log_dir
