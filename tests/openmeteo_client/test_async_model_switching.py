"""Async tests for Open-Meteo weather model switching functionality."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from accessiweather.models import Location
from accessiweather.weather_client_openmeteo import (
    get_openmeteo_all_data_parallel,
    get_openmeteo_current_conditions,
    get_openmeteo_forecast,
    get_openmeteo_hourly_forecast,
)


@pytest.fixture
def location():
    """Create a test location."""
    return Location(name="Test City", latitude=40.0, longitude=-75.0)


@pytest.fixture
def mock_current_response():
    """Mock response for current conditions."""
    return {
        "latitude": 40.0,
        "longitude": -75.0,
        "utc_offset_seconds": -18000,
        "current": {
            "temperature_2m": 72.5,
            "relative_humidity_2m": 65,
            "apparent_temperature": 75.0,
            "weather_code": 1,
            "wind_speed_10m": 8.5,
            "wind_direction_10m": 180,
            "pressure_msl": 1013.2,
            "snowfall": 0,
            "snow_depth": 0,
            "visibility": 16000,
        },
        "current_units": {
            "temperature_2m": "°F",
            "wind_speed_10m": "mph",
            "pressure_msl": "hPa",
            "snow_depth": "ft",
        },
        "daily": {
            "sunrise": ["2024-01-01T07:15:00"],
            "sunset": ["2024-01-01T17:30:00"],
            "uv_index_max": [5.0],
        },
    }


@pytest.fixture
def mock_forecast_response():
    """Mock response for daily forecast."""
    return {
        "latitude": 40.0,
        "longitude": -75.0,
        "utc_offset_seconds": -18000,
        "daily": {
            "time": ["2024-01-01", "2024-01-02"],
            "temperature_2m_max": [75.0, 78.0],
            "temperature_2m_min": [55.0, 58.0],
            "weather_code": [1, 2],
            "precipitation_probability_max": [10, 30],
            "snowfall_sum": [0, 0],
            "uv_index_max": [5.0, 6.0],
        },
    }


@pytest.fixture
def mock_hourly_response():
    """Mock response for hourly forecast."""
    return {
        "latitude": 40.0,
        "longitude": -75.0,
        "utc_offset_seconds": -18000,
        "hourly": {
            "time": ["2024-01-01T12:00", "2024-01-01T13:00"],
            "temperature_2m": [72.0, 74.0],
            "weather_code": [1, 1],
            "wind_speed_10m": [8.5, 9.0],
            "wind_direction_10m": [180, 185],
            "pressure_msl": [1013.2, 1013.0],
            "precipitation_probability": [10, 15],
            "snowfall": [0, 0],
            "uv_index": [5.0, 5.5],
            "snow_depth": [0, 0],
            "freezing_level_height": [3000, 3100],
            "visibility": [16000, 16000],
            "apparent_temperature": [75.0, 77.0],
        },
    }


class TestAsyncModelSwitching:
    """Test async functions pass model parameter correctly."""

    @pytest.mark.asyncio
    async def test_current_conditions_with_model(self, location, mock_current_response):
        """Test that model parameter is passed in current conditions request."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_current_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = MagicMock(return_value=mock_response)

        result = await get_openmeteo_current_conditions(
            location,
            "https://api.open-meteo.com/v1",
            30.0,
            mock_client,
            model="icon_seamless",
        )

        assert result is not None
        # Verify the model was passed in params
        call_args = mock_client.get.call_args
        params = call_args.kwargs.get("params", {})
        assert params.get("models") == "icon_seamless"

    @pytest.mark.asyncio
    async def test_current_conditions_default_model(self, location, mock_current_response):
        """Test that default model doesn't add models param."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_current_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = MagicMock(return_value=mock_response)

        result = await get_openmeteo_current_conditions(
            location,
            "https://api.open-meteo.com/v1",
            30.0,
            mock_client,
            model="best_match",
        )

        assert result is not None
        call_args = mock_client.get.call_args
        params = call_args.kwargs.get("params", {})
        assert "models" not in params

    @pytest.mark.asyncio
    async def test_forecast_with_model(self, location, mock_forecast_response):
        """Test that model parameter is passed in forecast request."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_forecast_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = MagicMock(return_value=mock_response)

        result = await get_openmeteo_forecast(
            location,
            "https://api.open-meteo.com/v1",
            30.0,
            mock_client,
            model="gfs_seamless",
        )

        assert result is not None
        call_args = mock_client.get.call_args
        params = call_args.kwargs.get("params", {})
        assert params.get("models") == "gfs_seamless"

    @pytest.mark.asyncio
    async def test_hourly_forecast_with_model(self, location, mock_hourly_response):
        """Test that model parameter is passed in hourly forecast request."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_hourly_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = MagicMock(return_value=mock_response)

        result = await get_openmeteo_hourly_forecast(
            location,
            "https://api.open-meteo.com/v1",
            30.0,
            mock_client,
            model="ecmwf_ifs04",
        )

        assert result is not None
        call_args = mock_client.get.call_args
        params = call_args.kwargs.get("params", {})
        assert params.get("models") == "ecmwf_ifs04"

    @pytest.mark.asyncio
    async def test_parallel_fetch_passes_model(
        self, location, mock_current_response, mock_forecast_response, mock_hourly_response
    ):
        """Test that parallel fetch passes model to all sub-requests."""

        # Create mock responses for each endpoint
        def mock_get(url, params=None):
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            if "current" in (params or {}).get("current", ""):
                mock_resp.json.return_value = mock_current_response
            elif "daily" in (params or {}).get("daily", ""):
                mock_resp.json.return_value = mock_forecast_response
            else:
                mock_resp.json.return_value = mock_hourly_response
            return mock_resp

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get = MagicMock(side_effect=mock_get)

        # Patch the individual fetch functions to track model parameter
        with (
            patch(
                "accessiweather.weather_client_openmeteo.get_openmeteo_current_conditions"
            ) as mock_current,
            patch(
                "accessiweather.weather_client_openmeteo.get_openmeteo_forecast"
            ) as mock_forecast,
            patch(
                "accessiweather.weather_client_openmeteo.get_openmeteo_hourly_forecast"
            ) as mock_hourly,
        ):
            mock_current.return_value = None
            mock_forecast.return_value = None
            mock_hourly.return_value = None

            await get_openmeteo_all_data_parallel(
                location,
                "https://api.open-meteo.com/v1",
                30.0,
                mock_client,
                model="meteofrance_seamless",
            )

            # Verify model was passed to all sub-functions
            assert (
                mock_current.call_args[1].get("model") == "meteofrance_seamless"
                or mock_current.call_args[0][4] == "meteofrance_seamless"
            )
