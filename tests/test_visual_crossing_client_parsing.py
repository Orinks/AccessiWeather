"""Regression coverage for Visual Crossing client parsing."""

from __future__ import annotations

import copy
from datetime import datetime

import pytest

from accessiweather.visual_crossing_client import VisualCrossingClient

AKRON_SAMPLE = {
    "address": "Akron, OH",
    "timezone": "America/New_York",
    "tzoffset": -4.0,
    "latitude": 41.0814,
    "longitude": -81.519,
    "currentConditions": {
        "datetimeEpoch": 1726665600,
        "datetime": "2024-09-18T08:00:00-04:00",
        "temp": 68.0,
        "feelslike": 67.0,
        "humidity": 72.0,
        "windspeed": 6.0,
        "winddir": 210.0,
        "pressure": 30.01,
        "visibility": 9.9,
        "dew": 58.0,
        "conditions": "Partly Cloudy",
    },
    "days": [
        {
            "datetime": "2024-09-18",
            "tempmax": 78.0,
            "tempmin": 59.0,
            "temp": 68.0,
            "conditions": "Partly Cloudy",
            "description": "Partly cloudy throughout the day with a gentle breeze.",
            "windspeed": 10.0,
            "winddir": 215.0,
            "icon": "partly-cloudy-day",
            "sunrise": "06:45:00",
            "sunriseEpoch": 1726656300,
            "sunset": "19:15:00",
            "sunsetEpoch": 1726697700,
            "moonrise": "11:20:00",
            "moonriseEpoch": 1726672800,
            "moonset": "22:05:00",
            "moonsetEpoch": 1726711500,
            "moonphase": 0.48,
            "hours": [
                {
                    "datetime": "08:00:00",
                    "temp": 65.0,
                    "conditions": "Partly Cloudy",
                    "windspeed": 8.0,
                    "winddir": 210.0,
                    "icon": "partly-cloudy-day",
                    "pressure": 1016.0,
                    "precipprob": 10.0,
                    "humidity": 70.0,
                },
                {
                    "datetime": "14:00:00",
                    "temp": 77.0,
                    "conditions": "Mostly Sunny",
                    "windspeed": 12.0,
                    "winddir": 220.0,
                    "icon": "clear-day",
                    "pressure": 1010.0,
                    "precipprob": 15.0,
                    "humidity": 55.0,
                },
            ],
        },
        {
            "datetime": "2024-09-19",
            "tempmax": 80.0,
            "tempmin": 60.0,
            "temp": 70.0,
            "conditions": "Sunny",
            "description": "Sunny with high clouds late.",
            "windspeed": 9.0,
            "winddir": 200.0,
            "icon": "clear-day",
            "hours": [],
        },
    ],
    "alerts": [
        {
            "event": "Heat Advisory",
            "severity": "moderate",
            "headline": "Heat Advisory for Summit County",
            "description": "Temperatures are expected to feel hotter during the afternoon.",
            "onset": "2024-09-18T17:00:00Z",
            "expires": "2024-09-19T00:00:00Z",
            "id": "alert-001",
        }
    ],
}


@pytest.fixture(scope="module")
def visual_crossing_payload() -> dict:
    """Provide a reusable copy of the captured Visual Crossing sample payload."""
    return copy.deepcopy(AKRON_SAMPLE)


@pytest.fixture
def visual_crossing_client() -> VisualCrossingClient:
    """Provide a Visual Crossing client instance with a dummy key."""
    return VisualCrossingClient(api_key="dummy-key")


def test_visual_crossing_forecast_preserves_fahrenheit(
    visual_crossing_client: VisualCrossingClient, visual_crossing_payload: dict
) -> None:
    """Ensure forecast parsing keeps Fahrenheit highs from the API payload."""
    forecast = visual_crossing_client._parse_forecast(visual_crossing_payload)

    assert forecast.periods, "Expected at least one forecast period"

    first_source_day = visual_crossing_payload["days"][0]
    first_period = forecast.periods[0]

    assert first_period.name == "Today"
    assert first_period.temperature == pytest.approx(first_source_day["tempmax"])
    assert first_period.temperature_unit == "F"
    assert first_period.short_forecast == first_source_day["conditions"]
    assert first_period.wind_speed == "10.0 mph"


def test_visual_crossing_hourly_forecast_keeps_fahrenheit(
    visual_crossing_client: VisualCrossingClient, visual_crossing_payload: dict
) -> None:
    """Ensure hourly forecast parsing keeps Fahrenheit temperatures."""
    hourly = visual_crossing_client._parse_hourly_forecast(visual_crossing_payload)

    assert hourly.periods, "Expected at least one hourly period"

    source_hour = visual_crossing_payload["days"][0]["hours"][0]
    first_hour = hourly.periods[0]

    assert first_hour.temperature == pytest.approx(source_hour["temp"])
    assert first_hour.temperature_unit == "F"
    assert first_hour.short_forecast == source_hour["conditions"]
    assert first_hour.wind_direction == "SSW"
    assert first_hour.wind_speed == "8.0 mph"


def test_visual_crossing_current_conditions_fahrenheit_fields(
    visual_crossing_client: VisualCrossingClient, visual_crossing_payload: dict
) -> None:
    """Confirm current conditions include Fahrenheit values and conversions."""
    current = visual_crossing_client._parse_current_conditions(visual_crossing_payload)

    assert current.temperature_f == pytest.approx(68.0)
    assert current.temperature_c == pytest.approx(20.0, abs=0.1)
    assert current.dewpoint_f == pytest.approx(58.0)
    assert current.dewpoint_c == pytest.approx(14.4, abs=0.1)
    assert current.visibility_miles == pytest.approx(9.9)
    # Times are parsed from string format in local timezone (tzoffset=-4 for EDT)
    from datetime import timedelta, timezone

    edt = timezone(timedelta(hours=-4))
    assert current.sunrise_time == datetime(2024, 9, 18, 6, 45, 0, tzinfo=edt)
    assert current.sunset_time == datetime(2024, 9, 18, 19, 15, 0, tzinfo=edt)
    assert current.moonrise_time == datetime(2024, 9, 18, 11, 20, 0, tzinfo=edt)
    assert current.moonset_time == datetime(2024, 9, 18, 22, 5, 0, tzinfo=edt)
    assert current.moon_phase == "Full Moon"


def test_visual_crossing_alerts_normalise_severity(
    visual_crossing_client: VisualCrossingClient, visual_crossing_payload: dict
) -> None:
    """Verify alerts parsing maps severity levels consistently."""
    alerts = visual_crossing_client._parse_alerts(visual_crossing_payload)

    assert len(alerts.alerts) == 1
    alert = alerts.alerts[0]

    assert alert.event == "Heat Advisory"
    assert alert.severity == "Moderate"
    assert alert.id == "alert-001"
