"""
Ensure the Advanced tab 'startup' checkbox actually toggles the OS startup entry.

Bug: toggling "Launch automatically at startup" only wrote startup_enabled to
JSON — the Windows Startup folder shortcut / macOS LaunchAgent / Linux .desktop
was never created or removed. These tests pin the fix: _save_settings must
delegate to config_manager.apply_startup_setting() so the OS entry is
reconciled whenever startup_enabled is in the saved settings.
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


def _make_dialog(*, startup_checkbox: bool) -> SettingsDialogSimple:
    dialog = SettingsDialogSimple.__new__(SettingsDialogSimple)
    dialog._controls = _Controls()
    dialog.config_manager = MagicMock()
    dialog.config_manager.update_settings.return_value = True
    dialog.config_manager.apply_startup_setting.return_value = True

    advanced = AdvancedTab(dialog)
    dialog._tab_objects = [advanced]

    dialog._controls["startup"].SetValue(startup_checkbox)

    return dialog


def test_save_delegates_startup_toggle_to_config_manager_when_checked():
    dialog = _make_dialog(startup_checkbox=True)

    assert dialog._save_settings() is True

    dialog.config_manager.apply_startup_setting.assert_called_once_with(desired=True)


def test_save_delegates_startup_toggle_to_config_manager_when_unchecked():
    dialog = _make_dialog(startup_checkbox=False)

    assert dialog._save_settings() is True

    dialog.config_manager.apply_startup_setting.assert_called_once_with(desired=False)


def test_save_still_succeeds_when_apply_startup_setting_fails():
    """
    A failing OS toggle is logged but does not fail _save_settings.

    Other settings still persisted via update_settings; we don't want a
    startup-folder permission error to lose the user's other edits.
    """
    dialog = _make_dialog(startup_checkbox=True)
    dialog.config_manager.apply_startup_setting.return_value = False

    assert dialog._save_settings() is True
    dialog.config_manager.apply_startup_setting.assert_called_once_with(desired=True)
