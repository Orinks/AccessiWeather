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
    SourceAttribution,
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


def test_weather_presenter_source_attribution_notes_current_hourly_minutely_disagreement():
    now = datetime(2026, 4, 27, 20, 0, tzinfo=UTC)
    weather_data = WeatherData(
        location=Location(name="Carrollton, Texas", latitude=32.95373, longitude=-96.89028),
        current=CurrentConditions(condition="Thunderstorms", temperature_f=91.0),
        forecast=Forecast(periods=[ForecastPeriod(name="Tonight", short_forecast="Partly Cloudy")]),
        hourly_forecast=HourlyForecast(
            periods=[
                HourlyForecastPeriod(
                    start_time=now,
                    temperature=91.0,
                    temperature_unit="F",
                    short_forecast="Mostly Clear",
                    precipitation_probability=14,
                )
            ],
            summary="Thunderstorms starting later this evening.",
        ),
        minutely_precipitation=MinutelyPrecipitationForecast(
            summary="Clear for the hour.",
            points=[
                MinutelyPrecipitationPoint(
                    time=now + timedelta(minutes=i),
                    precipitation_intensity=0.0,
                    precipitation_probability=0.0,
                    precipitation_type="none",
                )
                for i in range(3)
            ],
        ),
        source_attribution=SourceAttribution(
            field_sources={
                "condition": "nws",
                "hourly_source": "nws",
                "hourly_summary": "pirateweather",
            },
            contributing_sources={"nws", "pirateweather"},
        ),
    )

    presenter = WeatherPresenter(AppSettings(hourly_forecast_hours=1))
    presentation = presenter.present(weather_data)

    assert presentation.source_attribution is not None
    assert (
        "Data note: current conditions from National Weather Service report Thunderstorms; "
        "hourly forecast from National Weather Service says Mostly Clear; "
        "minute-by-minute precipitation outlook from Pirate Weather says Clear for the hour."
        in presentation.source_attribution.summary_text
    )


def test_weather_presenter_source_attribution_omits_note_when_sources_agree():
    now = datetime(2026, 4, 27, 20, 0, tzinfo=UTC)
    weather_data = WeatherData(
        location=Location(name="Carrollton, Texas", latitude=32.95373, longitude=-96.89028),
        current=CurrentConditions(condition="Mostly Clear", temperature_f=91.0),
        forecast=Forecast(periods=[ForecastPeriod(name="Tonight", short_forecast="Partly Cloudy")]),
        hourly_forecast=HourlyForecast(
            periods=[
                HourlyForecastPeriod(
                    start_time=now,
                    temperature=91.0,
                    temperature_unit="F",
                    short_forecast="Mostly Clear",
                )
            ]
        ),
        minutely_precipitation=MinutelyPrecipitationForecast(
            summary="Clear for the hour.",
            points=[
                MinutelyPrecipitationPoint(
                    time=now,
                    precipitation_intensity=0.0,
                    precipitation_probability=0.0,
                )
            ],
        ),
        source_attribution=SourceAttribution(
            field_sources={"condition": "nws", "hourly_source": "nws"},
            contributing_sources={"nws", "pirateweather"},
        ),
    )

    presenter = WeatherPresenter(AppSettings(hourly_forecast_hours=1))
    presentation = presenter.present(weather_data)

    assert presentation.source_attribution is not None
    assert "Data note:" not in presentation.source_attribution.summary_text
