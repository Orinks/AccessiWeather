"""
Entry point for `python -m accessiweather`.

Delegates entirely to main.py to keep a single source of truth for CLI args.
Exposes parse_args() for testability.
"""

from __future__ import annotations

import argparse


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments using the shared desktop entrypoint parser."""
    from accessiweather.main import parse_args as parse_main_args

    return parse_main_args(args)


def main() -> None:
    """Run the AccessiWeather application."""
    from accessiweather.main import main as run_main

    run_main()


if __name__ == "__main__":
    main()
