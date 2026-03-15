"""
Tests for split notification timer changes (coverage for PR #443).

Covers:
- app.py: _on_event_check_update
- notification_event_manager.py: summarize_discussion_change
- ui/main_window.py: refresh_notification_events_async, _fetch_notification_event_data,
  _on_notification_event_data_received
- weather_client_base.py: get_notification_event_data
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.models import Location, WeatherAlerts, WeatherData
from accessiweather.notifications.notification_event_manager import summarize_discussion_change

# ---------------------------------------------------------------------------
# summarize_discussion_change (notification_event_manager.py lines 54, 64)
# ---------------------------------------------------------------------------


class TestSummarizeDiscussionChange:
    """Tests for summarize_discussion_change helper."""

    def test_returns_none_when_current_is_empty(self):
        assert summarize_discussion_change("old text", "") is None
        assert summarize_discussion_change("old text", None) is None

    def test_skips_blank_and_dollar_lines(self):
        current = "$header\n\n$another\n"
        assert summarize_discussion_change(None, current) is None

    def test_returns_first_new_line(self):
        previous = "line one\nline two"
        current = "line one\nline two\nnew addition"
        result = summarize_discussion_change(previous, current)
        assert result == "new addition"

    def test_no_change_returns_none(self):
        text = "line one\nline two"
        assert summarize_discussion_change(text, text) is None

    def test_first_discussion_returns_first_line(self):
        result = summarize_discussion_change(None, "brand new content\nsecond line")
        assert result == "brand new content"

    def test_truncates_long_lines(self):
        long_line = "x" * 400
        result = summarize_discussion_change(None, long_line)
        assert len(result) == 300

    # ------------------------------------------------------------------
    # New section-extraction paths
    # ------------------------------------------------------------------

    def test_what_has_changed_section_used_when_present(self):
        """Path 1: .WHAT HAS CHANGED... section is found and returned."""
        afd = (
            ".SYNOPSIS...\n"
            "Some synopsis text\n"
            ".WHAT HAS CHANGED...\n"
            "Temperatures have risen significantly across the region.\n"
            "Winds will increase overnight.\n"
            ".SHORT TERM...\n"
            "Short term forecast content.\n"
            "&&\n"
        )
        result = summarize_discussion_change(None, afd)
        assert result is not None
        assert "Temperatures have risen" in result
        assert "Winds will increase overnight" in result
        # The short-term section body should NOT appear in the summary
        assert "Short term forecast content" not in result

    def test_key_messages_fallback_when_no_what_has_changed(self):
        """Path 2: .KEY MESSAGES... section used when no WHAT HAS CHANGED."""
        afd = (
            ".SYNOPSIS...\n"
            "Synopsis text here.\n"
            ".KEY MESSAGES...\n"
            "* Heavy rain expected Tuesday.\n"
            "* Flash flood watch in effect.\n"
            "&&\n"
            ".SHORT TERM...\n"
            "Short term text.\n"
        )
        result = summarize_discussion_change(None, afd)
        assert result is not None
        assert "Heavy rain expected Tuesday" in result
        assert "Flash flood watch in effect" in result
        assert "Short term text" not in result

    def test_first_new_line_fallback_when_no_special_sections(self):
        """Path 3: falls back to first new line when no special sections exist."""
        previous = "line one\nline two\n"
        current = "line one\nline two\nThis is brand new forecast text.\n"
        result = summarize_discussion_change(previous, current)
        assert result == "This is brand new forecast text."

    def test_what_has_changed_takes_priority_over_key_messages(self):
        """WHAT HAS CHANGED is preferred over KEY MESSAGES."""
        afd = ".WHAT HAS CHANGED...\nChange detail here.\n.KEY MESSAGES...\nKey message here.\n&&\n"
        result = summarize_discussion_change(None, afd)
        assert result is not None
        assert "Change detail here" in result
        assert "Key message here" not in result

    def test_truncates_section_to_300_chars(self):
        """Section content is truncated to 300 characters."""
        body = "word " * 100  # well over 300 chars
        afd = f".WHAT HAS CHANGED...\n{body}\n.SHORT TERM...\nother stuff\n"
        result = summarize_discussion_change(None, afd)
        assert result is not None
        assert len(result) <= 300


# ---------------------------------------------------------------------------
# app.py: _on_event_check_update (lines 1510-1511)
# ---------------------------------------------------------------------------


class TestOnEventCheckUpdate:
    """Tests for AccessiWeatherApp._on_event_check_update."""

    def test_calls_refresh_notification_events_async(self):
        from accessiweather.app import AccessiWeatherApp

        app = AccessiWeatherApp.__new__(AccessiWeatherApp)
        app.main_window = MagicMock()

        app._on_event_check_update(event=MagicMock())

        app.main_window.refresh_notification_events_async.assert_called_once()

    def test_noop_when_no_main_window(self):
        from accessiweather.app import AccessiWeatherApp

        app = AccessiWeatherApp.__new__(AccessiWeatherApp)
        app.main_window = None

        # Should not raise
        app._on_event_check_update(event=MagicMock())


# ---------------------------------------------------------------------------
# main_window.py: refresh_notification_events_async (lines 874-877)
# ---------------------------------------------------------------------------


class TestRefreshNotificationEventsAsync:
    """Tests for MainWindow.refresh_notification_events_async."""

    def _make_window(self):
        from accessiweather.ui.main_window import MainWindow

        with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
            win = MainWindow.__new__(MainWindow)
        win.app = MagicMock()
        return win

    def test_skips_when_is_updating(self):
        win = self._make_window()
        win.app.is_updating = True

        win.refresh_notification_events_async()

        win.app.run_async.assert_not_called()

    def test_runs_fetch_when_not_updating(self):
        win = self._make_window()
        win.app.is_updating = False

        win.refresh_notification_events_async()

        win.app.run_async.assert_called_once()


# ---------------------------------------------------------------------------
# main_window.py: _fetch_notification_event_data (lines 881-889)
# ---------------------------------------------------------------------------


class TestFetchNotificationEventData:
    """Tests for MainWindow._fetch_notification_event_data."""

    def _make_window(self):
        from accessiweather.ui.main_window import MainWindow

        with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
            win = MainWindow.__new__(MainWindow)
        win.app = MagicMock()
        return win

    @pytest.mark.asyncio
    async def test_returns_early_for_no_location(self):
        win = self._make_window()
        win.app.config_manager.get_current_location.return_value = None

        await win._fetch_notification_event_data()

        win.app.weather_client.get_notification_event_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_early_for_nationwide(self):
        win = self._make_window()
        loc = MagicMock()
        loc.name = "Nationwide"
        win.app.config_manager.get_current_location.return_value = loc

        await win._fetch_notification_event_data()

        win.app.weather_client.get_notification_event_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetches_and_posts_result(self):
        win = self._make_window()
        loc = Location(name="NYC", latitude=40.71, longitude=-74.0)
        win.app.config_manager.get_current_location.return_value = loc

        weather_data = WeatherData(location=loc)
        win.app.weather_client.get_notification_event_data = AsyncMock(return_value=weather_data)

        with patch("accessiweather.ui.main_window_notification_events.wx") as mock_wx:
            await win._fetch_notification_event_data()

            mock_wx.CallAfter.assert_called_once_with(
                win._on_notification_event_data_received, weather_data
            )

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self):
        win = self._make_window()
        loc = Location(name="NYC", latitude=40.71, longitude=-74.0)
        win.app.config_manager.get_current_location.return_value = loc
        win.app.weather_client.get_notification_event_data = AsyncMock(
            side_effect=RuntimeError("network error")
        )

        # Should not raise
        with patch("accessiweather.ui.main_window_notification_events.wx"):
            await win._fetch_notification_event_data()


# ---------------------------------------------------------------------------
# main_window.py: _on_notification_event_data_received (lines 1212-1235)
# ---------------------------------------------------------------------------


class TestOnNotificationEventDataReceived:
    """Tests for MainWindow._on_notification_event_data_received."""

    def _make_window(self):
        from accessiweather.ui.main_window import MainWindow

        with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
            win = MainWindow.__new__(MainWindow)
        win.app = MagicMock()
        win._process_notification_events = MagicMock()
        win._fallback_notifier = None
        return win

    def test_processes_alerts(self):
        win = self._make_window()
        alerts = MagicMock()
        alerts.has_alerts.return_value = True

        weather_data = MagicMock()
        weather_data.alerts = alerts
        weather_data.alert_lifecycle_diff = None

        win._on_notification_event_data_received(weather_data)

        win.app.run_async.assert_called_once()
        win._process_notification_events.assert_called_once_with(weather_data)

    def test_processes_lifecycle_diff(self):
        win = self._make_window()
        alerts = MagicMock()
        alerts.has_alerts.return_value = False

        diff = MagicMock()
        diff.has_changes = True

        weather_data = MagicMock()
        weather_data.alerts = alerts
        weather_data.alert_lifecycle_diff = diff

        win._on_notification_event_data_received(weather_data)

        # Should be called for lifecycle diff
        assert win.app.run_async.call_count == 1
        win._process_notification_events.assert_called_once_with(weather_data)

    def test_both_alerts_and_lifecycle(self):
        win = self._make_window()
        alerts = MagicMock()
        alerts.has_alerts.return_value = True

        diff = MagicMock()
        diff.has_changes = True

        weather_data = MagicMock()
        weather_data.alerts = alerts
        weather_data.alert_lifecycle_diff = diff

        win._on_notification_event_data_received(weather_data)

        # Two run_async calls: one for alerts, one for lifecycle
        assert win.app.run_async.call_count == 2
        win._process_notification_events.assert_called_once_with(weather_data)

    def test_no_alerts_no_diff(self):
        win = self._make_window()
        weather_data = MagicMock()
        weather_data.alerts = None
        weather_data.alert_lifecycle_diff = None

        win._on_notification_event_data_received(weather_data)

        win.app.run_async.assert_not_called()
        win._process_notification_events.assert_called_once_with(weather_data)

    def test_exception_is_caught(self):
        win = self._make_window()
        win._process_notification_events.side_effect = RuntimeError("boom")

        weather_data = MagicMock()
        weather_data.alerts = None
        weather_data.alert_lifecycle_diff = None

        # Should not raise
        win._on_notification_event_data_received(weather_data)


class TestNotificationEventHelpers:
    """Focused tests for extracted main window notification event helpers."""

    def _make_window(self):
        from pathlib import Path

        from accessiweather.ui.main_window import MainWindow

        with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
            win = MainWindow.__new__(MainWindow)

        win.app = MagicMock()
        win.app.paths.config = Path("/tmp/config")
        win._notification_event_manager = None
        win._fallback_notifier = None
        return win

    def test_get_notification_event_manager_caches_instance(self):
        win = self._make_window()

        with patch(
            "accessiweather.ui.main_window_notification_events.NotificationEventManager"
        ) as manager_cls:
            first = win._get_notification_event_manager()
            second = win._get_notification_event_manager()

        assert first is second
        manager_cls.assert_called_once_with(
            state_file=win.app.paths.config / "notification_event_state.json"
        )

    def test_process_notification_events_skips_when_both_disabled(self):
        win = self._make_window()
        settings = MagicMock()
        settings.notify_discussion_update = False
        settings.notify_severe_risk_change = False
        win.app.config_manager.get_settings.return_value = settings

        win._process_notification_events(MagicMock())

        win.app.config_manager.get_current_location.assert_not_called()

    def test_process_notification_events_uses_fallback_notifier(self):
        win = self._make_window()
        settings = MagicMock()
        settings.notify_discussion_update = True
        settings.notify_severe_risk_change = False
        settings.sound_enabled = True
        win.app.config_manager.get_settings.return_value = settings
        location = MagicMock()
        location.name = "PHI"
        win.app.config_manager.get_current_location.return_value = location
        win.app.notifier = None

        event = MagicMock()
        event.event_type = "discussion_update"
        event.title = "Updated discussion"
        event.message = "Summary"
        event.sound_event = "discussion_update"
        weather_data = MagicMock()

        with (
            patch(
                "accessiweather.ui.main_window_notification_events.NotificationEventManager"
            ) as manager_cls,
            patch(
                "accessiweather.ui.main_window_notification_events.SafeDesktopNotifier"
            ) as notifier_cls,
        ):
            manager_cls.return_value.check_for_events.return_value = [event]
            notifier = notifier_cls.return_value
            notifier.send_notification.return_value = True

            win._process_notification_events(weather_data)

        notifier.send_notification.assert_called_once_with(
            title="Updated discussion",
            message="Summary",
            timeout=10,
            sound_event="discussion_update",
            play_sound=True,
        )


# ---------------------------------------------------------------------------
# weather_client_base.py: get_notification_event_data (lines 383-416)
# ---------------------------------------------------------------------------


class TestGetNotificationEventData:
    """Tests for WeatherClient.get_notification_event_data."""

    @pytest.fixture
    def us_location(self):
        return Location(name="NYC", latitude=40.71, longitude=-74.0, country_code="US")

    @pytest.fixture
    def intl_location(self):
        return Location(name="London", latitude=51.51, longitude=-0.13, country_code="GB")

    @pytest.fixture
    def client(self):
        from accessiweather.weather_client import WeatherClient

        return WeatherClient(visual_crossing_api_key="test-key")

    @pytest.mark.asyncio
    async def test_us_location_fetches_nws_data(self, client, us_location):
        discussion = "Discussion text"
        issuance_time = MagicMock()
        alerts = WeatherAlerts(alerts=[])

        client._get_nws_discussion_only = AsyncMock(return_value=(discussion, issuance_time))
        client._get_nws_alerts = AsyncMock(return_value=alerts)

        result = await client.get_notification_event_data(us_location)

        assert result.discussion == discussion
        assert result.discussion_issuance_time == issuance_time
        assert result.alerts == alerts
        client._get_nws_discussion_only.assert_awaited_once_with(us_location)
        client._get_nws_alerts.assert_awaited_once_with(us_location)

    @pytest.mark.asyncio
    async def test_us_location_none_alerts_becomes_empty(self, client, us_location):
        client._get_nws_discussion_only = AsyncMock(return_value=(None, None))
        client._get_nws_alerts = AsyncMock(return_value=None)

        result = await client.get_notification_event_data(us_location)

        assert result.alerts is not None
        assert len(result.alerts.alerts) == 0

    @pytest.mark.asyncio
    async def test_intl_location_with_vc_client(self, client, intl_location):
        vc_client = MagicMock()
        current = MagicMock()
        alerts = WeatherAlerts(alerts=[])
        vc_client.get_current_conditions = AsyncMock(return_value=current)
        vc_client.get_alerts = AsyncMock(return_value=alerts)
        client._visual_crossing_client = vc_client

        result = await client.get_notification_event_data(intl_location)

        assert result.current == current
        assert result.alerts == alerts

    @pytest.mark.asyncio
    async def test_intl_location_without_vc_client(self, intl_location):
        from accessiweather.weather_client import WeatherClient

        client = WeatherClient()  # No VC API key

        result = await client.get_notification_event_data(intl_location)

        assert result.alerts is not None
        assert len(result.alerts.alerts) == 0

    @pytest.mark.asyncio
    async def test_tracks_alert_lifecycle_diff(self, client, us_location):
        alerts = WeatherAlerts(alerts=[])
        client._get_nws_discussion_only = AsyncMock(return_value=(None, None))
        client._get_nws_alerts = AsyncMock(return_value=alerts)

        result = await client.get_notification_event_data(us_location)

        assert result.alert_lifecycle_diff is not None

    @pytest.mark.asyncio
    async def test_exception_returns_empty_alerts(self, client, us_location):
        client._get_nws_discussion_only = AsyncMock(side_effect=RuntimeError("API down"))
        client._get_nws_alerts = AsyncMock(side_effect=RuntimeError("API down"))

        result = await client.get_notification_event_data(us_location)

        assert result.alerts is not None
        assert len(result.alerts.alerts) == 0
