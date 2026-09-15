"""Saved configs holding the retired Ctrl+Shift shortcut defaults move to the new ones."""

from __future__ import annotations

from accessiweather.models.config_settings import AppSettings


def test_from_dict_migrates_retired_ctrl_shift_defaults():
    settings = AppSettings.from_dict(
        {
            "shortcut_show_main_window": "Ctrl+Shift+W",
            "shortcut_hide_main_window": "Ctrl+Shift+M",
            "shortcut_read_tray_info": "Ctrl+Shift+I",
        }
    )

    assert settings.shortcut_show_main_window == "Ctrl+Alt+Shift+W"
    assert settings.shortcut_hide_main_window == "Ctrl+Alt+Shift+M"
    assert settings.shortcut_read_tray_info == "Ctrl+Alt+Shift+I"


def test_from_dict_uses_new_defaults_when_keys_are_missing():
    settings = AppSettings.from_dict({})

    assert settings.shortcut_show_main_window == "Ctrl+Alt+Shift+W"
    assert settings.shortcut_hide_main_window == "Ctrl+Alt+Shift+M"
    assert settings.shortcut_read_tray_info == "Ctrl+Alt+Shift+I"
    assert settings.noaa_radio_hotkey == "Ctrl+Alt+Shift+R"


def test_from_dict_blanks_a_migrated_shortcut_the_radio_hotkey_already_owns():
    settings = AppSettings.from_dict(
        {
            "shortcut_show_main_window": "Ctrl+Shift+W",
            "noaa_radio_hotkey": "ctrl+alt+shift+w",
        }
    )

    assert settings.noaa_radio_hotkey == "Ctrl+Alt+Shift+W"
    assert settings.shortcut_show_main_window == ""


def test_from_dict_keeps_a_deliberate_custom_shortcut():
    settings = AppSettings.from_dict({"shortcut_show_main_window": "ctrl+alt+y"})

    assert settings.shortcut_show_main_window == "Ctrl+Alt+Y"


def test_migrated_shortcuts_round_trip_through_to_dict():
    settings = AppSettings.from_dict({"shortcut_hide_main_window": "Ctrl+Shift+M"})

    assert AppSettings.from_dict(settings.to_dict()).shortcut_hide_main_window == (
        "Ctrl+Alt+Shift+M"
    )
