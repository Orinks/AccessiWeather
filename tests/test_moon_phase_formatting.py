"""Unit tests for moon phase formatting functions."""

from datetime import datetime

import pytest

from accessiweather.display.presentation.formatters import (
    format_moon_phase,
    format_moon_time,
)


@pytest.mark.unit
def test_format_moon_phase_new_moon():
    """Test formatting for new moon phase."""
    assert format_moon_phase(0.0) == "New Moon"
    assert format_moon_phase(0.01) == "New Moon"
    assert format_moon_phase(0.98) == "New Moon"


@pytest.mark.unit
def test_format_moon_phase_first_quarter():
    """Test formatting for first quarter moon phase."""
    assert format_moon_phase(0.25) == "First Quarter"
    assert format_moon_phase(0.24) == "First Quarter"
    assert format_moon_phase(0.26) == "First Quarter"


@pytest.mark.unit
def test_format_moon_phase_full_moon():
    """Test formatting for full moon phase."""
    assert format_moon_phase(0.5) == "Full Moon"
    assert format_moon_phase(0.49) == "Full Moon"
    assert format_moon_phase(0.51) == "Full Moon"


@pytest.mark.unit
def test_format_moon_phase_last_quarter():
    """Test formatting for last quarter moon phase."""
    assert format_moon_phase(0.75) == "Last Quarter"
    assert format_moon_phase(0.74) == "Last Quarter"
    assert format_moon_phase(0.76) == "Last Quarter"


@pytest.mark.unit
def test_format_moon_phase_waxing_crescent():
    """Test formatting for waxing crescent phase."""
    assert format_moon_phase(0.1) == "Waxing Crescent"
    assert format_moon_phase(0.15) == "Waxing Crescent"


@pytest.mark.unit
def test_format_moon_phase_waxing_gibbous():
    """Test formatting for waxing gibbous phase."""
    assert format_moon_phase(0.35) == "Waxing Gibbous"
    assert format_moon_phase(0.4) == "Waxing Gibbous"


@pytest.mark.unit
def test_format_moon_phase_waning_gibbous():
    """Test formatting for waning gibbous phase."""
    assert format_moon_phase(0.6) == "Waning Gibbous"
    assert format_moon_phase(0.65) == "Waning Gibbous"


@pytest.mark.unit
def test_format_moon_phase_waning_crescent():
    """Test formatting for waning crescent phase."""
    assert format_moon_phase(0.85) == "Waning Crescent"
    assert format_moon_phase(0.9) == "Waning Crescent"


@pytest.mark.unit
def test_format_moon_phase_none():
    """Test formatting when moon phase is None."""
    assert format_moon_phase(None) is None


@pytest.mark.unit
def test_format_moon_time():
    """Test formatting moonrise/moonset times."""
    moon_time = datetime(2024, 1, 1, 20, 15, 0)
    assert format_moon_time(moon_time) == "8:15 PM"


@pytest.mark.unit
def test_format_moon_time_leading_zero():
    """Test formatting moon time strips leading zero."""
    moon_time = datetime(2024, 1, 1, 8, 30, 0)
    assert format_moon_time(moon_time) == "8:30 AM"


@pytest.mark.unit
def test_format_moon_time_none():
    """Test formatting when moon time is None."""
    assert format_moon_time(None) is None
