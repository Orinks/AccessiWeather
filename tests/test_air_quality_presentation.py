"""
Property-based tests for air quality presentation functions.

Uses Hypothesis for property-based testing of air quality display formatting.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from accessiweather.display.presentation.environmental import (
    _POLLUTANT_LABELS,
    format_air_quality_summary,
    format_hourly_air_quality,
    format_pollutant_details,
)
from accessiweather.models import AppSettings, EnvironmentalConditions, HourlyAirQuality

AQI_CATEGORIES = [
    "Good",
    "Moderate",
    "Unhealthy for Sensitive Groups",
    "Unhealthy",
    "Very Unhealthy",
    "Hazardous",
]

POLLUTANT_CODES = ["PM2_5", "PM10", "O3", "NO2", "SO2", "CO"]


@st.composite
def environmental_conditions(draw: st.DrawFn) -> EnvironmentalConditions:
    """Strategy for generating EnvironmentalConditions with AQI data."""
    return EnvironmentalConditions(
        air_quality_index=draw(st.floats(min_value=0, max_value=500) | st.none()),
        air_quality_category=draw(st.sampled_from(AQI_CATEGORIES + [None])),
        air_quality_pollutant=draw(st.sampled_from(POLLUTANT_CODES + [None])),
        updated_at=draw(st.none() | st.just(datetime.now(UTC))),
    )


@st.composite
def environmental_with_aqi_and_category(draw: st.DrawFn) -> EnvironmentalConditions:
    """Strategy for EnvironmentalConditions with non-null AQI and category."""
    return EnvironmentalConditions(
        air_quality_index=draw(st.floats(min_value=0, max_value=500, allow_nan=False)),
        air_quality_category=draw(st.sampled_from(AQI_CATEGORIES)),
        air_quality_pollutant=draw(st.sampled_from(POLLUTANT_CODES + [None])),
        updated_at=draw(st.none() | st.just(datetime.now(UTC))),
    )


@st.composite
def environmental_with_pollutant(draw: st.DrawFn) -> EnvironmentalConditions:
    """Strategy for EnvironmentalConditions with non-null pollutant."""
    return EnvironmentalConditions(
        air_quality_index=draw(st.floats(min_value=0, max_value=500) | st.none()),
        air_quality_category=draw(st.sampled_from(AQI_CATEGORIES + [None])),
        air_quality_pollutant=draw(st.sampled_from(POLLUTANT_CODES)),
        updated_at=draw(st.none() | st.just(datetime.now(UTC))),
    )


@st.composite
def app_settings_strategy(draw: st.DrawFn) -> AppSettings:
    """Strategy for generating AppSettings."""
    return AppSettings(
        time_format_12hour=draw(st.booleans()),
    )


@st.composite
def hourly_air_quality_list(
    draw: st.DrawFn, min_size: int = 1, max_size: int = 24
) -> list[HourlyAirQuality]:
    """Strategy for generating a list of HourlyAirQuality entries."""
    base_time = datetime.now(UTC)
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    entries = []
    for i in range(size):
        entries.append(
            HourlyAirQuality(
                timestamp=base_time + timedelta(hours=i),
                aqi=draw(st.integers(min_value=0, max_value=500)),
                category=draw(st.sampled_from(AQI_CATEGORIES)),
                pm2_5=draw(st.floats(min_value=0, max_value=500) | st.none()),
                pm10=draw(st.floats(min_value=0, max_value=500) | st.none()),
                ozone=draw(st.floats(min_value=0, max_value=500) | st.none()),
                nitrogen_dioxide=draw(st.floats(min_value=0, max_value=500) | st.none()),
                sulphur_dioxide=draw(st.floats(min_value=0, max_value=500) | st.none()),
                carbon_monoxide=draw(st.floats(min_value=0, max_value=50000) | st.none()),
            )
        )
    return entries


@pytest.mark.unit
@given(env=environmental_with_aqi_and_category(), settings=app_settings_strategy())
@settings(max_examples=100)
def test_summary_contains_aqi_and_category(
    env: EnvironmentalConditions, settings: AppSettings
) -> None:
    """
    Property 2: Summary contains AQI and category.

    **Feature: air-quality-dialog, Property 2: Summary contains AQI and category**

    For any EnvironmentalConditions with non-null air_quality_index and air_quality_category,
    the formatted summary SHALL contain both the AQI value and the category text.
    """
    result = format_air_quality_summary(env, settings)

    aqi_rounded = int(round(env.air_quality_index))  # type: ignore[arg-type]
    assert str(aqi_rounded) in result, f"AQI value {aqi_rounded} not found in summary"
    assert env.air_quality_category in result, (
        f"Category '{env.air_quality_category}' not found in summary"
    )


@pytest.mark.unit
@given(env=environmental_with_pollutant(), settings=app_settings_strategy())
@settings(max_examples=100)
def test_dominant_pollutant_appears_when_available(
    env: EnvironmentalConditions, settings: AppSettings
) -> None:
    """
    Property 3: Dominant pollutant appears when available.

    **Feature: air-quality-dialog, Property 3: Dominant pollutant appears when available**

    For any EnvironmentalConditions with non-null air_quality_pollutant,
    the formatted summary SHALL contain the human-readable pollutant name.
    """
    result = format_air_quality_summary(env, settings)

    pollutant_code = env.air_quality_pollutant
    assert pollutant_code is not None
    human_readable_name = _POLLUTANT_LABELS.get(pollutant_code.upper(), pollutant_code)

    assert human_readable_name in result, (
        f"Pollutant name '{human_readable_name}' not found in summary"
    )
    assert "Dominant pollutant" in result, "Dominant pollutant label not found in summary"


@pytest.mark.unit
@given(category=st.sampled_from(AQI_CATEGORIES), settings=app_settings_strategy())
@settings(max_examples=100)
def test_health_guidance_matches_aqi_category(category: str, settings: AppSettings) -> None:
    """
    Property 4: Health guidance matches AQI category.

    **Feature: air-quality-dialog, Property 4: Health guidance matches AQI category**

    For any AQI category from {Good, Moderate, Unhealthy for Sensitive Groups,
    Unhealthy, Very Unhealthy, Hazardous}, the summary SHALL contain
    corresponding health guidance.
    """
    env = EnvironmentalConditions(
        air_quality_index=100.0,
        air_quality_category=category,
    )

    result = format_air_quality_summary(env, settings)

    assert "Health guidance:" in result, "Health guidance section not found in summary"

    guidance_keywords = {
        "Good": "satisfactory",
        "Moderate": "acceptable",
        "Unhealthy for Sensitive Groups": "Sensitive groups",
        "Unhealthy": "reduce prolonged",
        "Very Unhealthy": "Avoid outdoor exertion",
        "Hazardous": "Avoid all outdoor activity",
    }

    expected_keyword = guidance_keywords[category]
    assert expected_keyword in result, (
        f"Expected guidance keyword '{expected_keyword}' for category '{category}' not found"
    )


@pytest.mark.unit
@given(
    hourly_data=hourly_air_quality_list(min_size=1),
    pollutant=st.sampled_from(POLLUTANT_CODES),
)
@settings(max_examples=100)
def test_pollutant_names_are_human_readable(
    hourly_data: list[HourlyAirQuality], pollutant: str
) -> None:
    """
    Property 9: Pollutant names are human-readable.

    **Feature: air-quality-dialog, Property 9: Pollutant names are human-readable**

    For any pollutant code in {PM2_5, PM10, O3, NO2, SO2, CO}, output SHALL use
    human-readable names and indicate dominant pollutant.
    """
    result = format_pollutant_details(hourly_data, dominant_pollutant=pollutant)

    human_readable_name = _POLLUTANT_LABELS[pollutant]
    if any(
        getattr(hourly_data[0], attr) is not None
        for attr in [
            "pm2_5",
            "pm10",
            "ozone",
            "nitrogen_dioxide",
            "sulphur_dioxide",
            "carbon_monoxide",
        ]
    ):
        pass

    pollutant_to_attr = {
        "PM2_5": "pm2_5",
        "PM10": "pm10",
        "O3": "ozone",
        "NO2": "nitrogen_dioxide",
        "SO2": "sulphur_dioxide",
        "CO": "carbon_monoxide",
    }
    attr = pollutant_to_attr[pollutant]
    if getattr(hourly_data[0], attr) is not None:
        assert human_readable_name in result, (
            f"Human-readable name '{human_readable_name}' not found in output"
        )
        assert "(dominant)" in result, "Dominant indicator not found for specified pollutant"


@pytest.mark.unit
@given(env=environmental_conditions(), settings=app_settings_strategy())
@settings(max_examples=100)
def test_formatting_function_is_deterministic(
    env: EnvironmentalConditions, settings: AppSettings
) -> None:
    """
    Property 11: Formatting function is deterministic.

    **Feature: air-quality-dialog, Property 11: Formatting function is deterministic**

    Calling the formatting function twice with identical inputs SHALL produce
    identical output.
    """
    result1 = format_air_quality_summary(env, settings)
    result2 = format_air_quality_summary(env, settings)

    assert result1 == result2, "format_air_quality_summary is not deterministic"


@pytest.mark.unit
@given(
    hourly_data=hourly_air_quality_list(min_size=1),
    pollutant=st.sampled_from(POLLUTANT_CODES + [None]),
)
@settings(max_examples=100)
def test_pollutant_details_formatting_is_deterministic(
    hourly_data: list[HourlyAirQuality], pollutant: str | None
) -> None:
    """
    Property 11: format_pollutant_details is deterministic.

    **Feature: air-quality-dialog, Property 11: Formatting function is deterministic**

    Calling the format_pollutant_details function twice with identical inputs
    SHALL produce identical output.
    """
    result1 = format_pollutant_details(hourly_data, dominant_pollutant=pollutant)
    result2 = format_pollutant_details(hourly_data, dominant_pollutant=pollutant)

    assert result1 == result2, "format_pollutant_details is not deterministic"


@st.composite
def hourly_air_quality_list_extended(
    draw: st.DrawFn, min_size: int = 1, max_size: int = 48
) -> list[HourlyAirQuality]:
    """Strategy for generating a list of HourlyAirQuality entries (up to 48 hours)."""
    base_time = datetime.now(UTC)
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    entries = []
    for i in range(size):
        entries.append(
            HourlyAirQuality(
                timestamp=base_time + timedelta(hours=i),
                aqi=draw(st.integers(min_value=0, max_value=500)),
                category=draw(st.sampled_from(AQI_CATEGORIES)),
                pm2_5=draw(st.floats(min_value=0, max_value=500) | st.none()),
                pm10=draw(st.floats(min_value=0, max_value=500) | st.none()),
                ozone=draw(st.floats(min_value=0, max_value=500) | st.none()),
                nitrogen_dioxide=draw(st.floats(min_value=0, max_value=500) | st.none()),
                sulphur_dioxide=draw(st.floats(min_value=0, max_value=500) | st.none()),
                carbon_monoxide=draw(st.floats(min_value=0, max_value=50000) | st.none()),
            )
        )
    return entries


@pytest.mark.unit
@given(hourly_data=hourly_air_quality_list_extended(min_size=25, max_size=48))
@settings(max_examples=100)
def test_hourly_forecast_limited_to_24_hours(hourly_data: list[HourlyAirQuality]) -> None:
    """
    Property 5: Hourly forecast limited to 24 hours.

    For any list of HourlyAirQuality entries with length > 24, the formatted hourly
    output SHALL contain at most 24 hour entries.
    """
    result = format_hourly_air_quality(hourly_data)

    assert result is not None, "Expected non-empty result for non-empty input"

    lines = result.split("\n")
    hour_entry_count = 0
    for line in lines:
        if line.startswith("Current:") or "Peak:" in line or "Best time:" in line:
            hour_entry_count += 1

    assert hour_entry_count <= 24, f"Expected at most 24 hour entries, got {hour_entry_count}"


@st.composite
def hourly_with_trend(draw: st.DrawFn, trend: str) -> list[HourlyAirQuality]:
    """Strategy for generating hourly data with a specific trend."""
    base_time = datetime.now(UTC)

    if trend == "worsening":
        first_aqi = draw(st.integers(min_value=0, max_value=200))
        third_aqi = first_aqi + draw(st.integers(min_value=21, max_value=100))
        third_aqi = min(third_aqi, 500)
    elif trend == "improving":
        first_aqi = draw(st.integers(min_value=50, max_value=500))
        third_aqi = first_aqi - draw(st.integers(min_value=21, max_value=min(first_aqi, 100)))
        third_aqi = max(third_aqi, 0)
    else:
        first_aqi = draw(st.integers(min_value=0, max_value=500))
        diff = draw(st.integers(min_value=-20, max_value=20))
        third_aqi = max(0, min(500, first_aqi + diff))

    second_aqi = draw(st.integers(min_value=0, max_value=500))

    entries = []
    for i, aqi in enumerate([first_aqi, second_aqi, third_aqi]):
        entries.append(
            HourlyAirQuality(
                timestamp=base_time + timedelta(hours=i),
                aqi=aqi,
                category=draw(st.sampled_from(AQI_CATEGORIES)),
            )
        )

    extra_count = draw(st.integers(min_value=0, max_value=5))
    for i in range(extra_count):
        entries.append(
            HourlyAirQuality(
                timestamp=base_time + timedelta(hours=3 + i),
                aqi=draw(st.integers(min_value=0, max_value=500)),
                category=draw(st.sampled_from(AQI_CATEGORIES)),
            )
        )

    return entries


@pytest.mark.unit
@given(hourly_data=hourly_with_trend("worsening"))
@settings(max_examples=100)
def test_trend_worsening_identified(hourly_data: list[HourlyAirQuality]) -> None:
    """
    Property 6: Trend correctly identifies direction (worsening).

    For any sequence of at least 3 HourlyAirQuality entries where AQI increases
    by more than 20 from first to third entry, the trend SHALL be "Worsening".
    """
    result = format_hourly_air_quality(hourly_data)

    assert result is not None
    assert "Trend: Worsening" in result, f"Expected 'Worsening' trend, got: {result}"


@pytest.mark.unit
@given(hourly_data=hourly_with_trend("improving"))
@settings(max_examples=100)
def test_trend_improving_identified(hourly_data: list[HourlyAirQuality]) -> None:
    """
    Property 6: Trend correctly identifies direction (improving).

    For any sequence of at least 3 HourlyAirQuality entries where AQI decreases
    by more than 20 from first to third entry, the trend SHALL be "Improving".
    """
    result = format_hourly_air_quality(hourly_data)

    assert result is not None
    assert "Trend: Improving" in result, f"Expected 'Improving' trend, got: {result}"


@pytest.mark.unit
@given(hourly_data=hourly_with_trend("stable"))
@settings(max_examples=100)
def test_trend_stable_identified(hourly_data: list[HourlyAirQuality]) -> None:
    """
    Property 6: Trend correctly identifies direction (stable).

    For any sequence of at least 3 HourlyAirQuality entries where AQI change
    from first to third is within 20 (inclusive), the trend SHALL be "Stable".
    """
    result = format_hourly_air_quality(hourly_data)

    assert result is not None
    assert "Trend: Stable" in result, f"Expected 'Stable' trend, got: {result}"


@pytest.mark.unit
@given(hourly_data=hourly_air_quality_list(min_size=1, max_size=24))
@settings(max_examples=100)
def test_peak_aqi_is_maximum_value(hourly_data: list[HourlyAirQuality]) -> None:
    """
    Property 7: Peak AQI is maximum value.

    For any non-empty list of HourlyAirQuality entries, the reported peak AQI
    SHALL equal the maximum AQI value in the list.
    """
    result = format_hourly_air_quality(hourly_data)

    assert result is not None

    max_aqi = max(h.aqi for h in hourly_data)

    peak_in_result = f"Peak: AQI {max_aqi}" in result
    current_is_peak = f"Current: AQI {max_aqi}" in result

    assert peak_in_result or current_is_peak, f"Peak AQI {max_aqi} not found in result: {result}"


@st.composite
def hourly_with_good_aqi_entry(draw: st.DrawFn) -> list[HourlyAirQuality]:
    """Strategy for generating hourly data with at least one AQI < 100."""
    base_time = datetime.now(UTC)

    size = draw(st.integers(min_value=2, max_value=24))
    good_index = draw(st.integers(min_value=0, max_value=size - 1))

    entries = []
    for i in range(size):
        if i == good_index:
            aqi = draw(st.integers(min_value=0, max_value=99))
        else:
            aqi = draw(st.integers(min_value=0, max_value=500))

        entries.append(
            HourlyAirQuality(
                timestamp=base_time + timedelta(hours=i),
                aqi=aqi,
                category=draw(st.sampled_from(AQI_CATEGORIES)),
            )
        )

    return entries


@pytest.mark.unit
@given(hourly_data=hourly_with_good_aqi_entry())
@settings(max_examples=100)
def test_best_time_has_aqi_below_threshold(hourly_data: list[HourlyAirQuality]) -> None:
    """
    Property 8: Best time has AQI below threshold.

    For any list of HourlyAirQuality entries where at least one entry has AQI < 100,
    the reported best time SHALL correspond to an entry with AQI < 100.
    """
    result = format_hourly_air_quality(hourly_data)

    assert result is not None

    best_entry = min(hourly_data, key=lambda h: h.aqi)

    if best_entry.aqi < 100:
        if best_entry != hourly_data[0]:
            assert f"Best time: AQI {best_entry.aqi}" in result, (
                f"Expected best time with AQI {best_entry.aqi} in result: {result}"
            )
        else:
            assert f"Current: AQI {best_entry.aqi}" in result
