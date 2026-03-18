from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _load_settings_dialog_class():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "accessiweather"
        / "ui"
        / "dialogs"
        / "settings_dialog.py"
    )
    spec = importlib.util.spec_from_file_location("test_settings_dialog_module", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SettingsDialogSimple


SettingsDialogSimple = _load_settings_dialog_class()


class _DummyControl:
    def __init__(self) -> None:
        self._selection = 0
        self._value = False

    def SetSelection(self, value: int) -> None:
        self._selection = value

    def GetSelection(self) -> int:
        return self._selection

    def SetValue(self, value):
        self._value = value

    def GetValue(self):
        return self._value

    def Append(self, _value: str) -> None:
        return None

    def __getattr__(self, _name: str):
        return lambda *args, **kwargs: None


class _Controls(dict):
    def __missing__(self, key: str) -> _DummyControl:
        value = _DummyControl()
        self[key] = value
        return value


def _make_dialog_for_settings(settings: SimpleNamespace) -> SettingsDialogSimple:
    dialog = SettingsDialogSimple.__new__(SettingsDialogSimple)
    dialog._controls = _Controls()
    dialog._sound_pack_ids = ["default"]
    dialog._selected_specific_model = None
    dialog._update_minimize_on_startup_state = lambda _enabled: None
    dialog.config_manager = MagicMock()
    dialog.config_manager.get_settings.return_value = settings
    return dialog


def test_load_settings_maps_us_source_priority_to_index_1():
    # 4-element list (current format)
    settings = SimpleNamespace(
        source_priority_us=["nws", "visualcrossing", "openmeteo", "pirateweather"],
        source_priority_international=["openmeteo", "pirateweather", "visualcrossing"],
    )
    dialog = _make_dialog_for_settings(settings)

    dialog._load_settings()

    assert dialog._controls["us_priority"].GetSelection() == 1


def test_load_settings_maps_us_source_priority_legacy_3_element_to_index_1():
    # 3-element list (legacy config without pirateweather) - should still map correctly
    settings = SimpleNamespace(
        source_priority_us=["nws", "visualcrossing", "openmeteo"],
        source_priority_international=["openmeteo", "visualcrossing"],
    )
    dialog = _make_dialog_for_settings(settings)

    dialog._load_settings()

    assert dialog._controls["us_priority"].GetSelection() == 1


def test_load_settings_maps_international_source_priority_to_index_1():
    # 3-element list (current format)
    settings = SimpleNamespace(
        source_priority_us=["nws", "openmeteo", "visualcrossing", "pirateweather"],
        source_priority_international=["visualcrossing", "openmeteo", "pirateweather"],
    )
    dialog = _make_dialog_for_settings(settings)

    dialog._load_settings()

    assert dialog._controls["intl_priority"].GetSelection() == 1


def test_load_settings_maps_international_source_priority_legacy_2_element_to_index_1():
    # 2-element list (legacy config without pirateweather) - should still map correctly
    settings = SimpleNamespace(
        source_priority_us=["nws", "openmeteo", "visualcrossing"],
        source_priority_international=["visualcrossing", "openmeteo"],
    )
    dialog = _make_dialog_for_settings(settings)

    dialog._load_settings()

    assert dialog._controls["intl_priority"].GetSelection() == 1


def test_save_settings_persists_selected_us_source_priority_index_2():
    settings = SimpleNamespace()
    dialog = _make_dialog_for_settings(settings)
    dialog._get_ai_model_preference = lambda: "openrouter/free"
    dialog.config_manager.update_settings.return_value = True
    dialog._controls["us_priority"].SetSelection(2)
    dialog._controls["intl_priority"].SetSelection(0)

    success = dialog._save_settings()

    assert success is True
    kwargs = dialog.config_manager.update_settings.call_args.kwargs
    assert kwargs["source_priority_us"] == ["openmeteo", "nws", "visualcrossing", "pirateweather"]
