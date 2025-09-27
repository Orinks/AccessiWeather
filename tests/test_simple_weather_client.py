"""Tests for WeatherClient parsing helpers."""

from datetime import UTC, datetime

import pytest

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
    assert current.last_updated.tzinfo is not None
    assert current.last_updated == datetime(2025, 9, 27, 4, 10, tzinfo=UTC)


@pytest.mark.unit
def test_parse_openmeteo_current_conditions_converts_units():
    client = WeatherClient()
    sample = {
        "current": {
            "time": "2025-09-27T00:30",
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
    assert current.last_updated == datetime(2025, 9, 27, 0, 30)


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
    assert current.last_updated == datetime.fromtimestamp(1727414400, tz=UTC)
