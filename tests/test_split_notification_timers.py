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

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.models import (
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    TextProduct,
    WeatherAlerts,
    WeatherData,
)
from accessiweather.notifications.notification_event_manager import summarize_discussion_change
from accessiweather.ui.main_window_notification_events import (
    _filter_sps_products_for_location,
)

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

    def test_key_messages_stop_at_next_dot_section(self):
        """KEY MESSAGES must not absorb UPDATE/SHORT TERM text before &&."""
        afd = (
            ".KEY MESSAGES...\n"
            "- Heavy rain expected Tuesday.\n"
            "- Flash flood watch in effect.\n"
            ".UPDATE...\n"
            "Only aviation wording changed.\n"
            ".SHORT TERM...\n"
            "Short term text.\n"
            "&&\n"
        )
        result = summarize_discussion_change(None, afd)
        assert result is not None
        assert "Heavy rain expected Tuesday" in result
        assert "Flash flood watch in effect" in result
        assert "Only aviation wording changed" not in result
        assert "Short term text" not in result

    def test_key_messages_diff_prefers_new_messages_when_changed(self):
        """When KEY MESSAGES change, the toast summary should use the current messages."""
        previous = (
            ".KEY MESSAGES...\n"
            "1. Rain arrives later today.\n"
            "2. Saturday storm potential remains.\n"
            "&&\n"
        )
        current = (
            ".KEY MESSAGES...\n"
            "1. Rain arrives late this afternoon.\n"
            "2. Saturday storm potential remains.\n"
            "&&\n"
        )
        result = summarize_discussion_change(previous, current)
        assert result is not None
        assert "late this afternoon" in result
        assert "later today" not in result

    def test_no_changes_section_defers_to_changed_key_messages(self):
        """A no-change marker should not hide materially changed KEY MESSAGES."""
        previous = (
            ".WHAT HAS CHANGED...\n"
            "Rainfall totals have lowered a bit.\n"
            "&&\n"
            ".KEY MESSAGES...\n"
            "1. Rain arrives later today.\n"
            "&&\n"
        )
        current = (
            ".WHAT HAS CHANGED...\n"
            "No changes.\n"
            "&&\n"
            ".KEY MESSAGES...\n"
            "1. Rain arrives late this afternoon.\n"
            "&&\n"
        )
        result = summarize_discussion_change(previous, current)
        assert result is not None
        assert "late this afternoon" in result
        assert "No changes" not in result

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
    """
    Tests for MainWindow._on_notification_event_data_received.

    Note: Under the split-timer architecture, the lightweight event path handles
    alerts ONLY. Discussion/risk notifications are handled in _on_weather_data_received
    after full weather refreshes to prevent duplicate notifications.
    """

    def _make_window(self):
        from accessiweather.ui.main_window import MainWindow

        with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
            win = MainWindow.__new__(MainWindow)
        win.app = MagicMock()
        win._process_notification_events = MagicMock()
        win._fallback_notifier = None
        return win

    def test_processes_alerts_only_not_discussion(self):
        """Lightweight path processes alerts but NOT _process_notification_events."""
        win = self._make_window()
        alerts = MagicMock()
        alerts.has_alerts.return_value = True

        weather_data = MagicMock()
        weather_data.alerts = alerts
        weather_data.alert_lifecycle_diff = None

        win._on_notification_event_data_received(weather_data)

        # Alerts are processed
        win.app.run_async.assert_called_once()
        # But _process_notification_events is NOT called (discussion handled elsewhere)
        win._process_notification_events.assert_not_called()

    def test_processes_lifecycle_diff_only_not_discussion(self):
        """Lightweight path processes lifecycle diff but NOT _process_notification_events."""
        win = self._make_window()
        alerts = MagicMock()
        alerts.has_alerts.return_value = False

        diff = MagicMock()
        diff.has_changes = True

        weather_data = MagicMock()
        weather_data.alerts = alerts
        weather_data.alert_lifecycle_diff = diff

        win._on_notification_event_data_received(weather_data)

        # Lifecycle diff is processed
        assert win.app.run_async.call_count == 1
        # But _process_notification_events is NOT called
        win._process_notification_events.assert_not_called()

    def test_both_alerts_and_lifecycle_only_not_discussion(self):
        """Lightweight path processes both alerts and lifecycle, but not discussion."""
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
        # _process_notification_events is NOT called
        win._process_notification_events.assert_not_called()

    def test_no_alerts_no_diff_does_nothing(self):
        """When there's nothing to process, nothing is done."""
        win = self._make_window()
        weather_data = MagicMock()
        weather_data.alerts = None
        weather_data.alert_lifecycle_diff = None

        win._on_notification_event_data_received(weather_data)

        win.app.run_async.assert_not_called()
        win._process_notification_events.assert_not_called()

    def test_exception_is_caught(self):
        """Exceptions in alert processing are caught and logged."""
        win = self._make_window()
        # Force an exception in run_async
        win.app.run_async.side_effect = RuntimeError("boom")

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
        win.app.config_manager.config_dir = Path("/tmp/runtime-config")
        win._notification_event_manager = None
        win._fallback_notifier = None
        win.append_event_center_entry = MagicMock()
        return win

    def test_get_notification_event_manager_caches_instance(self):
        win = self._make_window()

        with patch(
            "accessiweather.ui.main_window_notification_events.NotificationEventManager"
        ) as manager_cls:
            first = win._get_notification_event_manager()
            second = win._get_notification_event_manager()

        assert first is second
        _, kwargs = manager_cls.call_args
        assert kwargs["runtime_state_manager"].state_file == (
            win.app.config_manager.config_dir / "state" / "runtime_state.json"
        )

    def test_process_notification_events_skips_when_both_disabled(self):
        win = self._make_window()
        settings = MagicMock()
        settings.notify_discussion_update = False
        settings.notify_severe_risk_change = False
        settings.notify_minutely_precipitation_start = False
        settings.notify_minutely_precipitation_stop = False
        settings.notify_precipitation_likelihood = False
        settings.notify_hwo_update = False
        settings.notify_sps_issued = False
        win.app.config_manager.get_settings.return_value = settings

        win._process_notification_events(MagicMock())

        win.app.config_manager.get_current_location.assert_not_called()

    def test_process_notification_events_uses_fallback_notifier(self):
        win = self._make_window()
        settings = MagicMock()
        settings.notify_discussion_update = True
        settings.notify_severe_risk_change = False
        settings.notify_minutely_precipitation_start = False
        settings.notify_minutely_precipitation_stop = False
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
            activation_arguments="accessiweather-toast:kind=discussion",
        )
        win.append_event_center_entry.assert_called_once_with(
            "Summary",
            category="Updated discussion",
        )

    def test_process_notification_events_logs_reviewable_text_when_notifier_returns_false(self):
        win = self._make_window()
        settings = MagicMock()
        settings.notify_discussion_update = True
        settings.notify_severe_risk_change = False
        settings.notify_minutely_precipitation_start = False
        settings.notify_minutely_precipitation_stop = False
        settings.sound_enabled = True
        win.app.config_manager.get_settings.return_value = settings
        location = MagicMock()
        location.name = "PHI"
        win.app.config_manager.get_current_location.return_value = location
        win.app.notifier = MagicMock()

        event = MagicMock()
        event.event_type = "discussion_update"
        event.title = "Updated discussion"
        event.message = "Summary"
        event.sound_event = "discussion_update"
        weather_data = MagicMock()

        with patch(
            "accessiweather.ui.main_window_notification_events.NotificationEventManager"
        ) as manager_cls:
            manager_cls.return_value.check_for_events.return_value = [event]
            win.app.notifier.send_notification.return_value = False

            win._process_notification_events(weather_data)

        win.append_event_center_entry.assert_called_once_with(
            "Summary",
            category="Updated discussion",
        )


