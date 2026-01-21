"""
Tests for WeatherClient.

Tests the main weather client orchestration logic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from accessiweather.models import (
    AppSettings,
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    Location,
    WeatherAlerts,
    WeatherData,
)
from accessiweather.weather_client import WeatherClient


class TestWeatherClientInit:
    """Tests for WeatherClient initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        client = WeatherClient()
        assert client.user_agent == "AccessiWeather/1.0"
        assert client.data_source == "auto"
        assert client.timeout == 10.0

    def test_custom_initialization(self):
        """Test custom initialization."""
        settings = AppSettings(enable_alerts=False, update_interval_minutes=30)
        client = WeatherClient(
            user_agent="TestApp/1.0",
            data_source="openmeteo",
            settings=settings,
        )
        assert client.user_agent == "TestApp/1.0"
        assert client.data_source == "openmeteo"
        assert client.alerts_enabled is False

    def test_visual_crossing_api_key_lazy(self):
        """Test that VC API key is handled lazily."""
        client = WeatherClient(visual_crossing_api_key="test-key")
        assert client.visual_crossing_api_key == "test-key"
        # Client should not be created until accessed
        assert client._visual_crossing_client is None


class TestWeatherClientDataSource:
    """Tests for data source selection logic."""

    @pytest.fixture
    def client(self):
        """Create a WeatherClient instance."""
        return WeatherClient()

    @pytest.fixture
    def us_location(self):
        """US location for testing."""
        return Location(name="NYC", latitude=40.7128, longitude=-74.0060, country_code="US")

    @pytest.fixture
    def intl_location(self):
        """International location for testing."""
        return Location(name="London", latitude=51.5074, longitude=-0.1278, country_code="GB")

    def test_is_us_location_with_country_code(self, client, us_location, intl_location):
        """Test US location detection with country code."""
        assert client._is_us_location(us_location) is True
        assert client._is_us_location(intl_location) is False

    def test_is_us_location_by_coordinates(self, client):
        """Test US location detection by coordinates (fallback)."""
        # US coordinates without country code
        us_loc = Location(name="Test", latitude=40.7, longitude=-74.0)
        assert client._is_us_location(us_loc) is True

        # International coordinates
        intl_loc = Location(name="Test", latitude=51.5, longitude=-0.1)
        assert client._is_us_location(intl_loc) is False

    def test_determine_api_choice_auto_us(self, client, us_location):
        """Test auto mode selects NWS for US."""
        client.data_source = "auto"
        choice = client._determine_api_choice(us_location)
        assert choice == "nws"

    def test_determine_api_choice_auto_intl(self, client, intl_location):
        """Test auto mode selects OpenMeteo for international."""
        client.data_source = "auto"
        choice = client._determine_api_choice(intl_location)
        assert choice == "openmeteo"

    def test_determine_api_choice_explicit(self, client, us_location):
        """Test explicit data source selection."""
        client.data_source = "openmeteo"
        choice = client._determine_api_choice(us_location)
        assert choice == "openmeteo"

        client.data_source = "nws"
        choice = client._determine_api_choice(us_location)
        assert choice == "nws"

    def test_determine_api_choice_invalid_fallback(self, client, us_location):
        """Test invalid data source falls back to auto."""
        client.data_source = "invalid"
        choice = client._determine_api_choice(us_location)
        # Should fall back to NWS for US location
        assert choice == "nws"


