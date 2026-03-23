"""Tests for the post-fusion plausibility validation layer."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from accessiweather.models.weather import CurrentConditions, Location
from accessiweather.weather_client_validators import (
    HUMIDITY_MAX,
    HUMIDITY_MIN,
    PRESSURE_MAX_INHG,
    PRESSURE_MAX_MB,
    PRESSURE_MIN_INHG,
    PRESSURE_MIN_MB,
    UV_INDEX_MAX,
    VISIBILITY_MAX_KM,
    VISIBILITY_MAX_MILES,
    PlausibilityValidator,
    _solar_elevation_deg,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LONDON = Location(name="London", latitude=51.5, longitude=-0.1, country_code="GB")
_SYDNEY = Location(name="Sydney", latitude=-33.9, longitude=151.2, country_code="AU")


def _midday_utc(lat: float, lon: float) -> datetime:
    """Return a UTC datetime that is solar noon at the given longitude."""
    # Solar noon UTC ≈ 12:00 - lon/15 hours
    noon_hour = 12.0 - lon / 15.0
    hour = int(noon_hour) % 24
    minute = int((noon_hour % 1) * 60)
    return datetime(2024, 6, 21, hour, minute, 0, tzinfo=UTC)


def _midnight_utc(lat: float, lon: float) -> datetime:
    """Return a UTC datetime that is solar midnight at the given longitude."""
    dt = _midday_utc(lat, lon)
    return dt.replace(hour=(dt.hour + 12) % 24)


# ---------------------------------------------------------------------------
# Solar elevation helper tests
# ---------------------------------------------------------------------------


def test_solar_elevation_day_london():
    """Solar elevation at London noon in June should be well above horizon."""
    noon = _midday_utc(_LONDON.latitude, _LONDON.longitude)
    elev = _solar_elevation_deg(_LONDON.latitude, _LONDON.longitude, noon)
    assert elev > 30, f"Expected high solar elevation at noon, got {elev:.1f}°"


def test_solar_elevation_night_london():
    """Solar elevation at London midnight in June should be below horizon."""
    midnight = _midnight_utc(_LONDON.latitude, _LONDON.longitude)
    elev = _solar_elevation_deg(_LONDON.latitude, _LONDON.longitude, midnight)
    assert elev < 0, f"Expected sub-horizon elevation at midnight, got {elev:.1f}°"


# ---------------------------------------------------------------------------
# PlausibilityValidator – UV nighttime zeroing
# ---------------------------------------------------------------------------


def test_uv_zeroed_at_night():
    """UV index must be set to 0 when the sun is below the horizon."""
    validator = PlausibilityValidator()
    night = _midnight_utc(_LONDON.latitude, _LONDON.longitude)
    conditions = CurrentConditions(uv_index=3.5)
    result = validator.validate(conditions, location=_LONDON, now=night)
    assert result.uv_index == 0.0


def test_uv_preserved_during_day():
    """UV index must be preserved (non-zero) when the sun is above the horizon."""
    validator = PlausibilityValidator()
    day = _midday_utc(_LONDON.latitude, _LONDON.longitude)
    conditions = CurrentConditions(uv_index=5.0)
    result = validator.validate(conditions, location=_LONDON, now=day)
    assert result.uv_index == pytest.approx(5.0)


def test_uv_zero_at_night_is_unchanged():
    """UV already 0 at night should remain 0 without logging spurious fixes."""
    validator = PlausibilityValidator()
    night = _midnight_utc(_LONDON.latitude, _LONDON.longitude)
    conditions = CurrentConditions(uv_index=0.0)
    result = validator.validate(conditions, location=_LONDON, now=night)
    assert result.uv_index == 0.0


def test_uv_none_unchanged():
    """A None UV index passes through without error."""
    validator = PlausibilityValidator()
    night = _midnight_utc(_LONDON.latitude, _LONDON.longitude)
    conditions = CurrentConditions(uv_index=None)
    result = validator.validate(conditions, location=_LONDON, now=night)
    assert result.uv_index is None


# ---------------------------------------------------------------------------
# PlausibilityValidator – UV range clamping
# ---------------------------------------------------------------------------


def test_uv_clamped_above_maximum():
    """UV index above the physical maximum must be clamped down."""
    validator = PlausibilityValidator()
    day = _midday_utc(_LONDON.latitude, _LONDON.longitude)
    conditions = CurrentConditions(uv_index=99.0)
    result = validator.validate(conditions, location=_LONDON, now=day)
    assert result.uv_index == UV_INDEX_MAX


def test_uv_clamped_below_zero():
    """Negative UV index must be clamped to 0."""
    validator = PlausibilityValidator()
    day = _midday_utc(_LONDON.latitude, _LONDON.longitude)
    conditions = CurrentConditions(uv_index=-1.0)
    result = validator.validate(conditions, location=_LONDON, now=day)
    assert result.uv_index == 0.0


def test_uv_within_range_unchanged():
    """UV index within valid range passes through unmodified."""
    validator = PlausibilityValidator()
    day = _midday_utc(_LONDON.latitude, _LONDON.longitude)
    conditions = CurrentConditions(uv_index=8.0)
    result = validator.validate(conditions, location=_LONDON, now=day)
    assert result.uv_index == pytest.approx(8.0)


# ---------------------------------------------------------------------------
# PlausibilityValidator – missing location data
# ---------------------------------------------------------------------------


def test_uv_nighttime_check_skipped_without_location():
    """UV index must not be zeroed when no location is provided."""
    validator = PlausibilityValidator()
    # Use a time that would be night somewhere — without location we can't know
    some_time = datetime(2024, 1, 15, 0, 0, 0, tzinfo=UTC)
    conditions = CurrentConditions(uv_index=3.0)
    result = validator.validate(conditions, location=None, now=some_time)
    # Range clamping still applies; nighttime check is skipped
    assert result.uv_index == pytest.approx(3.0)


def test_validate_with_no_location_no_crash():
    """Validator must handle None location gracefully for all validators."""
    validator = PlausibilityValidator()
    now = datetime(2024, 6, 21, 12, 0, 0, tzinfo=UTC)
    conditions = CurrentConditions(
        uv_index=5.0,
        temperature_f=75.0,
        feels_like_f=72.0,
    )
    result = validator.validate(conditions, location=None, now=now)
    assert result is not None


# ---------------------------------------------------------------------------
# PlausibilityValidator – feels-like warning (no correction applied)
# ---------------------------------------------------------------------------


def test_feels_like_large_divergence_not_corrected(caplog):
    """Feels-like far from actual temperature triggers a warning but is not corrected."""
    import logging

    validator = PlausibilityValidator()
    day = _midday_utc(_LONDON.latitude, _LONDON.longitude)
    conditions = CurrentConditions(
        temperature_f=70.0,
        feels_like_f=125.0,  # 55°F divergence — clearly bogus
    )
    with caplog.at_level(logging.WARNING):
        result = validator.validate(conditions, location=_LONDON, now=day)

    assert result.feels_like_f == pytest.approx(125.0), "Feels-like should NOT be corrected"
    assert any("feels_like" in record.message for record in caplog.records)


def test_feels_like_small_divergence_no_warning(caplog):
    """Normal feels-like difference produces no warning."""
    import logging

    validator = PlausibilityValidator()
    day = _midday_utc(_LONDON.latitude, _LONDON.longitude)
    conditions = CurrentConditions(
        temperature_f=70.0,
        feels_like_f=65.0,  # only 5°F off — normal
    )
    with caplog.at_level(logging.WARNING):
        result = validator.validate(conditions, location=_LONDON, now=day)

    assert result.feels_like_f == pytest.approx(65.0)
    assert not any("feels_like" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# PlausibilityValidator – original object is not mutated
# ---------------------------------------------------------------------------


def test_validate_does_not_mutate_original():
    """validate() must return a new object, leaving the original unchanged."""
    validator = PlausibilityValidator()
    night = _midnight_utc(_LONDON.latitude, _LONDON.longitude)
    original = CurrentConditions(uv_index=4.0)
    result = validator.validate(original, location=_LONDON, now=night)
    assert original.uv_index == pytest.approx(4.0), "Original conditions must not be mutated"
    assert result.uv_index == 0.0


# ---------------------------------------------------------------------------
# PlausibilityValidator – extensibility
# ---------------------------------------------------------------------------


def test_custom_validator_is_called():
    """A custom validator added to the pipeline must be invoked."""
    called = []

    def my_validator(conditions, location, now):
        called.append(True)
        return conditions, False

    validator = PlausibilityValidator(validators=[my_validator])
    validator.validate(CurrentConditions(), location=None, now=datetime.now(UTC))
    assert called, "Custom validator was not called"


def test_empty_validator_pipeline_passthrough():
    """An empty pipeline must return conditions unchanged."""
    validator = PlausibilityValidator(validators=[])
    conditions = CurrentConditions(uv_index=5.0)
    result = validator.validate(conditions, location=_LONDON, now=datetime.now(UTC))
    assert result.uv_index == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# PlausibilityValidator – visibility capping
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 6, 21, 12, 0, 0, tzinfo=UTC)


def test_visibility_capped_at_absolute_maximum():
    """Visibility above 40 mi / 64 km must be capped regardless of condition."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(visibility_miles=50.0, visibility_km=80.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.visibility_miles == pytest.approx(VISIBILITY_MAX_MILES)
    assert result.visibility_km == pytest.approx(VISIBILITY_MAX_KM)


