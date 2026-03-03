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

        dlg = MagicMock()
        dlg.EndModal = MagicMock()

        AirQualityDialog._on_char_hook(dlg, _make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.air_quality_dialog import AirQualityDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        AirQualityDialog._on_char_hook(dlg, event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestAlertDialogEscape:
    """Test Escape key handling in AlertDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.alert_dialog import AlertDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()

        AlertDialog._on_char_hook(dlg, _make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.alert_dialog import AlertDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        AlertDialog._on_char_hook(dlg, event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestAviationDialogEscape:
    """Test Escape key handling in AviationDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.aviation_dialog import AviationDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()

        AviationDialog._on_char_hook(dlg, _make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.aviation_dialog import AviationDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        AviationDialog._on_char_hook(dlg, event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestCommunityPacksBrowserDialogEscape:
    """Test Escape key handling in CommunityPacksBrowserDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.community_packs_dialog import CommunityPacksBrowserDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()

        CommunityPacksBrowserDialog._on_char_hook(dlg, _make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.community_packs_dialog import CommunityPacksBrowserDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        CommunityPacksBrowserDialog._on_char_hook(dlg, event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestDebugAlertDialogEscape:
    """Test Escape key handling in DebugAlertDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.debug_alert_dialog import DebugAlertDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()

        DebugAlertDialog._on_char_hook(dlg, _make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.debug_alert_dialog import DebugAlertDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        DebugAlertDialog._on_char_hook(dlg, event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestDiscussionDialogEscape:
    """Test Escape key handling in DiscussionDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.discussion_dialog import DiscussionDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()

        DiscussionDialog._on_char_hook(dlg, _make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.discussion_dialog import DiscussionDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        DiscussionDialog._on_char_hook(dlg, event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestExplanationDialogEscape:
    """Test Escape key handling in ExplanationDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.explanation_dialog import ExplanationDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()

        ExplanationDialog._on_char_hook(dlg, _make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.explanation_dialog import ExplanationDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        ExplanationDialog._on_char_hook(dlg, event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestNationwideDiscussionDialogEscape:
    """Test Escape key handling in NationwideDiscussionDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.nationwide_discussion_dialog import (
            NationwideDiscussionDialog,
        )

        dlg = MagicMock()
        dlg.EndModal = MagicMock()

        NationwideDiscussionDialog._on_char_hook(dlg, _make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.nationwide_discussion_dialog import (
            NationwideDiscussionDialog,
        )

        dlg = MagicMock()
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        NationwideDiscussionDialog._on_char_hook(dlg, event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestNOAARadioDialogEscape:
    """Test Escape key handling in NOAARadioDialog."""

    def test_escape_calls_close(self):
        from accessiweather.ui.dialogs.noaa_radio_dialog import NOAARadioDialog

        dlg = MagicMock()
        dlg.Close = MagicMock()

        NOAARadioDialog._on_char_hook(dlg, _make_escape_event())

        dlg.Close.assert_called_once()

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.noaa_radio_dialog import NOAARadioDialog

        dlg = MagicMock()
        dlg.Close = MagicMock()
        event = _make_other_key_event()

        NOAARadioDialog._on_char_hook(dlg, event)

        dlg.Close.assert_not_called()
        event.Skip.assert_called_once()


class TestSoundPackManagerDialogEscape:
    """Test Escape key handling in SoundPackManagerDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.soundpack_manager_dialog import SoundPackManagerDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()

        SoundPackManagerDialog._on_char_hook(dlg, _make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.soundpack_manager_dialog import SoundPackManagerDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        SoundPackManagerDialog._on_char_hook(dlg, event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestUVIndexDialogEscape:
    """Test Escape key handling in UVIndexDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.uv_index_dialog import UVIndexDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()

        UVIndexDialog._on_char_hook(dlg, _make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.uv_index_dialog import UVIndexDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        UVIndexDialog._on_char_hook(dlg, event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestWeatherHistoryDialogEscape:
    """Test Escape key handling in WeatherHistoryDialog."""

    def test_escape_calls_end_modal(self):
        from accessiweather.ui.dialogs.weather_history_dialog import WeatherHistoryDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()

        WeatherHistoryDialog._on_char_hook(dlg, _make_escape_event())

        dlg.EndModal.assert_called_once_with(ID_CANCEL)

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.weather_history_dialog import WeatherHistoryDialog

        dlg = MagicMock()
        dlg.EndModal = MagicMock()
        event = _make_other_key_event()

        WeatherHistoryDialog._on_char_hook(dlg, event)

        dlg.EndModal.assert_not_called()
        event.Skip.assert_called_once()


class TestWeatherAssistantDialogEscape:
    """Test existing Escape key handling in WeatherAssistantDialog."""

    def test_escape_calls_close(self):
        from accessiweather.ui.dialogs.weather_assistant_dialog import WeatherAssistantDialog

        dlg = MagicMock()
        dlg.Close = MagicMock()

        WeatherAssistantDialog._on_key(dlg, _make_escape_event())

        dlg.Close.assert_called_once()

    def test_other_key_skips(self):
        from accessiweather.ui.dialogs.weather_assistant_dialog import WeatherAssistantDialog

        dlg = MagicMock()
        dlg.Close = MagicMock()
        event = _make_other_key_event()

        WeatherAssistantDialog._on_key(dlg, event)

        dlg.Close.assert_not_called()
        event.Skip.assert_called_once()
