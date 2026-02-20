"""Tests for forecast confidence integration in WeatherData and multi-source pipeline."""

from __future__ import annotations

import pytest

from accessiweather.forecast_confidence import (
    ForecastConfidence,
    ForecastConfidenceLevel,
    calculate_forecast_confidence,
)
from accessiweather.models.weather import (
    Forecast,
    ForecastPeriod,
    Location,
    SourceData,
    WeatherData,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_source(
    temp: float,
    source: str = "nws",
    success: bool = True,
    precip: float | None = None,
) -> SourceData:
    period = ForecastPeriod(name="Today", temperature=temp, precipitation_probability=precip)
    forecast = Forecast(periods=[period])
    return SourceData(source=source, forecast=forecast, success=success)


def make_location() -> Location:
    return Location(name="TestCity", latitude=40.0, longitude=-75.0)


# ---------------------------------------------------------------------------
# WeatherData field presence
# ---------------------------------------------------------------------------

class TestWeatherDataForecastConfidenceField:
    def test_field_exists_and_defaults_none(self):
        """WeatherData must have forecast_confidence defaulting to None."""
        wd = WeatherData(location=make_location())
        assert hasattr(wd, "forecast_confidence")
        assert wd.forecast_confidence is None

    def test_field_can_be_set(self):
        """WeatherData.forecast_confidence can be assigned a ForecastConfidence."""
        fc = ForecastConfidence(
            level=ForecastConfidenceLevel.HIGH,
            rationale="Sources agree",
            sources_compared=2,
        )
        wd = WeatherData(location=make_location(), forecast_confidence=fc)
        assert wd.forecast_confidence is fc
        assert wd.forecast_confidence.level == ForecastConfidenceLevel.HIGH


# ---------------------------------------------------------------------------
# Pipeline: calculate_forecast_confidence with SourceData
# ---------------------------------------------------------------------------

class TestConfidencePipelineCalculation:
    def test_two_sources_high_agreement_gives_high(self):
        """Two sources with temp spread ≤ 5°F → HIGH confidence."""
        s1 = make_source(70.0, source="nws")
        s2 = make_source(73.0, source="openmeteo")
        result = calculate_forecast_confidence([s1, s2])
        assert result.level == ForecastConfidenceLevel.HIGH
        assert result.sources_compared == 2

    def test_two_sources_medium_agreement_gives_medium(self):
        """Two sources with temp spread 6–10°F → MEDIUM confidence."""
        s1 = make_source(70.0, source="nws")
        s2 = make_source(77.0, source="openmeteo")
        result = calculate_forecast_confidence([s1, s2])
        assert result.level == ForecastConfidenceLevel.MEDIUM
        assert result.sources_compared == 2

    def test_two_sources_low_agreement_gives_low(self):
        """Two sources with temp spread > 10°F → LOW confidence."""
        s1 = make_source(60.0, source="nws")
        s2 = make_source(80.0, source="openmeteo")
        result = calculate_forecast_confidence([s1, s2])
        assert result.level == ForecastConfidenceLevel.LOW

    def test_single_valid_source_gives_medium(self):
        """One valid source → MEDIUM with 'single' in rationale."""
        s1 = make_source(72.0, source="nws")
        s2 = make_source(0.0, source="openmeteo", success=False)
        result = calculate_forecast_confidence([s1, s2])
        assert result.level == ForecastConfidenceLevel.MEDIUM
        assert result.sources_compared == 1
        assert "single" in result.rationale.lower()

    def test_no_valid_sources_gives_low(self):
        """No valid sources → LOW with 'No forecast' rationale."""
        s1 = make_source(0.0, source="nws", success=False)
        result = calculate_forecast_confidence([s1])
        assert result.level == ForecastConfidenceLevel.LOW
        assert result.sources_compared == 0

    def test_three_sources_used_in_comparison(self):
        """Three valid sources: sources_compared == 3."""
        sources = [
            make_source(71.0, source="nws"),
            make_source(72.0, source="openmeteo"),
            make_source(73.0, source="visualcrossing"),
        ]
        result = calculate_forecast_confidence(sources)
        assert result.sources_compared == 3


# ---------------------------------------------------------------------------
# Integration: WeatherData with confidence attached
# ---------------------------------------------------------------------------

class TestWeatherDataWithConfidenceAttached:
    def test_high_confidence_stored_on_weather_data(self):
        """WeatherData can carry a HIGH ForecastConfidence from pipeline."""
        sources = [make_source(70.0, "nws"), make_source(72.0, "openmeteo")]
        confidence = calculate_forecast_confidence(sources)
        wd = WeatherData(location=make_location(), forecast_confidence=confidence)
        assert wd.forecast_confidence is not None
        assert wd.forecast_confidence.level == ForecastConfidenceLevel.HIGH

    def test_medium_confidence_stored_on_weather_data(self):
        """WeatherData can carry MEDIUM confidence when only one source succeeds."""
        sources = [
            make_source(72.0, "nws"),
            make_source(0.0, "openmeteo", success=False),
        ]
        confidence = calculate_forecast_confidence(sources)
        wd = WeatherData(location=make_location(), forecast_confidence=confidence)
        assert wd.forecast_confidence is not None
        assert wd.forecast_confidence.level == ForecastConfidenceLevel.MEDIUM

    def test_confidence_rationale_is_string(self):
        """confidence.rationale should be a non-empty string."""
        sources = [make_source(70.0, "nws"), make_source(71.0, "openmeteo")]
        confidence = calculate_forecast_confidence(sources)
        wd = WeatherData(location=make_location(), forecast_confidence=confidence)
        assert isinstance(wd.forecast_confidence.rationale, str)
        assert len(wd.forecast_confidence.rationale) > 0
