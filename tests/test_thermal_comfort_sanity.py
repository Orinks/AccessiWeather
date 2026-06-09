"""Regression tests for feels-like and heat-index sanity checks."""

from __future__ import annotations

import pytest

from accessiweather.display.presentation.measurement_formatters import (
    format_temperature_with_feels_like,
)
from accessiweather.models.weather import CurrentConditions, Location, SourceData
from accessiweather.pirate_weather_client import PirateWeatherClient
from accessiweather.utils.temperature_utils import TemperatureUnit
from accessiweather.weather_client_fusion import DataFusionEngine
from accessiweather.weather_client_nws_parsers import parse_nws_current_conditions
from accessiweather.weather_client_openmeteo import parse_openmeteo_current_conditions


def _f_to_c(value_f: float) -> float:
    return (value_f - 32) * 5 / 9


def _nws_observation_payload(
    *,
    temperature_f: float,
    humidity: int,
    heat_index_f: float | None = None,
    wind_chill_f: float | None = None,
) -> dict:
    return {
        "properties": {
            "temperature": {"value": _f_to_c(temperature_f)},
            "relativeHumidity": {"value": humidity},
            "windSpeed": {"value": 7.0, "unitCode": "wmoUnit:mi_h-1"},
            "heatIndex": {"value": _f_to_c(heat_index_f) if heat_index_f is not None else None},
            "windChill": {"value": _f_to_c(wind_chill_f) if wind_chill_f is not None else None},
            "textDescription": "Clear",
        }
    }


def _openmeteo_current_payload(
    *,
    temperature_f: float,
    humidity: int,
    apparent_f: float,
) -> dict:
    return {
        "current": {
            "temperature_2m": temperature_f,
            "relative_humidity_2m": humidity,
            "apparent_temperature": apparent_f,
            "weather_code": 0,
            "wind_speed_10m": 7.0,
            "pressure_msl": 1015.0,
            "rain": 0.0,
            "showers": 0.0,
            "snowfall": 0.0,
            "snow_depth": 0.0,
            "visibility": 10.0,
        },
        "current_units": {
            "temperature_2m": "°F",
            "apparent_temperature": "°F",
            "wind_speed_10m": "mph",
            "pressure_msl": "hPa",
            "snow_depth": "in",
            "visibility": "mi",
        },
        "daily": {"sunrise": [], "sunset": [], "uv_index_max": []},
    }


def _pirate_payload(
    *,
    temperature_f: float,
    humidity: float,
    apparent_f: float,
) -> dict:
    return {
        "currently": {
            "temperature": temperature_f,
            "humidity": humidity,
            "apparentTemperature": apparent_f,
            "summary": "Clear",
            "windSpeed": 7.0,
            "pressure": 1015.0,
        },
        "daily": {"data": []},
    }


def _source(name: str, current: CurrentConditions) -> SourceData:
    return SourceData(source=name, current=current, success=True)


def test_nws_drops_low_humidity_heat_index_reported_case() -> None:
    current = parse_nws_current_conditions(
        _nws_observation_payload(temperature_f=81.0, humidity=36, heat_index_f=87.0)
    )

    assert current.temperature_f == pytest.approx(81.0)
    assert current.humidity == 36
    assert current.feels_like_f is None
    assert current.heat_index_f is None


def test_nws_drops_low_humidity_heat_index_even_within_solar_apparent_range() -> None:
    current = parse_nws_current_conditions(
        _nws_observation_payload(temperature_f=81.0, humidity=36, heat_index_f=85.0)
    )

    assert current.feels_like_f is None
    assert current.heat_index_f is None


def test_nws_keeps_coherent_humid_heat_index() -> None:
    current = parse_nws_current_conditions(
        _nws_observation_payload(temperature_f=90.0, humidity=70, heat_index_f=106.0)
    )

    assert current.feels_like_f == pytest.approx(106.0)
    assert current.heat_index_f == pytest.approx(106.0)


def test_openmeteo_drops_low_humidity_warm_apparent_temperature() -> None:
    current = parse_openmeteo_current_conditions(
        _openmeteo_current_payload(temperature_f=81.0, humidity=36, apparent_f=87.0)
    )

    assert current.feels_like_f is None
    assert current.heat_index_f is None


def test_openmeteo_keeps_plausible_low_humidity_solar_apparent_temperature() -> None:
    current = parse_openmeteo_current_conditions(
        _openmeteo_current_payload(temperature_f=81.0, humidity=36, apparent_f=85.0)
    )

    assert current.feels_like_f == pytest.approx(85.0)
    assert current.heat_index_f is None


def test_openmeteo_drops_clearly_implausible_low_humidity_apparent_temperature() -> None:
    current = parse_openmeteo_current_conditions(
        _openmeteo_current_payload(temperature_f=90.0, humidity=35, apparent_f=99.0)
    )

    assert current.feels_like_f is None
    assert current.heat_index_f is None


