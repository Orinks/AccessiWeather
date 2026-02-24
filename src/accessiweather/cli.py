"""
Command-line interface for AccessiWeather.

This module provides a command-line interface for running the application.
"""

import argparse
import logging
import sys

from accessiweather.app import main as app_main
from accessiweather.main import setup_logging


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """
    Parse command-line arguments.

    Args:
    ----
        args: Command-line arguments (uses sys.argv if None)

    Returns:
    -------
        Parsed arguments

    """
    parser = argparse.ArgumentParser(
        description=("AccessiWeather - An accessible weather application using NOAA data")
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug mode with additional logging and alert testing features",
    )
    parser.add_argument("-c", "--config", help="Path to configuration directory")
    parser.add_argument(
        "--portable",
        action="store_true",
        help="Run in portable mode (saves configuration to local directory instead of user directory)",
    )

    return parser.parse_args(args)


def main() -> int:
    """
    Run the command-line interface.

    Returns
    -------
        Exit code

    """
    args = parse_args()

    setup_logging(debug=args.debug)

    try:
        # Pass arguments to main application entry point
        app_main(
            config_dir=args.config,
            portable_mode=args.portable,
            debug=args.debug,
        )
        return 0
    except Exception as e:
        logging.error(f"Error running application: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
