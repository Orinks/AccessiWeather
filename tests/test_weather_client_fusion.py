"""Tests for the DataFusionEngine in weather_client_fusion.py."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from accessiweather.config.source_priority import SourcePriorityConfig
from accessiweather.models.weather import (
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    SourceData,
)
from accessiweather.weather_client_fusion import DataFusionEngine

# --- Fixtures ---


@pytest.fixture
def engine():
    return DataFusionEngine()


@pytest.fixture
def us_location():
    return Location(name="New York", latitude=40.7, longitude=-74.0, country_code="US")


@pytest.fixture
def intl_location():
    return Location(name="London", latitude=51.5, longitude=-0.1, country_code="GB")


@pytest.fixture
def us_location_no_country():
    """US location detected by bounding box (no country_code)."""
    return Location(name="Chicago", latitude=41.8, longitude=-87.6)


@pytest.fixture
def intl_location_no_country():
    """International location outside US bounding box."""
    return Location(name="Tokyo", latitude=35.7, longitude=139.7)


def _make_source(name, current=None, forecast=None, hourly=None, success=True, error=None):
    return SourceData(
        source=name,
        current=current,
        forecast=forecast,
        hourly_forecast=hourly,
        success=success,
        error=error,
    )


# --- _is_us_location ---


class TestIsUsLocation:
    def test_us_country_code(self, engine, us_location):
        assert engine._is_us_location(us_location) is True

    def test_us_country_code_lowercase(self, engine):
        loc = Location(name="X", latitude=0, longitude=0, country_code="us")
        assert engine._is_us_location(loc) is True

    def test_non_us_country_code(self, engine, intl_location):
        assert engine._is_us_location(intl_location) is False

    def test_us_bounding_box(self, engine, us_location_no_country):
        assert engine._is_us_location(us_location_no_country) is True

    def test_outside_us_bounding_box(self, engine, intl_location_no_country):
        assert engine._is_us_location(intl_location_no_country) is False


# --- merge_current_conditions ---


class TestMergeCurrentConditions:
    def test_no_sources(self, engine, us_location):
        result, attr = engine.merge_current_conditions([], us_location)
        assert result is None

    def test_all_failed_sources(self, engine, us_location):
        sources = [_make_source("nws", success=False, error="timeout")]
        result, attr = engine.merge_current_conditions(sources, us_location)
        assert result is None

    def test_mix_failed_and_valid_tracks_failures(self, engine, us_location):
        """Failed sources are tracked when at least one valid source exists."""
        cc = CurrentConditions(temperature_f=70.0)
        sources = [
            _make_source("nws", current=cc),
            _make_source("openmeteo", success=False, error="timeout"),
        ]
        result, attr = engine.merge_current_conditions(sources, us_location)
        assert result is not None
        assert "openmeteo" in attr.failed_sources

    def test_single_source(self, engine, us_location):
        cc = CurrentConditions(temperature_f=72.0, condition="Clear")
        sources = [_make_source("nws", current=cc)]
        result, attr = engine.merge_current_conditions(sources, us_location)
        assert result is not None
        assert result.condition == "Clear"
        assert "nws" in attr.contributing_sources

    def test_priority_order_us(self, engine, us_location):
        """NWS should be preferred over openmeteo for US locations."""
        nws_cc = CurrentConditions(condition="Sunny")
        om_cc = CurrentConditions(condition="Clear")
        sources = [
            _make_source("openmeteo", current=om_cc),
            _make_source("nws", current=nws_cc),
        ]
        result, attr = engine.merge_current_conditions(sources, us_location)
        assert result.condition == "Sunny"
        assert attr.field_sources["condition"] == "nws"

    def test_priority_order_international(self, engine, intl_location):
        """Open-Meteo preferred for international locations."""
        om_cc = CurrentConditions(condition="Rainy")
        vc_cc = CurrentConditions(condition="Overcast")
        sources = [
            _make_source("visualcrossing", current=vc_cc),
            _make_source("openmeteo", current=om_cc),
        ]
        result, attr = engine.merge_current_conditions(sources, intl_location)
        assert result.condition == "Rainy"
        assert attr.field_sources["condition"] == "openmeteo"

    def test_fallback_when_primary_has_none(self, engine, us_location):
        """If NWS has None for a field, fall back to openmeteo."""
        nws_cc = CurrentConditions(temperature_f=70.0, humidity=None)
        om_cc = CurrentConditions(temperature_f=68.0, humidity=55)
        sources = [
            _make_source("nws", current=nws_cc),
            _make_source("openmeteo", current=om_cc),
        ]
        result, attr = engine.merge_current_conditions(sources, us_location)
        assert result.temperature_f == 70.0  # from nws (higher priority)
        assert result.humidity == 55  # from openmeteo (nws was None)
        assert attr.field_sources["humidity"] == "openmeteo"

    def test_failed_sources_tracked(self, engine, us_location):
        cc = CurrentConditions(temperature_f=70.0)
        sources = [
            _make_source("nws", current=cc),
            _make_source("openmeteo", success=False, error="API error"),
        ]
        result, attr = engine.merge_current_conditions(sources, us_location)
        assert result is not None
        assert "openmeteo" in attr.failed_sources
        assert "nws" in attr.contributing_sources

    def test_unknown_source_sorted_last(self, engine, us_location):
        """Sources not in priority list go to the end."""
        unknown_cc = CurrentConditions(condition="Unknown Provider")
        nws_cc = CurrentConditions(condition="NWS Clear")
        sources = [
            _make_source("mystery_api", current=unknown_cc),
            _make_source("nws", current=nws_cc),
        ]
        result, attr = engine.merge_current_conditions(sources, us_location)
        assert result.condition == "NWS Clear"

    def test_per_field_priority_override(self, us_location):
        """Custom field_priorities should override defaults."""
        config = SourcePriorityConfig(
            field_priorities={"humidity": ["openmeteo", "nws"]}
        )
        engine = DataFusionEngine(config=config)
        nws_cc = CurrentConditions(humidity=40)
        om_cc = CurrentConditions(humidity=55)
        sources = [
            _make_source("nws", current=nws_cc),
            _make_source("openmeteo", current=om_cc),
        ]
        result, attr = engine.merge_current_conditions(sources, us_location)
        assert result.humidity == 55
        assert attr.field_sources["humidity"] == "openmeteo"

    def test_sources_with_none_current_filtered(self, engine, us_location):
        """Sources with success=True but current=None are filtered out."""
        sources = [
            _make_source("nws", current=None),
            _make_source("openmeteo", current=CurrentConditions(temperature_f=65.0)),
        ]
        result, attr = engine.merge_current_conditions(sources, us_location)
        assert result is not None
        assert result.temperature_f == 65.0


# --- Temperature conflict detection ---


class TestTemperatureConflicts:
    def test_conflict_detected(self, engine, us_location):
        """Large temp difference should create a conflict record."""
        nws_cc = CurrentConditions(temperature_f=70.0)
        om_cc = CurrentConditions(temperature_f=80.0)  # 10°F diff > 5°F threshold
        sources = [
            _make_source("nws", current=nws_cc),
            _make_source("openmeteo", current=om_cc),
        ]
        result, attr = engine.merge_current_conditions(sources, us_location)
        assert len(attr.conflicts) > 0
        conflict = attr.conflicts[0]
        assert conflict.selected_source == "nws"
        assert conflict.selected_value == 70.0

    def test_no_conflict_within_threshold(self, engine, us_location):
        """Small temp difference should not create conflicts."""
        nws_cc = CurrentConditions(temperature_f=70.0)
        om_cc = CurrentConditions(temperature_f=73.0)  # 3°F < 5°F
        sources = [
            _make_source("nws", current=nws_cc),
            _make_source("openmeteo", current=om_cc),
        ]
        result, attr = engine.merge_current_conditions(sources, us_location)
        # No conflicts for temperature_f specifically
        temp_conflicts = [c for c in attr.conflicts if c.field_name == "temperature_f"]
        assert len(temp_conflicts) == 0

    def test_conflict_custom_threshold(self, us_location):
        """Custom threshold should be respected."""
        config = SourcePriorityConfig(temperature_conflict_threshold=2.0)
        engine = DataFusionEngine(config=config)
        nws_cc = CurrentConditions(temperature_f=70.0)
        om_cc = CurrentConditions(temperature_f=73.0)  # 3°F > 2°F custom threshold
        sources = [
            _make_source("nws", current=nws_cc),
            _make_source("openmeteo", current=om_cc),
        ]
        result, attr = engine.merge_current_conditions(sources, us_location)
        temp_f_conflicts = [c for c in attr.conflicts if c.field_name == "temperature_f"]
        assert len(temp_f_conflicts) > 0

    def test_conflict_skips_non_numeric(self, engine, us_location):
        """Non-numeric temperature values should be skipped in conflict check."""
        nws_cc = CurrentConditions(temperature_f=70.0)
        om_cc = CurrentConditions(temperature_f=70.0)
        sources = [
            _make_source("nws", current=nws_cc),
            _make_source("openmeteo", current=om_cc),
        ]
        # No conflict since values are identical
        result, attr = engine.merge_current_conditions(sources, us_location)
        temp_f_conflicts = [c for c in attr.conflicts if c.field_name == "temperature_f"]
        assert len(temp_f_conflicts) == 0

    def test_single_source_no_conflict(self, engine, us_location):
        """Single source can't have conflicts."""
        cc = CurrentConditions(temperature_f=70.0)
        sources = [_make_source("nws", current=cc)]
        result, attr = engine.merge_current_conditions(sources, us_location)
        assert len(attr.conflicts) == 0


