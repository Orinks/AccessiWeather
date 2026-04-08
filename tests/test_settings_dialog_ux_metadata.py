from __future__ import annotations

from unittest.mock import MagicMock

import accessiweather.ui.dialogs.settings_dialog as settings_module
from accessiweather.ui.dialogs.settings_dialog import SettingsDialogSimple
from accessiweather.ui.dialogs.settings_tabs.audio import AudioTab
from accessiweather.ui.dialogs.settings_tabs.data_sources import DataSourcesTab


def test_dialog_tab_definitions_follow_user_focused_order_and_labels():
    assert SettingsDialogSimple.get_tab_definitions() == [
        ("general", "General"),
        ("display", "Display"),
        ("notifications", "Alerts"),
        ("audio", "Audio"),
        ("data_sources", "Data Sources"),
        ("ai", "AI"),
        ("updates", "Updates"),
        ("advanced", "Advanced"),
    ]


def test_audio_event_sound_summary_mentions_sound_choices_clearly():
    enabled = AudioTab._build_default_event_sound_states()
    total = len(enabled)
    assert AudioTab.build_event_sound_summary_text(enabled) == (
        f"Sounds will play for all {total} selectable event types."
    )

    some_disabled = dict(enabled)
    some_disabled["data_updated"] = False
    some_disabled["fetch_error"] = False
    assert AudioTab.build_event_sound_summary_text(some_disabled) == (
        f"Sounds will play for {total - 2} of {total} selectable event types."
    )

    all_disabled = dict.fromkeys(enabled, False)
    assert (
        AudioTab.build_event_sound_summary_text(all_disabled)
        == "Sounds are turned off for every selectable event type."
    )


def test_source_settings_summary_uses_plain_language():
    state = {
        "auto_use_nws": True,
        "auto_use_openmeteo": True,
        "auto_use_visualcrossing": False,
        "auto_use_pirateweather": True,
        "station_selection_strategy": 2,
    }

    assert DataSourcesTab.build_source_settings_summary_text(state) == (
        "Automatic mode uses: NWS, Open-Meteo, Pirate Weather. "
        "NWS station strategy: Major airport preferred."
    )


def test_create_section_does_not_insert_helper_text_before_controls(monkeypatch):
    fake_section = MagicMock()
    monkeypatch.setattr(
        settings_module.wx,
        "StaticBoxSizer",
        MagicMock(return_value=fake_section),
        raising=False,
    )
    monkeypatch.setattr(settings_module.wx, "VERTICAL", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "EXPAND", 0, raising=False)
    monkeypatch.setattr(settings_module.wx, "ALL", 0, raising=False)

    dialog = SettingsDialogSimple.__new__(SettingsDialogSimple)
    dialog.add_help_text = MagicMock()
    parent_sizer = MagicMock()

    section = dialog.create_section(
        parent=MagicMock(),
        parent_sizer=parent_sizer,
        title="Weather refresh",
        description="This should not be injected before the first control.",
    )

    assert section is fake_section
    dialog.add_help_text.assert_not_called()
    parent_sizer.Add.assert_called_once()
