from __future__ import annotations

from accessiweather.cli import parse_args as parse_cli_args
from accessiweather.main import parse_args as parse_main_args


def test_parse_args_accepts_startup_launch_flag() -> None:
    args = parse_main_args(["--startup"])

    assert args.startup_launch is True


def test_parse_args_defaults_startup_launch_to_false() -> None:
    args = parse_main_args([])

    assert args.startup_launch is False


def test_cli_parse_args_accepts_startup_launch_flag() -> None:
    args = parse_cli_args(["--startup"])

    assert args.startup_launch is True
