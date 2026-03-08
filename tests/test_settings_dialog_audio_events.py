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
    spec = importlib.util.spec_from_file_location("test_settings_dialog_audio_module", module_path)
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

    def SetName(self, _value: str) -> None:
        return None

    def __getattr__(self, _name: str):
        return lambda *args, **kwargs: None


class _Controls(dict):
    def __missing__(self, key: str) -> _DummyControl:
        value = _DummyControl()
        self[key] = value
        return value


def _make_dialog(settings: SimpleNamespace) -> SettingsDialogSimple:
    dialog = SettingsDialogSimple.__new__(SettingsDialogSimple)
    dialog._controls = _Controls()
    dialog._sound_pack_ids = ["default"]
    dialog._selected_specific_model = None
    dialog.config_manager = MagicMock()
    dialog.config_manager.get_settings.return_value = settings
    dialog.config_manager.update_settings.return_value = True
    dialog._get_ai_model_preference = lambda: "openrouter/free"
    dialog._event_sound_controls = {
        "data_updated": dialog._controls["sound_event_data_updated"],
        "fetch_error": dialog._controls["sound_event_fetch_error"],
    }
    return dialog


def test_load_settings_marks_muted_events_as_unchecked():
    dialog = _make_dialog(
        SimpleNamespace(
            sound_enabled=True,
            sound_pack="default",
            muted_sound_events=["data_updated"],
        )
    )

    dialog._load_settings()

    assert dialog._controls["sound_event_data_updated"].GetValue() is False
    assert dialog._controls["sound_event_fetch_error"].GetValue() is True


def test_save_settings_collects_unchecked_audio_events():
    dialog = _make_dialog(SimpleNamespace())
    dialog._controls["sound_enabled"].SetValue(True)
    dialog._controls["sound_pack"].SetSelection(0)
    dialog._controls["sound_event_data_updated"].SetValue(False)
    dialog._controls["sound_event_fetch_error"].SetValue(True)

    success = dialog._save_settings()

    assert success is True
    kwargs = dialog.config_manager.update_settings.call_args.kwargs
    assert kwargs["muted_sound_events"] == ["data_updated"]
