"""Raw weather tools preserve measurements, units and valid times."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from hypothesis import (
    given,
    strategies as st,
)

from accessiweather.ai_tool_formatters import (
    format_current_weather,
    format_forecast,
    format_hourly_forecast,
    format_open_meteo_response,
)


def test_raw_current_keeps_zero_units_and_observation_time():
    text = format_current_weather(
        {
            "timezone": "America/New_York",
            "current": {
                "time": "2026-09-12T14:15",
                "temperature_2m": 0,
                "wind_speed_10m": 0,
            },
            "current_units": {"temperature_2m": "°C", "wind_speed_10m": "km/h"},
        }
    )
    assert "0°C" in text and "0km/h" in text
    assert "2026-09-12T14:15" in text and "America/New_York" in text and "Open-Meteo" in text


def test_raw_nws_observation_measurements():
    text = format_current_weather(
        {
            "properties": {
                "timestamp": "2026-09-12T18:00:00Z",
                "temperature": {"value": 0, "unitCode": "wmoUnit:degC"},
                "relativeHumidity": {"value": 0, "unitCode": "wmoUnit:percent"},
                "textDescription": "Clear",
            }
        }
    )
    assert "0°C" in text and "0%" in text and "2026-09-12T18:00:00Z" in text
    assert "NWS" in text


def test_forecast_uses_daily_values_not_metadata():
    text = format_forecast(
        {
            "latitude": 40,
            "timezone": "UTC",
            "daily": {
                "time": ["2026-09-12"],
                "temperature_2m_max": [24],
                "temperature_2m_min": [0],
            },
            "daily_units": {"temperature_2m_max": "°C", "temperature_2m_min": "°C"},
        }
    )
    assert "24°C" in text and "0°C" in text and "2026-09-12" in text
    assert "latitude" not in text


def test_hourly_selects_current_hour_in_location_timezone():
    data = {
        "timezone": "America/New_York",
        "hourly": {
            "time": ["2026-09-12T00:00", "2026-09-12T14:00", "2026-09-12T15:00"],
            "temperature_2m": [-99, 20, 21],
        },
        "hourly_units": {"temperature_2m": "°C"},
    }
    now = datetime(2026, 9, 12, 18, 30, tzinfo=UTC)
    for formatter in (format_hourly_forecast, format_open_meteo_response):
        text = formatter(data, now=now)
        assert "-99" not in text and "20°C" in text and "21°C" in text
        assert "14:00" in text and "America/New_York" in text


def test_metadata_is_not_current_conditions():
    text = format_current_weather(
        {"latitude": 40, "timezone": "UTC", "hourly": {"temperature_2m": [10]}}
    )
    assert "No current weather data available" in text
    assert "latitude:" not in text and "10" not in text


def test_forecast_days_is_forwarded_and_limits_daily_rows():
    from accessiweather.ai_tools import WeatherToolExecutor

    executor = MagicMock()
    executor._resolve_location.return_value = (40, -74, "Test")
    executor.weather_service.get_forecast.return_value = {
        "daily": {"time": ["2026-09-12", "2026-09-13"], "temperature_2m_max": [20, 21]}
    }
    text = WeatherToolExecutor._get_forecast(executor, {"location": "Test", "forecast_days": 1})
    executor.weather_service.get_forecast.assert_called_once_with(40, -74, days=1)
    assert "2026-09-12" in text and "2026-09-13" not in text


def test_elapsed_nws_hour_is_excluded():
    data = {
        "properties": {
            "periods": [
                {
                    "startTime": "2026-09-12T00:00:00-04:00",
                    "endTime": "2026-09-12T01:00:00-04:00",
                    "temperature": -99,
                },
                {
                    "startTime": "2026-09-12T14:00:00-04:00",
                    "endTime": "2026-09-12T15:00:00-04:00",
                    "temperature": 20,
                },
            ]
        }
    }
    text = format_hourly_forecast(data, now=datetime(2026, 9, 12, 18, 30, tzinfo=UTC))
    assert "-99" not in text and "20" in text and "NWS" in text


@given(
    st.one_of(
        st.none(),
        st.integers(),
        st.text(),
        st.lists(st.one_of(st.none(), st.integers(), st.text())),
    )
)
def test_malformed_arrays_are_safe(value):
    data = {
        "daily": {"time": value, "temperature_2m_max": value},
        "daily_units": None,
        "hourly": {"time": value, "temperature_2m": value},
        "hourly_units": [],
    }
    for formatter in (format_forecast, format_hourly_forecast, format_open_meteo_response):
        assert isinstance(formatter(data), str)