def test_visibility_within_limit_unchanged():
    """Visibility within the absolute maximum passes through unmodified."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(visibility_miles=10.0, visibility_km=16.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.visibility_miles == pytest.approx(10.0)
    assert result.visibility_km == pytest.approx(16.0)


def test_visibility_fog_condition_cap():
    """'Fog' condition caps visibility at 0.6 mi / 1 km."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(condition="Fog", visibility_miles=5.0, visibility_km=8.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.visibility_miles == pytest.approx(0.6)
    assert result.visibility_km == pytest.approx(1.0)


def test_visibility_dense_fog_condition_cap():
    """'Dense Fog' condition caps visibility at 0.25 mi / 0.4 km."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(
        condition="Dense Fog Advisory", visibility_miles=1.0, visibility_km=1.6
    )
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.visibility_miles == pytest.approx(0.25)
    assert result.visibility_km == pytest.approx(0.4)


def test_visibility_mist_condition_cap():
    """'Mist' condition caps visibility at 2 mi / 3.2 km."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(condition="Light Mist", visibility_miles=5.0, visibility_km=8.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.visibility_miles == pytest.approx(2.0)
    assert result.visibility_km == pytest.approx(3.2)


@pytest.mark.parametrize("condition_word", ["Haze", "Smoke", "Dust"])
def test_visibility_haze_smoke_dust_condition_cap(condition_word):
    """Haze/Smoke/Dust conditions cap visibility at 6 mi / 10 km."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(
        condition=condition_word, visibility_miles=20.0, visibility_km=32.0
    )
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.visibility_miles == pytest.approx(6.0)
    assert result.visibility_km == pytest.approx(10.0)


def test_visibility_condition_check_is_case_insensitive():
    """Condition keyword matching must be case-insensitive."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(condition="HEAVY FOG", visibility_miles=5.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.visibility_miles == pytest.approx(0.6)


