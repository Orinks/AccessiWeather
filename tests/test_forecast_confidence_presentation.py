"""Tests for forecast confidence surfacing in ForecastPresentation (US-003)."""

from __future__ import annotations

import pytest

from accessiweather.display.presentation.forecast import build_forecast
from accessiweather.display.weather_presenter import ForecastPresentation
from accessiweather.forecast_confidence import (
    ForecastConfidence,
    ForecastConfidenceLevel,
)
from accessiweather.models.weather import Forecast, ForecastPeriod, Location
from accessiweather.utils import TemperatureUnit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_location() -> Location:
    return Location(name="TestCity", latitude=40.0, longitude=-75.0)


def make_forecast(temp: float = 72.0) -> Forecast:
    period = ForecastPeriod(name="Today", temperature=temp, short_forecast="Sunny")
    return Forecast(periods=[period])


def high_confidence() -> ForecastConfidence:
    return ForecastConfidence(
        level=ForecastConfidenceLevel.HIGH,
        rationale="Sources agree on temperature and precipitation",
        sources_compared=2,
    )


def medium_confidence() -> ForecastConfidence:
    return ForecastConfidence(
        level=ForecastConfidenceLevel.MEDIUM,
        rationale="Based on a single forecast source",
        sources_compared=1,
    )


def low_confidence() -> ForecastConfidence:
    return ForecastConfidence(
        level=ForecastConfidenceLevel.LOW,
        rationale="Sources show significant disagreement on temperature or precipitation",
        sources_compared=2,
    )


def call_build(confidence: ForecastConfidence | None = None) -> ForecastPresentation:
    return build_forecast(
        make_forecast(),
        None,
        make_location(),
        TemperatureUnit.FAHRENHEIT,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# ForecastPresentation.confidence_label field
# ---------------------------------------------------------------------------

class TestForecastPresentationConfidenceLabelField:
    def test_field_exists_defaults_none(self):
        fp = ForecastPresentation(title="Test")
        assert hasattr(fp, "confidence_label")
        assert fp.confidence_label is None

    def test_field_can_be_set(self):
        fp = ForecastPresentation(title="Test", confidence_label="Confidence: High")
        assert fp.confidence_label == "Confidence: High"


# ---------------------------------------------------------------------------
# build_forecast with confidence=None (no change to existing behaviour)
# ---------------------------------------------------------------------------

class TestBuildForecastNoConfidence:
    def test_confidence_label_is_none_when_not_passed(self):
        result = call_build(confidence=None)
        assert result.confidence_label is None

    def test_fallback_text_unchanged_when_no_confidence(self):
        result = call_build(confidence=None)
        assert "Forecast confidence" not in result.fallback_text


# ---------------------------------------------------------------------------
# build_forecast with HIGH confidence
# ---------------------------------------------------------------------------

class TestBuildForecastHighConfidence:
    def test_confidence_label_is_confidence_high(self):
        result = call_build(confidence=high_confidence())
        assert result.confidence_label == "Confidence: High"

    def test_fallback_text_contains_forecast_confidence_high(self):
        result = call_build(confidence=high_confidence())
        assert "Forecast confidence: High" in result.fallback_text

    def test_fallback_text_contains_rationale(self):
        result = call_build(confidence=high_confidence())
        assert "Sources agree on temperature and precipitation" in result.fallback_text

    def test_fallback_text_ends_with_period(self):
        """The confidence sentence should be properly terminated."""
        result = call_build(confidence=high_confidence())
        # The confidence line ends with a period
        assert "High. Sources agree on temperature and precipitation." in result.fallback_text


# ---------------------------------------------------------------------------
# build_forecast with MEDIUM confidence
# ---------------------------------------------------------------------------

class TestBuildForecastMediumConfidence:
    def test_confidence_label_is_confidence_medium(self):
        result = call_build(confidence=medium_confidence())
        assert result.confidence_label == "Confidence: Medium"

    def test_fallback_text_contains_forecast_confidence_medium(self):
        result = call_build(confidence=medium_confidence())
        assert "Forecast confidence: Medium" in result.fallback_text

    def test_fallback_text_contains_single_source_rationale(self):
        result = call_build(confidence=medium_confidence())
        assert "single forecast source" in result.fallback_text.lower()


# ---------------------------------------------------------------------------
# build_forecast with LOW confidence
# ---------------------------------------------------------------------------

class TestBuildForecastLowConfidence:
    def test_confidence_label_is_confidence_low(self):
        result = call_build(confidence=low_confidence())
        assert result.confidence_label == "Confidence: Low"

    def test_fallback_text_contains_forecast_confidence_low(self):
        result = call_build(confidence=low_confidence())
        assert "Forecast confidence: Low" in result.fallback_text

    def test_fallback_text_contains_disagreement_rationale(self):
        result = call_build(confidence=low_confidence())
        assert "disagreement" in result.fallback_text.lower()


# ---------------------------------------------------------------------------
# WeatherPresenter.present() propagation
# ---------------------------------------------------------------------------

class TestWeatherPresenterPropagation:
    def _make_presenter(self):
        from accessiweather.display.weather_presenter import WeatherPresenter
        from accessiweather.models import AppSettings
        return WeatherPresenter(settings=AppSettings())

    def test_present_forecast_with_confidence(self):
        """present_forecast() with confidence kwarg returns confidence_label."""
        presenter = self._make_presenter()
        fc = high_confidence()
        result = presenter.present_forecast(
            make_forecast(), make_location(), confidence=fc
        )
        assert result is not None
        assert result.confidence_label == "Confidence: High"

    def test_present_forecast_without_confidence(self):
        """present_forecast() without confidence leaves label None."""
        presenter = self._make_presenter()
        result = presenter.present_forecast(make_forecast(), make_location())
        assert result is not None
        assert result.confidence_label is None

    def test_present_propagates_weather_data_confidence(self):
        """present() should pick up forecast_confidence from WeatherData."""
        from accessiweather.models.weather import WeatherData

        presenter = self._make_presenter()
        fc = high_confidence()
        wd = WeatherData(
            location=make_location(),
            forecast=make_forecast(),
            forecast_confidence=fc,
        )
        presentation = presenter.present(wd)
        assert presentation.forecast is not None
        assert presentation.forecast.confidence_label == "Confidence: High"
