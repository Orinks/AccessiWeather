"""Tests for Open-Meteo parser behavior."""

from accessiweather.weather_client_openmeteo import (
    _pick_precipitation_type,
    _resolve_current_condition_description,
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


def test_pick_precipitation_type_handles_snow_only_and_none():
    assert _pick_precipitation_type(0.0, 0.01) == ["snow"]
    assert _pick_precipitation_type(0.0, 0.0) is None


def test_resolve_condition_handles_invalid_code_and_precip_branches():
    # Invalid weather_code should safely fall back (covers ValueError path)
    assert (
        _resolve_current_condition_description(
            {"weather_code": "not-a-number", "rain": 0.0, "showers": 0.0, "snowfall": 0.0}
        )
        is not None
    )

    # Active rain with non-snow weather code should return base text
    rain_base = _resolve_current_condition_description(
        {"weather_code": 3, "rain": 0.01, "showers": 0.0, "snowfall": 0.0}
    )
    assert rain_base is not None
    assert "rain" not in rain_base.lower()

    # Snow dominates with rain-coded weather code should normalize to mixed
    assert (
        _resolve_current_condition_description(
            {"weather_code": 61, "rain": 0.01, "showers": 0.0, "snowfall": 0.02}
        )
        == "Mixed rain and snow"
    )

    # Snow dominates with non-rain code should keep base mapping
    mostly_snow = _resolve_current_condition_description(
        {"weather_code": 71, "rain": 0.005, "showers": 0.0, "snowfall": 0.02}
    )
    assert mostly_snow is not None
    assert "mixed" not in mostly_snow.lower()


def test_pick_precipitation_type_snow_only_returns_snow():
    assert _pick_precipitation_type(rain_in=0.0, snow_in=0.01) == ["snow"]


def test_resolve_condition_handles_invalid_weather_code_and_mixed_precip():
    condition = _resolve_current_condition_description(
        {
            "weather_code": "bad-code",
            "rain": 0.01,
            "showers": 0.0,
            "snowfall": 0.01,
        }
    )
    assert condition == "Mixed rain and snow"


def test_resolve_condition_returns_base_when_no_active_precipitation():
    condition = _resolve_current_condition_description(
        {
            "weather_code": 3,
            "rain": 0.0,
            "showers": 0.0,
            "snowfall": 0.0,
        }
    )
    assert condition == "Overcast"


def test_resolve_condition_snow_dominant_with_rain_code_returns_mixed_label():
    condition = _resolve_current_condition_description(
        {
            "weather_code": 61,
            "rain": 0.01,
            "showers": 0.0,
            "snowfall": 0.02,
        }
    )
    assert condition == "Mixed rain and snow"


def test_resolve_condition_snow_dominant_with_snow_code_keeps_base_label():
    condition = _resolve_current_condition_description(
        {
            "weather_code": 71,
            "rain": 0.01,
            "showers": 0.0,
            "snowfall": 0.02,
        }
    )
    assert condition is not None
    assert "snow" in condition.lower()


def test_resolve_condition_returns_base_when_snow_is_small_but_rain_above_epsilon():
    condition = _resolve_current_condition_description(
        {
            "weather_code": 3,
            "rain": 0.01,
            "showers": 0.0,
            "snowfall": 0.0008,
        }
    )
    assert condition == "Overcast"
