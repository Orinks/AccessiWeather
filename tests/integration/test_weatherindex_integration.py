"""Focused integration coverage for the live WeatherIndex NOAA radio API."""

from __future__ import annotations

import pytest
import requests


@pytest.mark.integration
class TestWeatherIndexIntegration:
    """Verify stable structural contracts for the live WeatherIndex API."""

    def test_states_endpoint_returns_expected_keys(self):
        response = requests.get("https://api.wxindex.org/v1/states", timeout=15)
        response.raise_for_status()

        payload = response.json()
        assert isinstance(payload, list)
        assert payload
        first = payload[0]
        assert isinstance(first, dict)
        assert {"state_name", "state_slug", "station_count", "stations_with_feeds"} <= set(first)

    def test_station_detail_returns_feeds_field(self):
        response = requests.get("https://api.wxindex.org/v1/stations/WXK27", timeout=15)
        response.raise_for_status()

        payload = response.json()
        assert isinstance(payload, dict)
        assert "feeds" in payload
        assert isinstance(payload["feeds"], list)
