"""
Main entry point for running the module directly.

Allows running the module with `python -m accessiweather`
or as a PyInstaller exe with CLI flags.
"""

import argparse


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="AccessiWeather - Accessible Weather Application",
    )
    parser.add_argument(
        "--config-dir",
        help="Custom configuration directory path",
    )
    parser.add_argument(
        "--portable",
        action="store_true",
        help="Run in portable mode",
    )
    parser.add_argument(
        "--fake-version",
        metavar="VERSION",
        help="Override version for update testing (e.g., '0.1.0')",
    )
    parser.add_argument(
        "--fake-nightly",
        metavar="TAG",
        help="Override nightly build tag for update testing (e.g., 'nightly-20250101')",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    from accessiweather.app import main

    main(
        config_dir=args.config_dir,
        portable_mode=args.portable,
        fake_version=args.fake_version,
        fake_nightly=args.fake_nightly,
    )
