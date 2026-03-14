"""Tests for Visual Crossing air quality fallback in EnvironmentalDataClient."""

from __future__ import annotations

from accessiweather.models import EnvironmentalConditions
from accessiweather.services.environmental_client import EnvironmentalDataClient


class TestVcAirQualityFallback:
    """Tests for populate_from_visual_crossing fallback."""

    def test_populates_when_no_existing_aq(self):
        """Test VC AQ data used when Open-Meteo has no data."""
        client = EnvironmentalDataClient()
        env = EnvironmentalConditions()

        assert env.air_quality_index is None

        vc_data = {"aqius": 55, "pm2p5": 12.3}
        client.populate_from_visual_crossing(vc_data, env)

        assert env.air_quality_index == 55.0
        assert env.air_quality_category == "Moderate"
        assert "Visual Crossing Air Quality" in env.sources

    def test_skips_when_existing_aq(self):
        """Test VC AQ data not used when Open-Meteo already has data."""
        client = EnvironmentalDataClient()
        env = EnvironmentalConditions()
        env.air_quality_index = 30.0
        env.air_quality_category = "Good"
        env.sources.append("Open-Meteo Air Quality")

        vc_data = {"aqius": 55}
        client.populate_from_visual_crossing(vc_data, env)

        # Should keep Open-Meteo data
        assert env.air_quality_index == 30.0
        assert env.air_quality_category == "Good"
        assert "Visual Crossing Air Quality" not in env.sources

    def test_handles_none_data(self):
        """Test graceful handling of None VC data."""
        client = EnvironmentalDataClient()
        env = EnvironmentalConditions()

        client.populate_from_visual_crossing(None, env)
        assert env.air_quality_index is None

    def test_handles_empty_data(self):
        """Test graceful handling of empty VC data."""
        client = EnvironmentalDataClient()
        env = EnvironmentalConditions()

        client.populate_from_visual_crossing({}, env)
        assert env.air_quality_index is None

    def test_category_mapping(self):
        """Test AQI category mapping from VC data."""
        client = EnvironmentalDataClient()

        # Good
        env = EnvironmentalConditions()
        client.populate_from_visual_crossing({"aqius": 25}, env)
        assert env.air_quality_category == "Good"

        # Unhealthy for Sensitive Groups
        env = EnvironmentalConditions()
        client.populate_from_visual_crossing({"aqius": 120}, env)
        assert env.air_quality_category == "Unhealthy for Sensitive Groups"

        # Hazardous
        env = EnvironmentalConditions()
        client.populate_from_visual_crossing({"aqius": 350}, env)
        assert env.air_quality_category == "Hazardous"
