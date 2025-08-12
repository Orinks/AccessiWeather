"""Main entry point for AccessiWeather application.

This module provides the main entry point for the AccessiWeather application,
handling configuration, logging setup, and launching the Toga-based GUI.

The main() function serves as the primary entry point, called by the CLI interface
and configured in setup.py/pyproject.toml entry points.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

from accessiweather.app import main as toga_main


def setup_logging(
    log_filename: str = "accessiweather.log",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 3,
    log_level: int = logging.INFO,
) -> logging.Logger:
    """Set up logging configuration with rotating file handler.

    Args:
        log_filename: Name of the log file (default: "accessiweather.log")
        max_bytes: Maximum size per log file in bytes (default: 5MB)
        backup_count: Number of backup files to keep (default: 3)
        log_level: Logging level (default: logging.INFO)

    Returns:
        Configured logger instance

    """
    console_handler = logging.StreamHandler(sys.stdout)
    file_handler = RotatingFileHandler(
        log_filename,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[console_handler, file_handler],
        force=True,  # Override any existing configuration
    )

    return logging.getLogger(__name__)


# Set up default logging configuration
logger = setup_logging()


def main(
    config_dir: str | None = None,
    debug_mode: bool = False,
    enable_caching: bool = True,
    portable_mode: bool = False,
):
    """Run the application.

    Args:
        config_dir: Configuration directory, defaults to ~/.accessiweather
        debug_mode: Whether to enable debug mode with additional logging and alert testing features
        enable_caching: Whether to enable API response caching
        portable_mode: Whether to run in portable mode (saves config to local directory)

    """
    try:
        logger.info(
            "Starting AccessiWeather application with parameters: "
            f"config_dir={config_dir}, debug_mode={debug_mode}, "
            f"enable_caching={enable_caching}, portable_mode={portable_mode}"
        )

        # TODO: Pass configuration parameters to the application
        # Currently, the AccessiWeatherApp doesn't accept these parameters in its constructor
        # Configuration is handled through ConfigManager which uses app.paths
        # Future enhancement: Modify AccessiWeatherApp to accept these parameters

        app = toga_main()
        app.main_loop()

    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        print(f"Error: {e}")
        sys.exit(1)


# Add blank line before if __name__ == "__main__":
if __name__ == "__main__":
    # If run directly, debug_mode defaults to False.
    # Assumes primary execution via cli.py which handles arg parsing.
    main()
