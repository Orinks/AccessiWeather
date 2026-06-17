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

import subprocess
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


def test_windows_startup_shortcut_uses_stable_accessiweather_name(manager):
    assert _shortcut_path(manager).name == "AccessiWeather.lnk"


def test_windows_shortcut_probe_timeout_is_short_for_settings_dialog(manager):
    assert manager._WINDOWS_SHORTCUT_COMMAND_TIMEOUT_SECONDS <= 2


def test_windows_startup_launch_command_marks_automatic_startup(manager, monkeypatch):
    executable = Path("C:/Program Files/AccessiWeather/AccessiWeather.exe")
    monkeypatch.setattr(manager, "_get_app_executable", lambda: executable)
    monkeypatch.setattr("accessiweather.services.startup_utils.is_compiled_runtime", lambda: True)

    assert manager._get_launch_command(for_startup=True) == (
        executable,
        ["--startup"],
    )


def test_enable_windows_startup_creates_shortcut_with_startup_marker(manager, monkeypatch):
    expected_target = Path("C:/Program Files/AccessiWeather/AccessiWeather.exe")
    created = {}

    monkeypatch.setattr(
        manager,
        "_get_launch_command",
        lambda *, for_startup=False: (expected_target, ["--startup"] if for_startup else []),
    )
    monkeypatch.setattr(
        manager,
        "_create_windows_shortcut",
        lambda target, shortcut_path, args: (
            shortcut_path.touch()
            or created.update({"target": target, "shortcut_path": shortcut_path, "args": args})
        ),
    )

    assert manager._enable_windows_startup() is True
    assert created == {
        "target": expected_target,
        "shortcut_path": _shortcut_path(manager),
        "args": ["--startup"],
    }


def test_enable_windows_startup_removes_legacy_shortcuts(manager, monkeypatch):
    expected_target = Path("C:/Program Files/AccessiWeather/AccessiWeather.exe")
    legacy_shortcut = _shortcut_path(manager).parent / "portable-copy.lnk"
    legacy_shortcut.touch()
    monkeypatch.setattr(
        manager,
        "_get_launch_command",
        lambda *, for_startup=False: (expected_target, ["--startup"] if for_startup else []),
    )
    monkeypatch.setattr(manager, "_get_legacy_windows_startup_shortcuts", lambda: [legacy_shortcut])
    monkeypatch.setattr(
        manager,
        "_create_windows_shortcut",
        lambda _target, shortcut_path, _args: shortcut_path.touch(),
    )

    assert manager._enable_windows_startup() is True
    assert not legacy_shortcut.exists()


def test_enable_windows_startup_fails_when_shortcut_is_not_created(manager, monkeypatch):
    expected_target = Path("C:/Program Files/AccessiWeather/AccessiWeather.exe")
    monkeypatch.setattr(
        manager,
        "_get_launch_command",
        lambda *, for_startup=False: (expected_target, ["--startup"] if for_startup else []),
    )
    monkeypatch.setattr(manager, "_create_windows_shortcut", lambda *_args: None)

    assert manager._enable_windows_startup() is False


def test_disable_windows_startup_removes_legacy_shortcuts(manager, monkeypatch):
    current_shortcut = _shortcut_path(manager)
    legacy_shortcut = current_shortcut.parent / "portable-copy.lnk"
    current_shortcut.touch()
    legacy_shortcut.touch()
    monkeypatch.setattr(manager, "_get_legacy_windows_startup_shortcuts", lambda: [legacy_shortcut])

    assert manager._disable_windows_startup() is True
    assert not current_shortcut.exists()
    assert not legacy_shortcut.exists()


def test_create_windows_shortcut_prefers_com_without_starting_powershell(
    manager, monkeypatch, tmp_path
):
    target = tmp_path / "AccessiWeather.exe"
    target.touch()
    shortcut_path = tmp_path / "AccessiWeather.lnk"
    created = {}

    def unexpected_powershell(*_args, **_kwargs):
        raise AssertionError("PowerShell should not run when COM shortcut creation succeeds")

    monkeypatch.setattr(subprocess, "run", unexpected_powershell)
    monkeypatch.setattr(
        manager,
        "_create_windows_shortcut_with_com",
        lambda target, shortcut_path, args: (
            created.update({"target": target, "shortcut_path": shortcut_path, "args": args}) or True
        ),
    )

    manager._create_windows_shortcut(target, shortcut_path, ["--startup"])

    assert created == {
        "target": target,
        "shortcut_path": shortcut_path,
        "args": ["--startup"],
    }


