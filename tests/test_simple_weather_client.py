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
