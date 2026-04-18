"""
Windows startup enablement must compare the shortcut's target, not just existence.

Previously `_is_windows_startup_enabled` returned True whenever any
`accessiweather.lnk` existed in the Startup folder — even one pointing at a
different install (e.g. a dev venv or an older path). That made
`apply_startup_setting` a no-op when it should have overwritten the shortcut
to point at the current executable, matching the macOS/Linux behavior.

These tests pin the new semantics: True only when the shortcut targets the
same executable and arguments as `_get_launch_command()` returns now.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from accessiweather.services.startup_utils import StartupManager


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    platform_detector = MagicMock()
    platform_info = MagicMock()
    platform_info.platform = "windows"
    platform_info.app_directory = Path("accessiweather")
    platform_detector.get_platform_info.return_value = platform_info
    return StartupManager(platform_detector=platform_detector)


def _shortcut_path(manager: StartupManager) -> Path:
    return manager._get_windows_startup_shortcut()


def test_disabled_when_shortcut_missing(manager):
    assert manager._is_windows_startup_enabled() is False


def test_enabled_when_shortcut_targets_current_launch_command(manager, monkeypatch):
    expected_target = Path("C:/Program Files/AccessiWeather/AccessiWeather.exe")
    expected_args: list[str] = []
    monkeypatch.setattr(manager, "_get_launch_command", lambda: (expected_target, expected_args))
    monkeypatch.setattr(
        manager,
        "_read_windows_shortcut",
        lambda _path: (str(expected_target), ""),
    )
    _shortcut_path(manager).touch()

    assert manager._is_windows_startup_enabled() is True


def test_disabled_when_shortcut_targets_different_executable(manager, monkeypatch):
    """
    A stale .lnk pointing at a different install must be treated as disabled.

    This is the dev-venv vs. installed-exe case: user's dev session created a
    shortcut pointing at the venv python; running the installed .exe must see
    the shortcut as out-of-date and overwrite it.
    """
    monkeypatch.setattr(
        manager,
        "_get_launch_command",
        lambda: (Path("C:/Program Files/AccessiWeather/AccessiWeather.exe"), []),
    )
    monkeypatch.setattr(
        manager,
        "_read_windows_shortcut",
        lambda _path: (
            "C:/Users/joshu/accessiweather/.venv/Scripts/python.exe",
            "-m accessiweather",
        ),
    )
    _shortcut_path(manager).touch()

    assert manager._is_windows_startup_enabled() is False


def test_enabled_when_shortcut_targets_python_with_matching_args(manager, monkeypatch):
    """Source-run case: python.exe + `-m accessiweather` args must match."""
    monkeypatch.setattr(
        manager,
        "_get_launch_command",
        lambda: (Path("C:/venv/Scripts/python.exe"), ["-m", "accessiweather"]),
    )
    monkeypatch.setattr(
        manager,
        "_read_windows_shortcut",
        lambda _path: ("C:/venv/Scripts/python.exe", "-m accessiweather"),
    )
    _shortcut_path(manager).touch()

    assert manager._is_windows_startup_enabled() is True


def test_disabled_when_shortcut_target_unreadable(manager, monkeypatch):
    """
    Unreadable .lnk (corrupt/PowerShell-missing) is treated as not-enabled.

    Safer to overwrite than to leave a potentially broken shortcut in place.
    """
    monkeypatch.setattr(
        manager, "_get_launch_command", lambda: (Path("C:/app/AccessiWeather.exe"), [])
    )
    monkeypatch.setattr(manager, "_read_windows_shortcut", lambda _path: None)
    _shortcut_path(manager).touch()

    assert manager._is_windows_startup_enabled() is False
