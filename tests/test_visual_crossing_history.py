"""Unit tests for Visual Crossing history API integration."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.models import Forecast, ForecastPeriod, Location
from accessiweather.visual_crossing_client import VisualCrossingClient


@pytest.fixture
def vc_client():
    """Create Visual Crossing client with mock API key."""
    return VisualCrossingClient(api_key="test_key")


@pytest.fixture
def test_location():
    """Test location."""
    return Location(name="Test City", latitude=40.7128, longitude=-74.0060)


@pytest.fixture
def mock_history_response():
    """Mock API response for historical weather data."""
    return {
        "days": [
            {
                "datetime": "2025-12-04",
                "tempmax": 45.0,
                "tempmin": 32.0,
                "temp": 38.5,
                "conditions": "Partly cloudy",
                "description": "Partly cloudy throughout the day.",
                "windspeed": 10.5,
                "winddir": 270,
                "icon": "partly-cloudy-day",
                "precipprob": 20,
                "snow": 0,
                "uvindex": 3,
            }
        ]
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_constructs_correct_url(vc_client, test_location):
    """Test that get_history constructs the correct API URL."""
    yesterday = datetime(2025, 12, 4)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"days": []}
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        await vc_client.get_history(test_location, yesterday, yesterday)

        # Verify the URL was constructed correctly
        call_args = mock_client.get.call_args
        url = call_args[0][0]
        assert "40.7128,-74.006" in url
        assert "2025-12-04" in url


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_includes_required_params(vc_client, test_location):
    """Test that get_history includes all required API parameters."""
    yesterday = datetime(2025, 12, 4)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"days": []}
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        await vc_client.get_history(test_location, yesterday, yesterday)

        # Verify parameters
        call_args = mock_client.get.call_args
        params = call_args[1]["params"]

        assert "key" in params
        assert params["key"] == "test_key"
        assert params["include"] == "days"
        assert params["unitGroup"] == "us"
        assert "elements" in params


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_parses_response(vc_client, test_location, mock_history_response):
    """Test that get_history correctly parses the API response."""
    yesterday = datetime(2025, 12, 4)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_history_response
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        result = await vc_client.get_history(test_location, yesterday, yesterday)

        assert result is not None
        assert isinstance(result, Forecast)
        assert len(result.periods) == 1

        period = result.periods[0]
        assert isinstance(period, ForecastPeriod)
        # Visual Crossing parser uses tempmax for daily forecasts
        assert period.temperature == 45.0  # tempmax from mock data
        assert period.temperature_unit == "F"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_handles_date_range(vc_client, test_location):
    """Test that get_history handles date ranges correctly."""
    end_date = datetime(2025, 12, 4)
    start_date = datetime(2025, 12, 2)

    mock_response_data = {
        "days": [
            {"datetime": "2025-12-02", "temp": 35.0, "tempmax": 40.0, "tempmin": 30.0},
            {"datetime": "2025-12-03", "temp": 38.0, "tempmax": 43.0, "tempmin": 33.0},
            {"datetime": "2025-12-04", "temp": 40.0, "tempmax": 45.0, "tempmin": 35.0},
        ]
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        result = await vc_client.get_history(test_location, start_date, end_date)

        assert result is not None
        assert len(result.periods) == 3

        # Verify URL contains both dates
        call_args = mock_client.get.call_args
        url = call_args[0][0]
        assert "2025-12-02" in url
        assert "2025-12-04" in url


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_handles_api_errors(vc_client, test_location):
    """Test that get_history handles API errors gracefully."""
    yesterday = datetime(2025, 12, 4)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 401  # Unauthorized
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        from accessiweather.visual_crossing_client import VisualCrossingApiError

        with pytest.raises(VisualCrossingApiError):
            await vc_client.get_history(test_location, yesterday, yesterday)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_history_formats_dates_correctly(vc_client, test_location):
    """Test that dates are formatted as YYYY-MM-DD."""
    test_date = datetime(2025, 12, 4, 15, 30, 45)  # Include time components

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"days": []}
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        await vc_client.get_history(test_location, test_date, test_date)

        # Verify date format in URL (should strip time)
        call_args = mock_client.get.call_args
        url = call_args[0][0]
        assert "2025-12-04" in url
        # Should not include time components
        assert "15:30" not in url