class TestSpsProductLocationFiltering:
    """SPS product notifications must honor the user's saved NWS zones."""

    def _product(self, product_text: str, product_id: str = "SPS-FWD") -> TextProduct:
        return TextProduct(
            product_type="SPS",
            product_id=product_id,
            cwa_office="FWD",
            issuance_time=datetime(2026, 4, 29, 18, 10, tzinfo=UTC),
            product_text=product_text,
            headline="Special Weather Statement",
        )

    def test_drops_office_sps_for_other_forecast_zones(self):
        location = Location(
            name="Copperas Cove",
            latitude=31.1241,
            longitude=-97.9031,
            country_code="US",
            cwa_office="FWD",
            forecast_zone_id="TXZ157",
            county_zone_id="TXC099",
            fire_zone_id="TXZ157",
        )
        dallas_sps = self._product(
            "\n"
            "TXZ118-119-291900-\n"
            "Tarrant TX-Dallas TX-\n"
            "110 PM CDT Wed Apr 29 2026\n"
            "...A strong thunderstorm will impact portions of southeastern Tarrant\n"
            "and Dallas Counties through 200 PM CDT...\n",
            product_id="SPS-DALLAS",
        )

        result = _filter_sps_products_for_location([dallas_sps], location)

        assert result == []

    def test_keeps_sps_for_location_forecast_zone(self):
        location = Location(
            name="Copperas Cove",
            latitude=31.1241,
            longitude=-97.9031,
            country_code="US",
            cwa_office="FWD",
            forecast_zone_id="TXZ157",
            county_zone_id="TXC099",
            fire_zone_id="TXZ157",
        )
        local_sps = self._product(
            "\n"
            "TXZ157-291900-\n"
            "Coryell TX-\n"
            "110 PM CDT Wed Apr 29 2026\n"
            "...A strong thunderstorm will impact portions of Coryell County...\n",
            product_id="SPS-CORYELL",
        )

        result = _filter_sps_products_for_location([local_sps], location)

        assert result == [local_sps]


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

    @pytest.mark.asyncio
    async def test_minutely_precipitation_fetch_uses_normal_interval_when_clear(
        self, client, intl_location
    ):
        settings = client.settings
        settings.update_interval_minutes = 30
        settings.notify_minutely_precipitation_start = True
        settings.notify_minutely_precipitation_stop = True
        client.data_source = "pirateweather"
        client.pirate_weather_client = MagicMock()
        client.pirate_weather_client.get_current_conditions = AsyncMock(return_value=MagicMock())
        client.pirate_weather_client.get_alerts = AsyncMock(return_value=WeatherAlerts(alerts=[]))
        client._get_pirate_weather_minutely = AsyncMock(return_value=MagicMock())

        now = datetime(2026, 4, 7, 12, 0, tzinfo=UTC)
        client._latest_weather_by_location[client._location_key(intl_location)] = WeatherData(
            location=intl_location,
            hourly_forecast=HourlyForecast(
                periods=[
                    HourlyForecastPeriod(
                        start_time=now + timedelta(hours=1),
                        precipitation_probability=10,
                    )
                ]
            ),
        )

        client._utcnow = MagicMock(
            side_effect=[
                now,
                now + timedelta(minutes=1),
                now + timedelta(minutes=31),
                now + timedelta(minutes=31),
            ]
        )

        await client.get_notification_event_data(intl_location)
        await client.get_notification_event_data(intl_location)
        await client.get_notification_event_data(intl_location)

        assert client._get_pirate_weather_minutely.await_count == 2

    @pytest.mark.asyncio
    async def test_minutely_precipitation_fetch_uses_fast_interval_when_rain_is_likely(
        self, client, intl_location
    ):
        settings = client.settings
        settings.update_interval_minutes = 30
        settings.notify_minutely_precipitation_start = True
        settings.notify_minutely_precipitation_stop = True
        settings.minutely_precipitation_fast_polling = True
        client.data_source = "pirateweather"
        client.pirate_weather_client = MagicMock()
        client.pirate_weather_client.get_current_conditions = AsyncMock(return_value=MagicMock())
        client.pirate_weather_client.get_alerts = AsyncMock(return_value=WeatherAlerts(alerts=[]))
        client._get_pirate_weather_minutely = AsyncMock(return_value=MagicMock())

        now = datetime(2026, 4, 7, 12, 0, tzinfo=UTC)
        client._latest_weather_by_location[client._location_key(intl_location)] = WeatherData(
            location=intl_location,
            hourly_forecast=HourlyForecast(
                periods=[
                    HourlyForecastPeriod(
                        start_time=now + timedelta(hours=1),
                        precipitation_probability=40,
                    )
                ]
            ),
        )

        client._utcnow = MagicMock(
            side_effect=[
                now,
                now,
                now + timedelta(minutes=4),
                now + timedelta(minutes=4),
                now + timedelta(minutes=6),
                now + timedelta(minutes=6),
                now + timedelta(minutes=6),
            ]
        )

        await client.get_notification_event_data(intl_location)
        await client.get_notification_event_data(intl_location)
        await client.get_notification_event_data(intl_location)

        assert client._get_pirate_weather_minutely.await_count == 2

    @pytest.mark.asyncio
    async def test_minutely_precipitation_fetch_defaults_to_recommended_floor(
        self, client, intl_location
    ):
        settings = client.settings
        settings.update_interval_minutes = 10
        settings.notify_minutely_precipitation_start = True
        settings.notify_minutely_precipitation_stop = True
        settings.minutely_precipitation_fast_polling = False
        client.data_source = "pirateweather"
        client.pirate_weather_client = MagicMock()
        client.pirate_weather_client.get_current_conditions = AsyncMock(return_value=MagicMock())
        client.pirate_weather_client.get_alerts = AsyncMock(return_value=WeatherAlerts(alerts=[]))
        client._get_pirate_weather_minutely = AsyncMock(return_value=MagicMock())

        now = datetime(2026, 4, 7, 12, 0, tzinfo=UTC)
        client._utcnow = MagicMock(
            side_effect=[
                now,
                now + timedelta(minutes=11),
                now + timedelta(minutes=16),
                now + timedelta(minutes=16),
            ]
        )

        await client.get_notification_event_data(intl_location)
        await client.get_notification_event_data(intl_location)
        await client.get_notification_event_data(intl_location)

        assert client._get_pirate_weather_minutely.await_count == 2
