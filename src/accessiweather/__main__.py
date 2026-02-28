"""
Entry point for `python -m accessiweather`.

Delegates entirely to main.py to keep a single source of truth for CLI args.
Exposes parse_args() for testability.
"""

from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments. Mirrors the argument definitions in main.py."""
    parser = argparse.ArgumentParser(description="AccessiWeather - Accessible Weather Application")
    parser.add_argument(
        "--config-dir",
        help="Custom configuration directory path",
        default=None,
    )
    parser.add_argument(
        "--portable",
        action="store_true",
        help="Run in portable mode (config stored in app directory)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--fake-version",
        help="Fake version for testing updates (e.g., '0.1.0')",
        default=None,
    )
    parser.add_argument(
        "--fake-nightly",
        help="Fake nightly tag for testing updates (e.g., 'nightly-20250101')",
        default=None,
    )
    parser.add_argument(
        "--wizard",
        action="store_true",
        help="Force the onboarding wizard to run even if it has already been shown",
    )
    return parser.parse_args()


def main() -> None:
    """Run the AccessiWeather application."""
    from accessiweather.main import setup_logging

    args = parse_args()
    setup_logging(debug=args.debug)

    from accessiweather.app import main as app_main

    app_main(
        config_dir=args.config_dir,
        portable_mode=args.portable,
        debug=args.debug,
        fake_version=args.fake_version,
        fake_nightly=args.fake_nightly,
        force_wizard=args.wizard,
    )


if __name__ == "__main__":
    main()
