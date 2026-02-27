"""Tests for Open-Meteo forecast parser behavior."""

from accessiweather.weather_client_openmeteo import parse_openmeteo_forecast


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
