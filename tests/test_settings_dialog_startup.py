from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from accessiweather.ui.dialogs.settings_dialog import SettingsDialogSimple


class _StartupTab:
    def __init__(self, startup_enabled: bool) -> None:
        self.startup_enabled = startup_enabled
        self.loaded_settings = None

    def load(self, settings) -> None:
        self.loaded_settings = settings

    def save(self) -> dict:
        return {"startup_enabled": self.startup_enabled}


def _make_dialog(*, startup_enabled: bool, actual_enabled: bool = False) -> SettingsDialogSimple:
    dialog = SettingsDialogSimple.__new__(SettingsDialogSimple)
    dialog._tab_objects = [_StartupTab(startup_enabled)]
    dialog.config_manager = MagicMock()
    dialog.config_manager.get_settings.return_value = SimpleNamespace(
        startup_enabled=actual_enabled
    )
    dialog.config_manager.update_settings.return_value = True
    dialog.config_manager.is_startup_enabled.return_value = actual_enabled
    dialog.config_manager.enable_startup.return_value = (True, "Startup enabled successfully")
    dialog.config_manager.disable_startup.return_value = (True, "Startup disabled successfully")
    return dialog


def test_load_settings_does_not_sync_startup_state_before_populating_tabs():
    dialog = _make_dialog(startup_enabled=False, actual_enabled=True)

    dialog._load_settings()

    dialog.config_manager.sync_startup_setting.assert_not_called()
    dialog.config_manager.get_settings.assert_called_once()
    assert dialog._tab_objects[0].loaded_settings.startup_enabled is True


def test_save_settings_enables_os_startup_before_persisting_setting():
    dialog = _make_dialog(startup_enabled=True, actual_enabled=False)

    assert dialog._save_settings() is True

    dialog.config_manager.enable_startup.assert_called_once()
    dialog.config_manager.disable_startup.assert_not_called()
    dialog.config_manager.update_settings.assert_called_once_with(startup_enabled=True)


def test_save_settings_disables_os_startup_before_persisting_setting():
    dialog = _make_dialog(startup_enabled=False, actual_enabled=True)

    assert dialog._save_settings() is True

    dialog.config_manager.disable_startup.assert_called_once()
    dialog.config_manager.enable_startup.assert_not_called()
    dialog.config_manager.update_settings.assert_called_once_with(startup_enabled=False)


def test_save_settings_stops_when_os_startup_enable_fails():
    dialog = _make_dialog(startup_enabled=True, actual_enabled=False)
    dialog.config_manager.enable_startup.return_value = (False, "Failed to enable startup")

    with patch("accessiweather.ui.dialogs.settings_dialog_core.wx.MessageBox") as message_box:
        assert dialog._save_settings() is False

    dialog.config_manager.update_settings.assert_not_called()
    message_box.assert_called_once()
