"""Tests for weather_anomaly module."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from accessiweather.weather_anomaly import (
    MIN_YEARS_REQUIRED,
    AnomalyCallout,
    _build_description,
    _classify_severity,
    compute_anomaly,
)

# ---------------------------------------------------------------------------
# _classify_severity
# ---------------------------------------------------------------------------


class TestClassifySeverity:
    def test_normal_small(self):
        assert _classify_severity(0.0) == "normal"

    def test_normal_under_threshold(self):
        assert _classify_severity(1.9) == "normal"
        assert _classify_severity(-1.9) == "normal"

    def test_notable_at_lower_boundary(self):
        assert _classify_severity(2.0) == "notable"
        assert _classify_severity(-2.0) == "notable"

    def test_notable_between(self):
        assert _classify_severity(3.5) == "notable"
        assert _classify_severity(-3.5) == "notable"

    def test_significant_at_lower_boundary(self):
        assert _classify_severity(5.0) == "significant"
        assert _classify_severity(-5.0) == "significant"

    def test_significant_large(self):
        assert _classify_severity(10.0) == "significant"
        assert _classify_severity(-10.0) == "significant"


# ---------------------------------------------------------------------------
# _build_description
# ---------------------------------------------------------------------------


class TestBuildDescription:
    def test_near_average(self):
        desc = _build_description(0.0, 5)
        assert "average" in desc.lower()
        assert "warmer" not in desc
        assert "cooler" not in desc

    def test_warmer(self):
        desc = _build_description(4.2, 5)
        assert "warmer" in desc
        assert "4.2" in desc
        assert "5-year" in desc

    def test_cooler(self):
        desc = _build_description(-3.1, 4)
        assert "cooler" in desc
        assert "3.1" in desc
        assert "4-year" in desc

    def test_near_zero_treated_as_average(self):
        desc = _build_description(0.4, 5)
        assert "average" in desc.lower()

    def test_boundary_just_above_near_average(self):
        desc = _build_description(0.5, 5)
        assert "warmer" in desc


# ---------------------------------------------------------------------------
# compute_anomaly
# ---------------------------------------------------------------------------


def _make_client(yearly_responses: list[dict | Exception]) -> MagicMock:
    """Build a stub OpenMeteoApiClient returning successive items from yearly_responses."""
    client = MagicMock()
    side_effects = []
    for r in yearly_responses:
        if isinstance(r, Exception):
            side_effects.append(r)
        else:
            side_effects.append(r)
    client._make_request.side_effect = side_effects
    return client


def _daily_response(temps: list[float | None]) -> dict:
    return {"daily": {"temperature_2m_mean": temps}}


class TestComputeAnomaly:
    def test_full_data_warmer(self):
        # Each year returns a 15-day window of temperatures averaging 60°F.
        # Current temp is 65°F -> +5°F anomaly (significant, warmer).
        per_year = _daily_response([60.0] * 15)
        client = _make_client([per_year] * 5)

        result = compute_anomaly(
            lat=40.0,
            lon=-74.0,
            current_temp_f=65.0,
            current_date=date(2025, 7, 15),
            client=client,
        )

        assert result is not None
        assert isinstance(result, AnomalyCallout)
        assert result.temp_anomaly == pytest.approx(5.0)
        assert result.severity == "significant"
        assert "warmer" in result.temp_anomaly_description
        assert "5.0" in result.temp_anomaly_description

    def test_full_data_cooler(self):
        per_year = _daily_response([70.0] * 15)
        client = _make_client([per_year] * 5)

        result = compute_anomaly(
            lat=40.0,
            lon=-74.0,
            current_temp_f=64.0,
            current_date=date(2025, 7, 15),
            client=client,
        )

        assert result is not None
        assert result.temp_anomaly == pytest.approx(-6.0)
        assert result.severity == "significant"
        assert "cooler" in result.temp_anomaly_description

    def test_notable_severity(self):
        per_year = _daily_response([70.0] * 15)
        client = _make_client([per_year] * 5)

        result = compute_anomaly(
            lat=40.0,
            lon=-74.0,
            current_temp_f=72.5,
            current_date=date(2025, 7, 15),
            client=client,
        )

        assert result is not None
        assert result.severity == "notable"

    def test_normal_severity(self):
        per_year = _daily_response([70.0] * 15)
        client = _make_client([per_year] * 5)

        result = compute_anomaly(
            lat=40.0,
            lon=-74.0,
            current_temp_f=70.5,
            current_date=date(2025, 7, 15),
            client=client,
        )

        assert result is not None
        assert result.severity == "normal"

    def test_returns_none_when_all_fetches_fail(self):
        client = _make_client([Exception("network error")] * 5)

        result = compute_anomaly(
            lat=40.0,
            lon=-74.0,
            current_temp_f=70.0,
            current_date=date(2025, 7, 15),
            client=client,
        )

        assert result is None

    def test_returns_none_when_insufficient_years(self):
        # Only 2 years return data (below MIN_YEARS_REQUIRED=3).
        per_year = _daily_response([70.0] * 15)
        client = _make_client([per_year, per_year] + [Exception("network error")] * 3)

        result = compute_anomaly(
            lat=40.0,
            lon=-74.0,
            current_temp_f=70.0,
            current_date=date(2025, 7, 15),
            client=client,
        )

        assert result is None

    def test_returns_none_when_empty_daily_data(self):
        empty = {"daily": {"temperature_2m_mean": []}}
        client = _make_client([empty] * 5)

        result = compute_anomaly(
            lat=40.0,
            lon=-74.0,
            current_temp_f=70.0,
            current_date=date(2025, 7, 15),
            client=client,
        )

        assert result is None

    def test_skips_none_temperature_values(self):
        # Mix of valid and None temperatures; should still compute from valid ones.
        mixed = _daily_response([70.0, None, 72.0, None, 68.0])
        client = _make_client([mixed] * 5)

        result = compute_anomaly(
            lat=40.0,
            lon=-74.0,
            current_temp_f=70.0,
            current_date=date(2025, 7, 15),
            client=client,
        )

        assert result is not None
        # baseline ≈ 70°F -> anomaly ≈ 0
        assert abs(result.temp_anomaly) < 1.0

    def test_partial_years_still_works_above_minimum(self):
        per_year = _daily_response([65.0] * 15)
        # 3 good years, 2 fail -> exactly MIN_YEARS_REQUIRED
        client = _make_client([per_year, per_year, per_year, Exception("fail"), Exception("fail")])

        result = compute_anomaly(
            lat=40.0,
            lon=-74.0,
            current_temp_f=65.0,
            current_date=date(2025, 7, 15),
            client=client,
        )

        assert result is not None
        assert result.temp_anomaly == pytest.approx(0.0, abs=0.01)

    def test_precip_anomaly_description_is_none(self):
        per_year = _daily_response([70.0] * 15)
        client = _make_client([per_year] * 5)

        result = compute_anomaly(
            lat=40.0,
            lon=-74.0,
            current_temp_f=70.0,
            current_date=date(2025, 7, 15),
            client=client,
        )

        assert result is not None
        assert result.precip_anomaly_description is None

    def test_missing_daily_key_in_response(self):
        bad_response = {"hourly": {}}
        client = _make_client([bad_response] * 5)

        result = compute_anomaly(
            lat=40.0,
            lon=-74.0,
            current_temp_f=70.0,
            current_date=date(2025, 7, 15),
            client=client,
        )

        assert result is None

    def test_min_years_required_constant(self):
        assert MIN_YEARS_REQUIRED == 3
