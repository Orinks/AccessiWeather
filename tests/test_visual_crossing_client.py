"""
Tests for VisualCrossingClient.

Tests the Visual Crossing weather API client.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.models import Location
from accessiweather.visual_crossing_client import (
    VisualCrossingApiError,
    VisualCrossingClient,
)


class TestVisualCrossingClientInit:
    """Tests for client initialization."""

    def test_initialization(self):
        """Test initialization with API key."""
        client = VisualCrossingClient(api_key="test-key")
        assert client.api_key == "test-key"
        assert client.user_agent == "AccessiWeather/1.0"

    def test_custom_user_agent(self):
        """Test custom user agent."""
        client = VisualCrossingClient(api_key="key", user_agent="CustomApp/2.0")
        assert client.user_agent == "CustomApp/2.0"


class TestVisualCrossingParsers:
    """Tests for response parsing methods."""

    @pytest.fixture
    def client(self):
        return VisualCrossingClient(api_key="test-key")

    def test_parse_current_conditions(self, client):
        """Test parsing current conditions."""
        data = {
            "tzoffset": -5,
            "currentConditions": {
                "temp": 72.0,
                "feelslike": 74.0,
                "humidity": 65,
                "windspeed": 10.0,
                "winddir": 180,
                "pressure": 30.05,
                "conditions": "Partly Cloudy",
                "visibility": 10.0,
            },
            "days": [
                {
                    "datetime": "2024-01-01",
                    "sunrise": "07:00:00",
                    "sunset": "17:30:00",
                    "moonphase": 0.5,
                }
            ],
        }

        current = client._parse_current_conditions(data)

        assert current.temperature_f == 72.0
        assert current.feels_like_f == 74.0
        assert current.humidity == 65
        assert current.wind_speed_mph == 10.0
        assert current.condition == "Partly Cloudy"

    def test_parse_forecast(self, client):
        """Test parsing forecast."""
        data = {
            "days": [
                {
                    "datetime": "2024-01-01",
                    "tempmax": 75.0,
                    "tempmin": 55.0,
                    "conditions": "Sunny",
                    "description": "Clear and sunny.",
                    "windspeed": 10.0,
                    "winddir": 180,
                    "icon": "clear-day",
                },
                {
                    "datetime": "2024-01-02",
                    "tempmax": 78.0,
                    "tempmin": 58.0,
                    "conditions": "Partly Cloudy",
                    "description": "Some clouds.",
                    "windspeed": 8.0,
                    "winddir": 200,
                    "icon": "partly-cloudy-day",
                },
            ]
        }

        forecast = client._parse_forecast(data)

        assert len(forecast.periods) == 2
        assert forecast.periods[0].name == "Today"
        assert forecast.periods[0].temperature == 75.0
        assert forecast.periods[1].name == "Tomorrow"

    def test_parse_hourly_forecast(self, client):
        """Test parsing hourly forecast."""
        data = {
            "timezone": "America/New_York",
            "days": [
                {
                    "datetime": "2024-01-01",
                    "hours": [
                        {
                            "datetime": "12:00:00",
                            "temp": 72.0,
                            "conditions": "Sunny",
                            "windspeed": 10.0,
                            "winddir": 180,
                        },
                        {
                            "datetime": "13:00:00",
                            "temp": 74.0,
                            "conditions": "Partly Cloudy",
                            "windspeed": 12.0,
                            "winddir": 190,
                        },
                    ],
                }
            ],
        }

        hourly = client._parse_hourly_forecast(data)

        assert len(hourly.periods) == 2
        assert hourly.periods[0].temperature == 72.0
        assert hourly.periods[1].temperature == 74.0

    def test_parse_alerts(self, client):
        """Test parsing alerts."""
        data = {
            "alerts": [
                {
                    "event": "Heat Advisory",
                    "headline": "Heat Advisory in effect",
                    "description": "High temperatures expected.",
                    "severity": "moderate",
                    "onset": "2024-01-01T12:00:00",
                    "expires": "2024-01-01T20:00:00",
                }
            ]
        }

        alerts = client._parse_alerts(data)

        assert len(alerts.alerts) == 1
        assert alerts.alerts[0].event == "Heat Advisory"
        assert alerts.alerts[0].severity == "Moderate"

    def test_parse_alerts_empty(self, client):
        """Test parsing empty alerts."""
        data = {"alerts": []}
        alerts = client._parse_alerts(data)
        assert len(alerts.alerts) == 0


class TestVisualCrossingSeverityMapping:
    """Tests for severity mapping."""

    @pytest.fixture
    def client(self):
        return VisualCrossingClient(api_key="test-key")

    def test_extreme_severity(self, client):
        assert client._map_visual_crossing_severity("extreme") == "Extreme"
        assert client._map_visual_crossing_severity("critical") == "Extreme"

    def test_severe_severity(self, client):
        assert client._map_visual_crossing_severity("severe") == "Severe"
        assert client._map_visual_crossing_severity("high") == "Severe"
        assert client._map_visual_crossing_severity("warning") == "Severe"

    def test_moderate_severity(self, client):
        assert client._map_visual_crossing_severity("moderate") == "Moderate"
        assert client._map_visual_crossing_severity("medium") == "Moderate"
        assert client._map_visual_crossing_severity("watch") == "Moderate"

    def test_minor_severity(self, client):
        assert client._map_visual_crossing_severity("minor") == "Minor"
        assert client._map_visual_crossing_severity("low") == "Minor"
        assert client._map_visual_crossing_severity("advisory") == "Minor"

    def test_unknown_severity(self, client):
        assert client._map_visual_crossing_severity("unknown") == "Unknown"
        assert client._map_visual_crossing_severity(None) == "Unknown"
        assert client._map_visual_crossing_severity("gibberish") == "Unknown"


class TestVisualCrossingHelpers:
    """Tests for helper methods."""

    @pytest.fixture
    def client(self):
        return VisualCrossingClient(api_key="test-key")

    def test_convert_f_to_c(self, client):
        """Test Fahrenheit to Celsius conversion."""
        assert client._convert_f_to_c(32.0) == 0.0
        assert client._convert_f_to_c(212.0) == 100.0
        assert client._convert_f_to_c(None) is None

    def test_degrees_to_cardinal(self, client):
        """Test wind direction conversion."""
        assert client._degrees_to_cardinal(0) == "N"
        assert client._degrees_to_cardinal(45) == "NE"
        assert client._degrees_to_cardinal(90) == "E"
        assert client._degrees_to_cardinal(180) == "S"
        assert client._degrees_to_cardinal(270) == "W"
        assert client._degrees_to_cardinal(None) is None


class TestVisualCrossingApiCalls:
    """Tests for API call methods."""

    @pytest.fixture
    def client(self):
        return VisualCrossingClient(api_key="test-key")

    @pytest.fixture
    def location(self):
        return Location(name="Test", latitude=40.7128, longitude=-74.0060)

    @pytest.mark.asyncio
    async def test_get_current_conditions_success(self, client, location):
        """Test successful current conditions fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tzoffset": -5,
            "currentConditions": {
                "temp": 72.0,
                "conditions": "Clear",
            },
            "days": [],
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            current = await client.get_current_conditions(location)

            assert current is not None
            assert current.temperature_f == 72.0

    @pytest.mark.asyncio
    async def test_get_current_conditions_invalid_key(self, client, location):
        """Test handling invalid API key."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(VisualCrossingApiError) as exc:
                await client.get_current_conditions(location)
            assert "Invalid API key" in str(exc.value)

    @pytest.mark.asyncio
    async def test_get_current_conditions_rate_limit(self, client, location):
        """Test handling rate limit."""
        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(VisualCrossingApiError) as exc:
                await client.get_current_conditions(location)
            assert "rate limit" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_get_forecast_success(self, client, location):
        """Test successful forecast fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "days": [
                {
                    "datetime": "2024-01-01",
                    "tempmax": 75.0,
                    "conditions": "Sunny",
                }
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            forecast = await client.get_forecast(location)

            assert forecast is not None
            assert len(forecast.periods) == 1

    @pytest.mark.asyncio
    async def test_get_alerts_returns_empty_on_error(self, client, location):
        """Test that get_alerts returns empty list on error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Network error")
            mock_client_class.return_value.__aenter__.return_value = mock_client

            alerts = await client.get_alerts(location)

            # Should return empty alerts, not raise
            assert alerts is not None
            assert len(alerts.alerts) == 0
