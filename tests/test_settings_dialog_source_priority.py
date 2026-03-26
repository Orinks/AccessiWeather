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
        self._parent = _DummyParent()
        self._label = ""

    def SetSelection(self, value: int) -> None:
        self._selection = value

    def GetSelection(self) -> int:
        return self._selection

    def SetValue(self, value):
        self._value = value

    def GetValue(self):
        return self._value

    def SetLabel(self, label: str) -> None:
        self._label = label

    def GetLabel(self) -> str:
        return self._label

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
    dialog._update_minimize_on_startup_state = lambda _enabled: None
    dialog._vc_config_sizer = _DummySizer()
    dialog._pw_config_sizer = _DummySizer()
    dialog._source_settings_states = SettingsDialogSimple._build_default_source_settings_states()
    dialog.config_manager = MagicMock()
    dialog.config_manager.get_settings.return_value = settings
    return dialog


def test_load_settings_all_sources_enabled_by_default():
    settings = SimpleNamespace(
        source_priority_us=["nws", "openmeteo", "visualcrossing", "pirateweather"],
        source_priority_international=["openmeteo", "pirateweather", "visualcrossing"],
    )
    dialog = _make_dialog_for_settings(settings)

    dialog._load_settings()

    assert dialog._source_settings_states["auto_use_nws"] is True
    assert dialog._source_settings_states["auto_use_openmeteo"] is True
    assert dialog._source_settings_states["auto_use_visualcrossing"] is True
    assert dialog._source_settings_states["auto_use_pirateweather"] is True


def test_load_settings_nws_disabled_when_absent_from_both_lists():
    settings = SimpleNamespace(
        source_priority_us=["openmeteo", "visualcrossing", "pirateweather"],
        source_priority_international=["openmeteo", "pirateweather", "visualcrossing"],
    )
    dialog = _make_dialog_for_settings(settings)

    dialog._load_settings()

    assert dialog._source_settings_states["auto_use_nws"] is False
    assert dialog._source_settings_states["auto_use_openmeteo"] is True


def test_load_settings_pirateweather_disabled_when_absent():
    settings = SimpleNamespace(
        source_priority_us=["nws", "openmeteo", "visualcrossing"],
        source_priority_international=["openmeteo", "visualcrossing"],
    )
    dialog = _make_dialog_for_settings(settings)

    dialog._load_settings()

    assert dialog._source_settings_states["auto_use_pirateweather"] is False
    assert dialog._source_settings_states["auto_use_nws"] is True
    assert dialog._source_settings_states["auto_use_openmeteo"] is True
    assert dialog._source_settings_states["auto_use_visualcrossing"] is True


def test_load_settings_visualcrossing_disabled_when_absent():
    settings = SimpleNamespace(
        source_priority_us=["nws", "openmeteo", "pirateweather"],
        source_priority_international=["openmeteo", "pirateweather"],
    )
    dialog = _make_dialog_for_settings(settings)

    dialog._load_settings()

    assert dialog._source_settings_states["auto_use_visualcrossing"] is False


def test_save_settings_all_enabled_produces_full_lists():
    settings = SimpleNamespace()
    dialog = _make_dialog_for_settings(settings)
    dialog._get_ai_model_preference = lambda: "openrouter/free"
    dialog.config_manager.update_settings.return_value = True
    dialog._source_settings_states["auto_use_nws"] = True
    dialog._source_settings_states["auto_use_openmeteo"] = True
    dialog._source_settings_states["auto_use_visualcrossing"] = True
    dialog._source_settings_states["auto_use_pirateweather"] = True

    success = dialog._save_settings()

    assert success is True
    kwargs = dialog.config_manager.update_settings.call_args.kwargs
    assert kwargs["source_priority_us"] == ["nws", "openmeteo", "visualcrossing", "pirateweather"]
    assert kwargs["source_priority_international"] == ["openmeteo", "visualcrossing", "pirateweather"]


def test_save_settings_nws_disabled_excludes_nws_from_us():
    settings = SimpleNamespace()
    dialog = _make_dialog_for_settings(settings)
    dialog._get_ai_model_preference = lambda: "openrouter/free"
    dialog.config_manager.update_settings.return_value = True
    dialog._source_settings_states["auto_use_nws"] = False
    dialog._source_settings_states["auto_use_openmeteo"] = True
    dialog._source_settings_states["auto_use_visualcrossing"] = True
    dialog._source_settings_states["auto_use_pirateweather"] = True

    success = dialog._save_settings()

    assert success is True
    kwargs = dialog.config_manager.update_settings.call_args.kwargs
    assert "nws" not in kwargs["source_priority_us"]
    assert kwargs["source_priority_us"] == ["openmeteo", "visualcrossing", "pirateweather"]


def test_save_settings_pirateweather_disabled_excludes_from_both():
    settings = SimpleNamespace()
    dialog = _make_dialog_for_settings(settings)
    dialog._get_ai_model_preference = lambda: "openrouter/free"
    dialog.config_manager.update_settings.return_value = True
    dialog._source_settings_states["auto_use_nws"] = True
    dialog._source_settings_states["auto_use_openmeteo"] = True
    dialog._source_settings_states["auto_use_visualcrossing"] = True
    dialog._source_settings_states["auto_use_pirateweather"] = False

    success = dialog._save_settings()

    assert success is True
    kwargs = dialog.config_manager.update_settings.call_args.kwargs
    assert "pirateweather" not in kwargs["source_priority_us"]
    assert "pirateweather" not in kwargs["source_priority_international"]


def test_save_settings_openmeteo_weather_model_hardcoded_best_match():
    settings = SimpleNamespace()
    dialog = _make_dialog_for_settings(settings)
    dialog._get_ai_model_preference = lambda: "openrouter/free"
    dialog.config_manager.update_settings.return_value = True

    dialog._save_settings()

    kwargs = dialog.config_manager.update_settings.call_args.kwargs
    assert kwargs["openmeteo_weather_model"] == "best_match"
