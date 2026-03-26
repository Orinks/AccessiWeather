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
        self._label = ""
        self._name = ""
        self._parent = _DummyParent()

    def SetSelection(self, value: int) -> None:
        self._selection = value

    def GetSelection(self) -> int:
        return self._selection

    def SetValue(self, value):
        self._value = value

    def GetValue(self):
        return self._value

    def SetLabel(self, value: str) -> None:
        self._label = value

    def GetLabel(self) -> str:
        return self._label

    def SetName(self, _value: str) -> None:
        self._name = _value

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


def _make_dialog(settings: SimpleNamespace) -> SettingsDialogSimple:
    dialog = SettingsDialogSimple.__new__(SettingsDialogSimple)
    dialog._controls = _Controls()
    dialog._controls["event_sounds_summary"] = _DummyControl()
    dialog._controls["configure_event_sounds"] = _DummyControl()
    dialog._sound_pack_ids = ["default"]
    dialog._selected_specific_model = None
    dialog._event_sound_states = dialog._build_default_event_sound_states()
    dialog._source_settings_states = dialog._build_default_source_settings_states()
    dialog._vc_config_sizer = _DummySizer()
    dialog._pw_config_sizer = _DummySizer()
    dialog._auto_sources_sizer = _DummySizer()
    dialog.config_manager = MagicMock()
    dialog.config_manager.get_settings.return_value = settings
    dialog.config_manager.update_settings.return_value = True
    dialog._get_ai_model_preference = lambda: "openrouter/free"
    return dialog


def test_load_settings_updates_event_sound_state_and_summary():
    dialog = _make_dialog(
        SimpleNamespace(
            sound_enabled=True,
            sound_pack="default",
            muted_sound_events=["data_updated"],
        )
    )

    dialog._load_settings()

    assert dialog._event_sound_states["data_updated"] is False
    assert dialog._event_sound_states["fetch_error"] is True
    total_events = len(dialog._build_default_event_sound_states())
    assert (
        dialog._controls["event_sounds_summary"].GetLabel()
        == f"{total_events - 1} of {total_events} sound events are enabled."
    )


def test_save_settings_collects_unchecked_audio_events():
    dialog = _make_dialog(SimpleNamespace())
    dialog._controls["sound_enabled"].SetValue(True)
    dialog._controls["sound_pack"].SetSelection(0)
    dialog._event_sound_states["data_updated"] = False
    dialog._event_sound_states["fetch_error"] = True

    success = dialog._save_settings()

    assert success is True
    kwargs = dialog.config_manager.update_settings.call_args.kwargs
    assert kwargs["muted_sound_events"] == ["data_updated"]


def test_configure_event_sounds_applies_modal_result_and_refreshes_summary():
    dialog = _make_dialog(SimpleNamespace())
    dialog._run_event_sounds_dialog = MagicMock(
        return_value={
            "data_updated": False,
            "fetch_error": True,
            "discussion_update": True,
            "severe_risk": False,
            "startup": True,
            "exit": True,
        }
    )

    dialog._on_configure_event_sounds(event=None)

    assert dialog._event_sound_states["data_updated"] is False
    assert dialog._event_sound_states["severe_risk"] is False
    total_events = len(dialog._build_default_event_sound_states())
    assert (
        dialog._controls["event_sounds_summary"].GetLabel()
        == f"{total_events - 2} of {total_events} sound events are enabled."
    )


def test_configure_event_sounds_cancel_keeps_existing_state():
    dialog = _make_dialog(SimpleNamespace())
    dialog._event_sound_states["startup"] = False
    dialog._run_event_sounds_dialog = MagicMock(return_value=None)

    dialog._on_configure_event_sounds(event=None)

    assert dialog._event_sound_states["startup"] is False
