"""
Command-line interface for AccessiWeather.

This module provides a command-line interface for running the application.
"""

import argparse
import logging
import sys

from accessiweather.app import main as app_main
from accessiweather.main import setup_logging
from accessiweather.notification_activation import extract_activation_request_from_argv


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

    parsed_args, extras = parser.parse_known_args(args)
    parsed_args.activation_request = extract_activation_request_from_argv(
        [sys.argv[0], *extras] if args is None else extras
    )
    unknown = [arg for arg in extras if extract_activation_request_from_argv([arg]) is None]
    if unknown:
        parser.error(f"unrecognized arguments: {' '.join(unknown)}")
    return parsed_args


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
            activation_request=args.activation_request,
        )
        return 0
    except Exception as e:
        logging.error(f"Error running application: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
