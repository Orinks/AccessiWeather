"""Tests for the forecast_confidence module."""

from __future__ import annotations

import pytest

from accessiweather.forecast_confidence import (
    ForecastConfidence,
    ForecastConfidenceLevel,
    calculate_forecast_confidence,
)
from accessiweather.models.weather import Forecast, ForecastPeriod, SourceData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_period(temperature: float, precip: float | None = None) -> ForecastPeriod:
    return ForecastPeriod(name="Period 1", temperature=temperature, precipitation_probability=precip)


def make_source(temperature: float, precip: float | None = None, source: str = "nws") -> SourceData:
    period = make_period(temperature, precip)
    forecast = Forecast(periods=[period])
    return SourceData(source=source, forecast=forecast, success=True)


def make_failed_source(source: str = "openmeteo") -> SourceData:
    return SourceData(source=source, forecast=None, success=False)


def make_empty_forecast_source(source: str = "visualcrossing") -> SourceData:
    return SourceData(source=source, forecast=Forecast(periods=[]), success=True)


# ---------------------------------------------------------------------------
# ForecastConfidenceLevel enum
# ---------------------------------------------------------------------------

class TestForecastConfidenceLevel:
    def test_has_exactly_three_members(self):
        assert len(list(ForecastConfidenceLevel)) == 3

    def test_high_value(self):
        assert ForecastConfidenceLevel.HIGH.value == "High"

    def test_medium_value(self):
        assert ForecastConfidenceLevel.MEDIUM.value == "Medium"

    def test_low_value(self):
        assert ForecastConfidenceLevel.LOW.value == "Low"


# ---------------------------------------------------------------------------
# Zero / one source edge cases
# ---------------------------------------------------------------------------

class TestZeroAndOneSources:
    def test_zero_sources_returns_low(self):
        result = calculate_forecast_confidence([])
        assert result.level == ForecastConfidenceLevel.LOW

    def test_zero_sources_rationale_contains_no_forecast(self):
        result = calculate_forecast_confidence([])
        assert "No forecast" in result.rationale

    def test_zero_sources_compared_is_zero(self):
        result = calculate_forecast_confidence([])
        assert result.sources_compared == 0

    def test_failed_sources_only_treated_as_zero(self):
        result = calculate_forecast_confidence([make_failed_source(), make_failed_source()])
        assert result.level == ForecastConfidenceLevel.LOW
        assert result.sources_compared == 0

    def test_empty_forecast_treated_as_invalid(self):
        result = calculate_forecast_confidence([make_empty_forecast_source()])
        assert result.level == ForecastConfidenceLevel.LOW

    def test_single_valid_source_returns_medium(self):
        result = calculate_forecast_confidence([make_source(72.0)])
        assert result.level == ForecastConfidenceLevel.MEDIUM

    def test_single_source_rationale_contains_single(self):
        result = calculate_forecast_confidence([make_source(72.0)])
        assert "single" in result.rationale.lower()

    def test_single_source_compared_is_one(self):
        result = calculate_forecast_confidence([make_source(72.0)])
        assert result.sources_compared == 1

    def test_one_valid_one_failed_treated_as_single(self):
        result = calculate_forecast_confidence([make_source(72.0), make_failed_source()])
        assert result.level == ForecastConfidenceLevel.MEDIUM
        assert result.sources_compared == 1


# ---------------------------------------------------------------------------
# Temperature-only scenarios (no precip data)
# ---------------------------------------------------------------------------

