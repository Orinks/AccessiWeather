"""Tests for Open-Meteo parser behavior."""

from accessiweather.weather_client_openmeteo import (
    parse_openmeteo_current_conditions,
    parse_openmeteo_forecast,
)


def test_parse_openmeteo_forecast_sets_start_time_for_periods():
    data = {
        "daily": {
            "time": ["2026-02-27", "2026-02-28"],
            "temperature_2m_max": [50.0, 52.0],
            "weather_code": [3, 2],
        }
    }

    forecast = parse_openmeteo_forecast(data)

    assert len(forecast.periods) == 2
    assert all(p.start_time is not None for p in forecast.periods)


def test_current_drizzle_not_mapped_to_snow_when_snowfall_is_zero():
    data = {
        "current": {
            "temperature_2m": 41.0,
            "relative_humidity_2m": 95,
            "apparent_temperature": 39.0,
            "weather_code": 71,  # snow code from provider
            "wind_speed_10m": 8.0,
            "wind_direction_10m": 180,
            "pressure_msl": 1010,
            "rain": 0.01,
            "showers": 0.0,
            "snowfall": 0.0,
            "snow_depth": 0.0,
            "visibility": 12000,
        },
        "current_units": {
            "temperature_2m": "°F",
            "apparent_temperature": "°F",
            "wind_speed_10m": "mph",
            "pressure_msl": "hPa",
            "snow_depth": "m",
        },
        "daily": {"sunrise": [], "sunset": [], "uv_index_max": []},
    }

    current = parse_openmeteo_current_conditions(data)

    assert current.condition is not None
    assert "snow" not in current.condition.lower()
    assert current.precipitation_type == ["rain"]


def test_current_mixed_precip_fields_return_mixed_condition():
    data = {
        "current": {
            "temperature_2m": 33.0,
            "relative_humidity_2m": 97,
            "apparent_temperature": 28.0,
            "weather_code": 61,  # rain code
            "wind_speed_10m": 12.0,
            "wind_direction_10m": 20,
            "pressure_msl": 1005,
            "rain": 0.01,
            "showers": 0.0,
            "snowfall": 0.01,
            "snow_depth": 0.2,
            "visibility": 6000,
        },
        "current_units": {
            "temperature_2m": "°F",
            "apparent_temperature": "°F",
            "wind_speed_10m": "mph",
            "pressure_msl": "hPa",
            "snow_depth": "m",
        },
        "daily": {"sunrise": [], "sunset": [], "uv_index_max": []},
    }

    current = parse_openmeteo_current_conditions(data)

    assert current.condition == "Mixed rain and snow"
    assert current.precipitation_type == ["rain", "snow"]
