from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from accessiweather.models.config import AppSettings
from accessiweather.sound_events import (
    LEGACY_SOUND_EVENT_KEYS,
    SOUND_EVENT_SECTIONS,
    USER_MUTABLE_SOUND_EVENT_KEYS,
    normalize_known_muted_sound_events,
)
from accessiweather.ui.dialogs.settings_dialog import SettingsDialogSimple
from accessiweather.ui.dialogs.settings_tabs.audio import AudioTab


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

    def Enable(self, value: bool) -> None:
        self._enabled = value

    def IsEnabled(self) -> bool:
        return self.__dict__.get("_enabled", True)

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
    dialog._controls["sound_enabled"] = _DummyControl()
    dialog._controls["sound_pack"] = _DummyControl()
    dialog._controls["specific_alert_sounds_for_pack"] = _DummyControl()
    dialog._controls["event_sounds_summary"] = _DummyControl()
    dialog._controls["configure_event_sounds"] = _DummyControl()
    dialog._sound_pack_ids = ["default"]
    dialog._selected_specific_model = None
    dialog._event_sound_states = AudioTab._build_default_event_sound_states()
    dialog._hidden_muted_sound_events = []
    dialog._specific_alert_sound_packs = []
    dialog._source_settings_states = SettingsDialogSimple._build_default_source_settings_states()
    dialog._pw_config_sizer = _DummySizer()
    dialog._auto_sources_sizer = _DummySizer()
    dialog.config_manager = MagicMock()
    dialog.config_manager.get_settings.return_value = settings
    dialog.config_manager.update_settings.return_value = True
    dialog._get_ai_model_preference = lambda: "openrouter/free"

    # Wire up tab objects so _load_settings/_save_settings delegate correctly
    audio_tab = AudioTab(dialog)
    audio_tab._pack_uses_specific_alert_sounds_by_default = lambda _pack: False
    dialog._audio_tab = audio_tab
    dialog._tab_objects = [audio_tab]

    return dialog


def test_load_settings_updates_event_sound_state_and_summary():
    dialog = _make_dialog(
        SimpleNamespace(
            sound_enabled=True,
            sound_pack="default",
            muted_sound_events=["data_updated"],
            specific_alert_sound_packs=["default"],
        )
    )

    dialog._load_settings()

    assert dialog._event_sound_states["data_updated"] is False
    assert dialog._event_sound_states["fetch_error"] is True
    assert dialog._controls["specific_alert_sounds_for_pack"].GetValue() is True
    total_events = len(AudioTab._build_default_event_sound_states())
    assert (
        dialog._controls["event_sounds_summary"].GetLabel()
        == f"Sounds will play for {total_events - 1} of {total_events} selectable event types."
    )


def test_save_settings_collects_unchecked_audio_events():
    dialog = _make_dialog(SimpleNamespace())
    dialog._controls["sound_enabled"].SetValue(True)
    dialog._controls["specific_alert_sounds_for_pack"].SetValue(True)
    dialog._controls["sound_pack"].SetSelection(0)
    dialog._event_sound_states["data_updated"] = False
    dialog._event_sound_states["fetch_error"] = True

    success = dialog._save_settings()

    assert success is True
    kwargs = dialog.config_manager.update_settings.call_args.kwargs
    assert kwargs["muted_sound_events"] == ["data_updated"]
    assert kwargs["specific_alert_sound_packs"] == ["default"]


def test_save_settings_preserves_hidden_legacy_muted_audio_events():
    dialog = _make_dialog(
        SimpleNamespace(
            sound_enabled=True,
            sound_pack="default",
            muted_sound_events=["tornado_warning", "data_updated"],
        )
    )
    dialog._controls["sound_enabled"].SetValue(True)
    dialog._controls["sound_pack"].SetSelection(0)

    dialog._load_settings()
    success = dialog._save_settings()

    assert success is True
    kwargs = dialog.config_manager.update_settings.call_args.kwargs
    assert kwargs["muted_sound_events"] == ["tornado_warning", "data_updated"]


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
    total_events = len(AudioTab._build_default_event_sound_states())
    assert (
        dialog._controls["event_sounds_summary"].GetLabel()
        == f"Sounds will play for {total_events - 2} of {total_events} selectable event types."
    )


def test_configure_event_sounds_cancel_keeps_existing_state():
    dialog = _make_dialog(SimpleNamespace())
    dialog._event_sound_states["startup"] = False
    dialog._run_event_sounds_dialog = MagicMock(return_value=None)

    dialog._on_configure_event_sounds(event=None)

    assert dialog._event_sound_states["startup"] is False


def test_weather_refresh_sound_is_muted_by_default():
    settings = AppSettings.from_dict({})

    assert settings.muted_sound_events == ["data_updated"]


def test_specific_alert_sound_packs_default_empty_and_round_trip():
    settings = AppSettings.from_dict({})

    assert settings.specific_alert_sound_packs == []
    payload = settings.to_dict()
    assert payload["specific_alert_sound_packs"] == []

    restored = AppSettings.from_dict(
        {"specific_alert_sound_packs": ["custom", "", "custom", " another "]}
    )
    assert restored.specific_alert_sound_packs == ["custom", "another"]

    migrated = AppSettings.from_dict(
        {"sound_pack": "first_pr_pack", "specific_alert_sounds_enabled": True}
    )
    assert migrated.specific_alert_sound_packs == ["first_pr_pack"]


def test_specific_alert_sounds_are_automatic_for_packs_with_specific_mappings():
    dialog = _make_dialog(
        SimpleNamespace(
            sound_enabled=True,
            sound_pack="default",
            muted_sound_events=[],
            specific_alert_sound_packs=["default"],
        )
    )
    dialog._audio_tab._pack_uses_specific_alert_sounds_by_default = lambda _pack: True

    dialog._load_settings()
    success = dialog._save_settings()

    assert success is True
    assert dialog._controls["specific_alert_sounds_for_pack"].GetValue() is True
    assert dialog._controls["specific_alert_sounds_for_pack"].IsEnabled() is False
    kwargs = dialog.config_manager.update_settings.call_args.kwargs
    assert kwargs["specific_alert_sound_packs"] == []


def test_visible_audio_events_are_core_lifecycle_and_severity_only():
    section_titles = [title for title, _description, _events in SOUND_EVENT_SECTIONS]

    assert section_titles == ["Core notifications", "App lifecycle", "Alert severities"]
    assert {
        "alert",
        "notify",
        "error",
        "success",
        "data_updated",
        "fetch_error",
        "discussion_update",
        "severe_risk",
        "alert_updated",
        "startup",
        "exit",
        "extreme",
        "severe",
        "moderate",
        "minor",
        "unknown",
    } == USER_MUTABLE_SOUND_EVENT_KEYS
    assert "tornado_warning" not in USER_MUTABLE_SOUND_EVENT_KEYS
    assert "warning" not in USER_MUTABLE_SOUND_EVENT_KEYS


def test_legacy_muted_alert_keys_are_preserved_but_hidden_from_ui():
    assert "tornado_warning" in LEGACY_SOUND_EVENT_KEYS
    assert "warning" in LEGACY_SOUND_EVENT_KEYS

    normalized = normalize_known_muted_sound_events(
        ["data_updated", "tornado_warning", "warning", "not_real"]
    )

    assert normalized == ["data_updated", "tornado_warning", "warning"]
