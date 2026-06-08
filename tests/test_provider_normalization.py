"""Tests for shared provider-adapter normalization helpers."""

from __future__ import annotations

import pytest

from accessiweather.provider_normalization import (
    classify_apparent_temperature,
    normalize_dewpoint_pair,
    normalize_humidity_percent,
    normalize_pressure_pair,
    normalize_pressure_to_pascals,
    normalize_speed_pair,
    normalize_temperature_pair,
    normalize_visibility_pair,
    pirate_temperature_unit,
    pirate_visibility_unit,
    pirate_wind_unit,
)


def test_normalize_temperature_pair_preserves_both_units():
    temperature = normalize_temperature_pair(20.0, "wmoUnit:degC")

    assert temperature.celsius == 20.0
    assert temperature.fahrenheit == pytest.approx(68.0)


def test_normalize_humidity_supports_provider_fraction_and_percent_values():
    assert normalize_humidity_percent(0.655, fraction=True) == 66
    assert normalize_humidity_percent(65.5) == 66
    assert normalize_humidity_percent("bad") is None


def test_normalize_dewpoint_uses_provider_value_before_calculating_fallback():
    explicit = normalize_dewpoint_pair(
        10.0,
        "degC",
        fallback_temperature_f=80.0,
        humidity_percent=90,
    )
    calculated = normalize_dewpoint_pair(
        None,
        "degF",
        fallback_temperature_f=68.0,
        humidity_percent=65,
    )

    assert explicit.celsius == 10.0
    assert explicit.fahrenheit == pytest.approx(50.0)
    assert calculated.fahrenheit is not None
    assert calculated.celsius is not None


def test_normalize_pressure_supports_display_pairs_and_pascal_mapper_units():
    pressure = normalize_pressure_pair(1013.25, "hPa")

    assert pressure.millibars == 1013.25
    assert pressure.inches == pytest.approx(29.92, abs=0.01)
    assert normalize_pressure_to_pascals(29.92, "inHg") == pytest.approx(101320.7888)


def test_normalize_speed_pair_accepts_provider_unit_labels():
    si_speed = normalize_speed_pair(10.0, "m/s")
    ca_speed = normalize_speed_pair(16.09344, "km/h")

    assert si_speed.mph == pytest.approx(22.37, abs=0.01)
    assert si_speed.kph == pytest.approx(36.0)
    assert ca_speed.mph == pytest.approx(10.0, abs=0.01)


def test_normalize_visibility_supports_capped_and_uncapped_provider_paths():
    capped = normalize_visibility_pair(52800.0, "ft", cap_miles=10.0)
    pirate_metric = normalize_visibility_pair(16.09344, "km")

    assert capped.miles == pytest.approx(10.0)
    assert capped.kilometers == pytest.approx(16.09344)
    assert pirate_metric.miles == pytest.approx(10.0)
    assert pirate_metric.kilometers == pytest.approx(16.09344)


def test_classify_apparent_temperature_splits_chill_and_heat_index():
    chill = classify_apparent_temperature(32.0, 25.0, -3.8889)
    heat = classify_apparent_temperature(90.0, 98.0, 36.6667)
    neutral = classify_apparent_temperature(72.0, 72.0, 22.2222)

    assert chill.wind_chill_f == 25.0
    assert chill.heat_index_f is None
    assert heat.heat_index_f == 98.0
    assert heat.wind_chill_f is None
    assert neutral.wind_chill_f is None
    assert neutral.heat_index_f is None


def test_pirate_unit_group_helpers_preserve_existing_adapter_contract():
    assert pirate_temperature_unit("us") == "F"
    assert pirate_temperature_unit("uk2") == "C"
    assert pirate_wind_unit("uk2") == "mph"
    assert pirate_wind_unit("ca") == "km/h"
    assert pirate_wind_unit("si") == "m/s"
    assert pirate_visibility_unit("us") == "mi"
    assert pirate_visibility_unit("uk2") == "mi"
    assert pirate_visibility_unit("si") == "km"
