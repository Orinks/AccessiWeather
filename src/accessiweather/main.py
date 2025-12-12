"""
Main entry point for AccessiWeather application.

This module provides the main entry point for the AccessiWeather application,
handling configuration, logging setup, and launching the Toga-based GUI.

The main() function serves as the primary entry point, called by the CLI interface
and configured in setup.py/pyproject.toml entry points.

Note:
    CLI parameters for configuration, debug mode, caching, and portability are accepted
    but currently not propagated into the GUI layer. Follow #316 for implementation updates.

"""

import logging

from accessiweather.app import main as toga_main
from accessiweather.logging_config import setup_logging

logger = logging.getLogger(__name__)


def main(
    config_dir: str | None = None,
    debug_mode: bool = False,
    enable_caching: bool = True,
    portable_mode: bool = False,
):
    """
    Create and return the Toga application instance.

    This function constructs the app and returns it to the caller. The caller is
    responsible for invoking app.main_loop() when appropriate (e.g., CLI entrypoint).

    Args:
    ----
        config_dir: Configuration directory, defaults to ~/.accessiweather
        debug_mode: Whether to enable debug mode with additional logging and alert testing features
        enable_caching: Whether to enable API response caching
        portable_mode: Whether to run in portable mode (saves config to local directory)

    Returns:
    -------
        The constructed Toga app instance.

    """
    # Set up logging with appropriate level based on debug_mode
    log_level = logging.DEBUG if debug_mode else logging.INFO
    setup_logging(log_level=log_level)

    logger.info(
        "Starting AccessiWeather application with parameters: "
        f"config_dir={config_dir}, debug_mode={debug_mode}, "
        f"enable_caching={enable_caching}, portable_mode={portable_mode}"
    )

    # Pass config_dir and portable_mode to the app
    return toga_main(config_dir=config_dir, portable_mode=portable_mode)


# Add blank line before if __name__ == "__main__":
if __name__ == "__main__":
    # If run directly, debug_mode defaults to False.
    # Assumes primary execution via cli.py which handles arg parsing.
    main()
