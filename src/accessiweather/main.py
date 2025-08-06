"""Main entry point for AccessiWeather.

This module provides the main entry point for running the application.
"""

import sys

from accessiweather.toga_app import main as toga_main

# Add blank line before function definition


def main(
    config_dir: str | None = None,
    debug_mode: bool = False,
    enable_caching: bool = True,
    portable_mode: bool = False,
):
    """Main entry point for the application.

    Args:
        config_dir: Configuration directory, defaults to ~/.accessiweather
        debug_mode: Whether to enable debug mode with additional logging and alert testing features
        enable_caching: Whether to enable API response caching
        portable_mode: Whether to run in portable mode (saves config to local directory)

    """
    return toga_main()


# Add blank line before if __name__ == "__main__":
if __name__ == "__main__":
    # If run directly, debug_mode defaults to False.
    # Assumes primary execution via cli.py which handles arg parsing.
    sys.exit(main())
