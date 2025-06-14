"""Client mock fixtures for testing."""

from unittest.mock import MagicMock

import pytest

from accessiweather.api_client import NoaaApiClient
from accessiweather.api_wrapper import NoaaApiWrapper
from accessiweather.openmeteo_client import OpenMeteoApiClient


@pytest.fixture
def mock_nws_client():
    """Mock NWS API client."""
    return MagicMock(spec=NoaaApiClient)


@pytest.fixture
def mock_nws_wrapper():
    """Mock NWS API wrapper."""
    return MagicMock(spec=NoaaApiWrapper)


@pytest.fixture
def mock_openmeteo_client():
    """Mock Open-Meteo API client."""
    return MagicMock(spec=OpenMeteoApiClient)
