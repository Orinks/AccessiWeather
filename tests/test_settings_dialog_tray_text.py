from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from accessiweather.ui.dialogs.settings_dialog import SettingsDialogSimple
from accessiweather.ui.dialogs.settings_tabs.display import DisplayTab
from accessiweather.ui.dialogs.settings_tabs.general import GeneralTab


class _DummyControl:
    def __init__(self) -> None:
        self._selection = 0
        self._value = False
        self.enabled = True
        self._parent = _DummyParent()

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

    def Append(self, _value: str) -> None:
        return None

    def GetParent(self):
        return self._parent

    def __getattr__(self, _name: str):
        return lambda *args, **kwargs: None


class _Controls(dict):
    def __missing__(self, key: str) -> _DummyControl:
        value = _DummyControl()
        self[key] = value
        return value


class _DummySizer:
    def ShowItems(self, _value: bool) -> None:
        return None


class _DummyParent:
    def Layout(self) -> None:
        return None

    def FitInside(self) -> None:
        return None


def _make_dialog_for_settings(settings: SimpleNamespace) -> SettingsDialogSimple:
    dialog = SettingsDialogSimple.__new__(SettingsDialogSimple)
    dialog._controls = _Controls()
    dialog._sound_pack_ids = ["default"]
    dialog._selected_specific_model = None
    dialog._vc_config_sizer = _DummySizer()
    dialog._pw_config_sizer = _DummySizer()
    dialog._source_settings_states = SettingsDialogSimple._build_default_source_settings_states()
    dialog._auto_sources_sizer = _DummySizer()
    dialog.config_manager = MagicMock()
    dialog.config_manager.get_settings.return_value = settings

    # Wire up tab objects so _load_settings/_save_settings delegate correctly
    general_tab = GeneralTab(dialog)
    display_tab = DisplayTab(dialog)
    dialog._display_tab = display_tab
    dialog._tab_objects = [general_tab, display_tab]

    return dialog


def test_load_settings_populates_tray_text_summary_and_disables_edit_actions_when_off():
    settings = SimpleNamespace(
        taskbar_icon_text_enabled=False,
        taskbar_icon_dynamic_enabled=True,
        taskbar_icon_text_format="{temp}",
    )
    dialog = _make_dialog_for_settings(settings)

    dialog._load_settings()

    assert dialog._controls["taskbar_icon_text_enabled"].GetValue() is False
    assert dialog._controls["taskbar_icon_dynamic_enabled"].GetValue() is True
    assert dialog._controls["taskbar_icon_text_format"].GetValue() == "{temp}"
    assert dialog._controls["taskbar_icon_dynamic_enabled"].enabled is False
    assert dialog._controls["taskbar_icon_text_format"].enabled is True
    assert dialog._controls["taskbar_icon_text_format_dialog"].enabled is False


def test_load_settings_keeps_tray_text_summary_readable_when_tray_text_on():
    settings = SimpleNamespace(
        taskbar_icon_text_enabled=True,
        taskbar_icon_dynamic_enabled=False,
        taskbar_icon_text_format="{temp} {condition}",
    )
    dialog = _make_dialog_for_settings(settings)

    dialog._load_settings()

    assert dialog._controls["taskbar_icon_dynamic_enabled"].enabled is True
    assert dialog._controls["taskbar_icon_text_format"].enabled is True
    assert dialog._controls["taskbar_icon_text_format_dialog"].enabled is True


def test_save_settings_persists_tray_text_fields():
    dialog = _make_dialog_for_settings(SimpleNamespace())
    dialog._get_ai_model_preference = lambda: "openrouter/free"
    dialog.config_manager.update_settings.return_value = True

    dialog._controls["taskbar_icon_text_enabled"].SetValue(True)
    dialog._controls["taskbar_icon_dynamic_enabled"].SetValue(False)
    dialog._controls["taskbar_icon_text_format"].SetValue("{temp}")

    success = dialog._save_settings()

    assert success is True
    kwargs = dialog.config_manager.update_settings.call_args.kwargs
    assert kwargs["taskbar_icon_text_enabled"] is True
    assert kwargs["taskbar_icon_dynamic_enabled"] is False
    assert kwargs["taskbar_icon_text_format"] == "{temp}"


def test_get_selected_temperature_unit_uses_current_choice():
    dialog = _make_dialog_for_settings(SimpleNamespace())
    dialog._controls["temp_unit"].SetSelection(2)

    assert dialog._get_selected_temperature_unit() == "c"


def test_get_selected_temperature_unit_returns_auto_for_first_choice():
    dialog = _make_dialog_for_settings(SimpleNamespace())
    dialog._controls["temp_unit"].SetSelection(0)

    assert dialog._get_selected_temperature_unit() == "auto"