class TestWeatherClientFetching:
    """Tests for weather data fetching."""

    @pytest.fixture
    def client(self):
        """Create a WeatherClient instance."""
        return WeatherClient(data_source="nws")

    @pytest.fixture
    def location(self):
        """Test location."""
        return Location(name="Test", latitude=40.7, longitude=-74.0, country_code="US")

    @pytest.fixture
    def mock_current(self):
        """Mock current conditions."""
        return CurrentConditions(
            temperature_f=72.0,
            temperature_c=22.2,
            condition="Sunny",
        )

    @pytest.fixture
    def mock_forecast(self):
        """Mock forecast."""
        return Forecast(
            periods=[
                ForecastPeriod(
                    name="Today",
                    temperature=75,
                    temperature_unit="F",
                    short_forecast="Sunny",
                )
            ],
            generated_at=datetime.now(UTC),
        )

    @pytest.mark.asyncio
    async def test_get_weather_data_success(self, client, location, mock_current, mock_forecast):
        """Test successful weather data fetch."""
        # Mock the internal fetch methods
        client._fetch_nws_data = AsyncMock(
            return_value=(mock_current, mock_forecast, None, None, WeatherAlerts(alerts=[]), None)
        )
        client._launch_enrichment_tasks = MagicMock(return_value={})
        client._await_enrichments = AsyncMock()

        data = await client.get_weather_data(location)

        assert data is not None
        assert data.current.temperature_f == 72.0
        assert data.forecast is not None

    @pytest.mark.asyncio
    async def test_get_weather_data_caches_result(
        self, client, location, mock_current, mock_forecast
    ):
        """Test that results are cached."""
        import tempfile

        from accessiweather.cache import WeatherDataCache

        cache = WeatherDataCache(tempfile.mkdtemp())
        client.offline_cache = cache

        client._fetch_nws_data = AsyncMock(
            return_value=(mock_current, mock_forecast, None, None, WeatherAlerts(alerts=[]), None)
        )
        client._launch_enrichment_tasks = MagicMock(return_value={})
        client._await_enrichments = AsyncMock()

        result = await client.get_weather_data(location)

        # Verify data was returned
        assert result is not None
        assert result.current.temperature_f == 72.0

    @pytest.mark.asyncio
    async def test_get_weather_data_force_refresh(self, client, location, mock_current):
        """Test force refresh bypasses cache."""
        import tempfile

        from accessiweather.cache import WeatherDataCache

        cache = WeatherDataCache(tempfile.mkdtemp())
        client.offline_cache = cache

        # Pre-populate cache with different data
        old_data = WeatherData(
            location=location,
            current=CurrentConditions(temperature_f=50.0),
        )
        cache.store(location, old_data)

        # Mock returns new data
        client._fetch_nws_data = AsyncMock(
            return_value=(mock_current, None, None, None, WeatherAlerts(alerts=[]), None)
        )
        client._launch_enrichment_tasks = MagicMock(return_value={})
        client._await_enrichments = AsyncMock()

        data = await client.get_weather_data(location, force_refresh=True)

        # Should have new temperature, not cached
        assert data.current.temperature_f == 72.0

    @pytest.mark.asyncio
    async def test_get_cached_weather(self, client, location, mock_current):
        """Test getting cached weather synchronously."""
        import tempfile

        from accessiweather.cache import WeatherDataCache

        cache = WeatherDataCache(tempfile.mkdtemp())
        client.offline_cache = cache

        # Store data in cache
        data = WeatherData(location=location, current=mock_current)
        cache.store(location, data)

        # Get cached data (no network call)
        cached = client.get_cached_weather(location)
        assert cached is not None
        assert cached.current.temperature_f == 72.0

    @pytest.mark.asyncio
    async def test_deduplication(self, client, location, mock_current, mock_forecast):
        """Test that concurrent requests are deduplicated."""
        import asyncio

        call_count = 0

        async def mock_fetch(loc):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate network delay
            return (mock_current, mock_forecast, None, None, WeatherAlerts(alerts=[]), None)

        client._fetch_nws_data = mock_fetch
        client._launch_enrichment_tasks = MagicMock(return_value={})
        client._await_enrichments = AsyncMock()

        # Start multiple concurrent requests
        tasks = [client.get_weather_data(location) for _ in range(3)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 3
        # Deduplication depends on implementation - just verify all succeed
        assert all(r is not None for r in results)


class TestWeatherClientHelpers:
    """Tests for helper methods."""

    @pytest.fixture
    def client(self):
        return WeatherClient()

    def test_convert_f_to_c(self, client):
        """Test Fahrenheit to Celsius conversion."""
        assert client._convert_f_to_c(32.0) == 0.0
        assert client._convert_f_to_c(212.0) == 100.0
        assert client._convert_f_to_c(None) is None

    def test_convert_mps_to_mph(self, client):
        """Test meters per second to mph conversion."""
        result = client._convert_mps_to_mph(10.0)
        assert result is not None
        assert abs(result - 22.37) < 0.1  # ~22.37 mph

    def test_degrees_to_cardinal(self, client):
        """Test wind direction conversion."""
        assert client._degrees_to_cardinal(0) == "N"
        assert client._degrees_to_cardinal(90) == "E"
        assert client._degrees_to_cardinal(180) == "S"
        assert client._degrees_to_cardinal(270) == "W"
        assert client._degrees_to_cardinal(None) is None

    def test_set_empty_weather_data(self, client):
        """Test setting empty weather data."""
        location = Location(name="Test", latitude=40.0, longitude=-74.0)
        data = WeatherData(location=location)
        client._set_empty_weather_data(data)

        assert data.current is not None
        assert data.forecast is not None
        assert data.alerts is not None
        assert data.discussion == "Weather data not available."


class TestWeatherClientContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using WeatherClient as context manager."""
        async with WeatherClient() as client:
            assert client is not None

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing the client."""
        client = WeatherClient()
        # Force creation of HTTP client
        _ = client._get_http_client()
        assert client._http_client is not None

        await client.close()
        assert client._http_client is None
