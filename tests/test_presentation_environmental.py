"""Tests for display/presentation/environmental.py — issue #314."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

from accessiweather.display.presentation.environmental import (
    AirQualityPresentation,
    _build_pollen_line,
    _build_pollutant_line,
    _build_summary_line,
    _build_updated_line,
    _format_time,
    _get_pollutant_display_name,
    _get_uv_category,
    build_air_quality_panel,
    format_air_quality_brief,
    format_air_quality_summary,
    format_hourly_air_quality,
    format_hourly_uv_index,
    format_pollen_details,
    format_pollutant_details,
)
from accessiweather.models.weather import (
    EnvironmentalConditions,
    HourlyAirQuality,
    HourlyUVIndex,
    Location,
)


def _loc(name: str = "Test City") -> Location:
    return Location(name=name, latitude=40.0, longitude=-74.0)


def _env(**kw) -> EnvironmentalConditions:
    return EnvironmentalConditions(**kw)


@dataclass
class _FakeSettings:
    time_display_mode: str = "local"
    time_format_12hour: bool = True
    show_timezone_suffix: bool = False


# ── _get_uv_category ──


class TestGetUvCategory:
    def test_none(self):
        assert _get_uv_category(None) is None

    @pytest.mark.parametrize(
        "val,expected",
        [
            (0, "Low"),
            (2, "Low"),
            (3, "Moderate"),
            (5, "Moderate"),
            (6, "High"),
            (7, "High"),
            (8, "Very High"),
            (10, "Very High"),
            (11, "Extreme"),
            (15, "Extreme"),
        ],
    )
    def test_categories(self, val, expected):
        assert _get_uv_category(val) == expected


# ── _build_summary_line ──


class TestBuildSummaryLine:
    def test_both_none(self):
        assert _build_summary_line(None, None) is None

    def test_index_only(self):
        assert _build_summary_line(42.6, None) == "AQI 43"

    def test_category_only(self):
        assert _build_summary_line(None, "Good") == "Good"

    def test_both(self):
        assert _build_summary_line(50.0, "Moderate") == "AQI 50 (Moderate)"


# ── _build_pollutant_line ──


class TestBuildPollutantLine:
    def test_none(self):
        assert _build_pollutant_line(None) is None

    def test_empty(self):
        assert _build_pollutant_line("") is None

    def test_known(self):
        assert _build_pollutant_line("pm2_5") == "Dominant pollutant: PM2.5"
        assert _build_pollutant_line("O3") == "Dominant pollutant: Ozone"
        assert _build_pollutant_line(" co ") == "Dominant pollutant: Carbon Monoxide"

    def test_unknown_with_underscore(self):
        assert _build_pollutant_line("some_thing") == "Dominant pollutant: Some Thing"

    def test_unknown_no_underscore(self):
        assert _build_pollutant_line("VOC") == "Dominant pollutant: VOC"


# ── _build_pollen_line ──


class TestBuildPollenLine:
    def test_no_data(self):
        assert _build_pollen_line(_env()) is None

    def test_category(self):
        assert _build_pollen_line(_env(pollen_category="High")) == "Pollen: High"

    def test_index_only(self):
        assert _build_pollen_line(_env(pollen_index=7.4)) == "Pollen Index: 7"

    def test_with_allergen(self):
        result = _build_pollen_line(_env(pollen_category="High", pollen_primary_allergen="Oak"))
        assert result == "Pollen: High (Oak)"


# ── _build_updated_line ──


class TestBuildUpdatedLine:
    def test_none(self):
        assert _build_updated_line(None) is None

    def test_with_datetime(self):
        dt = datetime(2026, 2, 17, 14, 30)
        result = _build_updated_line(dt)
        assert result is not None
        assert "Updated" in result

    def test_with_settings(self):
        """Cover settings branch (lines 274-276)."""
        dt = datetime(2026, 2, 17, 14, 30)
        settings = _FakeSettings(time_format_12hour=False, show_timezone_suffix=True)
        result = _build_updated_line(dt, settings)
        assert result is not None
        assert "Updated" in result


# ── _get_pollutant_display_name ──


class TestGetPollutantDisplayName:
    def test_known(self):
        assert _get_pollutant_display_name("PM2_5") == "PM2.5"

    def test_pm25_dot(self):
        assert _get_pollutant_display_name("PM2.5") == "PM2.5"

    def test_ozone_word(self):
        assert _get_pollutant_display_name("OZONE") == "Ozone"

    def test_unknown(self):
        assert _get_pollutant_display_name("XYZ") == "XYZ"


# ── _format_time ──


class TestFormatTime:
    def test_12hour(self):
        dt = datetime(2026, 1, 1, 14, 5)
        assert _format_time(dt, True) == "2:05 PM"

    def test_24hour(self):
        dt = datetime(2026, 1, 1, 9, 30)
        assert _format_time(dt, False) == "09:30"


# ── build_air_quality_panel ──


class TestBuildAirQualityPanel:
    def test_no_data_returns_none(self):
        assert build_air_quality_panel(_loc(), _env()) is None

    def test_basic_panel(self):
        env = _env(
            air_quality_index=55.0, air_quality_category="Moderate", air_quality_pollutant="PM2_5"
        )
        panel = build_air_quality_panel(_loc(), env)
        assert panel is not None
        assert isinstance(panel, AirQualityPresentation)
        assert "Moderate" in panel.summary
        assert panel.guidance is not None
        assert "Test City" in panel.title

    def test_with_pollen(self):
        env = _env(pollen_category="High", pollen_primary_allergen="Grass")
        panel = build_air_quality_panel(_loc(), env)
        # pollen_category alone doesn't trigger panel (needs AQ data too)
        # Actually checking: pollen alone won't have index/pollutant/category for AQ
        assert panel is None  # no AQ data

    def test_with_sources(self):
        env = _env(
            air_quality_index=30, air_quality_category="Good", sources=["EPA", "EPA", "OpenWeather"]
        )
        panel = build_air_quality_panel(_loc(), env)
        assert panel is not None
        assert "EPA" in panel.sources
        assert "OpenWeather" in panel.sources
        assert len(panel.sources) == 2  # deduplicated

    def test_category_only(self):
        env = _env(air_quality_category="Unhealthy")
        panel = build_air_quality_panel(_loc(), env)
        assert panel is not None
        assert "Unhealthy" in panel.summary

    def test_with_pollen_and_aqi(self):
        """Cover pollen branch inside build_air_quality_panel (lines 180-186, 209, 211)."""
        env = _env(
            air_quality_index=55.0,
            air_quality_category="Moderate",
            pollen_category="High",
            pollen_primary_allergen="Oak",
            pollen_tree_index=8.0,
            pollen_grass_index=3.0,
        )
        panel = build_air_quality_panel(_loc(), env)
        assert panel is not None
        assert "Pollen" in panel.fallback_text
        assert any("Pollen" in d for d in panel.details)
        # pollen_details breakdown should also be in details
        assert any("Tree" in d for d in panel.details)

    def test_pollen_only_no_summary_line(self):
        """Cover pollen_line and not summary_line branch (line 209)."""
        env = _env(
            air_quality_pollutant="PM2_5",  # triggers panel but no index/category
            pollen_category="Low",
        )
        panel = build_air_quality_panel(_loc(), env)
        assert panel is not None
        assert "Pollen: Low" in panel.summary

    def test_with_updated_line(self):
        """Cover updated_line branch (lines 195-196)."""
        env = _env(
            air_quality_index=30,
            air_quality_category="Good",
            updated_at=datetime(2026, 2, 17, 14, 0),
        )
        panel = build_air_quality_panel(_loc(), env)
        assert panel is not None
        assert any("Updated" in d for d in panel.details)


# ── format_air_quality_summary ──


class TestFormatAirQualitySummary:
    def test_no_data(self):
        result = format_air_quality_summary(_env())
        assert "guidance" in result.lower() or "Monitor" in result

    def test_with_aqi_and_category(self):
        env = _env(
            air_quality_index=150, air_quality_category="Unhealthy", air_quality_pollutant="O3"
        )
        result = format_air_quality_summary(env)
        assert "150" in result
        assert "Unhealthy" in result
        assert "Ozone" in result

    def test_with_updated_at(self):
        env = _env(
            air_quality_index=50,
            air_quality_category="Good",
            updated_at=datetime(2026, 2, 17, 10, 0),
        )
        result = format_air_quality_summary(env)
        assert "February" in result or "10:00" in result

    def test_24hour_format(self):
        settings = _FakeSettings(time_format_12hour=False)
        env = _env(
            air_quality_index=50,
            air_quality_category="Good",
            updated_at=datetime(2026, 2, 17, 14, 30),
        )
        result = format_air_quality_summary(env, settings)
        assert "14:30" in result

    def test_category_only_no_index(self):
        """Cover category-only branch (line 456)."""
        env = _env(air_quality_category="Moderate")
        result = format_air_quality_summary(env)
        assert "Moderate" in result
        # Should not have "AQI" since no index
        assert "AQI" not in result


# ── format_air_quality_brief ──


class TestFormatAirQualityBrief:
    def test_empty(self):
        assert format_air_quality_brief(_env()) == ""

    def test_aqi_with_category(self):
        env = _env(air_quality_index=45, air_quality_category="Good")
        result = format_air_quality_brief(env)
        assert "AQI: 45" in result
        assert "Good" in result
        assert "Stable" in result

    def test_category_only(self):
        result = format_air_quality_brief(_env(air_quality_category="Moderate"))
        assert "Moderate" in result
        assert "Stable" in result  # no hourly data → default Stable

    def test_stable_with_hourly_data(self):
        """Cover stable trend with hourly data (line 602)."""
        hourly = [
            HourlyAirQuality(timestamp=datetime(2026, 1, 1, 12 + i), aqi=50, category="Good")
            for i in range(3)
        ]
        env = _env(air_quality_index=50, air_quality_category="Good", hourly_air_quality=hourly)
        result = format_air_quality_brief(env)
        assert "Stable" in result

    def test_trend_worsening(self):
        hourly = [
            HourlyAirQuality(timestamp=datetime(2026, 1, 1, 12 + i), aqi=50 + i * 30, category="x")
            for i in range(3)
        ]
        env = _env(air_quality_index=50, air_quality_category="Moderate", hourly_air_quality=hourly)
        result = format_air_quality_brief(env)
        assert "Worsening" in result

    def test_trend_improving(self):
        hourly = [
            HourlyAirQuality(timestamp=datetime(2026, 1, 1, 12 + i), aqi=100 - i * 30, category="x")
            for i in range(3)
        ]
        env = _env(
            air_quality_index=100, air_quality_category="Moderate", hourly_air_quality=hourly
        )
        result = format_air_quality_brief(env)
        assert "Improving" in result


# ── format_hourly_air_quality ──


class TestFormatHourlyAirQuality:
    def test_empty(self):
        assert format_hourly_air_quality([]) is None

    def test_single_entry(self):
        data = [HourlyAirQuality(timestamp=datetime(2026, 1, 1, 12), aqi=50, category="Good")]
        result = format_hourly_air_quality(data)
        assert result is not None
        assert "Current: AQI 50" in result

    def test_multiple_entries_with_peak(self):
        data = [
            HourlyAirQuality(timestamp=datetime(2026, 1, 1, 12 + i), aqi=aqi, category=cat)
            for i, (aqi, cat) in enumerate(
                [(40, "Good"), (60, "Moderate"), (80, "Moderate"), (30, "Good")]
            )
        ]
        result = format_hourly_air_quality(data)
        assert "Peak:" in result
        assert "Best time:" in result
        assert "Worsening" in result

    def test_stable_trend(self):
        """Cover stable trend branch."""
        data = [
            HourlyAirQuality(timestamp=datetime(2026, 1, 1, 12 + i), aqi=50, category="Good")
            for i in range(4)
        ]
        result = format_hourly_air_quality(data)
        assert "Stable" in result

    def test_improving_trend(self):
        """Cover improving trend branch (line 329)."""
        data = [
            HourlyAirQuality(timestamp=datetime(2026, 1, 1, 12 + i), aqi=aqi, category="x")
            for i, aqi in enumerate([100, 70, 40, 30])
        ]
        result = format_hourly_air_quality(data)
        assert "Improving" in result

    def test_max_hours(self):
        start = datetime(2026, 1, 1, 0)
        data = [
            HourlyAirQuality(timestamp=start + timedelta(hours=i), aqi=50, category="Good")
            for i in range(30)
        ]
        result = format_hourly_air_quality(data, max_hours=5)
        # Should only show up to 5 hours of data
        assert result is not None

    def test_24hour_format(self):
        settings = _FakeSettings(time_format_12hour=False)
        data = [HourlyAirQuality(timestamp=datetime(2026, 1, 1, 14, 30), aqi=50, category="Good")]
        result = format_hourly_air_quality(data, settings)
        assert "14:30" in result


# ── format_hourly_uv_index ──


class TestFormatHourlyUvIndex:
    def test_empty(self):
        assert format_hourly_uv_index([]) is None

    def test_single_entry(self):
        data = [
            HourlyUVIndex(timestamp=datetime(2026, 1, 1, 12), uv_index=3.5, category="Moderate")
        ]
        result = format_hourly_uv_index(data)
        assert "UV Index 3.5" in result

    def test_trend_rising(self):
        data = [
            HourlyUVIndex(
                timestamp=datetime(2026, 1, 1, 10 + i), uv_index=2.0 + i * 3, category="x"
            )
            for i in range(4)
        ]
        result = format_hourly_uv_index(data)
        assert "Rising" in result

    def test_trend_falling(self):
        data = [
            HourlyUVIndex(
                timestamp=datetime(2026, 1, 1, 10 + i), uv_index=10.0 - i * 3, category="x"
            )
            for i in range(4)
        ]
        result = format_hourly_uv_index(data)
        assert "Falling" in result

    def test_peak_shown(self):
        data = [
            HourlyUVIndex(timestamp=datetime(2026, 1, 1, 10 + i), uv_index=uv, category="x")
            for i, uv in enumerate([5.0, 8.0, 3.0])
        ]
        result = format_hourly_uv_index(data)
        assert "Peak:" in result

    def test_lowest_shown(self):
        data = [
            HourlyUVIndex(timestamp=datetime(2026, 1, 1, 10 + i), uv_index=uv, category="x")
            for i, uv in enumerate([5.0, 8.0, 1.0])
        ]
        result = format_hourly_uv_index(data)
        assert "Lowest UV:" in result


# ── format_pollutant_details ──


class TestFormatPollutantDetails:
    def test_empty(self):
        assert "No pollutant data" in format_pollutant_details([])

    def test_with_data(self):
        entry = HourlyAirQuality(
            timestamp=datetime(2026, 1, 1, 12),
            aqi=50,
            category="Good",
            pm2_5=12.3,
            pm10=25.0,
            ozone=40.0,
        )
        result = format_pollutant_details([entry], "PM2_5")
        assert "PM2.5: 12.3" in result
        assert "(dominant)" in result
        assert "PM10: 25.0" in result

    def test_no_values(self):
        entry = HourlyAirQuality(timestamp=datetime(2026, 1, 1, 12), aqi=50, category="Good")
        result = format_pollutant_details([entry])
        assert "No pollutant measurements" in result


# ── format_pollen_details ──


class TestFormatPollenDetails:
    def test_no_data(self):
        assert format_pollen_details(_env()) is None

    def test_all_types(self):
        env = _env(pollen_tree_index=5.6, pollen_grass_index=3.2, pollen_weed_index=1.8)
        result = format_pollen_details(env)
        assert "Tree: 6" in result
        assert "Grass: 3" in result
        assert "Weed: 2" in result

    def test_partial(self):
        env = _env(pollen_grass_index=4.0)
        result = format_pollen_details(env)
        assert "Grass: 4" in result
        assert "Tree" not in result
