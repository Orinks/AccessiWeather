from __future__ import annotations

from datetime import UTC, datetime, timedelta

from accessiweather.models import (
    CurrentConditions,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    MinutelyPrecipitationForecast,
    MinutelyPrecipitationPoint,
    WeatherData,
)


def _make_location() -> Location:
    return Location(name="Testville", latitude=40.0, longitude=-75.0, timezone="UTC")


def test_build_mobility_briefing_uses_minutely_precip_start_and_hourly_gusts():
    from accessiweather.services.mobility_briefing import build_mobility_briefing

    now = datetime(2026, 4, 12, 12, 0, tzinfo=UTC)
    minutely = MinutelyPrecipitationForecast(
        points=[
            MinutelyPrecipitationPoint(time=now + timedelta(minutes=i), precipitation_intensity=0.0)
            for i in range(30)
        ]
        + [
            MinutelyPrecipitationPoint(
                time=now + timedelta(minutes=i),
                precipitation_intensity=0.08,
                precipitation_type="rain",
            )
            for i in range(30, 91)
        ]
    )
    hourly = HourlyForecast(
        periods=[
            HourlyForecastPeriod(
                start_time=now,
                short_forecast="Cloudy",
                wind_speed="10 mph",
                wind_gust_mph=15.0,
                visibility_miles=10.0,
            ),
            HourlyForecastPeriod(
                start_time=now + timedelta(hours=1),
                short_forecast="Light Rain",
                wind_speed="15 mph",
                wind_gust_mph=28.0,
                visibility_miles=8.0,
            ),
        ]
    )
    weather_data = WeatherData(
        location=_make_location(),
        current=CurrentConditions(visibility_miles=10.0),
        hourly_forecast=hourly,
        minutely_precipitation=minutely,
    )

    result = build_mobility_briefing(weather_data, reference_time=now)

    assert result is not None
    assert "Dry for 30 minutes" in result
    assert "gusts increase" in result


def test_build_mobility_briefing_falls_back_to_hourly_when_minutely_missing():
    from accessiweather.services.mobility_briefing import build_mobility_briefing

    now = datetime(2026, 4, 12, 12, 0, tzinfo=UTC)
    hourly = HourlyForecast(
        periods=[
            HourlyForecastPeriod(
                start_time=now,
                short_forecast="Mostly Cloudy",
                precipitation_probability=10.0,
                wind_gust_mph=14.0,
                visibility_miles=10.0,
            ),
            HourlyForecastPeriod(
                start_time=now + timedelta(hours=1),
                short_forecast="Rain Likely",
                precipitation_probability=75.0,
                wind_gust_mph=18.0,
                visibility_miles=4.0,
            ),
        ]
    )
    weather_data = WeatherData(
        location=_make_location(),
        current=CurrentConditions(visibility_miles=10.0),
        hourly_forecast=hourly,
        minutely_precipitation=None,
    )

    result = build_mobility_briefing(weather_data, reference_time=now)

    assert result is not None
    assert "rain likely" in result.lower()
    assert "visibility" in result.lower()


def test_build_mobility_briefing_returns_none_when_no_near_term_signals_exist():
    from accessiweather.services.mobility_briefing import build_mobility_briefing

    now = datetime(2026, 4, 12, 12, 0, tzinfo=UTC)
    hourly = HourlyForecast(
        periods=[
            HourlyForecastPeriod(
                start_time=now,
                short_forecast="Clear",
                precipitation_probability=0.0,
                wind_gust_mph=8.0,
                visibility_miles=10.0,
            ),
            HourlyForecastPeriod(
                start_time=now + timedelta(hours=1),
                short_forecast="Clear",
                precipitation_probability=0.0,
                wind_gust_mph=9.0,
                visibility_miles=10.0,
            ),
        ]
    )
    weather_data = WeatherData(
        location=_make_location(),
        current=CurrentConditions(visibility_miles=10.0),
        hourly_forecast=hourly,
    )

    result = build_mobility_briefing(weather_data, reference_time=now)

    assert result is None


def test_build_mobility_briefing_infers_reference_time_from_forecast_timeline():
    from accessiweather.services.mobility_briefing import build_mobility_briefing

    now = datetime(2026, 4, 12, 12, 0, tzinfo=UTC)
    weather_data = WeatherData(
        location=_make_location(),
        current=CurrentConditions(visibility_miles=10.0),
        hourly_forecast=HourlyForecast(
            periods=[
                HourlyForecastPeriod(
                    start_time=now,
                    short_forecast="Cloudy",
                    wind_gust_mph=15.0,
                    visibility_miles=10.0,
                ),
                HourlyForecastPeriod(
                    start_time=now + timedelta(hours=1),
                    short_forecast="Light Rain",
                    wind_gust_mph=28.0,
                    visibility_miles=8.0,
                ),
            ]
        ),
        minutely_precipitation=MinutelyPrecipitationForecast(
            points=[
                MinutelyPrecipitationPoint(
                    time=now + timedelta(minutes=i), precipitation_intensity=0.0
                )
                for i in range(20)
            ]
            + [
                MinutelyPrecipitationPoint(
                    time=now + timedelta(minutes=i),
                    precipitation_intensity=0.08,
                    precipitation_type="rain",
                )
                for i in range(20, 91)
            ]
        ),
    )

    result = build_mobility_briefing(weather_data)

    assert result is not None
    assert "Dry for 20 minutes" in result
