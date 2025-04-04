"""Command-line interface for AccessiWeather.

This module provides a command-line interface for running the application.
"""

import argparse
import logging
import sys
from typing import List, Optional

from accessiweather.main import run_app as app_main


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Command-line arguments (uses sys.argv if None)

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description=("AccessiWeather - An accessible weather " "application using NOAA data")
    )
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("-c", "--config", help="Path to configuration directory")

    return parser.parse_args(args)


def main() -> int:
    """Run the command-line interface.

    Returns:
        Exit code
    """
    args = parse_args()

    # Logging setup is now handled in main.py

    try:
        # Pass debug flag to main application entry point
        app_main(config_dir=args.config, debug_mode=args.debug)
        return 0
    except Exception as e:
        logging.error(f"Error running application: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
