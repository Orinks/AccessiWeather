"""Command-line interface for AccessiWeather

This module provides a command-line interface for running the application.
"""

import argparse
import logging
import sys
from typing import List, Optional

from accessiweather.main import main as app_main


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments

    Args:
        args: Command-line arguments (uses sys.argv if None)

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description=("AccessiWeather - An accessible weather " "application using NOAA data")
    )

    # Debug mode options
    debug_group = parser.add_argument_group("Debug Options")
    debug_group.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
    debug_group.add_argument(
        "--debug-mode",
        choices=["test-alert", "verify-interval"],
        help="Run in specific debug mode: test-alert to trigger test alerts, "
        "verify-interval to verify alert update intervals",
    )
    debug_group.add_argument(
        "--alert-severity",
        choices=["Extreme", "Severe", "Moderate", "Minor"],
        default="Moderate",
        help="Severity level for test alerts",
    )
    debug_group.add_argument(
        "--alert-event", default="Test Alert", help="Event name for test alerts"
    )

    # General options
    parser.add_argument("-c", "--config", help="Path to configuration directory")
    parser.add_argument("--no-cache", action="store_true", help="Disable API response caching")

    return parser.parse_args(args)


def main() -> int:
    """Main entry point for the command-line interface

    Returns:
        Exit code
    """
    args = parse_args()

    # Logging setup is now handled in main.py

    try:
        # Create debug options dictionary
        debug_options = (
            {
                "debug_mode": args.debug_mode,
                "alert_severity": args.alert_severity,
                "alert_event": args.alert_event,
            }
            if args.debug_mode
            else None
        )

        # Pass arguments to main application entry point
        app_main(
            config_dir=args.config,
            debug_mode=args.debug,
            enable_caching=not args.no_cache,
            debug_options=debug_options,
        )
        return 0
    except Exception as e:
        logging.error(f"Error running application: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
