"""Tests for Pollen data presentation in the Air Quality panel."""

from __future__ import annotations

from datetime import datetime

from accessiweather.display.presentation.environmental import build_air_quality_panel
from accessiweather.models import EnvironmentalConditions, Location


def test_pollen_data_in_air_quality_panel():
    """Test that pollen data is included in the air quality panel output."""
    location = Location(name="Test City", latitude=0.0, longitude=0.0)

    # Create conditions with BOTH air quality and pollen data
    env = EnvironmentalConditions(
        air_quality_index=50,
        air_quality_category="Good",
        pollen_index=80,
        pollen_category="High",
        pollen_primary_allergen="Grass",
        pollen_tree_index=10,
        pollen_grass_index=80,
        pollen_weed_index=20,
        updated_at=datetime.now(),
    )

    presentation = build_air_quality_panel(location, env)

    assert presentation is not None

    # These assertions are expected to FAIL initially
    assert (
        "Pollen: High (Grass)" in presentation.summary
        or "Pollen High" in presentation.summary
        or any("Pollen" in line for line in presentation.details)
    ), "Pollen summary not found in presentation"

    assert any("Grass: 80" in line for line in presentation.details), (
        "Grass pollen details not found"
    )
    assert any("Tree: 10" in line for line in presentation.details), "Tree pollen details not found"
    assert any("Weed: 20" in line for line in presentation.details), "Weed pollen details not found"
