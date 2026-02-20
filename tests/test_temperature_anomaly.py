"""Tests for the temperature_anomaly module (US-001, feat/historical-anomaly-callouts)."""

from __future__ import annotations

from datetime import date

import pytest

from accessiweather.temperature_anomaly import (
    HistoricalBaseline,
    TemperatureAnomaly,
    build_historical_baseline,
    compute_temperature_anomaly,
)
from accessiweather.weather_history import HistoricalWeatherData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_sample(year: int, temp_mean: float) -> HistoricalWeatherData:
    return HistoricalWeatherData(
        date=date(year, 7, 15),
        temperature_max=temp_mean + 5,
        temperature_min=temp_mean - 5,
        temperature_mean=temp_mean,
        condition="Sunny",
        humidity=50,
        wind_speed=5.0,
        wind_direction=180,
        pressure=1013.0,
    )


def make_baseline(mean: float, count: int = 3) -> HistoricalBaseline:
    years = list(range(2020, 2020 + count))
    return HistoricalBaseline(
        baseline_mean_temp=mean,
        sample_count=count,
        years_used=years,
    )


# ---------------------------------------------------------------------------
# compute_temperature_anomaly — callout thresholds
# ---------------------------------------------------------------------------

class TestComputeTemperatureAnomalyCallouts:
    def test_above_normal_large_delta(self):
        """85°F vs 70°F baseline → above normal callout."""
        baseline = make_baseline(70.0)
        result = compute_temperature_anomaly(85.0, baseline)
        assert "above normal" in result.callout

    def test_above_normal_contains_delta(self):
        """Above-normal callout should include the formatted delta."""
        baseline = make_baseline(70.0)
        result = compute_temperature_anomaly(85.0, baseline)
        assert "15.0" in result.callout

    def test_below_normal_large_delta(self):
        """55°F vs 70°F baseline → below normal callout."""
        baseline = make_baseline(70.0)
        result = compute_temperature_anomaly(55.0, baseline)
        assert "below normal" in result.callout

    def test_below_normal_contains_absolute_delta(self):
        """Below-normal callout should include the absolute delta (not negative)."""
        baseline = make_baseline(70.0)
        result = compute_temperature_anomaly(55.0, baseline)
        assert "15.0" in result.callout
        assert "-" not in result.callout.split("°")[0]  # No minus sign before the number

    def test_near_normal_small_positive_delta(self):
        """71°F vs 70°F baseline (delta=1) → near normal."""
        baseline = make_baseline(70.0)
        result = compute_temperature_anomaly(71.0, baseline)
        assert result.callout == "Near normal for this time of year"

    def test_near_normal_small_negative_delta(self):
        """-1°F delta → near normal."""
        baseline = make_baseline(70.0)
        result = compute_temperature_anomaly(69.0, baseline)
        assert result.callout == "Near normal for this time of year"

    def test_near_normal_zero_delta(self):
        """Exactly matching baseline → near normal."""
        baseline = make_baseline(70.0)
        result = compute_temperature_anomaly(70.0, baseline)
        assert result.callout == "Near normal for this time of year"

    def test_exactly_2_is_above_normal(self):
        """delta == 2.0 exactly is NOT near normal — it's above normal."""
        baseline = make_baseline(70.0)
        result = compute_temperature_anomaly(72.0, baseline)
        assert "above normal" in result.callout

    def test_exactly_minus_2_is_below_normal(self):
        """delta == -2.0 exactly is NOT near normal — it's below normal."""
        baseline = make_baseline(70.0)
        result = compute_temperature_anomaly(68.0, baseline)
        assert "below normal" in result.callout

    def test_callout_contains_time_of_year(self):
        """All callouts should include 'this time of year'."""
        baseline = make_baseline(70.0)
        for temp in [55.0, 70.0, 85.0]:
            result = compute_temperature_anomaly(temp, baseline)
            assert "this time of year" in result.callout


# ---------------------------------------------------------------------------
# compute_temperature_anomaly — delta and baseline
# ---------------------------------------------------------------------------

class TestComputeTemperatureAnomalyDelta:
    def test_delta_is_current_minus_baseline(self):
        baseline = make_baseline(70.0)
        result = compute_temperature_anomaly(85.0, baseline)
        assert abs(result.delta - 15.0) < 1e-9

    def test_negative_delta(self):
        baseline = make_baseline(70.0)
        result = compute_temperature_anomaly(55.0, baseline)
        assert abs(result.delta - (-15.0)) < 1e-9

    def test_baseline_stored_on_result(self):
        baseline = make_baseline(70.0)
        result = compute_temperature_anomaly(85.0, baseline)
        assert result.baseline is baseline


# ---------------------------------------------------------------------------
# build_historical_baseline
# ---------------------------------------------------------------------------

class TestBuildHistoricalBaseline:
    def test_empty_list_returns_none(self):
        assert build_historical_baseline([]) is None

    def test_single_sample_returns_none(self):
        samples = [make_sample(2023, 72.0)]
        assert build_historical_baseline(samples) is None

    def test_two_samples_returns_baseline(self):
        samples = [make_sample(2022, 70.0), make_sample(2023, 74.0)]
        result = build_historical_baseline(samples)
        assert result is not None
        assert abs(result.baseline_mean_temp - 72.0) < 1e-9

    def test_three_samples_correct_mean(self):
        """3 samples at 70, 72, 74 → mean 72."""
        samples = [
            make_sample(2021, 70.0),
            make_sample(2022, 72.0),
            make_sample(2023, 74.0),
        ]
        result = build_historical_baseline(samples)
        assert result is not None
        assert abs(result.baseline_mean_temp - 72.0) < 1e-9

    def test_sample_count_correct(self):
        samples = [make_sample(2021 + i, 70.0 + i) for i in range(3)]
        result = build_historical_baseline(samples)
        assert result is not None
        assert result.sample_count == 3

    def test_years_used_correct(self):
        samples = [make_sample(2021, 70.0), make_sample(2022, 72.0), make_sample(2023, 74.0)]
        result = build_historical_baseline(samples)
        assert result is not None
        assert set(result.years_used) == {2021, 2022, 2023}

    def test_five_samples(self):
        """5 samples: mean should be correct."""
        temps = [68.0, 70.0, 72.0, 74.0, 76.0]
        samples = [make_sample(2019 + i, t) for i, t in enumerate(temps)]
        result = build_historical_baseline(samples)
        assert result is not None
        assert abs(result.baseline_mean_temp - 72.0) < 1e-9
        assert result.sample_count == 5


# ---------------------------------------------------------------------------
# HistoricalBaseline and TemperatureAnomaly dataclasses
# ---------------------------------------------------------------------------

class TestDataclasses:
    def test_historical_baseline_fields(self):
        b = HistoricalBaseline(baseline_mean_temp=70.0, sample_count=3, years_used=[2021, 2022, 2023])
        assert b.baseline_mean_temp == 70.0
        assert b.sample_count == 3
        assert b.years_used == [2021, 2022, 2023]

    def test_temperature_anomaly_fields(self):
        baseline = make_baseline(70.0)
        anomaly = TemperatureAnomaly(delta=5.0, callout="5.0°F above normal", baseline=baseline)
        assert anomaly.delta == 5.0
        assert anomaly.callout == "5.0°F above normal"
        assert anomaly.baseline is baseline

    def test_exported_in_all(self):
        from accessiweather import temperature_anomaly as mod
        assert "HistoricalBaseline" in mod.__all__
        assert "TemperatureAnomaly" in mod.__all__
        assert "build_historical_baseline" in mod.__all__
        assert "compute_temperature_anomaly" in mod.__all__
