"""
Ensure the Advanced tab 'startup' checkbox actually toggles the OS startup entry.

Bug: toggling "Launch automatically at startup" only wrote startup_enabled to
JSON — the Windows Startup folder shortcut / macOS LaunchAgent / Linux .desktop
was never created or removed. These tests pin the fix: _save_settings must call
config_manager.enable_startup() / disable_startup() when the checkbox state
diverges from the actual OS-level state.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from accessiweather.ui.dialogs.settings_dialog import SettingsDialogSimple
from accessiweather.ui.dialogs.settings_tabs.advanced import AdvancedTab


class _DummyControl:
    def __init__(self) -> None:
        self._selection = 0
        self._value = False
        self.enabled = True

    def SetSelection(self, value: int) -> None:
        self._selection = value

    def GetSelection(self) -> int:
        return self._selection

    def SetValue(self, value):
        self._value = value

    def GetValue(self):
        return self._value

    def Enable(self, value: bool) -> None:
        self.enabled = value

    def __getattr__(self, _name: str):
        return lambda *args, **kwargs: None


class _Controls(dict):
    def __missing__(self, key: str) -> _DummyControl:
        value = _DummyControl()
        self[key] = value
        return value


def _make_dialog(
    *,
    startup_checkbox: bool,
    os_startup_enabled: bool,
) -> SettingsDialogSimple:
    dialog = SettingsDialogSimple.__new__(SettingsDialogSimple)
    dialog._controls = _Controls()
    dialog.config_manager = MagicMock()
    dialog.config_manager.update_settings.return_value = True
    dialog.config_manager.is_startup_enabled.return_value = os_startup_enabled
    dialog.config_manager.enable_startup.return_value = (True, "ok")
    dialog.config_manager.disable_startup.return_value = (True, "ok")

    advanced = AdvancedTab(dialog)
    dialog._tab_objects = [advanced]

    dialog._controls["startup"].SetValue(startup_checkbox)

    return dialog


def test_save_enables_os_startup_when_box_checked_and_os_disabled():
    dialog = _make_dialog(startup_checkbox=True, os_startup_enabled=False)

    assert dialog._save_settings() is True

    dialog.config_manager.enable_startup.assert_called_once()
    dialog.config_manager.disable_startup.assert_not_called()


def test_save_disables_os_startup_when_box_unchecked_and_os_enabled():
    dialog = _make_dialog(startup_checkbox=False, os_startup_enabled=True)

    assert dialog._save_settings() is True

    dialog.config_manager.disable_startup.assert_called_once()
    dialog.config_manager.enable_startup.assert_not_called()


def test_save_noop_when_checkbox_matches_os_state_enabled():
    dialog = _make_dialog(startup_checkbox=True, os_startup_enabled=True)

    assert dialog._save_settings() is True

    dialog.config_manager.enable_startup.assert_not_called()
    dialog.config_manager.disable_startup.assert_not_called()


def test_save_noop_when_checkbox_matches_os_state_disabled():
    dialog = _make_dialog(startup_checkbox=False, os_startup_enabled=False)

    assert dialog._save_settings() is True

    dialog.config_manager.enable_startup.assert_not_called()
    dialog.config_manager.disable_startup.assert_not_called()


def test_save_still_succeeds_when_os_toggle_reports_failure():
    """
    A failed OS toggle is logged but does not cause _save_settings to fail.

    Other settings still persisted correctly via update_settings; we don't want
    a startup-folder permission error to lose the user's other edits.
    """
    dialog = _make_dialog(startup_checkbox=True, os_startup_enabled=False)
    dialog.config_manager.enable_startup.return_value = (False, "permission denied")

    assert dialog._save_settings() is True
    dialog.config_manager.enable_startup.assert_called_once()
