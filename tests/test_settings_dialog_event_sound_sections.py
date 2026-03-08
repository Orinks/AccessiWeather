from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_settings_dialog_class():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "accessiweather"
        / "ui"
        / "dialogs"
        / "settings_dialog.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_settings_dialog_event_sections_module", module_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SettingsDialogSimple


SettingsDialogSimple = _load_settings_dialog_class()


def test_event_sound_sections_cover_each_mutable_event_once():
    from accessiweather.notifications.sound_player import USER_MUTABLE_SOUND_EVENTS

    sections = SettingsDialogSimple._get_event_sound_sections()

    assert [title for title, _description, _keys in sections] == [
        "Weather updates",
        "Weather events",
        "App lifecycle",
    ]

    grouped_keys = [key for _title, _description, keys in sections for key in keys]
    expected_keys = [event_key for event_key, _label in USER_MUTABLE_SOUND_EVENTS]

    assert grouped_keys == expected_keys
    assert len(grouped_keys) == len(set(grouped_keys))
