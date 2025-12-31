"""
Property-based tests for seasonal weather display logic.

These tests validate the correctness properties defined in the design document
for the seasonal-current-conditions feature.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from hypothesis import (
    given,
    settings,
    strategies as st,
)

from accessiweather.display.presentation.formatters import (
    format_frost_risk,
    format_snow_depth,
    select_feels_like_temperature,
)
from accessiweather.models.weather import (
    CurrentConditions,
    Season,
    get_hemisphere,
    get_season,
)
from accessiweather.utils import TemperatureUnit


# Strategies for generating test data
@st.composite
def dates(draw: st.DrawFn) -> datetime:
    """Generate random dates across all months."""
    return draw(
        st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31),
        )
    )


@st.composite
def latitudes(draw: st.DrawFn) -> float:
    """Generate random latitudes (-90 to 90)."""
    return draw(st.floats(min_value=-90.0, max_value=90.0, allow_nan=False))


@st.composite
def current_conditions_with_seasonal(draw: st.DrawFn) -> CurrentConditions:
    """Generate CurrentConditions with random seasonal fields."""
    return CurrentConditions(
        temperature_f=draw(st.one_of(st.none(), st.floats(-40, 120, allow_nan=False))),
        temperature_c=draw(st.one_of(st.none(), st.floats(-40, 50, allow_nan=False))),
        humidity=draw(st.one_of(st.none(), st.integers(0, 100))),
        wind_speed_mph=draw(st.one_of(st.none(), st.floats(0, 100, allow_nan=False))),
        snow_depth_in=draw(st.one_of(st.none(), st.floats(0, 100, allow_nan=False))),
        snow_depth_cm=draw(st.one_of(st.none(), st.floats(0, 250, allow_nan=False))),
        wind_chill_f=draw(st.one_of(st.none(), st.floats(-60, 50, allow_nan=False))),
        wind_chill_c=draw(st.one_of(st.none(), st.floats(-50, 10, allow_nan=False))),
        heat_index_f=draw(st.one_of(st.none(), st.floats(80, 130, allow_nan=False))),
        heat_index_c=draw(st.one_of(st.none(), st.floats(27, 55, allow_nan=False))),
        frost_risk=draw(st.one_of(st.none(), st.sampled_from(["None", "Low", "Moderate", "High"]))),
        visibility_miles=draw(st.one_of(st.none(), st.floats(0, 10, allow_nan=False))),
        feels_like_f=draw(st.one_of(st.none(), st.floats(-40, 120, allow_nan=False))),
        feels_like_c=draw(st.one_of(st.none(), st.floats(-40, 50, allow_nan=False))),
    )


# Feature: seasonal-current-conditions, Property 1: Season Detection Consistency
# Validates: Requirements 1.1, 1.2
class TestSeasonDetectionProperty:
    """Tests for season detection consistency property."""

    @given(date=dates(), latitude=latitudes())
    @settings(max_examples=50)
    def test_season_detection_returns_valid_season(self, date: datetime, latitude: float) -> None:
        """For any date/latitude, get_season() returns a valid Season enum."""
        season = get_season(date, latitude)
        assert season in [Season.WINTER, Season.SPRING, Season.SUMMER, Season.FALL]

    @given(date=dates(), latitude=st.floats(min_value=0.1, max_value=90.0, allow_nan=False))
    @settings(max_examples=50)
    def test_northern_hemisphere_season_matches_calendar(
        self, date: datetime, latitude: float
    ) -> None:
        """For any Northern Hemisphere date, season matches calendar definitions."""
        season = get_season(date, latitude)
        month = date.month

        if month in (12, 1, 2):
            assert season == Season.WINTER
        elif month in (3, 4, 5):
            assert season == Season.SPRING
        elif month in (6, 7, 8):
            assert season == Season.SUMMER
        else:  # 9, 10, 11
            assert season == Season.FALL

    @given(
        date=dates(),
        latitude=st.floats(min_value=-90.0, max_value=-0.1, allow_nan=False),
    )
    @settings(max_examples=50)
    def test_southern_hemisphere_season_is_flipped(self, date: datetime, latitude: float) -> None:
        """For any Southern Hemisphere date, season is flipped from Northern."""
        season = get_season(date, latitude)
        month = date.month

        # Southern hemisphere has opposite seasons
        if month in (12, 1, 2):
            assert season == Season.SUMMER  # Flipped from winter
        elif month in (3, 4, 5):
            assert season == Season.FALL  # Flipped from spring
        elif month in (6, 7, 8):
            assert season == Season.WINTER  # Flipped from summer
        else:  # 9, 10, 11
            assert season == Season.SPRING  # Flipped from fall

    @given(latitude=latitudes())
    @settings(max_examples=50)
    def test_hemisphere_detection_consistency(self, latitude: float) -> None:
        """For any latitude, get_hemisphere() returns consistent results."""
        hemisphere = get_hemisphere(latitude)
        if latitude >= 0:
            assert hemisphere == "northern"
        else:
            assert hemisphere == "southern"


# Feature: seasonal-current-conditions, Property 2: Seasonal Data Display Completeness
# Validates: Requirements 2.1, 2.2, 2.3, 3.1, 4.1
class TestSeasonalDataDisplayProperty:
    """Tests for seasonal data display completeness property."""

    @given(
        snow_depth_in=st.floats(min_value=0.1, max_value=100.0, allow_nan=False),
        unit_pref=st.sampled_from(
            [TemperatureUnit.FAHRENHEIT, TemperatureUnit.CELSIUS, TemperatureUnit.BOTH]
        ),
    )
    @settings(max_examples=50)
    def test_snow_depth_formatted_when_available(
        self, snow_depth_in: float, unit_pref: TemperatureUnit
    ) -> None:
        """For any non-None snow depth, format_snow_depth() returns formatted string."""
        result = format_snow_depth(snow_depth_in, None, unit_pref)
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

        # Check unit is present
        if unit_pref == TemperatureUnit.CELSIUS:
            assert "cm" in result
        elif unit_pref == TemperatureUnit.BOTH:
            assert "in" in result and "cm" in result
        else:
            assert "in" in result

    @given(frost_risk=st.sampled_from(["Low", "Moderate", "High"]))
    @settings(max_examples=50)
    def test_frost_risk_formatted_when_not_none(self, frost_risk: str) -> None:
        """For any non-None frost risk, format_frost_risk() returns the value."""
        result = format_frost_risk(frost_risk)
        assert result is not None
        assert result == frost_risk

    @pytest.mark.unit
    def test_frost_risk_none_returns_none(self) -> None:
        """Frost risk of None or 'None' should return None."""
        assert format_frost_risk(None) is None
        assert format_frost_risk("None") is None
        assert format_frost_risk("none") is None


# Feature: seasonal-current-conditions, Property 3: Graceful Degradation
# Validates: Requirements 5.1, 5.2
class TestGracefulDegradationProperty:
    """Tests for graceful degradation property."""

    @given(
        unit_pref=st.sampled_from(
            [TemperatureUnit.FAHRENHEIT, TemperatureUnit.CELSIUS, TemperatureUnit.BOTH]
        )
    )
    @settings(max_examples=50)
    def test_snow_depth_none_returns_none(self, unit_pref: TemperatureUnit) -> None:
        """For any unit preference, format_snow_depth() with None returns None."""
        result = format_snow_depth(None, None, unit_pref)
        assert result is None

    @pytest.mark.unit
    def test_select_feels_like_with_no_data(self) -> None:
        """CurrentConditions with all None values should not raise an exception."""
        current = CurrentConditions()
        feels_f, feels_c, reason = select_feels_like_temperature(current)
        # Should return None values without crashing
        assert feels_f is None
        assert feels_c is None
        assert reason is None

    @given(conditions=current_conditions_with_seasonal())
    @settings(max_examples=50)
    def test_select_feels_like_never_crashes(self, conditions: CurrentConditions) -> None:
        """For any CurrentConditions, select_feels_like_temperature() should not raise."""
        # This should never raise an exception
        feels_f, feels_c, reason = select_feels_like_temperature(conditions)
        # Result types should be correct
        assert feels_f is None or isinstance(feels_f, float)
        assert feels_c is None or isinstance(feels_c, float)
        assert reason is None or isinstance(reason, str)


# Feature: seasonal-current-conditions, Property 4: Feels-Like Temperature Selection
# Validates: Requirements 6.1, 6.2, 6.3
class TestFeelsLikeSelectionProperty:
    """Tests for feels-like temperature selection property."""

    @given(
        temp_f=st.floats(min_value=-20.0, max_value=45.0, allow_nan=False),
        wind_mph=st.floats(min_value=5.0, max_value=50.0, allow_nan=False),
        wind_chill_f=st.floats(min_value=-60.0, max_value=40.0, allow_nan=False),
    )
    @settings(max_examples=50)
    def test_wind_chill_selected_when_cold_and_windy(
        self, temp_f: float, wind_mph: float, wind_chill_f: float
    ) -> None:
        """When temp < 50F and wind > 3 mph, select_feels_like uses wind_chill."""
        current = CurrentConditions(
            temperature_f=temp_f,
            wind_speed_mph=wind_mph,
            wind_chill_f=wind_chill_f,
        )
        feels_f, feels_c, reason = select_feels_like_temperature(current)
        assert feels_f == wind_chill_f
        assert reason == "wind chill"

    @given(
        temp_f=st.floats(min_value=85.0, max_value=110.0, allow_nan=False),
        humidity=st.integers(min_value=45, max_value=100),
        heat_index_f=st.floats(min_value=90.0, max_value=130.0, allow_nan=False),
    )
    @settings(max_examples=50)
    def test_heat_index_selected_when_hot_and_humid(
        self, temp_f: float, humidity: int, heat_index_f: float
    ) -> None:
        """When temp > 80F and humidity > 40%, select_feels_like uses heat_index."""
        current = CurrentConditions(
            temperature_f=temp_f,
            humidity=humidity,
            heat_index_f=heat_index_f,
        )
        feels_f, feels_c, reason = select_feels_like_temperature(current)
        assert feels_f == heat_index_f
        assert reason == "heat index"

    @given(
        temp_f=st.floats(min_value=55.0, max_value=75.0, allow_nan=False),
        feels_like_f=st.floats(min_value=50.0, max_value=80.0, allow_nan=False),
    )
    @settings(max_examples=50)
    def test_fallback_to_feels_like_in_moderate_temps(
        self, temp_f: float, feels_like_f: float
    ) -> None:
        """In moderate temps (50-80F), select_feels_like falls back to feels_like."""
        current = CurrentConditions(
            temperature_f=temp_f,
            feels_like_f=feels_like_f,
            humidity=30,  # Low humidity, no heat index
            wind_speed_mph=1.0,  # Low wind, no wind chill
        )
        feels_f, feels_c, reason = select_feels_like_temperature(current)
        assert feels_f == feels_like_f
        assert reason is None

    @given(temp_f=st.floats(min_value=55.0, max_value=75.0, allow_nan=False))
    @settings(max_examples=50)
    def test_fallback_to_actual_temp_when_no_feels_like(self, temp_f: float) -> None:
        """In moderate temps with no feels_like, returns actual temperature."""
        current = CurrentConditions(
            temperature_f=temp_f,
            humidity=30,
            wind_speed_mph=1.0,
        )
        feels_f, feels_c, reason = select_feels_like_temperature(current)
        assert feels_f == temp_f
        assert reason is None
