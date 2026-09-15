from __future__ import annotations

from types import SimpleNamespace

import pytest

from accessiweather.shortcut_preferences import (
    RESERVED_SHORTCUTS,
    WINDOW_TRAY_SHORTCUT_DEFAULTS,
    WINDOW_TRAY_SHORTCUTS,
    migrate_legacy_window_tray_shortcuts,
    normalize_shortcut_text,
    parse_shortcut_text,
)


class _FakeWx:
    ACCEL_NORMAL = 0
    ACCEL_CTRL = 1
    ACCEL_ALT = 2
    ACCEL_SHIFT = 4
    MOD_CONTROL = 8
    MOD_ALT = 16
    MOD_SHIFT = 32
    WXK_TAB = 9


def test_normalize_shortcut_text_canonicalizes_aliases():
    assert normalize_shortcut_text(" control + shift + w ") == "Ctrl+Shift+W"


def test_normalize_shortcut_text_allows_blank_to_disable():
    assert normalize_shortcut_text("   ") == ""


def test_normalize_shortcut_text_rejects_unknown_key():
    with pytest.raises(ValueError, match="Shortcut keys must be"):
        normalize_shortcut_text("Ctrl+Weather")


def test_parse_shortcut_text_produces_accelerator_and_hotkey_values():
    binding = parse_shortcut_text("Ctrl+Alt+Tab")

    assert binding is not None
    assert binding.accelerator_flags(_FakeWx) == _FakeWx.ACCEL_CTRL | _FakeWx.ACCEL_ALT
    assert binding.hotkey_modifiers(_FakeWx) == _FakeWx.MOD_CONTROL | _FakeWx.MOD_ALT
    assert binding.key_code(_FakeWx) == _FakeWx.WXK_TAB


@pytest.mark.parametrize(
    "value", ["A", "Space", "Tab", "Shift+A", "Alt+F4", "F2", "Ctrl+Alt+N", "Ctrl+R"]
)
def test_tray_shortcuts_reject_typing_and_reserved_actions(value):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from accessiweather.ui.dialogs.settings_dialog_handlers import SettingsDialogHandlersMixin

    controls = {}
    for name in (
        "shortcut_show_main_window",
        "shortcut_hide_main_window",
        "shortcut_read_tray_info",
    ):
        controls[name] = MagicMock()
        controls[name].GetValue.return_value = value if name == "shortcut_show_main_window" else ""
    dialog = SimpleNamespace(_controls=controls)
    assert SettingsDialogHandlersMixin._validate_window_tray_shortcuts(dialog) is not None


def test_window_tray_defaults_never_use_plain_ctrl_shift():
    assert WINDOW_TRAY_SHORTCUT_DEFAULTS == {
        "shortcut_show_main_window": "Ctrl+Alt+Shift+W",
        "shortcut_hide_main_window": "Ctrl+Alt+Shift+M",
        "shortcut_read_tray_info": "Ctrl+Alt+Shift+I",
    }
    for preference in WINDOW_TRAY_SHORTCUTS:
        modifiers = preference.default.split("+")[:-1]
        assert modifiers != ["Ctrl", "Shift"], preference.default


def test_reserved_shortcuts_track_the_new_in_app_bindings():
    assert RESERVED_SHORTCUTS["F2"] == "edit a location"
    assert RESERVED_SHORTCUTS["Ctrl+Alt+N"] == "open NOAA Weather Radio"
    assert not any(combo.startswith("Ctrl+Shift+") for combo in RESERVED_SHORTCUTS)


def test_migrate_legacy_window_tray_shortcuts_moves_old_defaults_forward():
    settings = SimpleNamespace(
        shortcut_show_main_window="Ctrl+Shift+W",
        shortcut_hide_main_window="Ctrl+Shift+M",
        shortcut_read_tray_info="Ctrl+Shift+I",
        noaa_radio_hotkey="Ctrl+Alt+Shift+R",
    )

    changed = migrate_legacy_window_tray_shortcuts(settings)

    assert set(changed) == set(WINDOW_TRAY_SHORTCUT_DEFAULTS)
    assert settings.shortcut_show_main_window == "Ctrl+Alt+Shift+W"
    assert settings.shortcut_hide_main_window == "Ctrl+Alt+Shift+M"
    assert settings.shortcut_read_tray_info == "Ctrl+Alt+Shift+I"


def test_migrate_legacy_window_tray_shortcuts_keeps_custom_and_blank_values():
    settings = SimpleNamespace(
        shortcut_show_main_window="Ctrl+Alt+Y",
        shortcut_hide_main_window="",
        shortcut_read_tray_info="Ctrl+Shift+I",
        noaa_radio_hotkey="",
    )

    changed = migrate_legacy_window_tray_shortcuts(settings)

    assert changed == ["shortcut_read_tray_info"]
    assert settings.shortcut_show_main_window == "Ctrl+Alt+Y"
    assert settings.shortcut_hide_main_window == ""
    assert settings.shortcut_read_tray_info == "Ctrl+Alt+Shift+I"


def test_migrate_legacy_window_tray_shortcuts_blanks_a_combo_already_in_use():
    settings = SimpleNamespace(
        shortcut_show_main_window="Ctrl+Shift+W",
        shortcut_hide_main_window="Ctrl+Alt+Shift+W",
        shortcut_read_tray_info="Ctrl+Shift+I",
        noaa_radio_hotkey="Ctrl+Alt+Shift+I",
    )

    changed = migrate_legacy_window_tray_shortcuts(settings)

    assert set(changed) == {"shortcut_show_main_window", "shortcut_read_tray_info"}
    assert settings.shortcut_show_main_window == ""
    assert settings.shortcut_hide_main_window == "Ctrl+Alt+Shift+W"
    assert settings.shortcut_read_tray_info == ""
