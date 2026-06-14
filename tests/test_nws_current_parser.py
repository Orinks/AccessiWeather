"""Regression tests for NWS current-condition parsing."""

from __future__ import annotations

import pytest

from accessiweather.weather_client_nws import parse_nws_current_conditions


def test_parse_nws_current_conditions_normalizes_measurements_to_current_model():
    payload = {
        "properties": {
            "temperature": {"value": 0.0, "unitCode": "wmoUnit:degC"},
            "dewpoint": {"value": -5.0, "unitCode": "wmoUnit:degC"},
            "relativeHumidity": {"value": 72.4, "unitCode": "wmoUnit:percent"},
            "windSpeed": {"value": 10.0, "unitCode": "wmoUnit:km_h-1"},
            "windDirection": {"value": 270},
            "barometricPressure": {"value": 101325.0, "unitCode": "wmoUnit:Pa"},
            "visibility": {"value": 1609.344, "unitCode": "wmoUnit:m"},
            "windChill": {"value": -8.0, "unitCode": "wmoUnit:degC"},
            "heatIndex": {"value": None, "unitCode": "wmoUnit:degC"},
            "textDescription": "Mostly Cloudy",
            "uvIndex": {"value": "2.5"},
        }
    }

    current = parse_nws_current_conditions(payload)

    assert current.temperature_f == 32.0
    assert current.temperature_c == 0.0
    assert current.dewpoint_f == pytest.approx(23.0)
    assert current.humidity == 72
    assert current.wind_speed_mph == pytest.approx(6.21, abs=0.01)
    assert current.wind_speed_kph == 10.0
    assert current.wind_direction == 270
    assert current.pressure_mb == pytest.approx(1013.25)
    assert current.pressure_in == pytest.approx(29.92, abs=0.01)
    assert current.visibility_miles == pytest.approx(1.0)
    assert current.visibility_km == pytest.approx(1.609344)
    assert current.feels_like_f == pytest.approx(17.6)
    assert current.wind_chill_f == pytest.approx(17.6)
    assert current.heat_index_f is None
    assert current.condition == "Mostly Cloudy"
    assert current.uv_index == 2.5
