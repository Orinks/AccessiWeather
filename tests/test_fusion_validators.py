"""Tests for the post-fusion plausibility validation layer."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from accessiweather.models.weather import CurrentConditions, Location
from accessiweather.weather_client_validators import (
    UV_INDEX_MAX,
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
