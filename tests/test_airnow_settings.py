from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from accessiweather.config import ConfigManager
from accessiweather.config.secure_storage import SecureStorage
from accessiweather.models import AppConfig, AppSettings
from accessiweather.ui.dialogs import settings_dialog as settings_module
from accessiweather.ui.dialogs.settings_tabs.data_sources import DataSourcesTab


def test_airnow_key_is_loaded_but_not_serialized():
    settings = AppSettings.from_dict({"airnow_api_key": "FAKE_AIRNOW_KEY_TEST"})

    assert settings.airnow_api_key == "FAKE_AIRNOW_KEY_TEST"
    assert "airnow_api_key" not in settings.to_dict()


def test_config_manager_loads_airnow_key_from_secure_storage(tmp_path, monkeypatch):
    manager = ConfigManager(SimpleNamespace(_portable_mode=False), config_dir=tmp_path)
    manager._config = AppConfig.default()
    monkeypatch.setattr(
        SecureStorage,
        "get_password",
        staticmethod(
            lambda key_name: "FAKE_AIRNOW_KEY_TEST" if key_name == "airnow_api_key" else None
        ),
    )

    manager._load_secure_keys()

    assert str(manager._config.settings.airnow_api_key) == "FAKE_AIRNOW_KEY_TEST"


def test_airnow_key_is_supplemental_data_source_setting():
    class ValueControl:
        def __init__(self, value="", selection=0):
            self.value = value
            self.selection = selection

        def GetSelection(self):
            return self.selection

        def GetValue(self):
            return self.value

    dialog = SimpleNamespace(
        _controls={
            "data_source": ValueControl(selection=0),
            "pw_key": ValueControl(),
            "airnow_key": ValueControl("FAKE_AIRNOW_KEY_TEST"),
        },
        _source_settings_states=DataSourcesTab._build_default_source_settings_states(),
    )

    saved = DataSourcesTab(dialog).save()

    assert saved["data_source"] == "auto"
    assert saved["airnow_api_key"] == "FAKE_AIRNOW_KEY_TEST"


def test_airnow_blank_key_guard_preserves_unloaded_keyring_value():
    dialog = settings_module.SettingsDialogSimple.__new__(settings_module.SettingsDialogSimple)
    dialog._tab_objects = [SimpleNamespace(save=lambda: {"airnow_api_key": ""})]
    dialog._original_airnow_key = "FAKE_EXISTING_AIRNOW_KEY"
    dialog._airnow_key_cleared = False
    dialog.config_manager = SimpleNamespace(update_settings=MagicMock(return_value=True))

    assert dialog._save_settings() is True
    dialog.config_manager.update_settings.assert_called_once_with()


def test_airnow_blank_key_guard_allows_explicit_clear():
    dialog = settings_module.SettingsDialogSimple.__new__(settings_module.SettingsDialogSimple)
    dialog._tab_objects = [SimpleNamespace(save=lambda: {"airnow_api_key": ""})]
    dialog._original_airnow_key = "FAKE_EXISTING_AIRNOW_KEY"
    dialog._airnow_key_cleared = True
    dialog.config_manager = SimpleNamespace(update_settings=MagicMock(return_value=True))

    assert dialog._save_settings() is True
    dialog.config_manager.update_settings.assert_called_once_with(airnow_api_key="")


def test_get_airnow_key_button_opens_account_request_page(monkeypatch):
    opened = MagicMock()
    monkeypatch.setattr(settings_module.webbrowser, "open", opened)
    dialog = settings_module.SettingsDialogSimple.__new__(settings_module.SettingsDialogSimple)

    dialog._on_get_airnow_api_key(None)

    opened.assert_called_once_with("https://docs.airnowapi.org/account/request/")


def _make_validation_dialog(monkeypatch, key: str, messages: list):
    from accessiweather.ui.dialogs import settings_dialog_handlers as handlers_module

    monkeypatch.setattr(
        handlers_module.wx,
        "MessageBox",
        lambda *args, **kwargs: messages.append(args),
    )
    monkeypatch.setattr(handlers_module.wx, "BeginBusyCursor", lambda: None, raising=False)
    monkeypatch.setattr(handlers_module.wx, "EndBusyCursor", lambda: None, raising=False)

    dialog = settings_module.SettingsDialogSimple.__new__(settings_module.SettingsDialogSimple)
    dialog._controls = {"airnow_key": SimpleNamespace(GetValue=lambda: key)}
    return dialog


def test_validate_airnow_key_button_reports_valid_key(monkeypatch):
    from accessiweather.services.airnow_client import AirNowClient

    async def fake_validate(self):
        return True, None

    monkeypatch.setattr(AirNowClient, "validate_api_key", fake_validate)
    messages: list = []
    dialog = _make_validation_dialog(monkeypatch, "FAKE_AIRNOW_KEY_TEST", messages)

    dialog._on_validate_airnow_api_key(None)

    assert messages and messages[0][1] == "Validation Successful"


def test_validate_airnow_key_button_reports_invalid_key(monkeypatch):
    from accessiweather.services.airnow_client import AirNowClient

    async def fake_validate(self):
        return False, "Invalid API key"

    monkeypatch.setattr(AirNowClient, "validate_api_key", fake_validate)
    messages: list = []
    dialog = _make_validation_dialog(monkeypatch, "FAKE_AIRNOW_KEY_TEST", messages)

    dialog._on_validate_airnow_api_key(None)

    assert messages and messages[0][1] == "Validation Failed"
    assert "Invalid API key" in messages[0][0]


def test_validate_airnow_key_button_requires_key_before_request(monkeypatch):
    messages: list = []
    dialog = _make_validation_dialog(monkeypatch, "", messages)

    dialog._on_validate_airnow_api_key(None)

    assert messages and messages[0][0] == "Please enter an API key first."
