from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import wx

from accessiweather.app import AccessiWeatherApp
from accessiweather.models import AppSettings, WeatherData
from accessiweather.notifications.notification_event_manager import NotificationEventManager


def test_start_background_updates_uses_split_intervals(monkeypatch):
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.config_manager = MagicMock()
    app.config_manager.get_settings.return_value = SimpleNamespace(
        update_interval_minutes=60,
        event_check_interval_minutes=2,
    )

    weather_timer = MagicMock()
    event_timer = MagicMock()
    timer_factory = MagicMock(side_effect=[weather_timer, event_timer])
    monkeypatch.setattr(wx, "Timer", timer_factory)

    app._start_background_updates()

    assert timer_factory.call_count == 2
    weather_timer.Bind.assert_called_once_with(wx.EVT_TIMER, app._on_background_update)
    weather_timer.Start.assert_called_once_with(60 * 60 * 1000)
    event_timer.Bind.assert_called_once_with(wx.EVT_TIMER, app._on_event_check_update)
    event_timer.Start.assert_called_once_with(2 * 60 * 1000)


def test_request_exit_stops_weather_and_event_timers():
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    weather_timer = MagicMock()
    event_timer = MagicMock()
    auto_update_timer = MagicMock()
    app._update_timer = weather_timer
    app._event_check_timer = event_timer
    app._auto_update_check_timer = auto_update_timer
    app.config_manager = MagicMock()
    app.config_manager.get_settings.return_value = SimpleNamespace(sound_enabled=False)
    app.tray_icon = None
    app.single_instance_manager = None
    app._async_loop = None
    app.main_window = None
    app.ExitMainLoop = MagicMock()

    app.request_exit()

    weather_timer.Stop.assert_called_once()
    event_timer.Stop.assert_called_once()
    auto_update_timer.Stop.assert_called_once()


def test_refresh_runtime_settings_restarts_background_updates():
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    settings = SimpleNamespace(
        data_source="auto",
        enable_alerts=True,
        sound_enabled=True,
        sound_pack="default",
        taskbar_icon_text_enabled=False,
        taskbar_icon_dynamic_enabled=True,
        taskbar_icon_text_format="{temp} {condition}",
        temperature_unit="both",
        verbosity_level="standard",
    )
    app.config_manager = MagicMock()
    app.config_manager.get_settings.return_value = settings
    app.weather_client = None
    app.presenter = None
    app._notifier = None
    app.alert_notification_system = None
    app.taskbar_icon_updater = None
    app._start_auto_update_checks = MagicMock()
    app._start_background_updates = MagicMock()

    app.refresh_runtime_settings()

    app._start_auto_update_checks.assert_called_once()
    app._start_background_updates.assert_called_once()


def test_discussion_update_message_includes_change_summary():
    manager = NotificationEventManager(state_file=None)
    settings = AppSettings(notify_discussion_update=True, notify_severe_risk_change=False)

    weather_data = WeatherData(location=SimpleNamespace(name="Test Location"))
    weather_data.current = None
    weather_data.discussion = "Old headline\nOld details"
    weather_data.discussion_issuance_time = datetime(2026, 3, 9, 20, 0, tzinfo=timezone.utc)

    assert manager.check_for_events(weather_data, settings, "Test Location") == []

    weather_data.discussion = "New headline\nOld details"
    weather_data.discussion_issuance_time = datetime(2026, 3, 9, 20, 5, tzinfo=timezone.utc)
    events = manager.check_for_events(weather_data, settings, "Test Location")

    assert len(events) == 1
    assert "updated by the National Weather Service" in events[0].message
    assert "Change summary: New headline" in events[0].message