def test_visibility_none_unchanged():
    """None visibility fields pass through without error."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(condition="Fog")
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.visibility_miles is None
    assert result.visibility_km is None


def test_visibility_only_miles_present():
    """Cap is applied only to whichever field is present."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(visibility_miles=50.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.visibility_miles == pytest.approx(VISIBILITY_MAX_MILES)
    assert result.visibility_km is None


# ---------------------------------------------------------------------------
# PlausibilityValidator – humidity clamping
# ---------------------------------------------------------------------------


def test_humidity_clamped_above_100(caplog):
    """Humidity over 100 must be clamped to 100 with a warning."""
    import logging

    validator = PlausibilityValidator()
    conditions = CurrentConditions(humidity=110)
    with caplog.at_level(logging.WARNING):
        result = validator.validate(conditions, location=None, now=_NOW)
    assert result.humidity == HUMIDITY_MAX
    assert any("humidity" in r.message for r in caplog.records)


def test_humidity_clamped_below_zero():
    """Negative humidity must be clamped to 0."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(humidity=-5)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.humidity == HUMIDITY_MIN


def test_humidity_within_range_unchanged():
    """Humidity within [0, 100] passes through unmodified."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(humidity=65)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.humidity == 65


def test_humidity_none_unchanged():
    """None humidity passes through without error."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(humidity=None)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.humidity is None


# ---------------------------------------------------------------------------
# PlausibilityValidator – pressure clamping
# ---------------------------------------------------------------------------


def test_pressure_in_clamped_below_minimum():
    """pressure_in below 26 inHg must be clamped to 26."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(pressure_in=20.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.pressure_in == pytest.approx(PRESSURE_MIN_INHG)


