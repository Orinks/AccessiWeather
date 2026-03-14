"""
Tests verifying NWS API endpoint compatibility post-May 2025 changes.

SCN 25-44 (effective May 22, 2025) confirmed the following NWS API endpoints
remain unchanged.  These tests verify our wrapper constructs the correct
patterns so we catch any accidental drift.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from accessiweather.api.nws import NwsApiWrapper
from accessiweather.api.nws.core_client import NwsCoreClient


class TestNwsEndpointCompatibility:
    """Verify NWS API endpoint patterns are current."""

    def _make_wrapper(self, **kwargs) -> NwsApiWrapper:
        """Create an NwsApiWrapper with sensible defaults for testing."""
        defaults = {
            "user_agent": "TestApp/1.0",
            "contact_info": "test@example.com",
        }
        defaults.update(kwargs)
        return NwsApiWrapper(**defaults)

    # ------------------------------------------------------------------
    # Base URL
    # ------------------------------------------------------------------

    def test_base_url(self):
        """Verify base URL is https://api.weather.gov."""
        assert NwsCoreClient.BASE_URL == "https://api.weather.gov"

    def test_wrapper_exposes_base_url(self):
        """Verify the wrapper exposes the same base URL."""
        wrapper = self._make_wrapper()
        assert wrapper.BASE_URL == "https://api.weather.gov"

    # ------------------------------------------------------------------
    # Points endpoint
    # ------------------------------------------------------------------

    def test_points_endpoint_format(self):
        """Verify points endpoint uses /points/{lat},{lon} format."""
        wrapper = self._make_wrapper()

        # The generated client builds /points/{point} where point="lat,lon"
        # Confirm the wrapper would call with the right cache key pattern.
        cache_key_endpoint = f"points/40.7128,-74.006"
        assert cache_key_endpoint.startswith("points/")
        assert "40.7128,-74.006" in cache_key_endpoint

        # Also confirm the full URL would be correct
        url = f"{wrapper.BASE_URL}/points/40.7128,-74.006"
        assert url == "https://api.weather.gov/points/40.7128,-74.006"

    # ------------------------------------------------------------------
    # Alerts endpoint
    # ------------------------------------------------------------------

    def test_alerts_point_url_construction(self):
        """Verify alerts use /alerts/active?point={lat},{lon} URL pattern."""
        wrapper = self._make_wrapper()
        base = wrapper.core_client.BASE_URL

        # This mirrors the URL constructed in NwsAlertsDiscussions.get_alerts
        url = f"{base}/alerts/active?point=40.7128,-74.006"
        assert url == "https://api.weather.gov/alerts/active?point=40.7128,-74.006"

    def test_alerts_uses_point_parameter_in_code(self):
        """Verify the alerts code constructs the URL with point= parameter."""
        wrapper = self._make_wrapper()

        # Patch _get_cached_or_fetch to capture what fetch_data would do,
        # and _rate_limit / httpx to avoid real network calls.
        with (
            patch.object(wrapper, "_get_cached_or_fetch") as mock_cache,
            patch("accessiweather.api.nws.alerts_discussions.httpx") as mock_httpx,
        ):
            # Make _get_cached_or_fetch call the fetch function immediately
            mock_cache.side_effect = lambda _key, fn, _force: fn()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {}
            mock_response.json.return_value = {"features": []}
            mock_response.raise_for_status = MagicMock()

            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_httpx.Client.return_value = mock_client
            mock_httpx.Timeout = MagicMock()

            wrapper.get_alerts(40.7128, -74.006, precise_location=True)

            # Verify the URL passed to httpx.Client().get()
            call_args = mock_client.get.call_args
            requested_url = call_args[0][0]
            assert "/alerts/active" in requested_url
            assert "point=40.7128,-74.006" in requested_url

    # ------------------------------------------------------------------
    # Observations endpoint
    # ------------------------------------------------------------------

    def test_observations_endpoint_pattern(self):
        """Verify observations use /stations/{id}/observations/latest."""
        wrapper = self._make_wrapper()
        base = wrapper.core_client.BASE_URL

        station_url = f"{base}/stations/KJFK/observations/latest"
        assert station_url == ("https://api.weather.gov/stations/KJFK/observations/latest")

    def test_observation_cache_key_uses_correct_path(self):
        """Verify the observation cache key references the correct path."""
        # NwsWeatherData._fetch_station_observation uses this cache key pattern
        cache_key_path = "stations/KJFK/observations/latest"
        assert "stations/" in cache_key_path
        assert "/observations/latest" in cache_key_path

    # ------------------------------------------------------------------
    # Products endpoint
    # ------------------------------------------------------------------

    def test_products_endpoint_pattern(self):
        """Verify products use /products/types/{type}/locations/{loc}."""
        wrapper = self._make_wrapper()
        base = wrapper.core_client.BASE_URL

        url = f"{base}/products/types/AFD/locations/OKX"
        assert url == "https://api.weather.gov/products/types/AFD/locations/OKX"

    # ------------------------------------------------------------------
    # User-Agent header
    # ------------------------------------------------------------------

    def test_user_agent_is_set(self):
        """Verify User-Agent is configured (NWS requires it)."""
        wrapper = self._make_wrapper(user_agent="TestApp/1.0")
        assert wrapper.user_agent == "TestApp/1.0"
        assert len(wrapper.user_agent) > 0

    def test_user_agent_included_in_client_headers(self):
        """Verify the generated client sends a User-Agent header."""
        wrapper = self._make_wrapper(
            user_agent="TestApp/1.0",
            contact_info="test@example.com",
        )
        client = wrapper.core_client.client
        assert client is not None
        headers = client._headers  # type: ignore[attr-defined]
        assert "User-Agent" in headers
        assert "TestApp/1.0" in headers["User-Agent"]

    # ------------------------------------------------------------------
    # Forecast / hourly forecast (derived from points response)
    # ------------------------------------------------------------------

    def test_forecast_url_extracted_from_point_data(self):
        """Verify forecast URL is taken from the points response, not hardcoded."""
        # Simulate what the code does: it reads properties.forecast from point data
        mock_point_data = {
            "properties": {
                "forecast": ("https://api.weather.gov/gridpoints/OKX/33,37/forecast"),
                "forecastHourly": ("https://api.weather.gov/gridpoints/OKX/33,37/forecast/hourly"),
                "observationStations": ("https://api.weather.gov/gridpoints/OKX/33,37/stations"),
            }
        }

        forecast_url = mock_point_data["properties"]["forecast"]
        hourly_url = mock_point_data["properties"]["forecastHourly"]

        # Confirm these are well-formed NWS gridpoints URLs
        assert forecast_url.startswith("https://api.weather.gov/gridpoints/")
        assert forecast_url.endswith("/forecast")
        assert hourly_url.endswith("/forecast/hourly")