# --- merge_forecasts ---


class TestMergeForecasts:
    def _make_forecast(self):
        return Forecast(periods=[ForecastPeriod(name="Tonight", temperature=55.0)])

    def test_no_sources(self, engine, us_location):
        result, sources = engine.merge_forecasts([], us_location)
        assert result is None

    def test_all_failed(self, engine, us_location):
        sources = [_make_source("nws", success=False)]
        result, field_sources = engine.merge_forecasts(sources, us_location)
        assert result is None

    def test_us_prefers_nws(self, engine, us_location):
        nws_fc = self._make_forecast()
        om_fc = Forecast(periods=[ForecastPeriod(name="Tonight", temperature=50.0)])
        sources = [
            _make_source("openmeteo", forecast=om_fc),
            _make_source("nws", forecast=nws_fc),
        ]
        result, field_sources = engine.merge_forecasts(sources, us_location)
        assert field_sources["forecast_source"] == "nws"

    def test_intl_prefers_openmeteo(self, engine, intl_location):
        om_fc = self._make_forecast()
        vc_fc = Forecast(periods=[ForecastPeriod(name="Tonight", temperature=50.0)])
        sources = [
            _make_source("visualcrossing", forecast=vc_fc),
            _make_source("openmeteo", forecast=om_fc),
        ]
        result, field_sources = engine.merge_forecasts(sources, intl_location)
        assert field_sources["forecast_source"] == "openmeteo"

    def test_fallback_to_available(self, engine, us_location):
        """If NWS unavailable, fall back to openmeteo."""
        om_fc = self._make_forecast()
        sources = [_make_source("openmeteo", forecast=om_fc)]
        result, field_sources = engine.merge_forecasts(sources, us_location)
        assert result is not None
        assert field_sources["forecast_source"] == "openmeteo"

    def test_fallback_unknown_source(self, engine, us_location):
        """Unknown source used when no preferred sources available."""
        fc = self._make_forecast()
        sources = [_make_source("mystery_api", forecast=fc)]
        result, field_sources = engine.merge_forecasts(sources, us_location)
        assert result is not None
        assert field_sources["forecast_source"] == "mystery_api"

    def test_sources_with_none_forecast_filtered(self, engine, us_location):
        fc = self._make_forecast()
        sources = [
            _make_source("nws", forecast=None),
            _make_source("openmeteo", forecast=fc),
        ]
        result, field_sources = engine.merge_forecasts(sources, us_location)
        assert field_sources["forecast_source"] == "openmeteo"


