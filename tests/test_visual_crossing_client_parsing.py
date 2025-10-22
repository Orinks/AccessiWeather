"""Regression coverage for Visual Crossing client parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from accessiweather.visual_crossing_client import VisualCrossingClient

FIXTURE_PATH = Path(__file__).with_name("visual_crossing_akron_forecast.json")


@pytest.fixture(scope="module")
def visual_crossing_payload() -> dict:
    """Load the captured Visual Crossing sample payload for Akron, Ohio."""
    return json.loads(FIXTURE_PATH.read_text())


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
