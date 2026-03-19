"""Tests for the DataFusionEngine in weather_client_fusion.py."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
        config = SourcePriorityConfig(field_priorities={"humidity": ["openmeteo", "nws"]})
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

    def test_visibility_prefers_most_conservative_value(self, engine, us_location):
        """Visibility should favor the lowest reported value, not source priority."""
        nws_cc = CurrentConditions(visibility_miles=0.25, visibility_km=0.4)
        om_cc = CurrentConditions(visibility_miles=10.0, visibility_km=16.1)
        sources = [
            _make_source("openmeteo", current=om_cc),
            _make_source("nws", current=nws_cc),
        ]

        result, attr = engine.merge_current_conditions(sources, us_location)

        assert result is not None
        assert result.visibility_miles == pytest.approx(0.25)
        assert result.visibility_km == pytest.approx(0.4)
        assert attr.field_sources["visibility_miles"] == "nws"
        assert attr.field_sources["visibility_km"] == "nws"

    def test_visibility_keeps_units_from_same_winning_source(self, engine, us_location):
        """Do not mix unit variants from different sources for one visibility reading."""
        nws_cc = CurrentConditions(visibility_miles=0.5)
        om_cc = CurrentConditions(visibility_km=5.0)
        sources = [
            _make_source("openmeteo", current=om_cc),
            _make_source("nws", current=nws_cc),
        ]

        result, attr = engine.merge_current_conditions(sources, us_location)

        assert result is not None
        assert result.visibility_miles == pytest.approx(0.5)
        assert result.visibility_km == pytest.approx(0.804672)
        assert attr.field_sources["visibility_miles"] == "nws"
        assert attr.field_sources["visibility_km"] == "nws"

    def test_visibility_can_select_source_with_only_km(self, engine, intl_location):
        """Comparison should still work when the best source only reports kilometers."""
        pw_cc = CurrentConditions(visibility_km=0.8)
        om_cc = CurrentConditions(visibility_miles=2.0, visibility_km=3.2)
        sources = [
            _make_source("openmeteo", current=om_cc),
            _make_source("pirateweather", current=pw_cc),
        ]

        result, attr = engine.merge_current_conditions(sources, intl_location)

        assert result is not None
        assert result.visibility_km == pytest.approx(0.8)
        assert result.visibility_miles == pytest.approx(0.4970969538)
        assert attr.field_sources["visibility_miles"] == "pirateweather"
        assert attr.field_sources["visibility_km"] == "pirateweather"

    def test_temperature_group_stays_aligned_to_one_source(self, engine, us_location):
        """Temperature variants should come from one provider once auto selects a reading."""
        nws_cc = CurrentConditions(temperature_f=72.0)
        om_cc = CurrentConditions(temperature_c=10.0)
        sources = [
            _make_source("openmeteo", current=om_cc),
            _make_source("nws", current=nws_cc),
        ]

        result, attr = engine.merge_current_conditions(sources, us_location)

        assert result is not None
        assert result.temperature == pytest.approx(72.0)
        assert result.temperature_f == pytest.approx(72.0)
        assert result.temperature_c == pytest.approx(22.2222222222)
        assert attr.field_sources["temperature"] == "nws"
        assert attr.field_sources["temperature_f"] == "nws"
        assert attr.field_sources["temperature_c"] == "nws"

    def test_pressure_group_stays_aligned_to_one_source(self, engine, us_location):
        """Pressure aliases and unit variants should not mix providers."""
        nws_cc = CurrentConditions(pressure_in=30.0)
        om_cc = CurrentConditions(pressure_mb=990.0)
        sources = [
            _make_source("openmeteo", current=om_cc),
            _make_source("nws", current=nws_cc),
        ]

        result, attr = engine.merge_current_conditions(sources, us_location)

        assert result is not None
        assert result.pressure == pytest.approx(30.0)
        assert result.pressure_in == pytest.approx(30.0)
        assert result.pressure_mb == pytest.approx(1015.917)
        assert attr.field_sources["pressure"] == "nws"
        assert attr.field_sources["pressure_in"] == "nws"
        assert attr.field_sources["pressure_mb"] == "nws"

    def test_wind_speed_group_respects_per_field_priority_override(self, us_location):
        """Semantic group selection should still honor custom field priority overrides."""
        config = SourcePriorityConfig(field_priorities={"wind_speed": ["openmeteo", "nws"]})
        engine = DataFusionEngine(config=config)
        nws_cc = CurrentConditions(wind_speed_mph=12.0)
        om_cc = CurrentConditions(wind_speed_kph=20.0)
        sources = [
            _make_source("nws", current=nws_cc),
            _make_source("openmeteo", current=om_cc),
        ]

        result, attr = engine.merge_current_conditions(sources, us_location)

        assert result is not None
        assert result.wind_speed == pytest.approx(20.0)
        assert result.wind_speed_mph == pytest.approx(12.4274238447)
        assert result.wind_speed_kph == pytest.approx(20.0)
        assert attr.field_sources["wind_speed"] == "openmeteo"
        assert attr.field_sources["wind_speed_mph"] == "openmeteo"
        assert attr.field_sources["wind_speed_kph"] == "openmeteo"

    def test_us_strips_openmeteo_snow_depth(self, engine, us_location):
        """Open-Meteo snow depth (ERA5/GFS model) is stripped for US locations."""
        nws_cc = CurrentConditions(temperature_f=32.0, snow_depth_in=None, snow_depth_cm=None)
        om_cc = CurrentConditions(temperature_f=31.0, snow_depth_in=17.3, snow_depth_cm=44.0)
        sources = [
            _make_source("nws", current=nws_cc),
            _make_source("openmeteo", current=om_cc),
        ]
        result, attr = engine.merge_current_conditions(sources, us_location)
        assert result is not None
        assert result.snow_depth_in is None
        assert result.snow_depth_cm is None

    def test_us_strips_visualcrossing_snow_depth(self, engine, us_location):
        """Visual Crossing snow depth is also stripped for US locations (likely SNODAS-derived)."""
        nws_cc = CurrentConditions(temperature_f=32.0, snow_depth_in=None, snow_depth_cm=None)
        vc_cc = CurrentConditions(temperature_f=31.5, snow_depth_in=12.0, snow_depth_cm=30.5)
        sources = [
            _make_source("nws", current=nws_cc),
            _make_source("visualcrossing", current=vc_cc),
        ]
        result, attr = engine.merge_current_conditions(sources, us_location)
        assert result is not None
        assert result.snow_depth_in is None
        assert result.snow_depth_cm is None

    def test_us_keeps_nws_snow_depth(self, engine, us_location):
        """NWS snow depth is preserved for US locations."""
        nws_cc = CurrentConditions(temperature_f=28.0, snow_depth_in=5.0, snow_depth_cm=12.7)
        sources = [_make_source("nws", current=nws_cc)]
        result, attr = engine.merge_current_conditions(sources, us_location)
        assert result is not None
        assert result.snow_depth_in == 5.0
        assert result.snow_depth_cm == 12.7

    def test_international_keeps_openmeteo_snow_depth(self, engine, intl_location):
        """Open-Meteo snow depth is preserved for international locations (ECMWF reliable)."""
        om_cc = CurrentConditions(temperature_f=25.0, snow_depth_in=8.0, snow_depth_cm=20.3)
        sources = [_make_source("openmeteo", current=om_cc)]
        result, attr = engine.merge_current_conditions(sources, intl_location)
        assert result is not None
        assert result.snow_depth_in == 8.0
        assert result.snow_depth_cm == 20.3


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


# --- helper coverage for semantic groups ---


class TestFusionHelpers:
    def test_source_group_helpers_handle_missing_current_and_clear_stale_fields(self, engine):
        source = _make_source("nws", current=None)
        assert engine._source_has_any_field(source, ("temperature_f", "temperature_c")) is False

        merged_values = {"temperature_f": 70.0, "temperature_c": 21.1}
        attr = engine.merge_current_conditions([], Location(name="X", latitude=0, longitude=0))[1]

        engine._set_group_values(
            {"temperature_f": None, "temperature_c": 20.0},
            merged_values,
            attr,
            "openmeteo",
        )

        assert "temperature_f" not in merged_values
        assert "temperature_f" not in attr.field_sources
        assert merged_values["temperature_c"] == 20.0
        assert attr.field_sources["temperature_c"] == "openmeteo"

    def test_visibility_helpers_skip_missing_current_and_clear_missing_units(
        self, engine, monkeypatch
    ):
        result = engine._select_visibility(
            [
                _make_source("missing", current=None),
                _make_source("nws", current=CurrentConditions(visibility_miles=0.5)),
            ]
        )

        assert result == pytest.approx((0.5, 0.804672, "nws"))

        merged_values = {"visibility_miles": 1.0, "visibility_km": 1.6}
        attr = engine.merge_current_conditions([], Location(name="X", latitude=0, longitude=0))[1]
        attr.field_sources["visibility_miles"] = "nws"
        attr.field_sources["visibility_km"] = "nws"

        monkeypatch.setattr(engine, "_select_visibility", lambda _: (None, 2.0, "openmeteo"))
        engine._apply_visibility_selection([], merged_values, attr)
        assert "visibility_miles" not in merged_values
        assert "visibility_miles" not in attr.field_sources
        assert merged_values["visibility_km"] == 2.0
        assert attr.field_sources["visibility_km"] == "openmeteo"

        monkeypatch.setattr(engine, "_select_visibility", lambda _: (1.0, None, "pirateweather"))
        engine._apply_visibility_selection([], merged_values, attr)
        assert merged_values["visibility_miles"] == 1.0
        assert attr.field_sources["visibility_miles"] == "pirateweather"
        assert "visibility_km" not in merged_values
        assert "visibility_km" not in attr.field_sources

    def test_semantic_group_builders_fill_missing_units_and_base_values(self, engine):
        temperature_current = CurrentConditions(temperature_c=10.0)
        temperature_current.temperature = None
        temperature_values = engine._build_temperature_values(temperature_current)
        dewpoint_values = engine._build_dewpoint_values(CurrentConditions(dewpoint_c=5.0))
        feels_like_values = engine._build_feels_like_values(CurrentConditions(feels_like_c=9.0))
        wind_chill_values = engine._build_wind_chill_values(CurrentConditions(wind_chill_c=-4.0))
        heat_index_values = engine._build_heat_index_values(CurrentConditions(heat_index_c=31.0))
        wind_speed_current = CurrentConditions(wind_speed_mph=12.0)
        wind_speed_current.wind_speed = None
        wind_speed_values = engine._build_speed_values(wind_speed_current)
        wind_gust_values = engine._build_wind_gust_values(CurrentConditions(wind_gust_kph=40.0))
        pressure_current = CurrentConditions(pressure_mb=1013.25)
        pressure_current.pressure = None
        pressure_values = engine._build_pressure_values(pressure_current)

        assert temperature_values["temperature"] == pytest.approx(50.0)
        assert temperature_values["temperature_f"] == pytest.approx(50.0)
        assert temperature_values["temperature_c"] == pytest.approx(10.0)
        assert dewpoint_values == pytest.approx({"dewpoint_f": 41.0, "dewpoint_c": 5.0})
        assert feels_like_values == pytest.approx({"feels_like_f": 48.2, "feels_like_c": 9.0})
        assert wind_chill_values == pytest.approx({"wind_chill_f": 24.8, "wind_chill_c": -4.0})
        assert heat_index_values == pytest.approx({"heat_index_f": 87.8, "heat_index_c": 31.0})
        assert wind_speed_values["wind_speed"] == pytest.approx(12.0)
        assert wind_speed_values["wind_speed_mph"] == pytest.approx(12.0)
        assert wind_speed_values["wind_speed_kph"] == pytest.approx(19.312128)
        assert wind_gust_values == pytest.approx(
            {"wind_gust_mph": 24.8548476895, "wind_gust_kph": 40.0}
        )
        assert pressure_values["pressure"] == pytest.approx(29.9212524019)
        assert pressure_values["pressure_in"] == pytest.approx(29.9212524019)
        assert pressure_values["pressure_mb"] == pytest.approx(1013.25)

    def test_depth_precipitation_and_freezing_helpers_fill_both_conversion_directions(self, engine):
        precipitation_from_mm = engine._build_precipitation_values(
            CurrentConditions(precipitation_mm=12.7)
        )
        precipitation_from_in = engine._build_precipitation_values(
            CurrentConditions(precipitation_in=0.5)
        )
        snow_from_cm = engine._build_snow_depth_values(CurrentConditions(snow_depth_cm=10.16))
        snow_from_in = engine._build_snow_depth_values(CurrentConditions(snow_depth_in=4.0))
        freezing_from_m = engine._build_freezing_level_values(
            CurrentConditions(freezing_level_m=304.8)
        )
        freezing_from_ft = engine._build_freezing_level_values(
            CurrentConditions(freezing_level_ft=1000.0)
        )

        assert precipitation_from_mm == pytest.approx(
            {"precipitation_in": 0.5, "precipitation_mm": 12.7}
        )
        assert precipitation_from_in == pytest.approx(
            {"precipitation_in": 0.5, "precipitation_mm": 12.7}
        )
        assert snow_from_cm == pytest.approx({"snow_depth_in": 4.0, "snow_depth_cm": 10.16})
        assert snow_from_in == pytest.approx({"snow_depth_in": 4.0, "snow_depth_cm": 10.16})
        assert freezing_from_m == pytest.approx(
            {"freezing_level_ft": 1000.0, "freezing_level_m": 304.8}
        )
        assert freezing_from_ft == pytest.approx(
            {"freezing_level_ft": 1000.0, "freezing_level_m": 304.8}
        )


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

    def test_us_extended_forecast_prefers_openmeteo_full_range(self, engine, us_location):
        start = datetime(2026, 2, 1, tzinfo=UTC)
        nws_periods = [
            ForecastPeriod(name=f"NWS {i}", start_time=start + timedelta(hours=12 * i))
            for i in range(14)
        ]
        om_periods = [
            ForecastPeriod(name=f"OM {i}", start_time=start + timedelta(days=i)) for i in range(15)
        ]
        sources = [
            _make_source("nws", forecast=Forecast(periods=nws_periods)),
            _make_source("openmeteo", forecast=Forecast(periods=om_periods)),
        ]

        result, field_sources = engine.merge_forecasts(sources, us_location, requested_days=15)

        assert result is not None
        assert result.periods == om_periods
        assert field_sources["forecast_source"] == "openmeteo"

    def test_preserves_pirateweather_daily_summary_when_other_source_selected(
        self, engine, intl_location
    ):
        om_forecast = self._make_forecast()
        pw_forecast = Forecast(
            periods=[ForecastPeriod(name="Tonight", temperature=54.0)],
            summary="Rain later this evening.",
        )
        sources = [
            _make_source("openmeteo", forecast=om_forecast),
            _make_source("pirateweather", forecast=pw_forecast),
        ]

        result, field_sources = engine.merge_forecasts(sources, intl_location)

        assert result is not None
        assert result is not om_forecast
        assert result.summary == "Rain later this evening."
        assert field_sources["forecast_source"] == "openmeteo"
        assert field_sources["forecast_summary"] == "pirateweather"


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

    def test_preserves_pirateweather_hourly_summary_when_other_source_selected(
        self, engine, intl_location
    ):
        om_hourly = self._make_hourly()
        pw_hourly = HourlyForecast(
            periods=[HourlyForecastPeriod(start_time=datetime.now(UTC), temperature=64.0)],
            summary="Light rain developing overnight.",
        )
        sources = [
            _make_source("openmeteo", hourly=om_hourly),
            _make_source("pirateweather", hourly=pw_hourly),
        ]

        result, field_sources = engine.merge_hourly_forecasts(sources, intl_location)

        assert result is not None
        assert result is not om_hourly
        assert result.summary == "Light rain developing overnight."
        assert field_sources["hourly_source"] == "openmeteo"
        assert field_sources["hourly_summary"] == "pirateweather"


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
