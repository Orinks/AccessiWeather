from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from accessiweather.display.presentation.forecast import (
    build_forecast,
    build_hourly_section_text,
    build_hourly_summary,
    render_hourly_fallback,
)
from accessiweather.models import (
    AppSettings,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    MarineForecast,
    MarineForecastPeriod,
)
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


def test_hourly_section_text_omits_empty_section_without_summary():
    section_text = build_hourly_section_text([], hours=6)

    assert section_text == ""


def test_build_forecast_exposes_daily_and_hourly_sections():
    forecast = Forecast(
        periods=[
            ForecastPeriod(
                name="Today",
                temperature=70.0,
                temperature_low=54.0,
                temperature_unit="F",
                short_forecast="Sunny",
            )
        ],
        summary="Dry and pleasant through tomorrow.",
    )
    hourly = HourlyForecast(
        periods=[
            HourlyForecastPeriod(
                start_time=datetime(2026, 3, 19, 12, tzinfo=UTC),
                temperature=72.0,
                temperature_unit="F",
                short_forecast="Sunny",
            )
        ],
        summary="Clear through mid afternoon.",
    )
    result = build_forecast(
        forecast,
        hourly,
        Location(name="Testville", latitude=40.0, longitude=-75.0),
        TemperatureUnit.FAHRENHEIT,
        settings=AppSettings(hourly_forecast_hours=1),
    )

    assert result.daily_section_text.startswith("Daily forecast for Testville:")
    assert "Overall: Dry and pleasant through tomorrow." in result.daily_section_text
    assert result.hourly_section_text.startswith("Hourly forecast:")
    assert "Hourly outlook: Clear through mid afternoon." in result.hourly_section_text
    assert "Next 1 Hours:" in result.hourly_section_text
    assert result.fallback_text == (f"{result.daily_section_text}\n\n{result.hourly_section_text}")


def test_build_forecast_formats_generated_time_in_location_timezone():
    forecast = Forecast(
        periods=[
            ForecastPeriod(
                name="Today",
                temperature=70.0,
                temperature_low=54.0,
                temperature_unit="F",
                short_forecast="Sunny",
            )
        ],
        generated_at=datetime(2026, 7, 1, 12, tzinfo=UTC),
    )

    result = build_forecast(
        forecast,
        None,
        Location(
            name="London",
            latitude=51.5074,
            longitude=-0.1278,
            timezone="Europe/London",
        ),
        TemperatureUnit.FAHRENHEIT,
        settings=AppSettings(show_timezone_suffix=True),
    )

    expected_generated = "1:00 PM BST"
    assert result.generated_at == expected_generated
    assert f"Forecast generated: {expected_generated}" in result.daily_section_text


def test_build_forecast_includes_marine_section_in_fallback_text():
    forecast = Forecast(
        periods=[
            ForecastPeriod(
                name="Today",
                temperature=70.0,
                temperature_low=54.0,
                temperature_unit="F",
                short_forecast="Sunny",
            )
        ]
    )
    marine = MarineForecast(
        zone_id="ANZ530",
        zone_name="Chesapeake Bay from Pooles Island to Sandy Point",
        forecast_summary="South winds 10 to 15 knots with waves 1 to 2 feet.",
        highlights=["South winds 10 to 15 knots", "Waves 1 to 2 feet"],
        periods=[
            MarineForecastPeriod(
                name="Tonight",
                summary="South winds 10 to 15 knots with waves 1 to 2 feet.",
            )
        ],
    )

    result = build_forecast(
        forecast,
        None,
        Location(name="Annapolis", latitude=38.9784, longitude=-76.4922, marine_mode=True),
        TemperatureUnit.FAHRENHEIT,
        settings=AppSettings(),
        marine=marine,
    )

    assert result.marine_summary == marine.forecast_summary
    assert result.marine_highlights == marine.highlights
    assert "Marine conditions for Annapolis:" in result.marine_section_text
    assert (
        "Marine zone: Chesapeake Bay from Pooles Island to Sandy Point (ANZ530)"
        in result.marine_section_text
    )
    assert "Wind and wave highlights:" in result.marine_section_text
    assert result.fallback_text == (f"{result.daily_section_text}\n\n{result.marine_section_text}")


def test_build_forecast_includes_mobility_briefing_at_top_of_hourly_section():
    forecast = Forecast(
        periods=[
            ForecastPeriod(
                name="Today",
                temperature=70.0,
                temperature_low=54.0,
                temperature_unit="F",
                short_forecast="Sunny",
            )
        ]
    )
    hourly = HourlyForecast(
        periods=[
            HourlyForecastPeriod(
                start_time=datetime(2026, 3, 19, 12, tzinfo=UTC),
                temperature=72.0,
                temperature_unit="F",
                short_forecast="Sunny",
            )
        ]
    )

    result = build_forecast(
        forecast,
        hourly,
        Location(name="Testville", latitude=40.0, longitude=-75.0),
        TemperatureUnit.FAHRENHEIT,
        settings=AppSettings(hourly_forecast_hours=1),
        mobility_briefing="Dry for 30 minutes, then rain likely.",
    )

    assert result.mobility_briefing == "Dry for 30 minutes, then rain likely."
    assert result.hourly_section_text.startswith(
        "Hourly forecast:\nMobility briefing: Dry for 30 minutes, then rain likely."
    )


def test_build_forecast_normalizes_hourly_timezone_label_from_offset_to_location_name():
    london_tz = ZoneInfo("Europe/London")
    forecast = Forecast(
        periods=[
            ForecastPeriod(
                name="Today",
                temperature=70.0,
                temperature_low=54.0,
                temperature_unit="F",
                short_forecast="Sunny",
            )
        ]
    )
    hourly = HourlyForecast(
        periods=[
            HourlyForecastPeriod(
                start_time=datetime(2026, 7, 1, 13, tzinfo=timezone(timedelta(hours=1))),
                temperature=72.0,
                temperature_unit="F",
                short_forecast="Sunny",
            )
        ]
    )

    result = build_forecast(
        forecast,
        hourly,
        Location(
            name="London",
            latitude=51.5074,
            longitude=-0.1278,
            timezone="Europe/London",
        ),
        TemperatureUnit.FAHRENHEIT,
        settings=AppSettings(show_timezone_suffix=True, hourly_forecast_hours=1),
    )

    expected_label = result.hourly_periods[0].time
    assert expected_label == "1:00 PM BST"
    assert expected_label.endswith(london_tz.tzname(datetime(2026, 7, 1, 13, tzinfo=london_tz)))
