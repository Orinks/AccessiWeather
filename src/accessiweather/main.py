"""Main entry point for AccessiWeather."""

from __future__ import annotations

import argparse
import logging
import sys

from .notification_activation import extract_activation_request_from_argv


def setup_logging(
    debug: bool = False,
    config_dir: str | None = None,
    portable_mode: bool = False,
) -> None:
    """
    Set up console and rotating file logging.

    Packaged builds have no console, so file logging is on by default: without
    it there is no record of what the app did.  Logs go to ``logs/`` under the
    same config root the app itself uses, which keeps a portable copy's logs
    beside the portable config instead of in the user profile.
    """
    level = logging.DEBUG if debug else logging.INFO

    # Mirror the app's own portable resolution so logs and config agree.
    if not portable_mode and config_dir is None:
        try:
            from .paths import detect_portable_mode

            portable_mode = detect_portable_mode()
        except Exception:
            portable_mode = False

    try:
        from .logging_config import setup_logging as setup_file_logging

        setup_file_logging(level, config_dir=config_dir, portable_mode=portable_mode)
        return
    except Exception:
        # A read-only or missing log directory must never stop the app starting.
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        logging.getLogger(__name__).warning("File logging unavailable; console only", exc_info=True)


def _build_parser() -> argparse.ArgumentParser:
    """Build the shared parser for desktop entrypoints."""
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
    parser.add_argument(
        "--updated",
        action="store_true",
        help="Mark this launch as an update restart",
    )
    parser.add_argument(
        "--startup",
        action="store_true",
        dest="startup_launch",
        help="Mark this launch as an automatic startup launch",
    )
    return parser


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse desktop entrypoint arguments, allowing Windows toast activation tokens."""
    parser = _build_parser()
    parsed_args, extras = parser.parse_known_args(args)
    token_argv = [sys.argv[0], *extras] if args is None else extras
    parsed_args.activation_request = extract_activation_request_from_argv(token_argv)
    unknown = [arg for arg in extras if extract_activation_request_from_argv([arg]) is None]
    if unknown:
        parser.error(f"unrecognized arguments: {' '.join(unknown)}")
    return parsed_args


def main() -> None:
    """Run the AccessiWeather application."""
    args = parse_args()

    setup_logging(debug=args.debug, config_dir=args.config_dir, portable_mode=args.portable)

    from .app import main as app_main

    app_main(
        config_dir=args.config_dir,
        portable_mode=args.portable,
        debug=args.debug,
        fake_version=args.fake_version,
        fake_nightly=args.fake_nightly,
        force_wizard=args.wizard,
        updated=args.updated,
        startup_launch=args.startup_launch,
        activation_request=args.activation_request,
    )


if __name__ == "__main__":
    main()
