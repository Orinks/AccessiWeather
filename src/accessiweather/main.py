"""Main entry point for AccessiWeather."""

from __future__ import annotations

import argparse
import logging
import sys

from .notification_activation import extract_activation_request_from_argv


def setup_logging(debug: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


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
        help="Skip lock-file prompt (set automatically after an update restart)",
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

    setup_logging(debug=args.debug)

    from .app import main as app_main

    app_main(
        config_dir=args.config_dir,
        portable_mode=args.portable,
        debug=args.debug,
        fake_version=args.fake_version,
        fake_nightly=args.fake_nightly,
        force_wizard=args.wizard,
        updated=args.updated,
        activation_request=args.activation_request,
    )


if __name__ == "__main__":
    main()
