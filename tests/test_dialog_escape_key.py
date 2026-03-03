"""Tests for Escape key handling in all dialogs (issue #407)."""

from __future__ import annotations

from unittest.mock import MagicMock

WXK_ESCAPE = 27
ID_CANCEL = 5101


def _make_escape_event() -> MagicMock:
    """Create a mock wx.KeyEvent that returns WXK_ESCAPE."""
    event = MagicMock()
    event.GetKeyCode.return_value = WXK_ESCAPE
    return event


def _make_other_key_event(key_code: int = 65) -> MagicMock:
    """Create a mock wx.KeyEvent for a non-Escape key."""
    event = MagicMock()
    event.GetKeyCode.return_value = key_code
    return event


# ---------------------------------------------------------------------------
# Tests for each dialog's _on_char_hook / _on_key method
# ---------------------------------------------------------------------------


class TestAirQualityDialogEscape:
    """Test Escape key handling in AirQualityDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.air_quality_dialog import AirQualityDialog

        dlg = object.__new__(AirQualityDialog)
        dlg.EndModal = MagicMock()

        dlg._on_char_hook(_make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.air_quality_dialog import AirQualityDialog

        dlg = object.__new__(AirQualityDialog)
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        dlg._on_char_hook(event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestAlertDialogEscape:
    """Test Escape key handling in AlertDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.alert_dialog import AlertDialog

        dlg = object.__new__(AlertDialog)
        dlg.EndModal = MagicMock()

        dlg._on_char_hook(_make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.alert_dialog import AlertDialog

        dlg = object.__new__(AlertDialog)
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        dlg._on_char_hook(event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestAviationDialogEscape:
    """Test Escape key handling in AviationDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.aviation_dialog import AviationDialog

        dlg = object.__new__(AviationDialog)
        dlg.EndModal = MagicMock()

        dlg._on_char_hook(_make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.aviation_dialog import AviationDialog

        dlg = object.__new__(AviationDialog)
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        dlg._on_char_hook(event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestCommunityPacksBrowserDialogEscape:
    """Test Escape key handling in CommunityPacksBrowserDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.community_packs_dialog import CommunityPacksBrowserDialog

        dlg = object.__new__(CommunityPacksBrowserDialog)
        dlg.EndModal = MagicMock()

        dlg._on_char_hook(_make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.community_packs_dialog import CommunityPacksBrowserDialog

        dlg = object.__new__(CommunityPacksBrowserDialog)
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        dlg._on_char_hook(event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestDebugAlertDialogEscape:
    """Test Escape key handling in DebugAlertDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.debug_alert_dialog import DebugAlertDialog

        dlg = object.__new__(DebugAlertDialog)
        dlg.EndModal = MagicMock()

        dlg._on_char_hook(_make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.debug_alert_dialog import DebugAlertDialog

        dlg = object.__new__(DebugAlertDialog)
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        dlg._on_char_hook(event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestDiscussionDialogEscape:
    """Test Escape key handling in DiscussionDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.discussion_dialog import DiscussionDialog

        dlg = object.__new__(DiscussionDialog)
        dlg.EndModal = MagicMock()

        dlg._on_char_hook(_make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.discussion_dialog import DiscussionDialog

        dlg = object.__new__(DiscussionDialog)
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        dlg._on_char_hook(event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestExplanationDialogEscape:
    """Test Escape key handling in ExplanationDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.explanation_dialog import ExplanationDialog

        dlg = object.__new__(ExplanationDialog)
        dlg.EndModal = MagicMock()

        dlg._on_char_hook(_make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.explanation_dialog import ExplanationDialog

        dlg = object.__new__(ExplanationDialog)
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        dlg._on_char_hook(event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestNationwideDiscussionDialogEscape:
    """Test Escape key handling in NationwideDiscussionDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.nationwide_discussion_dialog import (
            NationwideDiscussionDialog,
        )

        dlg = object.__new__(NationwideDiscussionDialog)
        dlg.EndModal = MagicMock()

        dlg._on_char_hook(_make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.nationwide_discussion_dialog import (
            NationwideDiscussionDialog,
        )

        dlg = object.__new__(NationwideDiscussionDialog)
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        dlg._on_char_hook(event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestNOAARadioDialogEscape:
    """Test Escape key handling in NOAARadioDialog."""

    def test_escape_calls_close(self):
        from accessiweather.ui.dialogs.noaa_radio_dialog import NOAARadioDialog

        dlg = object.__new__(NOAARadioDialog)
        dlg.Close = MagicMock()

        dlg._on_char_hook(_make_escape_event())

        dlg.Close.assert_called_once()

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.noaa_radio_dialog import NOAARadioDialog

        dlg = object.__new__(NOAARadioDialog)
        dlg.Close = MagicMock()
        event = _make_other_key_event()

        dlg._on_char_hook(event)

        dlg.Close.assert_not_called()
        event.Skip.assert_called_once()


class TestSoundPackManagerDialogEscape:
    """Test Escape key handling in SoundPackManagerDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.soundpack_manager_dialog import SoundPackManagerDialog

        dlg = object.__new__(SoundPackManagerDialog)
        dlg.EndModal = MagicMock()

        dlg._on_char_hook(_make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.soundpack_manager_dialog import SoundPackManagerDialog

        dlg = object.__new__(SoundPackManagerDialog)
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        dlg._on_char_hook(event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestUVIndexDialogEscape:
    """Test Escape key handling in UVIndexDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.uv_index_dialog import UVIndexDialog

        dlg = object.__new__(UVIndexDialog)
        dlg.EndModal = MagicMock()

        dlg._on_char_hook(_make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.uv_index_dialog import UVIndexDialog

        dlg = object.__new__(UVIndexDialog)
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        dlg._on_char_hook(event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestWeatherHistoryDialogEscape:
    """Test Escape key handling in WeatherHistoryDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.weather_history_dialog import WeatherHistoryDialog

        dlg = object.__new__(WeatherHistoryDialog)
        dlg.EndModal = MagicMock()

        dlg._on_char_hook(_make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.weather_history_dialog import WeatherHistoryDialog

        dlg = object.__new__(WeatherHistoryDialog)
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        dlg._on_char_hook(event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestWeatherAssistantDialogEscape:
    """Test existing Escape key handling in WeatherAssistantDialog."""

    def test_escape_calls_close(self):
        from accessiweather.ui.dialogs.weather_assistant_dialog import WeatherAssistantDialog

        dlg = object.__new__(WeatherAssistantDialog)
        dlg.Close = MagicMock()

        dlg._on_key(_make_escape_event())

        dlg.Close.assert_called_once()

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.weather_assistant_dialog import WeatherAssistantDialog

        dlg = object.__new__(WeatherAssistantDialog)
        dlg.Close = MagicMock()
        event = _make_other_key_event()

        dlg._on_key(event)

        dlg.Close.assert_not_called()
        event.Skip.assert_called_once()
