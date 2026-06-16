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


def _make_dialog(
    *,
    checkbox_enabled: bool,
    configured_enabled: bool,
    actual_enabled: bool,
) -> SettingsDialogSimple:
    dialog = SettingsDialogSimple.__new__(SettingsDialogSimple)
    dialog._tab_objects = [_StartupTab(checkbox_enabled)]
    dialog._loaded_startup_enabled = configured_enabled
    dialog.config_manager = MagicMock()
    dialog.config_manager.get_settings.return_value = SimpleNamespace(
        startup_enabled=configured_enabled
    )
    dialog.config_manager.update_settings.return_value = True
    dialog.config_manager.is_startup_enabled.return_value = actual_enabled
    dialog.config_manager.enable_startup.return_value = (True, "Startup enabled successfully")
    dialog.config_manager.disable_startup.return_value = (True, "Startup disabled successfully")
    return dialog


def test_load_settings_populates_startup_checkbox_from_actual_os_state():
    dialog = _make_dialog(
        checkbox_enabled=True,
        configured_enabled=True,
        actual_enabled=False,
    )

    dialog._load_settings()

    dialog.config_manager.get_settings.assert_called_once()
    dialog.config_manager.is_startup_enabled.assert_called_once()
    assert dialog._tab_objects[0].loaded_settings.startup_enabled is False
    assert dialog._loaded_startup_enabled is False


def test_load_settings_keeps_startup_checkbox_enabled_when_os_entry_is_current():
    dialog = _make_dialog(
        checkbox_enabled=False,
        configured_enabled=True,
        actual_enabled=True,
    )

    dialog._load_settings()

    assert dialog._tab_objects[0].loaded_settings.startup_enabled is True
    assert dialog._loaded_startup_enabled is True


def test_save_settings_repairs_missing_os_startup_when_checkbox_is_enabled():
    dialog = _make_dialog(
        checkbox_enabled=True,
        configured_enabled=True,
        actual_enabled=False,
    )

    assert dialog._save_settings() is True

    dialog.config_manager.is_startup_enabled.assert_called_once()
    dialog.config_manager.enable_startup.assert_called_once()
    dialog.config_manager.disable_startup.assert_not_called()
    dialog.config_manager.update_settings.assert_called_once_with(startup_enabled=True)


def test_save_settings_does_not_reapply_when_os_state_matches_checkbox():
    dialog = _make_dialog(
        checkbox_enabled=True,
        configured_enabled=True,
        actual_enabled=True,
    )

    assert dialog._save_settings() is True

    dialog.config_manager.is_startup_enabled.assert_called_once()
    dialog.config_manager.enable_startup.assert_not_called()
    dialog.config_manager.disable_startup.assert_not_called()
    dialog.config_manager.update_settings.assert_called_once_with(startup_enabled=True)


def test_save_settings_disables_os_startup_before_persisting_setting():
    dialog = _make_dialog(
        checkbox_enabled=False,
        configured_enabled=False,
        actual_enabled=True,
    )

    assert dialog._save_settings() is True

    dialog.config_manager.is_startup_enabled.assert_called_once()
    dialog.config_manager.disable_startup.assert_called_once()
    dialog.config_manager.enable_startup.assert_not_called()
    dialog.config_manager.update_settings.assert_called_once_with(startup_enabled=False)


def test_save_settings_stops_when_os_startup_enable_fails():
    dialog = _make_dialog(
        checkbox_enabled=True,
        configured_enabled=False,
        actual_enabled=False,
    )
    dialog.config_manager.enable_startup.return_value = (False, "Failed to enable startup")

    with patch("accessiweather.ui.dialogs.settings_dialog_core.wx.MessageBox") as message_box:
        assert dialog._save_settings() is False

    dialog.config_manager.update_settings.assert_not_called()
    message_box.assert_called_once()