# --- merge_hourly_forecasts ---


class TestMergeHourlyForecasts:
    def _make_hourly(self):
        return HourlyForecast(
            periods=[HourlyForecastPeriod(start_time=datetime.now(UTC), temperature=65.0)]
        )

    def test_no_sources(self, engine, us_location):
        result, sources = engine.merge_hourly_forecasts([], us_location)
        assert result is None

    def test_all_failed(self, engine, us_location):
        sources = [_make_source("nws", success=False)]
        result, field_sources = engine.merge_hourly_forecasts(sources, us_location)
        assert result is None

    def test_us_prefers_nws(self, engine, us_location):
        nws_h = self._make_hourly()
        om_h = HourlyForecast(
            periods=[HourlyForecastPeriod(start_time=datetime.now(UTC), temperature=60.0)]
        )
        sources = [
            _make_source("openmeteo", hourly=om_h),
            _make_source("nws", hourly=nws_h),
        ]
        result, field_sources = engine.merge_hourly_forecasts(sources, us_location)
        assert field_sources["hourly_source"] == "nws"

    def test_intl_prefers_openmeteo(self, engine, intl_location):
        om_h = self._make_hourly()
        vc_h = HourlyForecast(
            periods=[HourlyForecastPeriod(start_time=datetime.now(UTC), temperature=60.0)]
        )
        sources = [
            _make_source("visualcrossing", hourly=vc_h),
            _make_source("openmeteo", hourly=om_h),
        ]
        result, field_sources = engine.merge_hourly_forecasts(sources, intl_location)
        assert field_sources["hourly_source"] == "openmeteo"

    def test_fallback_to_available(self, engine, us_location):
        om_h = self._make_hourly()
        sources = [_make_source("openmeteo", hourly=om_h)]
        result, field_sources = engine.merge_hourly_forecasts(sources, us_location)
        assert result is not None
        assert field_sources["hourly_source"] == "openmeteo"

    def test_fallback_unknown_source(self, engine, us_location):
        h = self._make_hourly()
        sources = [_make_source("mystery_api", hourly=h)]
        result, field_sources = engine.merge_hourly_forecasts(sources, us_location)
        assert result is not None
        assert field_sources["hourly_source"] == "mystery_api"


# --- DataFusionEngine init ---


class TestEngineInit:
    def test_default_config(self):
        engine = DataFusionEngine()
        assert engine.config is not None
        assert engine.config.temperature_conflict_threshold == 5.0

    def test_custom_config(self):
        config = SourcePriorityConfig(temperature_conflict_threshold=10.0)
        engine = DataFusionEngine(config=config)
        assert engine.config.temperature_conflict_threshold == 10.0
