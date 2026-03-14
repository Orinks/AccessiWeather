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
        long_line = "x" * 200
        result = summarize_discussion_change(None, long_line)
        assert len(result) == 160


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

        with patch("accessiweather.ui.main_window.wx") as mock_wx:
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
        with patch("accessiweather.ui.main_window.wx"):
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
