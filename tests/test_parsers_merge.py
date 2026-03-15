"""Tests for merge_current_conditions in weather_client_parsers."""

from __future__ import annotations

from accessiweather.models import CurrentConditions
from accessiweather.weather_client_parsers import merge_current_conditions


def make_conditions(**kwargs):
    """Return a minimal CurrentConditions with all fields defaulting to None."""
    return CurrentConditions(**kwargs)


class TestMergeCurrentConditions:
    """Tests for merge_current_conditions."""

    def test_primary_none_returns_fallback(self):
        """If primary is None, the fallback is returned unchanged."""
        fallback = make_conditions(temperature=72.0, condition="Sunny")
        result = merge_current_conditions(None, fallback)
        assert result is fallback

    def test_primary_wins_when_all_fields_populated(self):
        """When primary has values, fallback fields are not applied."""
        primary = make_conditions(temperature=65.0, condition="Cloudy")
        fallback = make_conditions(temperature=80.0, condition="Sunny")
        result = merge_current_conditions(primary, fallback)
        assert result.temperature == 65.0
        assert result.condition == "Cloudy"

    def test_fallback_fills_none_field(self):
        """When primary has temperature=None, fallback value is copied."""
        primary = make_conditions(temperature=None, condition="Rain")
        fallback = make_conditions(temperature=55.0, condition="Clear")
        result = merge_current_conditions(primary, fallback)
        assert result.temperature == 55.0
        # Primary condition wins
        assert result.condition == "Rain"

    def test_fallback_fills_empty_string_field(self):
        """When primary has condition='', fallback value is copied."""
        primary = make_conditions(condition="")
        fallback = make_conditions(condition="Partly Cloudy")
        result = merge_current_conditions(primary, fallback)
        assert result.condition == "Partly Cloudy"

    def test_fallback_none_leaves_field_as_none(self):
        """When both primary and fallback have temperature=None, field stays None."""
        primary = make_conditions(temperature=None)
        fallback = make_conditions(temperature=None)
        result = merge_current_conditions(primary, fallback)
        assert result.temperature is None

    def test_post_init_called_after_merge(self):
        """After merge, result is a valid CurrentConditions (no exception raised)."""
        primary = make_conditions(temperature=None)
        fallback = make_conditions(temperature=68.0)
        result = merge_current_conditions(primary, fallback)
        assert isinstance(result, CurrentConditions)

    def test_fallback_not_mutated(self):
        """The returned object is primary, not fallback."""
        primary = make_conditions(temperature=None)
        fallback = make_conditions(temperature=75.0)
        result = merge_current_conditions(primary, fallback)
        assert result is primary
        # fallback is untouched
        assert fallback.temperature == 75.0

    def test_multiple_fields_merged(self):
        """Multiple missing fields are all filled from fallback."""
        primary = make_conditions()
        fallback = make_conditions(
            temperature=70.0,
            humidity=60,
            wind_speed=10.0,
            wind_direction="NW",
        )
        result = merge_current_conditions(primary, fallback)
        assert result.temperature == 70.0
        assert result.humidity == 60
        assert result.wind_speed == 10.0
        assert result.wind_direction == "NW"
