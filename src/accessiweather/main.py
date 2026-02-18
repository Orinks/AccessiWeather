"""Main entry point for AccessiWeather."""

from __future__ import annotations

import argparse
import logging
import sys


def setup_logging(debug: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> None:
    """Run the AccessiWeather application."""
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
        "--play-exit-sound-only",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--sound-pack",
        default="default",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    setup_logging(debug=args.debug)

    if args.play_exit_sound_only:
        from .notifications.sound_player import play_exit_sound_blocking

        play_exit_sound_blocking(args.sound_pack)
        return

    from .app import main as app_main

    app_main(
        config_dir=args.config_dir,
        portable_mode=args.portable,
        debug=args.debug,
        fake_version=args.fake_version,
        fake_nightly=args.fake_nightly,
    )


if __name__ == "__main__":
    main()
