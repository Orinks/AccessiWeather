"""
Windows startup registration via the HKCU Run registry key.

The legacy implementation dropped a .lnk into the Startup folder and needed a
PowerShell subprocess (with a 2 second timeout) just to read it back. A cold
PowerShell start after a reboot or an app update routinely exceeded that
timeout, so the status probe reported "disabled", the settings dialog synced
the checkbox off, and saving then deleted the shortcut — the classic
"startup unchecks itself after every update" bug.

The registry implementation is in-process and instant. These tests pin:
- enable/disable/status never spawn a subprocess
- "enabled" is keyed on the Run value name, not on a strict path comparison,
  so a stale command after an update still reads as enabled (and is repaired)
- Task Manager's StartupApproved disable flag is honored and cleared on
  explicit re-enable
- legacy Startup-folder shortcuts are detected as enabled and migrated
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from accessiweather.services import startup_utils
from accessiweather.services.startup_utils import StartupManager

RUN_KEY = StartupManager._WINDOWS_RUN_KEY_PATH
APPROVED_RUN_KEY = StartupManager._WINDOWS_STARTUP_APPROVED_RUN_KEY_PATH
APPROVED_FOLDER_KEY = StartupManager._WINDOWS_STARTUP_APPROVED_FOLDER_KEY_PATH
RUN_VALUE = StartupManager._WINDOWS_RUN_VALUE_NAME

APPROVED_ENABLED = bytes([0x02] + [0x00] * 11)
APPROVED_DISABLED = bytes([0x03] + [0x00] * 11)


class _FakeKey:
    def __init__(self, registry: FakeWinreg, path: str) -> None:
        self.registry = registry
        self.path = path

    def __enter__(self) -> _FakeKey:
        return self

    def __exit__(self, *exc_info) -> None:
        return None


class FakeWinreg:
    """In-memory stand-in for the winreg module (HKCU only)."""

    HKEY_CURRENT_USER = object()
    REG_SZ = 1
    REG_BINARY = 3
    KEY_SET_VALUE = 0x0002

    def __init__(self) -> None:
        """Create an empty in-memory registry store."""
        self.store: dict[str, dict[str, tuple[object, int]]] = {}

    def OpenKey(self, _root, path: str, _reserved: int = 0, _access: int = 0) -> _FakeKey:
        if path not in self.store:
            raise FileNotFoundError(path)
        return _FakeKey(self, path)

    def CreateKey(self, _root, path: str) -> _FakeKey:
        self.store.setdefault(path, {})
        return _FakeKey(self, path)

    def QueryValueEx(self, key: _FakeKey, name: str) -> tuple[object, int]:
        values = self.store[key.path]
        if name not in values:
            raise FileNotFoundError(name)
        return values[name]

    def SetValueEx(self, key: _FakeKey, name: str, _reserved: int, type_: int, value) -> None:
        self.store[key.path][name] = (value, type_)

    def DeleteValue(self, key: _FakeKey, name: str) -> None:
        values = self.store[key.path]
        if name not in values:
            raise FileNotFoundError(name)
        del values[name]

    # Test conveniences -------------------------------------------------
    def set_value(self, key_path: str, name: str, value, type_: int) -> None:
        self.store.setdefault(key_path, {})[name] = (value, type_)

    def get_value(self, key_path: str, name: str):
        return self.store.get(key_path, {}).get(name, (None, None))[0]

    def has_value(self, key_path: str, name: str) -> bool:
        return name in self.store.get(key_path, {})


@pytest.fixture
def fake_winreg(monkeypatch) -> FakeWinreg:
    fake = FakeWinreg()
    monkeypatch.setattr(startup_utils, "winreg", fake)
    return fake


@pytest.fixture
def manager(tmp_path, monkeypatch, fake_winreg) -> StartupManager:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    platform_detector = MagicMock()
    platform_info = MagicMock()
    platform_info.platform = "windows"
    platform_info.app_directory = Path("accessiweather")
    platform_detector.get_platform_info.return_value = platform_info

    manager = StartupManager(platform_detector=platform_detector)
    executable = Path("C:/Program Files/AccessiWeather/AccessiWeather.exe")
    monkeypatch.setattr(
        manager,
        "_get_launch_command",
        lambda *, for_startup=False: (executable, ["--startup"] if for_startup else []),
    )
    return manager


@pytest.fixture
def no_subprocess(monkeypatch):
    def _fail(*_args, **_kwargs):
        raise AssertionError("Windows startup management must not spawn subprocesses")

    monkeypatch.setattr(subprocess, "run", _fail)
    monkeypatch.setattr(subprocess, "Popen", _fail)


def _startup_dir(tmp_path: Path) -> Path:
    return tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


EXPECTED_COMMAND = '"C:\\Program Files\\AccessiWeather\\AccessiWeather.exe" --startup'


def test_disabled_when_nothing_registered(manager, no_subprocess):
    assert manager._is_windows_startup_enabled() is False


def test_enable_writes_quoted_run_command_with_startup_marker(manager, fake_winreg, no_subprocess):
    assert manager._enable_windows_startup() is True
    assert fake_winreg.get_value(RUN_KEY, RUN_VALUE) == EXPECTED_COMMAND
    assert manager._is_windows_startup_enabled() is True


def test_enable_clears_task_manager_disable_flag(manager, fake_winreg, no_subprocess):
    fake_winreg.set_value(APPROVED_RUN_KEY, RUN_VALUE, APPROVED_DISABLED, FakeWinreg.REG_BINARY)

    assert manager._enable_windows_startup() is True

    assert not fake_winreg.has_value(APPROVED_RUN_KEY, RUN_VALUE)
    assert manager._is_windows_startup_enabled() is True


def test_enable_migrates_legacy_startup_folder_shortcuts(
    manager, fake_winreg, tmp_path, no_subprocess
):
    startup_dir = _startup_dir(tmp_path)
    startup_dir.mkdir(parents=True)
    legacy = startup_dir / "AccessiWeather.lnk"
    legacy.touch()
    fake_winreg.set_value(APPROVED_FOLDER_KEY, legacy.name, APPROVED_ENABLED, FakeWinreg.REG_BINARY)

    assert manager._enable_windows_startup() is True

    assert not legacy.exists()
    assert not fake_winreg.has_value(APPROVED_FOLDER_KEY, legacy.name)
    assert fake_winreg.get_value(RUN_KEY, RUN_VALUE) == EXPECTED_COMMAND


def test_disable_removes_run_value_flag_and_legacy_shortcuts(
    manager, fake_winreg, tmp_path, no_subprocess
):
    startup_dir = _startup_dir(tmp_path)
    startup_dir.mkdir(parents=True)
    legacy = startup_dir / "accessiweather.lnk"
    legacy.touch()
    fake_winreg.set_value(RUN_KEY, RUN_VALUE, EXPECTED_COMMAND, FakeWinreg.REG_SZ)
    fake_winreg.set_value(APPROVED_RUN_KEY, RUN_VALUE, APPROVED_ENABLED, FakeWinreg.REG_BINARY)

    assert manager._disable_windows_startup() is True

    assert not fake_winreg.has_value(RUN_KEY, RUN_VALUE)
    assert not fake_winreg.has_value(APPROVED_RUN_KEY, RUN_VALUE)
    assert not legacy.exists()
    assert manager._is_windows_startup_enabled() is False


def test_disable_succeeds_when_appdata_is_missing(manager, fake_winreg, monkeypatch):
    """Registry cleanup must not depend on the Startup folder being locatable."""
    monkeypatch.delenv("APPDATA", raising=False)
    fake_winreg.set_value(RUN_KEY, RUN_VALUE, EXPECTED_COMMAND, FakeWinreg.REG_SZ)

    assert manager._disable_windows_startup() is True
    assert not fake_winreg.has_value(RUN_KEY, RUN_VALUE)


def test_enabled_even_when_stored_command_is_stale(manager, fake_winreg, no_subprocess):
    """
    After an update the stored command may point at an old path.

    That is still user intent "start with Windows" — status must stay enabled
    so the settings checkbox does not silently uncheck; repair happens
    separately.
    """
    fake_winreg.set_value(
        RUN_KEY, RUN_VALUE, '"C:\\Old Install\\AccessiWeather.exe" --startup', FakeWinreg.REG_SZ
    )

    assert manager._is_windows_startup_enabled() is True
    assert manager.is_startup_registration_current() is False


def test_disabled_when_task_manager_flagged_off(manager, fake_winreg, no_subprocess):
    fake_winreg.set_value(RUN_KEY, RUN_VALUE, EXPECTED_COMMAND, FakeWinreg.REG_SZ)
    fake_winreg.set_value(APPROVED_RUN_KEY, RUN_VALUE, APPROVED_DISABLED, FakeWinreg.REG_BINARY)

    assert manager._is_windows_startup_enabled() is False
    assert manager.is_startup_disabled_by_os() is True


def test_enabled_flag_even_first_byte_counts_as_enabled(manager, fake_winreg):
    fake_winreg.set_value(RUN_KEY, RUN_VALUE, EXPECTED_COMMAND, FakeWinreg.REG_SZ)
    fake_winreg.set_value(APPROVED_RUN_KEY, RUN_VALUE, APPROVED_ENABLED, FakeWinreg.REG_BINARY)

    assert manager._is_windows_startup_enabled() is True
    assert manager.is_startup_disabled_by_os() is False


def test_legacy_shortcut_counts_as_enabled_pending_migration(manager, tmp_path, no_subprocess):
    startup_dir = _startup_dir(tmp_path)
    startup_dir.mkdir(parents=True)
    (startup_dir / "AccessiWeather.lnk").touch()

    assert manager._is_windows_startup_enabled() is True
    assert manager.is_startup_registration_current() is False


def test_legacy_shortcut_disabled_by_task_manager_reports_disabled(
    manager, fake_winreg, tmp_path, no_subprocess
):
    startup_dir = _startup_dir(tmp_path)
    startup_dir.mkdir(parents=True)
    legacy = startup_dir / "AccessiWeather.lnk"
    legacy.touch()
    fake_winreg.set_value(
        APPROVED_FOLDER_KEY, legacy.name, APPROVED_DISABLED, FakeWinreg.REG_BINARY
    )

    assert manager._is_windows_startup_enabled() is False
    assert manager.is_startup_disabled_by_os() is True


def test_registration_current_only_when_command_matches_and_no_legacy_leftovers(
    manager, fake_winreg, tmp_path, no_subprocess
):
    fake_winreg.set_value(RUN_KEY, RUN_VALUE, EXPECTED_COMMAND, FakeWinreg.REG_SZ)
    assert manager.is_startup_registration_current() is True

    # A leftover legacy shortcut would double-launch the app at logon.
    startup_dir = _startup_dir(tmp_path)
    startup_dir.mkdir(parents=True)
    (startup_dir / "AccessiWeather.lnk").touch()
    assert manager.is_startup_registration_current() is False

    # Re-enable migrates the shortcut and restores a current registration.
    assert manager._enable_windows_startup() is True
    assert manager.is_startup_registration_current() is True


def test_full_toggle_cycle_never_spawns_subprocess(manager, no_subprocess):
    assert manager.enable_startup() is True
    assert manager.is_startup_enabled() is True
    assert manager.is_startup_registration_current() is True
    assert manager.disable_startup() is True
    assert manager.is_startup_enabled() is False


def test_source_run_command_quotes_paths_with_spaces(manager, fake_winreg, monkeypatch):
    python = Path("C:/Python With Spaces/python.exe")
    monkeypatch.setattr(
        manager,
        "_get_launch_command",
        lambda *, for_startup=False: (
            python,
            ["-m", "accessiweather"] + (["--startup"] if for_startup else []),
        ),
    )

    assert manager._enable_windows_startup() is True
    assert (
        fake_winreg.get_value(RUN_KEY, RUN_VALUE)
        == '"C:\\Python With Spaces\\python.exe" -m accessiweather --startup'
    )


class _EnsureConfigStub(SimpleNamespace):
    """Just enough ConfigManager surface for ensure_startup_registration."""

    def __init__(self, *, startup_enabled: bool, manager) -> None:
        super().__init__()
        self._settings = SimpleNamespace(startup_enabled=startup_enabled)
        self._manager = manager
        self.updated: dict | None = None

    def get_settings(self):
        return self._settings

    def _get_startup_manager(self):
        return self._manager

    def update_settings(self, **kwargs) -> bool:
        self.updated = kwargs
        for key, value in kwargs.items():
            setattr(self._settings, key, value)
        return True


def _ensure(stub) -> bool:
    from accessiweather.config.config_manager import ConfigManager

    return ConfigManager.ensure_startup_registration(stub)


def test_ensure_repairs_stale_registration_after_update(manager, fake_winreg):
    fake_winreg.set_value(
        RUN_KEY, RUN_VALUE, '"C:\\Old Install\\AccessiWeather.exe" --startup', FakeWinreg.REG_SZ
    )
    stub = _EnsureConfigStub(startup_enabled=True, manager=manager)

    assert _ensure(stub) is True

    assert fake_winreg.get_value(RUN_KEY, RUN_VALUE) == EXPECTED_COMMAND
    assert stub.updated is None


def test_ensure_respects_task_manager_disable(manager, fake_winreg):
    fake_winreg.set_value(RUN_KEY, RUN_VALUE, EXPECTED_COMMAND, FakeWinreg.REG_SZ)
    fake_winreg.set_value(APPROVED_RUN_KEY, RUN_VALUE, APPROVED_DISABLED, FakeWinreg.REG_BINARY)
    stub = _EnsureConfigStub(startup_enabled=True, manager=manager)

    assert _ensure(stub) is True

    assert stub.updated == {"startup_enabled": False}
    # The registration itself is left untouched for the user to re-enable.
    assert fake_winreg.get_value(RUN_KEY, RUN_VALUE) == EXPECTED_COMMAND


def test_ensure_recreates_missing_registration_when_setting_enabled(manager, fake_winreg):
    stub = _EnsureConfigStub(startup_enabled=True, manager=manager)

    assert _ensure(stub) is True

    assert fake_winreg.get_value(RUN_KEY, RUN_VALUE) == EXPECTED_COMMAND


def test_ensure_adopts_existing_registration_when_setting_disabled(manager, fake_winreg):
    fake_winreg.set_value(RUN_KEY, RUN_VALUE, EXPECTED_COMMAND, FakeWinreg.REG_SZ)
    stub = _EnsureConfigStub(startup_enabled=False, manager=manager)

    assert _ensure(stub) is True

    assert stub.updated == {"startup_enabled": True}


def test_ensure_is_noop_when_setting_and_os_both_disabled(manager, fake_winreg):
    stub = _EnsureConfigStub(startup_enabled=False, manager=manager)

    assert _ensure(stub) is True

    assert stub.updated is None
    assert not fake_winreg.has_value(RUN_KEY, RUN_VALUE)


def test_legacy_migration_end_to_end_after_update(manager, fake_winreg, tmp_path):
    """
    Upgrade scenario: old release registered via Startup-folder shortcut.

    The setting says enabled and the shortcut is stale. The launch-time
    repair must migrate to the Run key and remove the shortcut.
    """
    startup_dir = _startup_dir(tmp_path)
    startup_dir.mkdir(parents=True)
    legacy = startup_dir / "AccessiWeather.lnk"
    legacy.touch()
    stub = _EnsureConfigStub(startup_enabled=True, manager=manager)

    assert _ensure(stub) is True

    assert not legacy.exists()
    assert fake_winreg.get_value(RUN_KEY, RUN_VALUE) == EXPECTED_COMMAND
    assert manager.is_startup_registration_current() is True
