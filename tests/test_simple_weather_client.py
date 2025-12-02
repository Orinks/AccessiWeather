"""Tests for WeatherClient parsing helpers."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from accessiweather import weather_client_nws
from accessiweather.models import (
    AppSettings,
    CurrentConditions,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)
from accessiweather.openmeteo_client import OpenMeteoApiClient
from accessiweather.weather_client import WeatherClient


@pytest.mark.unit
def test_parse_nws_current_conditions_converts_units():
    client = WeatherClient()
    sample = {
        "properties": {
            "temperature": {"value": 20.0},
            "dewpoint": {"value": 12.0},
            "relativeHumidity": {"value": 55.4},
            "windSpeed": {"value": 3.6, "unitCode": "wmoUnit:m_s-1"},
            "windDirection": {"value": 270},
            "barometricPressure": {"value": 100000.0},
            "visibility": {"value": 10000.0},
            "timestamp": "2025-09-27T04:10:00+00:00",
            "textDescription": "Clear",
        }
    }

    current = client._parse_nws_current_conditions(sample)

    assert current.temperature_f == pytest.approx(68.0, rel=1e-3)
    assert current.dewpoint_c == pytest.approx(12.0, rel=1e-3)
    assert current.dewpoint_f == pytest.approx(53.6, rel=1e-3)
    assert current.humidity == 55  # rounded
    assert current.wind_speed_mph == pytest.approx(8.053, rel=1e-3)
    assert current.wind_speed_kph == pytest.approx(12.96, rel=1e-3)
    assert current.wind_direction == 270
    assert current.pressure_in == pytest.approx(29.53, rel=1e-2)
    assert current.pressure_mb == pytest.approx(1000.0, rel=1e-3)
    assert current.visibility_miles == pytest.approx(6.213, rel=1e-3)
    assert current.visibility_km == pytest.approx(10.0, rel=1e-3)


@pytest.mark.unit
def test_parse_openmeteo_current_conditions_converts_units():
    client = WeatherClient()
    sample = {
        "current": {
            "time": "2025-09-27T00:30-04:00",
            "temperature_2m": 64.0,
            "relative_humidity_2m": 82.3,
            "apparent_temperature": 63.2,
            "weather_code": 1,
            "wind_speed_10m": 5.0,
            "wind_direction_10m": 135,
            "pressure_msl": 1011.5,
        },
        "current_units": {
            "temperature_2m": "°F",
            "relative_humidity_2m": "%",
            "apparent_temperature": "°F",
            "wind_speed_10m": "mph",
            "wind_direction_10m": "°",
            "pressure_msl": "hPa",
        },
        "daily": {
            "sunrise": ["2025-09-27T06:45-04:00"],
            "sunset": ["2025-09-27T18:15-04:00"],
            "uv_index_max": [7.5],
        },
    }

    current = client._parse_openmeteo_current_conditions(sample)

    assert current.temperature_f == pytest.approx(64.0, rel=1e-3)
    assert current.temperature_c == pytest.approx(17.777, rel=1e-3)
    assert current.humidity == 82
    assert current.wind_speed_mph == pytest.approx(5.0, rel=1e-3)
    assert current.wind_speed_kph == pytest.approx(8.0467, rel=1e-3)
    assert current.wind_direction == 135
    assert current.pressure_mb == pytest.approx(1011.5, rel=1e-3)
    assert current.pressure_in == pytest.approx(29.856, rel=1e-3)
    assert current.feels_like_f == pytest.approx(63.2, rel=1e-3)
    assert current.feels_like_c == pytest.approx(17.333, rel=1e-3)
    assert current.dewpoint_f is not None
    # After timezone fix, these should be timezone-aware in location's local timezone
    # Using UTC-4 as example (Eastern Daylight Time)
    from datetime import timedelta, timezone

    edt = timezone(timedelta(hours=-4))
    assert current.sunrise_time == datetime(2025, 9, 27, 6, 45, tzinfo=edt)
    assert current.sunset_time == datetime(2025, 9, 27, 18, 15, tzinfo=edt)
    assert current.uv_index == pytest.approx(7.5, rel=1e-3)


@pytest.mark.unit
def test_parse_openmeteo_current_conditions_handles_missing_fields():
    client = WeatherClient()
    sample = {
        "current": {
            "time": "2025-09-27T01:00",
            "temperature_2m": 68.0,
            "relative_humidity_2m": None,
            "apparent_temperature": None,
            "weather_code": None,
        },
        "current_units": {
            "temperature_2m": "°F",
            "apparent_temperature": "°F",
        },
        "daily": {},
    }

    current = client._parse_openmeteo_current_conditions(sample)

    assert current.temperature_f == pytest.approx(68.0, rel=1e-3)
    assert current.condition is None
    assert current.humidity is None
    assert current.feels_like_f is None


@pytest.mark.unit
def test_parse_openmeteo_forecast_handles_partial_arrays():
    client = WeatherClient()
    sample = {
        "daily": {
            "time": ["2025-09-27", "2025-09-28"],
            "temperature_2m_max": [77.0],
            "weather_code": [80, 81],
        }
    }

    forecast = client._parse_openmeteo_forecast(sample)

    assert len(forecast.periods) == 1
    assert forecast.periods[0].short_forecast == "Slight rain showers"


@pytest.mark.unit
def test_parse_openmeteo_hourly_forecast_handles_sparse_payload():
    client = WeatherClient()
    sample = {
        "hourly": {
            "time": ["2025-09-27T01:00", "2025-09-27T02:00"],
            "temperature_2m": [70.0],
            "weather_code": [None, 80],
            "wind_speed_10m": [5.0],
            "wind_direction_10m": [180],
            "pressure_msl": [1015.0],
        }
    }

    hourly = client._parse_openmeteo_hourly_forecast(sample)

    assert len(hourly.periods) == 2
    first_period, second_period = hourly.periods
    assert first_period.short_forecast is None
    assert second_period.short_forecast == "Slight rain showers"


@pytest.mark.unit
def test_openmeteo_client_weather_description_accepts_string_codes():
    """OpenMeteo client should provide descriptions for stringified codes."""
    assert OpenMeteoApiClient.get_weather_description(80) == "Slight rain showers"
    assert OpenMeteoApiClient.get_weather_description("80") == "Slight rain showers"


@pytest.mark.unit
def test_parse_nws_forecast_handles_qv_payloads():
    data = {
        "properties": {
            "periods": [
                {
                    "name": "Today",
                    "temperature": {"value": 70},
                    "temperatureUnit": {"value": "F"},
                    "shortForecast": "Sunny",
                    "windSpeed": {"value": 15, "unitCode": "wmoUnit:km_h-1"},
                    "windDirection": {"value": 220},
                }
            ]
        }
    }

    forecast = weather_client_nws.parse_nws_forecast(data)

    assert len(forecast.periods) == 1
    period = forecast.periods[0]
    assert period.temperature == 70.0
    assert period.temperature_unit == "F"
    assert period.wind_speed.startswith("9")  # 15 km/h -> ~9 mph
    assert period.wind_direction == "220"


@pytest.mark.unit
def test_parse_nws_hourly_forecast_handles_qv_payloads():
    data = {
        "properties": {
            "periods": [
                {
                    "startTime": "2025-01-01T00:00:00+00:00",
                    "endTime": "2025-01-01T01:00:00+00:00",
                    "temperature": {"value": 65},
                    "temperatureUnit": {"value": "F"},
                    "shortForecast": "Clear",
                    "windSpeed": {"value": 10, "unitCode": "wmoUnit:mi_h-1"},
                    "windDirection": {"value": "NW"},
                }
            ]
        }
    }

    hourly = weather_client_nws.parse_nws_hourly_forecast(data)

    assert len(hourly.periods) == 1
    period = hourly.periods[0]
    assert period.temperature == 65.0
    assert period.temperature_unit == "F"
    assert period.wind_speed.startswith("10")
    assert period.wind_direction == "NW"


@pytest.mark.unit
def test_parse_nws_hourly_forecast_converts_celsius_payloads():
    data = {
        "properties": {
            "periods": [
                {
                    "startTime": "2025-01-01T00:00:00+00:00",
                    "endTime": "2025-01-01T01:00:00+00:00",
                    "temperature": {"unitCode": "wmoUnit:degC", "value": 7.7777777778},
                    # temperatureUnit intentionally omitted to mimic Feature-Flag payloads
                    "shortForecast": "Cloudy",
                    "windSpeed": {"unitCode": "wmoUnit:km_h-1", "value": 28.0},
                    "windDirection": "SW",
                }
            ]
        }
    }

    hourly = weather_client_nws.parse_nws_hourly_forecast(data)

    assert len(hourly.periods) == 1
    period = hourly.periods[0]
    assert period.temperature == pytest.approx(46.0, rel=1e-3)
    assert period.temperature_unit == "F"
    assert period.wind_speed.startswith("17")
    assert period.wind_direction == "SW"


@pytest.mark.unit
def test_parse_nws_forecast_converts_celsius_payloads():
    data = {
        "properties": {
            "periods": [
                {
                    "name": "Today",
                    "temperature": {"unitCode": "wmoUnit:degC", "value": 10},
                    "shortForecast": "Rain Showers Likely",
                    "windSpeed": {"unitCode": "wmoUnit:km_h-1", "value": 30.0},
                    "windDirection": "SW",
                }
            ]
        }
    }

    forecast = weather_client_nws.parse_nws_forecast(data)

    assert len(forecast.periods) == 1
    period = forecast.periods[0]
    assert period.temperature == pytest.approx(50.0, rel=1e-3)
    assert period.temperature_unit == "F"
    assert period.wind_speed.startswith("19")
    assert period.wind_direction == "SW"


@pytest.mark.unit
def test_weather_client_computes_temperature_trend():
    settings = AppSettings(trend_insights_enabled=True, trend_hours=24)
    client = WeatherClient(settings=settings)
    location = Location(name="Test", latitude=35.0, longitude=140.0)
    weather_data = WeatherData(
        location=location,
        current=CurrentConditions(temperature_f=70.0, pressure_mb=1015.0, pressure_in=29.97),
        hourly_forecast=HourlyForecast(
            periods=[
                HourlyForecastPeriod(
                    start_time=datetime.now() + timedelta(hours=24),
                    temperature=80.0,
                    temperature_unit="F",
                    pressure_mb=1012.0,
                    pressure_in=29.88,
                )
            ]
        ),
    )

    client._apply_trend_insights(weather_data)

    assert weather_data.trend_insights
    metrics = {trend.metric for trend in weather_data.trend_insights}
    assert "temperature" in metrics


@pytest.mark.unit
def test_weather_client_skips_pressure_trend_when_disabled():
    settings = AppSettings(
        trend_insights_enabled=True,
        trend_hours=24,
        show_pressure_trend=False,
    )
    client = WeatherClient(settings=settings)
    location = Location(name="Test", latitude=35.0, longitude=140.0)
    weather_data = WeatherData(
        location=location,
        current=CurrentConditions(temperature_f=70.0, pressure_mb=1015.0, pressure_in=29.97),
        hourly_forecast=HourlyForecast(
            periods=[
                HourlyForecastPeriod(
                    start_time=datetime.now() + timedelta(hours=24),
                    temperature=80.0,
                    temperature_unit="F",
                    pressure_mb=1012.0,
                    pressure_in=29.88,
                )
            ]
        ),
    )

    client._apply_trend_insights(weather_data)

    metrics = {trend.metric for trend in weather_data.trend_insights}
    assert "pressure" not in metrics
    assert "temperature" in metrics


@pytest.mark.asyncio
async def test_weather_client_merges_meteoalarm_alerts():
    class DummyMeteoAlarm:
        async def fetch_alerts(self, location):
            return WeatherAlerts(
                alerts=[
                    WeatherAlert(
                        title="Storm Warning",
                        description="Severe storm expected",
                        severity="Severe",
                        urgency="Immediate",
                        certainty="Likely",
                        source="MeteoAlarm",
                    )
                ]
            )

    settings = AppSettings(international_alerts_enabled=True)
    client = WeatherClient(settings=settings, meteoalarm_client=DummyMeteoAlarm())
    location = Location(name="Paris", latitude=48.8566, longitude=2.3522)
    weather_data = WeatherData(location=location, alerts=WeatherAlerts(alerts=[]))

    await client._merge_international_alerts(weather_data, location)

    assert weather_data.alerts is not None
    assert weather_data.alerts.alerts
    assert weather_data.alerts.alerts[0].source == "MeteoAlarm"


@pytest.mark.asyncio
async def test_enrich_with_aviation_data_populates_taf():
    settings = AppSettings()
    client = WeatherClient(settings=settings)
    location = Location(name="Dulles", latitude=38.9445, longitude=-77.4558)
    weather_data = WeatherData(location=location)

    taf_text = "TAF KIAD 010000Z 0100/0206 17008KT P6SM SCT040"

    with (
        patch(
            "accessiweather.weather_client_nws.get_nws_primary_station_info",
            new=AsyncMock(return_value=("KIAD", "Dulles International")),
        ) as station_mock,
        patch(
            "accessiweather.weather_client_nws.get_nws_tafs",
            new=AsyncMock(return_value=taf_text),
        ) as taf_mock,
        patch(
            "accessiweather.weather_client_nws.get_nws_station_metadata",
            new=AsyncMock(
                return_value={"properties": {"name": "Dulles International", "cwa": "ZDC"}}
            ),
        ) as metadata_mock,
    ):
        await client._enrich_with_aviation_data(weather_data, location)

    station_mock.assert_awaited()
    taf_mock.assert_awaited_once()
    metadata_mock.assert_awaited_once()

    aviation = weather_data.aviation
    assert aviation is not None
    assert aviation.station_id == "KIAD"
    assert aviation.raw_taf == taf_text
    assert aviation.decoded_taf is not None


@pytest.mark.asyncio
async def test_get_aviation_weather_returns_decoded_taf():
    client = WeatherClient()
    taf_text = "TAF KIAD 010000Z 0100/0206 17008KT P6SM SCT040"

    with (
        patch(
            "accessiweather.weather_client.nws_client.get_nws_tafs",
            new=AsyncMock(return_value=taf_text),
        ) as taf_mock,
        patch(
            "accessiweather.weather_client.nws_client.get_nws_station_metadata",
            new=AsyncMock(return_value={"properties": {"name": "Dulles International"}}),
        ),
    ):
        aviation = await client.get_aviation_weather("kiad")

    taf_mock.assert_awaited_once()
    assert aviation.station_id == "KIAD"
    assert aviation.raw_taf == taf_text
    assert aviation.decoded_taf is not None
    assert not aviation.decoded_taf.lower().startswith("no taf available")


@pytest.mark.asyncio
async def test_get_aviation_weather_requires_station():
    client = WeatherClient()
    with pytest.raises(ValueError):
        await client.get_aviation_weather("")


@pytest.mark.asyncio
async def test_get_aviation_weather_handles_nil_taf():
    client = WeatherClient()
    nil_taf = "TAF KATL 010000Z NIL"

    with (
        patch(
            "accessiweather.weather_client.nws_client.get_nws_tafs",
            new=AsyncMock(return_value=nil_taf),
        ),
        patch(
            "accessiweather.weather_client.nws_client.get_nws_station_metadata",
            new=AsyncMock(return_value={"properties": {"name": "Hartsfield-Jackson Atlanta"}}),
        ),
    ):
        aviation = await client.get_aviation_weather("KATL")

    assert aviation.raw_taf is None
    assert aviation.decoded_taf is None
    assert not aviation.has_taf()


@pytest.mark.asyncio
async def test_get_aviation_weather_filters_advisories():
    client = WeatherClient()
    taf_text = "TAF KJFK 010000Z 0100/0206 17008KT P6SM SCT040"
    sigmets = [
        {
            "name": "SIGMET ALPHA",
            "description": "Impacts CWA ZNY and station KJFK",
            "regions": ["ZNY"],
        },
        {
            "name": "SIGMET BRAVO",
            "description": "Western region ZOA",
            "regions": ["ZOA"],
        },
    ]
    cwas = [
        {
            "event": "CWA 101",
            "description": "Advisory covering ZNY area with low ceilings",
            "cwsuId": "ZNY",
        },
        {
            "event": "CWA 202",
            "description": "Applies to ZSE",
            "cwsuId": "ZSE",
        },
    ]

    with (
        patch(
            "accessiweather.weather_client.nws_client.get_nws_tafs",
            new=AsyncMock(return_value=taf_text),
        ),
        patch(
            "accessiweather.weather_client.nws_client.get_nws_station_metadata",
            new=AsyncMock(
                return_value={
                    "properties": {
                        "name": "John F. Kennedy International",
                        "cwa": "ZNY",
                        "country": "US",
                    }
                }
            ),
        ),
        patch(
            "accessiweather.weather_client.nws_client.get_nws_sigmets",
            new=AsyncMock(return_value=sigmets),
        ) as sigmet_mock,
        patch(
            "accessiweather.weather_client.nws_client.get_nws_cwas",
            new=AsyncMock(return_value=cwas),
        ) as cwa_mock,
    ):
        aviation = await client.get_aviation_weather(
            "KJFK", include_sigmets=True, include_cwas=True
        )

    sigmet_mock.assert_awaited_once()
    cwa_mock.assert_awaited_once()
    assert len(aviation.active_sigmets) == 1
    assert aviation.active_sigmets[0]["name"] == "SIGMET ALPHA"
    assert len(aviation.active_cwas) == 1
    assert aviation.active_cwas[0]["event"] == "CWA 101"


@pytest.mark.unit
def test_parse_visual_crossing_current_conditions():
    from accessiweather.visual_crossing_client import VisualCrossingClient

    client = VisualCrossingClient(api_key="test")
    sample = {
        "currentConditions": {
            "temp": 72.0,
            "feelslike": 73.0,
            "humidity": 58.4,
            "dew": 56.0,
            "windspeed": 7.0,
            "winddir": 200,
            "pressure": 30.12,
            "visibility": 9.5,
            "datetimeEpoch": 1727414400,
            "conditions": "Partly Cloudy",
        }
    }

    current = client._parse_current_conditions(sample)

    assert current.temperature_f == 72.0
    assert current.temperature_c == pytest.approx(22.222, rel=1e-3)
    assert current.dewpoint_f == pytest.approx(56.0, rel=1e-3)
    assert current.dewpoint_c == pytest.approx(13.333, rel=1e-3)
    assert current.humidity == 58
    assert current.wind_speed_mph == 7.0
    assert current.wind_speed_kph == pytest.approx(11.265, rel=1e-3)
    assert current.wind_direction == 200
    assert current.pressure_in == 30.12
    assert current.pressure_mb == pytest.approx(30.12 * 33.8639, rel=1e-3)
    assert current.visibility_miles == 9.5
    assert current.visibility_km == pytest.approx(15.288, rel=1e-3)
    assert current.feels_like_f == 73.0
    assert current.feels_like_c == pytest.approx(22.777, rel=1e-3)