def test_pressure_in_clamped_above_maximum():
    """pressure_in above 32 inHg must be clamped to 32."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(pressure_in=35.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.pressure_in == pytest.approx(PRESSURE_MAX_INHG)


def test_pressure_mb_clamped_below_minimum():
    """pressure_mb below 880 hPa must be clamped to 880."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(pressure_mb=700.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.pressure_mb == pytest.approx(PRESSURE_MIN_MB)


def test_pressure_mb_clamped_above_maximum():
    """pressure_mb above 1085 hPa must be clamped to 1085."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(pressure_mb=1200.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.pressure_mb == pytest.approx(PRESSURE_MAX_MB)


def test_pressure_within_range_unchanged():
    """Pressure within valid range passes through unmodified."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(pressure_in=29.92, pressure_mb=1013.25)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.pressure_in == pytest.approx(29.92)
    assert result.pressure_mb == pytest.approx(1013.25)


def test_pressure_none_unchanged():
    """None pressure fields pass through without error."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions()
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.pressure_in is None
    assert result.pressure_mb is None


# ---------------------------------------------------------------------------
# PlausibilityValidator – wind speed
# ---------------------------------------------------------------------------


def test_wind_speed_mph_negative_set_to_zero():
    """Negative wind_speed_mph must be corrected to 0."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(wind_speed_mph=-5.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.wind_speed_mph == pytest.approx(0.0)


def test_wind_speed_kph_negative_set_to_zero():
    """Negative wind_speed_kph must be corrected to 0."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(wind_speed_kph=-10.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.wind_speed_kph == pytest.approx(0.0)


def test_wind_speed_generic_negative_set_to_zero():
    """Negative wind_speed (generic field) must be corrected to 0."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(wind_speed=-3.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.wind_speed == pytest.approx(0.0)


def test_wind_speed_above_250mph_warns_not_corrected(caplog):
    """Wind speed above 250 mph triggers a warning but the value is retained."""
    import logging

    validator = PlausibilityValidator()
    conditions = CurrentConditions(wind_speed_mph=300.0)
    with caplog.at_level(logging.WARNING):
        result = validator.validate(conditions, location=None, now=_NOW)
    assert result.wind_speed_mph == pytest.approx(300.0), "Wind speed must NOT be corrected"
    assert any("wind_speed_mph" in r.message for r in caplog.records)


def test_wind_speed_within_range_unchanged():
    """Normal wind speed passes through unmodified."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(wind_speed_mph=15.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.wind_speed_mph == pytest.approx(15.0)


# ---------------------------------------------------------------------------
# PlausibilityValidator – dewpoint constraint
# ---------------------------------------------------------------------------


def test_dewpoint_above_temperature_clamped():
    """dewpoint_f exceeding temperature_f must be set to temperature_f."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(temperature_f=60.0, dewpoint_f=70.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.dewpoint_f == pytest.approx(60.0)


