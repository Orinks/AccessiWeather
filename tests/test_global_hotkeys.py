"""Tests for system-wide hotkey parsing and registration."""

from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.global_hotkeys import (
    DEFAULT_NOAA_RADIO_HOTKEY,
    GlobalHotkeyManager,
    HotkeyParseError,
    normalize_hotkey,
    parse_hotkey,
)


class TestParseHotkey:
    def test_parses_modifiers_and_letter(self) -> None:
        flags, keycode = parse_hotkey("Ctrl+Alt+Shift+R")

        assert flags == wx.MOD_CONTROL | wx.MOD_ALT | wx.MOD_SHIFT
        assert keycode == ord("R")

    def test_is_case_and_whitespace_insensitive(self) -> None:
        assert parse_hotkey(" ctrl + alt+shift + r ") == parse_hotkey("Ctrl+Alt+Shift+R")

    def test_accepts_modifier_aliases(self) -> None:
        assert parse_hotkey("Control+Win+K") == (wx.MOD_CONTROL | wx.MOD_WIN, ord("K"))

    def test_parses_function_keys(self) -> None:
        assert parse_hotkey("Ctrl+Shift+F9") == (wx.MOD_CONTROL | wx.MOD_SHIFT, wx.WXK_F9)

    def test_parses_digits(self) -> None:
        assert parse_hotkey("Ctrl+Alt+7") == (wx.MOD_CONTROL | wx.MOD_ALT, ord("7"))

    def test_default_hotkey_parses(self) -> None:
        assert parse_hotkey(DEFAULT_NOAA_RADIO_HOTKEY)

    @pytest.mark.parametrize(
        "combo",
        [
            "",
            "   ",
            "R",  # no modifier: a bare global key would swallow it app-wide
            "Ctrl+",
            "Ctrl+Alt",  # modifiers only, no key
            "Ctrl+Meta+R",  # unknown modifier
            "Ctrl+F99",  # out of range function key
            "Ctrl+Escape",  # unsupported key name
            "Ctrl+RR",
        ],
    )
    def test_rejects_invalid_combos(self, combo: str) -> None:
        with pytest.raises(HotkeyParseError):
            parse_hotkey(combo)

    def test_rejects_non_string(self) -> None:
        with pytest.raises(HotkeyParseError):
            parse_hotkey(None)  # type: ignore[arg-type]


class TestNormalizeHotkey:
    def test_orders_modifiers_canonically(self) -> None:
        assert normalize_hotkey("shift+alt+ctrl+r") == "Ctrl+Alt+Shift+R"

    def test_roundtrips_through_parse(self) -> None:
        canonical = normalize_hotkey("win+ctrl+f4")

        assert canonical == "Ctrl+Win+F4"
        assert parse_hotkey(canonical) == parse_hotkey("win+ctrl+f4")

    def test_raises_for_invalid_combo(self) -> None:
        with pytest.raises(HotkeyParseError):
            normalize_hotkey("nope")


class TestGlobalHotkeyManager:
    def _window(self, *, register_ok: bool = True) -> MagicMock:
        window = MagicMock()
        window.RegisterHotKey.return_value = register_ok
        return window

    def test_registers_hotkey_and_binds_event(self) -> None:
        window = self._window()
        on_trigger = MagicMock()
        manager = GlobalHotkeyManager(window, on_trigger)

        with patch("accessiweather.global_hotkeys.sys.platform", "win32"):
            assert manager.apply("Ctrl+Alt+Shift+R") is True

        window.RegisterHotKey.assert_called_once_with(
            manager.hotkey_id, wx.MOD_CONTROL | wx.MOD_ALT | wx.MOD_SHIFT, ord("R")
        )
        window.Bind.assert_called_once()
        assert manager.registered_combo == "Ctrl+Alt+Shift+R"

    def test_apply_unregisters_previous_combo_first(self) -> None:
        window = self._window()
        manager = GlobalHotkeyManager(window, MagicMock())

        with patch("accessiweather.global_hotkeys.sys.platform", "win32"):
            manager.apply("Ctrl+Alt+Shift+R")
            manager.apply("Ctrl+Alt+Shift+W")

        window.UnregisterHotKey.assert_called_once_with(manager.hotkey_id)
        assert manager.registered_combo == "Ctrl+Alt+Shift+W"

    def test_apply_reports_failure_when_windows_refuses_combo(self) -> None:
        window = self._window(register_ok=False)
        manager = GlobalHotkeyManager(window, MagicMock())

        with patch("accessiweather.global_hotkeys.sys.platform", "win32"):
            assert manager.apply("Ctrl+Alt+Shift+R") is False

        assert manager.registered_combo is None

    def test_apply_reports_failure_for_unparseable_combo(self) -> None:
        window = self._window()
        manager = GlobalHotkeyManager(window, MagicMock())

        with patch("accessiweather.global_hotkeys.sys.platform", "win32"):
            assert manager.apply("Ctrl+Nonsense") is False

        window.RegisterHotKey.assert_not_called()

    def test_empty_combo_disables_without_registering(self) -> None:
        window = self._window()
        manager = GlobalHotkeyManager(window, MagicMock())

        with patch("accessiweather.global_hotkeys.sys.platform", "win32"):
            manager.apply("Ctrl+Alt+Shift+R")
            assert manager.apply("") is True

        window.UnregisterHotKey.assert_called_once_with(manager.hotkey_id)
        assert manager.registered_combo is None

    def test_is_noop_off_windows(self) -> None:
        window = self._window()
        manager = GlobalHotkeyManager(window, MagicMock())

        with patch("accessiweather.global_hotkeys.sys.platform", "linux"):
            assert manager.apply("Ctrl+Alt+Shift+R") is False

        window.RegisterHotKey.assert_not_called()

    def test_survives_wx_raising_on_register(self) -> None:
        window = self._window()
        window.RegisterHotKey.side_effect = RuntimeError("no hotkey support")
        manager = GlobalHotkeyManager(window, MagicMock())

        with patch("accessiweather.global_hotkeys.sys.platform", "win32"):
            assert manager.apply("Ctrl+Alt+Shift+R") is False

    def test_unregister_is_safe_when_nothing_registered(self) -> None:
        window = self._window()
        manager = GlobalHotkeyManager(window, MagicMock())

        manager.unregister()

        window.UnregisterHotKey.assert_not_called()

    def test_bound_handler_invokes_callback(self) -> None:
        window = self._window()
        on_trigger = MagicMock()
        manager = GlobalHotkeyManager(window, on_trigger)

        with patch("accessiweather.global_hotkeys.sys.platform", "win32"):
            manager.apply("Ctrl+Alt+Shift+R")

        handler = window.Bind.call_args[0][1]
        handler(MagicMock())

        on_trigger.assert_called_once_with()

    def test_bound_handler_swallows_callback_errors(self) -> None:
        window = self._window()
        on_trigger = MagicMock(side_effect=RuntimeError("boom"))
        manager = GlobalHotkeyManager(window, on_trigger)

        with patch("accessiweather.global_hotkeys.sys.platform", "win32"):
            manager.apply("Ctrl+Alt+Shift+R")

        handler = window.Bind.call_args[0][1]
        handler(MagicMock())

        on_trigger.assert_called_once_with()
