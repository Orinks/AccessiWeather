"""Focused tests for current-conditions event emission in MainWindow."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from accessiweather.models import CurrentConditions


@patch("accessiweather.ui.main_window.MainWindow.__init__", lambda self, *a, **kw: None)
def test_on_weather_data_received_emits_now_event_for_meaningful_change():
    from accessiweather.ui.main_window import MainWindow

    previous_data = SimpleNamespace(
        current_conditions=CurrentConditions(temperature=70.0, condition="Clear", wind_speed=2.0)
    )
    incoming_data = SimpleNamespace(
        current_conditions=CurrentConditions(temperature=75.0, condition="Cloudy", wind_speed=3.0),
        alerts=None,
        alert_lifecycle_diff=None,
    )
    presentation = SimpleNamespace(
        current_conditions=SimpleNamespace(fallback_text="Cloudy and cooler"),
        source_attribution=SimpleNamespace(summary_text="Source: Open-Meteo"),
        status_messages=[],
        forecast=SimpleNamespace(fallback_text="Tonight: Breezy"),
    )

    event_dispatcher = MagicMock()
    app = SimpleNamespace(
        current_weather_data=previous_data,
        presenter=SimpleNamespace(present=MagicMock(return_value=presentation)),
        event_dispatcher=event_dispatcher,
        config_manager=SimpleNamespace(
            get_current_location=MagicMock(return_value=SimpleNamespace(name="Boston"))
        ),
        alert_notification_system=None,
        update_tray_tooltip=MagicMock(),
        run_async=MagicMock(),
        is_updating=True,
    )

    win = MainWindow.__new__(MainWindow)
    win.app = app
    win.current_conditions = SimpleNamespace(SetValue=MagicMock())
    win.forecast_display = SimpleNamespace(SetValue=MagicMock())
    win.stale_warning_label = SimpleNamespace(SetLabel=MagicMock())
    win.refresh_button = SimpleNamespace(Enable=MagicMock())
    win._update_alerts = MagicMock()
    win._process_notification_events = MagicMock()
    win.set_status = MagicMock()
    win._alert_lifecycle_labels = {}

    win._on_weather_data_received(incoming_data)

    assert event_dispatcher.dispatch_event.call_count == 1
    dispatched_event = event_dispatcher.dispatch_event.call_args.args[0]
    assert dispatched_event.channel == "now"
    assert dispatched_event.location == "Boston"
    assert dispatched_event.headline == "Current conditions: Cloudy"
    assert dispatched_event.payload == {"condition": "Cloudy", "temperature": 75.0}
    assert event_dispatcher.dispatch_event.call_args.kwargs == {
        "announce": True,
        "mirror_toast": False,
    }
    app.update_tray_tooltip.assert_called_once_with(incoming_data, "Boston")
    win._process_notification_events.assert_called_once_with(incoming_data)
    assert app.is_updating is False
    win.refresh_button.Enable.assert_called_once()