def test_openmeteo_keeps_coherent_humid_heat_index() -> None:
    current = parse_openmeteo_current_conditions(
        _openmeteo_current_payload(temperature_f=90.0, humidity=70, apparent_f=106.0)
    )

    assert current.feels_like_f == pytest.approx(106.0)
    assert current.heat_index_f == pytest.approx(106.0)


def test_pirate_weather_drops_low_humidity_warm_apparent_temperature() -> None:
    client = PirateWeatherClient(api_key="test", units="us")

    current = client._parse_current_conditions(
        _pirate_payload(temperature_f=81.0, humidity=0.36, apparent_f=87.0)
    )

    assert current.feels_like_f is None
    assert current.heat_index_f is None


def test_pirate_weather_keeps_plausible_low_humidity_solar_apparent_temperature() -> None:
    client = PirateWeatherClient(api_key="test", units="us")

    current = client._parse_current_conditions(
        _pirate_payload(temperature_f=90.0, humidity=0.30, apparent_f=95.0)
    )

    assert current.feels_like_f == pytest.approx(95.0)
    assert current.heat_index_f is None


def test_pirate_weather_keeps_coherent_humid_heat_index() -> None:
    client = PirateWeatherClient(api_key="test", units="us")

    current = client._parse_current_conditions(
        _pirate_payload(temperature_f=90.0, humidity=0.70, apparent_f=106.0)
    )

    assert current.feels_like_f == pytest.approx(106.0)
    assert current.heat_index_f == pytest.approx(106.0)


def test_fusion_drops_cross_source_implausible_feels_like() -> None:
    engine = DataFusionEngine()
    location = Location(name="Lansing", latitude=42.7, longitude=-84.6, country_code="US")
    nws_current = CurrentConditions(temperature_f=81.0, temperature_c=27.2, humidity=36)
    pirate_current = CurrentConditions(feels_like_f=87.0, feels_like_c=30.6)

    current, attribution = engine.merge_current_conditions(
        [_source("nws", nws_current), _source("pirateweather", pirate_current)],
        location,
    )

    assert current is not None
    assert current.temperature_f == pytest.approx(81.0)
    assert current.humidity == 36
    assert current.feels_like_f is None
    assert "feels_like_f" not in attribution.field_sources


def test_fusion_keeps_cross_source_plausible_solar_apparent_temperature() -> None:
    engine = DataFusionEngine()
    location = Location(name="Lansing", latitude=42.7, longitude=-84.6, country_code="US")
    nws_current = CurrentConditions(temperature_f=81.0, temperature_c=27.2, humidity=36)
    pirate_current = CurrentConditions(feels_like_f=85.0, feels_like_c=29.4)

    current, attribution = engine.merge_current_conditions(
        [_source("nws", nws_current), _source("pirateweather", pirate_current)],
        location,
    )

    assert current is not None
    assert current.feels_like_f == pytest.approx(85.0)
    assert current.heat_index_f is None
    assert attribution.field_sources["feels_like_f"] == "pirateweather"
    assert "heat_index_f" not in attribution.field_sources


def test_fusion_keeps_cross_source_coherent_humid_heat_index() -> None:
    engine = DataFusionEngine()
    location = Location(name="Houston", latitude=29.76, longitude=-95.37, country_code="US")
    nws_current = CurrentConditions(temperature_f=90.0, temperature_c=32.2, humidity=70)
    pirate_current = CurrentConditions(feels_like_f=106.0, feels_like_c=41.1)

    current, attribution = engine.merge_current_conditions(
        [_source("nws", nws_current), _source("pirateweather", pirate_current)],
        location,
    )

    assert current is not None
    assert current.feels_like_f == pytest.approx(106.0)
    assert current.heat_index_f == pytest.approx(106.0)
    assert attribution.field_sources["feels_like_f"] == "pirateweather"


def test_presentation_ignores_implausible_warm_feels_like_fallback() -> None:
    current = CurrentConditions(temperature_f=81.0, humidity=36, feels_like_f=87.0)

    temperature, reason = format_temperature_with_feels_like(
        current,
        TemperatureUnit.FAHRENHEIT,
        precision=1,
    )

    assert temperature == "81°F"
    assert reason is None


def test_presentation_shows_plausible_low_humidity_solar_feels_like() -> None:
    current = CurrentConditions(temperature_f=81.0, humidity=36, feels_like_f=85.0)

    temperature, reason = format_temperature_with_feels_like(
        current,
        TemperatureUnit.FAHRENHEIT,
        precision=1,
    )

    assert temperature == "81°F (feels like 85°F)"
    assert reason is None
