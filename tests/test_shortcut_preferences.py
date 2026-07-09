from __future__ import annotations

import pytest

from accessiweather.shortcut_preferences import normalize_shortcut_text, parse_shortcut_text


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
