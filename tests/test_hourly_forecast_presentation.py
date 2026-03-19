from __future__ import annotations

from datetime import UTC, datetime

from accessiweather.display.presentation.forecast import (
    build_hourly_summary,
    render_hourly_fallback,
)
from accessiweather.models import AppSettings, HourlyForecast, HourlyForecastPeriod
from accessiweather.utils import TemperatureUnit


def test_hourly_summary_surfaces_humidity_and_dewpoint_at_standard_verbosity():
    hourly = HourlyForecast(
        periods=[
            HourlyForecastPeriod(
                start_time=datetime(2026, 3, 19, 12, tzinfo=UTC),
                temperature=72.0,
                temperature_unit="F",
                short_forecast="Partly Cloudy",
                humidity=55,
                dewpoint_f=54.0,
                wind_speed="8 mph",
                wind_direction="S",
            )
        ]
    )
    settings = AppSettings(verbosity_level="standard", hourly_forecast_hours=1)

    summary = build_hourly_summary(hourly, TemperatureUnit.FAHRENHEIT, settings=settings)

    assert summary[0].humidity == "55%"
    assert summary[0].dewpoint == "54°F"


def test_hourly_fallback_includes_humidity_and_dewpoint():
    lines = render_hourly_fallback(
        [
            build_hourly_summary(
                HourlyForecast(
                    periods=[
                        HourlyForecastPeriod(
                            start_time=datetime(2026, 3, 19, 12, tzinfo=UTC),
                            temperature=72.0,
                            temperature_unit="F",
                            short_forecast="Partly Cloudy",
                            humidity=55,
                            dewpoint_f=54.0,
                            wind_speed="8 mph",
                            wind_direction="S",
                        )
                    ]
                ),
                TemperatureUnit.FAHRENHEIT,
                settings=AppSettings(verbosity_level="standard", hourly_forecast_hours=1),
            )
        ][0],
        hours=1,
    )

    assert "Humidity 55%" in lines
    assert "Dewpoint 54°F" in lines
