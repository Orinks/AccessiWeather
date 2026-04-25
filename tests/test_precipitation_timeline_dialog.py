from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from accessiweather.models import MinutelyPrecipitationForecast, MinutelyPrecipitationPoint
from accessiweather.ui.dialogs.precipitation_timeline_dialog import (
    build_precipitation_timeline_text,
    has_precipitation_timeline_data,
    show_precipitation_timeline_dialog,
)


def _make_forecast() -> MinutelyPrecipitationForecast:
    start = datetime(2026, 1, 1, 15, 4, tzinfo=UTC)
    return MinutelyPrecipitationForecast(
        summary="Light rain starting soon.",
        points=[
            MinutelyPrecipitationPoint(time=start, precipitation_intensity=0.0),
            MinutelyPrecipitationPoint(
                time=start + timedelta(minutes=1),
                precipitation_intensity=0.12,
                precipitation_probability=0.6,
                precipitation_type="rain",
            ),
            MinutelyPrecipitationPoint(
                time=start + timedelta(minutes=2),
                precipitation_intensity=0.03,
                precipitation_probability=0.3,
                precipitation_type="rain",
            ),
        ],
    )


def test_has_precipitation_timeline_data_requires_minutely_points():
    assert has_precipitation_timeline_data(SimpleNamespace(minutely_precipitation=_make_forecast()))
    assert not has_precipitation_timeline_data(SimpleNamespace(minutely_precipitation=None))
    assert not has_precipitation_timeline_data(
        SimpleNamespace(minutely_precipitation=MinutelyPrecipitationForecast(points=[]))
    )


def test_build_precipitation_timeline_text_returns_plain_text_timeline():
    text = build_precipitation_timeline_text(_make_forecast())

    assert "Times shown in forecast time." in text
    assert "Offset  Time      Conditions" in text
    assert "Now" in text
    assert "+01m" in text
    assert "3:04 PM" in text
    assert "Rain | 60% chance | 0.120 mm/hr" in text


def test_build_precipitation_timeline_text_includes_intensity_error():
    start = datetime(2026, 1, 1, 15, 4, tzinfo=UTC)
    forecast = MinutelyPrecipitationForecast(
        points=[
            MinutelyPrecipitationPoint(
                time=start,
                precipitation_intensity=0.12,
                precipitation_intensity_error=0.03,
                precipitation_type="rain",
            )
        ]
    )

    text = build_precipitation_timeline_text(forecast)

    assert "0.120 mm/hr (+/- 0.030 mm/hr)" in text


def test_show_precipitation_timeline_dialog_warns_when_minutely_data_missing():
    app = MagicMock()
    app.config_manager.get_current_location.return_value = SimpleNamespace(name="Test City")
    app.current_weather_data = SimpleNamespace(minutely_precipitation=None)

    with patch(
        "accessiweather.ui.dialogs.precipitation_timeline_dialog.wx.MessageBox",
        create=True,
    ) as message_box:
        show_precipitation_timeline_dialog(MagicMock(), app)

    message_box.assert_called_once()
    assert "Minutely precipitation data is not available" in message_box.call_args.args[0]


def test_show_precipitation_timeline_dialog_creates_modal_dialog():
    app = MagicMock()
    app.config_manager.get_current_location.return_value = SimpleNamespace(
        name="Test City",
        timezone="America/New_York",
    )
    app.current_weather_data = SimpleNamespace(minutely_precipitation=_make_forecast())

    created: dict[str, object] = {}

    class _FakeDialog:
        def __init__(self, parent, *, location_name, forecast, timezone_name=None):
            created["parent"] = parent
            created["location_name"] = location_name
            created["forecast"] = forecast
            created["timezone_name"] = timezone_name
            created["shown"] = False
            created["destroyed"] = False

        def ShowModal(self):
            created["shown"] = True

        def Destroy(self):
            created["destroyed"] = True

    with patch(
        "accessiweather.ui.dialogs.precipitation_timeline_dialog.PrecipitationTimelineDialog",
        _FakeDialog,
    ):
        show_precipitation_timeline_dialog(MagicMock(), app)

    assert created["location_name"] == "Test City"
    assert created["forecast"] is app.current_weather_data.minutely_precipitation
    assert created["timezone_name"] == "America/New_York"
    assert created["shown"] is True
    assert created["destroyed"] is True