def test_create_windows_shortcut_falls_back_to_powershell_when_com_is_unavailable(
    manager, monkeypatch, tmp_path
):
    target = tmp_path / "AccessiWeather.exe"
    target.touch()
    shortcut_path = tmp_path / "AccessiWeather.lnk"
    captured = {}

    def capture_run(command, **_kwargs):
        captured["command"] = command
        shortcut_path.touch()
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", capture_run)
    monkeypatch.setattr(manager, "_create_windows_shortcut_with_com", lambda *_args: False)

    manager._create_windows_shortcut(target, shortcut_path, ["--startup"])

    assert captured["command"][0] == "powershell.exe"
    assert shortcut_path.exists()


def test_create_windows_shortcut_quotes_source_args_with_spaces(manager, monkeypatch, tmp_path):
    target = tmp_path / "Python With Spaces" / "python.exe"
    target.parent.mkdir()
    target.touch()
    shortcut_path = tmp_path / "AccessiWeather.lnk"
    captured = {}

    def capture_run(command, **_kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(manager, "_create_windows_shortcut_with_com", lambda *_args: False)
    monkeypatch.setattr(subprocess, "run", capture_run)

    manager._create_windows_shortcut(
        target,
        shortcut_path,
        [
            "-m",
            "accessiweather",
            "--config-dir",
            "C:\\Users\\Name With Spaces\\Config",
            "--startup",
        ],
    )

    script = captured["command"][-1]
    assert "$shortcut.TargetPath = " in script
    assert (
        "$shortcut.Arguments = "
        "'-m accessiweather --config-dir \"C:\\Users\\Name With Spaces\\Config\" --startup';"
    ) in script
    assert f"$shortcut.IconLocation = '{target},0';" in script


def test_disable_windows_startup_returns_false_when_appdata_is_missing(manager, monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)

    assert manager._disable_windows_startup() is False


def test_enabled_when_shortcut_targets_current_launch_command(manager, monkeypatch):
    expected_target = Path("C:/Program Files/AccessiWeather/AccessiWeather.exe")
    expected_args = ["--startup"]
    monkeypatch.setattr(
        manager,
        "_get_launch_command",
        lambda *, for_startup=False: (expected_target, expected_args if for_startup else []),
    )
    monkeypatch.setattr(
        manager,
        "_read_windows_shortcut",
        lambda _path: (str(expected_target), "--startup"),
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
        lambda *, for_startup=False: (
            Path("C:/Program Files/AccessiWeather/AccessiWeather.exe"),
            ["--startup"] if for_startup else [],
        ),
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
        lambda *, for_startup=False: (
            Path("C:/venv/Scripts/python.exe"),
            ["-m", "accessiweather", "--startup"] if for_startup else ["-m", "accessiweather"],
        ),
    )
    monkeypatch.setattr(
        manager,
        "_read_windows_shortcut",
        lambda _path: ("C:/venv/Scripts/python.exe", "-m accessiweather --startup"),
    )
    _shortcut_path(manager).touch()

    assert manager._is_windows_startup_enabled() is True


def test_disabled_when_shortcut_target_unreadable(manager, monkeypatch):
    """
    Unreadable .lnk (corrupt/PowerShell-missing) is treated as not-enabled.

    Safer to overwrite than to leave a potentially broken shortcut in place.
    """
    monkeypatch.setattr(
        manager,
        "_get_launch_command",
        lambda *, for_startup=False: (
            Path("C:/app/AccessiWeather.exe"),
            ["--startup"] if for_startup else [],
        ),
    )
    monkeypatch.setattr(manager, "_read_windows_shortcut", lambda _path: None)
    _shortcut_path(manager).touch()

    assert manager._is_windows_startup_enabled() is False


def test_disabled_when_shortcut_read_times_out(manager, monkeypatch):
    """A stalled PowerShell shortcut read must not hang settings dialog startup."""
    monkeypatch.setattr(
        manager,
        "_get_launch_command",
        lambda *, for_startup=False: (
            Path("C:/app/AccessiWeather.exe"),
            ["--startup"] if for_startup else [],
        ),
    )
    _shortcut_path(manager).touch()

    def timeout_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout"))

    monkeypatch.setattr(subprocess, "run", timeout_run)

    assert manager._read_windows_shortcut(_shortcut_path(manager)) is None
    assert manager._is_windows_startup_enabled() is False
