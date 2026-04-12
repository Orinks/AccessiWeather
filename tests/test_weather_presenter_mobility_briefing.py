from __future__ import annotations

from datetime import UTC, datetime, timedelta

from accessiweather.display.weather_presenter import WeatherPresenter
from accessiweather.models import (
    AppSettings,
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    MinutelyPrecipitationForecast,
    MinutelyPrecipitationPoint,
    WeatherData,
)


def test_weather_presenter_populates_forecast_mobility_briefing():
    now = datetime(2026, 4, 12, 12, 0, tzinfo=UTC)
    weather_data = WeatherData(
        location=Location(name="Testville", latitude=40.0, longitude=-75.0, timezone="UTC"),
        current=CurrentConditions(visibility_miles=10.0),
        forecast=Forecast(
            periods=[
                ForecastPeriod(
                    name="Today",
                    temperature=70.0,
                    temperature_low=54.0,
                    temperature_unit="F",
                    short_forecast="Cloudy",
                )
            ]
        ),
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

    presenter = WeatherPresenter(AppSettings(hourly_forecast_hours=2))
    presentation = presenter.present(weather_data)

    assert presentation.forecast is not None
    assert presentation.forecast.mobility_briefing is not None
    assert "Dry for 20 minutes" in presentation.forecast.mobility_briefing
    assert presentation.forecast.hourly_section_text.startswith(
        "Hourly forecast:\nMobility briefing:"
    )
