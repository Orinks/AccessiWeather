"""Tests for hourly air quality presentation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from accessiweather.display.presentation.environmental import format_hourly_air_quality
from accessiweather.models import AppSettings, HourlyAirQuality


@pytest.mark.unit
def test_format_hourly_air_quality_basic():
    """Test basic formatting of hourly air quality data."""
    now = datetime.now(UTC)
    hourly_data = [
        HourlyAirQuality(timestamp=now, aqi=45, category="Good"),
        HourlyAirQuality(timestamp=now + timedelta(hours=1), aqi=55, category="Moderate"),
        HourlyAirQuality(
            timestamp=now + timedelta(hours=2), aqi=125, category="Unhealthy for Sensitive Groups"
        ),
    ]

    result = format_hourly_air_quality(hourly_data)

    assert result is not None
    assert "45" in result
    assert "Good" in result
    assert "125" in result
    assert "Unhealthy for Sensitive Groups" in result


@pytest.mark.unit
def test_format_hourly_air_quality_shows_trend():
    """Test that formatting identifies AQI trends."""
    now = datetime.now(UTC)
    # Worsening trend
    hourly_data = [
        HourlyAirQuality(timestamp=now, aqi=50, category="Good"),
        HourlyAirQuality(timestamp=now + timedelta(hours=1), aqi=75, category="Moderate"),
        HourlyAirQuality(
            timestamp=now + timedelta(hours=2), aqi=110, category="Unhealthy for Sensitive Groups"
        ),
    ]

    result = format_hourly_air_quality(hourly_data)

    assert result is not None
    assert "worsening" in result.lower() or "increasing" in result.lower()


@pytest.mark.unit
def test_format_hourly_air_quality_shows_improving_trend():
    """Test that formatting identifies improving AQI trends."""
    now = datetime.now(UTC)
    # Improving trend
    hourly_data = [
        HourlyAirQuality(timestamp=now, aqi=150, category="Unhealthy"),
        HourlyAirQuality(timestamp=now + timedelta(hours=1), aqi=100, category="Moderate"),
        HourlyAirQuality(timestamp=now + timedelta(hours=2), aqi=60, category="Moderate"),
    ]

    result = format_hourly_air_quality(hourly_data)

    assert result is not None
    assert "improving" in result.lower() or "decreasing" in result.lower()


@pytest.mark.unit
def test_format_hourly_air_quality_identifies_peak():
    """Test that formatting identifies peak AQI times."""
    now = datetime.now(UTC)
    hourly_data = [
        HourlyAirQuality(timestamp=now, aqi=50, category="Good"),
        HourlyAirQuality(timestamp=now + timedelta(hours=3), aqi=150, category="Unhealthy"),
        HourlyAirQuality(timestamp=now + timedelta(hours=6), aqi=60, category="Moderate"),
    ]

    result = format_hourly_air_quality(hourly_data)

    assert result is not None
    assert "150" in result
    assert "peak" in result.lower() or "worst" in result.lower() or "highest" in result.lower()


@pytest.mark.unit
def test_format_hourly_air_quality_identifies_best_time():
    """Test that formatting identifies best air quality times."""
    now = datetime.now(UTC)
    hourly_data = [
        HourlyAirQuality(timestamp=now, aqi=85, category="Moderate"),
        HourlyAirQuality(timestamp=now + timedelta(hours=2), aqi=35, category="Good"),
        HourlyAirQuality(timestamp=now + timedelta(hours=4), aqi=90, category="Moderate"),
    ]

    result = format_hourly_air_quality(hourly_data)

    assert result is not None
    assert "35" in result or "best" in result.lower()


@pytest.mark.unit
def test_format_hourly_air_quality_empty_list():
    """Test handling of empty hourly data."""
    result = format_hourly_air_quality([])

    assert result is None or result == ""


@pytest.mark.unit
def test_format_hourly_air_quality_with_settings():
    """Test formatting respects time display settings."""
    now = datetime.now(UTC)
    hourly_data = [
        HourlyAirQuality(timestamp=now, aqi=50, category="Good"),
        HourlyAirQuality(timestamp=now + timedelta(hours=1), aqi=75, category="Moderate"),
    ]

    settings = AppSettings(time_format_12hour=True)
    result = format_hourly_air_quality(hourly_data, settings=settings)

    assert result is not None
    # Should contain time information
    assert any(char.isdigit() for char in result)
