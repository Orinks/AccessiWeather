"""Tests for Open-Meteo parsing helpers."""

from accessiweather.weather_client_openmeteo import (
    parse_openmeteo_current_conditions,
    parse_openmeteo_hourly_forecast,
)


def test_parse_openmeteo_current_conditions_handles_z_times():
    """Ensure current conditions parsing accepts ISO timestamps with trailing Z."""
    payload = {
        "current": {
            "time": "2024-06-15T12:00:00Z",
            "temperature_2m": 72.0,
            "relative_humidity_2m": 55,
            "apparent_temperature": 70.0,
            "weather_code": 1,
            "wind_speed_10m": 8.0,
            "wind_direction_10m": 180,
            "pressure_msl": 1015.0,
        },
        "current_units": {
            "temperature_2m": "°F",
            "relative_humidity_2m": "%",
            "apparent_temperature": "°F",
            "wind_speed_10m": "mph",
            "pressure_msl": "hPa",
        },
        "daily": {
            "sunrise": ["2024-06-15T05:30:00Z"],
            "sunset": ["2024-06-15T20:45:00Z"],
        },
    }

    current = parse_openmeteo_current_conditions(payload)

    assert current.last_updated is not None
    assert current.sunrise_time is not None
    assert current.sunset_time is not None


def test_parse_openmeteo_hourly_forecast_handles_z_times():
    """Ensure hourly forecast parsing accepts ISO timestamps with trailing Z."""
    payload = {
        "hourly": {
            "time": ["2024-06-15T12:00:00Z"],
            "temperature_2m": [72.0],
            "weather_code": [1],
            "wind_speed_10m": [8.0],
            "wind_direction_10m": [90],
            "pressure_msl": [1015.0],
        }
    }

    hourly = parse_openmeteo_hourly_forecast(payload)

    assert hourly.periods
    assert hourly.periods[0].start_time is not None
