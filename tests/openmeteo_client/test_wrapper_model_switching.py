"""Tests for Open-Meteo API wrapper model switching functionality."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.api.openmeteo_wrapper import OpenMeteoApiWrapper


class TestOpenMeteoWrapperModelSwitching:
    """Test suite for Open-Meteo wrapper model parameter handling."""

    @pytest.fixture
    def wrapper(self):
        """Create an OpenMeteoApiWrapper instance for testing."""
        with patch("accessiweather.api.openmeteo_wrapper.OpenMeteoApiClient"):
            wrapper = OpenMeteoApiWrapper(user_agent="TestWrapper")
            # Mock the underlying client
            wrapper.openmeteo_client = MagicMock()
            return wrapper

    @pytest.fixture
    def mock_current_response(self):
        """Mock response for current conditions."""
        return {
            "current": {"temperature_2m": 72.5},
            "current_units": {"temperature_2m": "°F"},
        }

    @pytest.fixture
    def mock_forecast_response(self):
        """Mock response for forecast."""
        return {
            "daily": {"time": ["2024-01-01"], "temperature_2m_max": [75.0]},
            "daily_units": {"temperature_2m_max": "°F"},
        }

    @pytest.fixture
    def mock_hourly_response(self):
        """Mock response for hourly forecast."""
        return {
            "hourly": {"time": ["2024-01-01T12:00"], "temperature_2m": [72.0]},
            "hourly_units": {"temperature_2m": "°F"},
        }

    def test_get_current_conditions_passes_model(self, wrapper, mock_current_response):
        """Test that model parameter is passed to underlying client."""
        wrapper.openmeteo_client.get_current_weather.return_value = mock_current_response

        wrapper.get_current_conditions(40.0, -75.0, model="icon_seamless")

        wrapper.openmeteo_client.get_current_weather.assert_called_once()
        call_kwargs = wrapper.openmeteo_client.get_current_weather.call_args.kwargs
        assert call_kwargs.get("model") == "icon_seamless"

    def test_get_current_conditions_default_model(self, wrapper, mock_current_response):
        """Test that default model is passed when not specified."""
        wrapper.openmeteo_client.get_current_weather.return_value = mock_current_response

        wrapper.get_current_conditions(40.0, -75.0)

        call_kwargs = wrapper.openmeteo_client.get_current_weather.call_args.kwargs
        assert call_kwargs.get("model") == "best_match"

    def test_get_forecast_passes_model(self, wrapper, mock_forecast_response):
        """Test that model parameter is passed for forecast."""
        wrapper.openmeteo_client.get_forecast.return_value = mock_forecast_response

        wrapper.get_forecast(40.0, -75.0, model="gfs_seamless")

        call_kwargs = wrapper.openmeteo_client.get_forecast.call_args.kwargs
        assert call_kwargs.get("model") == "gfs_seamless"

    def test_get_hourly_forecast_passes_model(self, wrapper, mock_hourly_response):
        """Test that model parameter is passed for hourly forecast."""
        wrapper.openmeteo_client.get_hourly_forecast.return_value = mock_hourly_response

        wrapper.get_hourly_forecast(40.0, -75.0, model="ecmwf_ifs04")

        call_kwargs = wrapper.openmeteo_client.get_hourly_forecast.call_args.kwargs
        assert call_kwargs.get("model") == "ecmwf_ifs04"

    def test_cache_key_includes_model(self, wrapper, mock_current_response):
        """Test that cache key includes model for proper cache invalidation."""
        wrapper.openmeteo_client.get_current_weather.return_value = mock_current_response

        # Call with different models
        wrapper.get_current_conditions(40.0, -75.0, model="icon_seamless", force_refresh=True)
        wrapper.get_current_conditions(40.0, -75.0, model="gfs_seamless", force_refresh=True)

        # Both should have been called (different cache keys due to different models)
        assert wrapper.openmeteo_client.get_current_weather.call_count == 2

    @pytest.mark.parametrize(
        "model",
        [
            "best_match",
            "icon_seamless",
            "icon_global",
            "icon_eu",
            "icon_d2",
            "gfs_seamless",
            "gfs_global",
            "ecmwf_ifs04",
            "meteofrance_seamless",
            "gem_seamless",
            "jma_seamless",
        ],
    )
    def test_all_models_passed_correctly(self, wrapper, mock_current_response, model):
        """Test all supported models are passed to underlying client."""
        wrapper.openmeteo_client.get_current_weather.return_value = mock_current_response

        wrapper.get_current_conditions(40.0, -75.0, model=model)

        call_kwargs = wrapper.openmeteo_client.get_current_weather.call_args.kwargs
        assert call_kwargs.get("model") == model
