from __future__ import annotations

from unittest.mock import MagicMock, patch

from accessiweather.display.weather_presenter import ForecastPresentation


def _make_window():
    from accessiweather.ui.main_window import MainWindow

    with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
        win = MainWindow.__new__(MainWindow)

    win.app = MagicMock()
    win.app.alert_notification_system = None
    win.app.config_manager.get_settings.return_value = MagicMock(
        sound_enabled=False,
        sound_pack="default",
        muted_sound_events=[],
    )
    win.app.presenter.present.return_value = MagicMock(
        current_conditions=MagicMock(fallback_text="Current conditions"),
        source_attribution=None,
        status_messages=[],
        forecast=ForecastPresentation(
            title="Forecast",
            fallback_text="Combined forecast",
            daily_section_text="Daily section",
            hourly_section_text="Hourly section",
        ),
    )
    win.app.is_updating = True
    win.current_conditions = MagicMock()
    win.stale_warning_label = MagicMock()
    win.daily_forecast_display = MagicMock()
    win.hourly_forecast_display = MagicMock()
    win.refresh_button = MagicMock()
    win.set_status = MagicMock()
    win._update_alerts = MagicMock()
    win._process_notification_events = MagicMock()
    win._alert_lifecycle_labels = {}
    return win


def test_on_weather_data_received_sets_daily_and_hourly_forecast_sections():
    win = _make_window()

    weather_data = MagicMock()
    weather_data.alerts = None
    weather_data.alert_lifecycle_diff = None

    win._on_weather_data_received(weather_data)

    win.daily_forecast_display.SetValue.assert_called_once_with("Daily section")
    win.hourly_forecast_display.SetValue.assert_called_once_with("Hourly section")


def test_set_forecast_sections_updates_both_controls():
    win = _make_window()

    from accessiweather.ui.main_window import MainWindow

    MainWindow._set_forecast_sections(win, "Daily text", "Hourly text")

    win.daily_forecast_display.SetValue.assert_called_with("Daily text")
    win.hourly_forecast_display.SetValue.assert_called_with("Hourly text")