class TestTemperatureOnlyConfidence:
    def test_high_confidence_temp_spread_3(self):
        """Spread ≤ 5°F → HIGH."""
        s1 = make_source(70.0)
        s2 = make_source(73.0)
        result = calculate_forecast_confidence([s1, s2])
        assert result.level == ForecastConfidenceLevel.HIGH

    def test_high_confidence_temp_spread_exactly_5(self):
        """Spread == 5°F → HIGH."""
        s1 = make_source(70.0)
        s2 = make_source(75.0)
        result = calculate_forecast_confidence([s1, s2])
        assert result.level == ForecastConfidenceLevel.HIGH

    def test_medium_confidence_temp_spread_7(self):
        """5°F < spread ≤ 10°F → MEDIUM."""
        s1 = make_source(70.0)
        s2 = make_source(77.0)
        result = calculate_forecast_confidence([s1, s2])
        assert result.level == ForecastConfidenceLevel.MEDIUM

    def test_medium_confidence_temp_spread_exactly_10(self):
        """Spread == 10°F → MEDIUM."""
        s1 = make_source(70.0)
        s2 = make_source(80.0)
        result = calculate_forecast_confidence([s1, s2])
        assert result.level == ForecastConfidenceLevel.MEDIUM

    def test_low_confidence_temp_spread_15(self):
        """Spread > 10°F → LOW."""
        s1 = make_source(70.0)
        s2 = make_source(85.0)
        result = calculate_forecast_confidence([s1, s2])
        assert result.level == ForecastConfidenceLevel.LOW

    def test_sources_compared_matches_valid_count(self):
        """sources_compared should equal number of valid sources."""
        sources = [make_source(70.0 + i) for i in range(3)]
        result = calculate_forecast_confidence(sources)
        assert result.sources_compared == 3


# ---------------------------------------------------------------------------
# Mixed temperature + precipitation scenarios
# ---------------------------------------------------------------------------

class TestMixedConfidence:
    def test_high_both_within_thresholds(self):
        """temp_spread ≤ 5 AND precip_spread ≤ 15 → HIGH."""
        s1 = make_source(72.0, precip=30.0)
        s2 = make_source(74.0, precip=40.0)
        result = calculate_forecast_confidence([s1, s2])
        assert result.level == ForecastConfidenceLevel.HIGH

    def test_high_rationale_mentions_agreement(self):
        s1 = make_source(72.0, precip=30.0)
        s2 = make_source(74.0, precip=40.0)
        result = calculate_forecast_confidence([s1, s2])
        assert "agree" in result.rationale.lower()

    def test_medium_temp_ok_precip_borderline(self):
        """temp_spread ≤ 10 but precip_spread > 15 → MEDIUM (temp satisfies OR)."""
        s1 = make_source(72.0, precip=20.0)
        s2 = make_source(79.0, precip=50.0)   # precip_spread=30, temp_spread=7
        result = calculate_forecast_confidence([s1, s2])
        assert result.level == ForecastConfidenceLevel.MEDIUM

    def test_medium_precip_ok_temp_borderline(self):
        """temp_spread > 10 but precip_spread ≤ 25 → MEDIUM (precip satisfies OR)."""
        s1 = make_source(60.0, precip=30.0)
        s2 = make_source(75.0, precip=40.0)   # temp_spread=15 (>10), precip_spread=10 (≤25)
        result = calculate_forecast_confidence([s1, s2])
        assert result.level == ForecastConfidenceLevel.MEDIUM

    def test_low_both_exceed_thresholds(self):
        """temp_spread > 10 AND precip_spread > 25 → LOW."""
        s1 = make_source(60.0, precip=10.0)
        s2 = make_source(80.0, precip=70.0)   # temp_spread=20, precip_spread=60
        result = calculate_forecast_confidence([s1, s2])
        assert result.level == ForecastConfidenceLevel.LOW

    def test_low_rationale_mentions_disagreement(self):
        s1 = make_source(60.0, precip=10.0)
        s2 = make_source(80.0, precip=70.0)
        result = calculate_forecast_confidence([s1, s2])
        assert "disagree" in result.rationale.lower() or "significant" in result.rationale.lower()


# ---------------------------------------------------------------------------
# ForecastConfidence dataclass
# ---------------------------------------------------------------------------

class TestForecastConfidenceDataclass:
    def test_is_dataclass(self):
        fc = ForecastConfidence(
            level=ForecastConfidenceLevel.HIGH,
            rationale="Test",
            sources_compared=2,
        )
        assert fc.level == ForecastConfidenceLevel.HIGH
        assert fc.rationale == "Test"
        assert fc.sources_compared == 2

    def test_exported_in_all(self):
        from accessiweather import forecast_confidence as mod
        assert "ForecastConfidenceLevel" in mod.__all__
        assert "ForecastConfidence" in mod.__all__
        assert "calculate_forecast_confidence" in mod.__all__