def test_dewpoint_below_temperature_unchanged():
    """Normal dewpoint (below temperature) passes through unmodified."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(temperature_f=75.0, dewpoint_f=55.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.dewpoint_f == pytest.approx(55.0)


def test_dewpoint_equal_temperature_unchanged():
    """Dewpoint equal to temperature (100% RH) is physically valid."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(temperature_f=68.0, dewpoint_f=68.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.dewpoint_f == pytest.approx(68.0)


def test_dewpoint_none_unchanged():
    """None dewpoint passes through without error."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(temperature_f=70.0, dewpoint_f=None)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.dewpoint_f is None


def test_dewpoint_no_temperature_unchanged():
    """Dewpoint check is skipped when temperature_f is absent."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(dewpoint_f=80.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.dewpoint_f == pytest.approx(80.0)


# ---------------------------------------------------------------------------
# PlausibilityValidator – precipitation
# ---------------------------------------------------------------------------


def test_precipitation_in_negative_set_to_zero():
    """Negative precipitation_in must be corrected to 0."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(precipitation_in=-0.1)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.precipitation_in == pytest.approx(0.0)


def test_precipitation_mm_negative_set_to_zero():
    """Negative precipitation_mm must be corrected to 0."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(precipitation_mm=-2.5)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.precipitation_mm == pytest.approx(0.0)


def test_precipitation_zero_unchanged():
    """Zero precipitation is valid and must not be changed."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(precipitation_in=0.0, precipitation_mm=0.0)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.precipitation_in == pytest.approx(0.0)
    assert result.precipitation_mm == pytest.approx(0.0)


def test_precipitation_positive_unchanged():
    """Positive precipitation passes through unmodified."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(precipitation_in=0.5, precipitation_mm=12.7)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.precipitation_in == pytest.approx(0.5)
    assert result.precipitation_mm == pytest.approx(12.7)


# ---------------------------------------------------------------------------
# PlausibilityValidator – temperature sanity (warn only, no correction)
# ---------------------------------------------------------------------------


def test_temperature_below_extreme_minimum_warns(caplog):
    """temperature_f below -100°F triggers a warning but is not corrected."""
    import logging

    validator = PlausibilityValidator()
    conditions = CurrentConditions(temperature_f=-150.0)
    with caplog.at_level(logging.WARNING):
        result = validator.validate(conditions, location=None, now=_NOW)
    assert result.temperature_f == pytest.approx(-150.0), "Temperature must NOT be corrected"
    assert any("temperature_f" in r.message for r in caplog.records)


def test_temperature_above_extreme_maximum_warns(caplog):
    """temperature_f above 150°F triggers a warning but is not corrected."""
    import logging

    validator = PlausibilityValidator()
    conditions = CurrentConditions(temperature_f=200.0)
    with caplog.at_level(logging.WARNING):
        result = validator.validate(conditions, location=None, now=_NOW)
    assert result.temperature_f == pytest.approx(200.0), "Temperature must NOT be corrected"
    assert any("temperature_f" in r.message for r in caplog.records)


def test_temperature_within_plausible_range_no_warning(caplog):
    """Normal temperature produces no warning."""
    import logging

    validator = PlausibilityValidator()
    conditions = CurrentConditions(temperature_f=72.0)
    with caplog.at_level(logging.WARNING):
        result = validator.validate(conditions, location=None, now=_NOW)
    assert result.temperature_f == pytest.approx(72.0)
    assert not any("temperature_f" in r.message for r in caplog.records)


def test_temperature_none_unchanged():
    """None temperature_f passes through without error."""
    validator = PlausibilityValidator()
    conditions = CurrentConditions(temperature_f=None)
    result = validator.validate(conditions, location=None, now=_NOW)
    assert result.temperature_f is None
