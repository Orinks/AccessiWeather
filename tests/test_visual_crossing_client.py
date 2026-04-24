"""
Tests for VisualCrossingClient.

Tests the Visual Crossing weather API client.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.models import HourlyForecast, HourlyForecastPeriod, Location
from accessiweather.visual_crossing_client import (
    VisualCrossingApiError,
    VisualCrossingClient,
)
from accessiweather.weather_client_parsers import convert_f_to_c, degrees_to_cardinal


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

    def test_starts_with_standard_timeline_endpoint(self):
        """Test that client starts with the standard timeline endpoint."""
        client = VisualCrossingClient(api_key="key")
        assert "timeline" in client.base_url
        assert "timelinellx" not in client.base_url

    @pytest.mark.asyncio
    async def test_falls_back_to_standard_on_failure(self):
        """Test that client falls back to standard timeline on 404."""
        mock_llx_response = MagicMock()
        mock_llx_response.status_code = 404

        mock_std_response = MagicMock()
        mock_std_response.status_code = 200
        mock_std_response.json.return_value = {
            "currentConditions": {"temp": 72.0, "conditions": "Clear"},
            "days": [{"datetime": "2024-01-01"}],
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [mock_llx_response, mock_std_response]

            client = VisualCrossingClient(api_key="test-key")
            result = await client.get_current_conditions(Location("NYC", 40.7, -74.0))

        assert result is not None
        assert client.base_url == client._STANDARD_URL
        assert client._fell_back_to_standard is True

    def test_standard_timeline_endpoint_stays_in_use(self):
        """Test that the client continues using the standard timeline endpoint."""
        client = VisualCrossingClient(api_key="key")
        client._fell_back_to_standard = True
        client.base_url = client._STANDARD_URL
        assert "timeline" in client.base_url
        assert "timelinellx" not in client.base_url


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
                "cloudcover": 45.0,
                "windgust": 22.0,
                "precip": 0.1,
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
        assert current.cloud_cover == 45.0
        assert current.wind_gust_mph == 22.0
        assert current.precipitation_in == 0.1

    def test_parse_current_conditions_prefers_epoch_sun_moon_times(self, client):
        """Sun/moon fields should use VC epoch values when available."""
        data = {
            "tzoffset": -5,
            "currentConditions": {"temp": 72.0, "conditions": "Clear"},
            "days": [
                {
                    "datetime": "2024-01-01",
                    "sunrise": "07:00:00",
                    "sunset": "17:30:00",
                    "moonrise": "21:00:00",
                    "moonset": "09:00:00",
                    "sunriseEpoch": 1704111000,
                    "sunsetEpoch": 1704148200,
                    "moonriseEpoch": 1704160800,
                    "moonsetEpoch": 1704117600,
                }
            ],
        }

        current = client._parse_current_conditions(data)

        assert current.sunrise_time == datetime.fromtimestamp(
            1704111000, tz=timezone(timedelta(hours=-5))
        )
        assert current.sunset_time == datetime.fromtimestamp(
            1704148200, tz=timezone(timedelta(hours=-5))
        )
        assert current.moonrise_time == datetime.fromtimestamp(
            1704160800, tz=timezone(timedelta(hours=-5))
        )
        assert current.moonset_time == datetime.fromtimestamp(
            1704117600, tz=timezone(timedelta(hours=-5))
        )

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
                    "cloudcover": 30.0,
                    "windgust": 18.0,
                    "precip": 0.05,
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
                    "cloudcover": 50.0,
                    "windgust": 20.0,
                    "precip": 0.1,
                },
            ]
        }

        forecast = client._parse_forecast(data)

        assert len(forecast.periods) == 2
        assert forecast.periods[0].name == "Today"
        assert forecast.periods[0].temperature == 75.0
        assert forecast.periods[1].name == "Tomorrow"
        assert forecast.periods[0].cloud_cover == 30.0
        assert forecast.periods[0].wind_gust == "18.0 mph"
        assert forecast.periods[0].precipitation_amount == 0.05

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
                            "cloudcover": 10.0,
                            "windgust": 15.0,
                            "precip": 0.0,
                        },
                        {
                            "datetime": "13:00:00",
                            "temp": 74.0,
                            "conditions": "Partly Cloudy",
                            "windspeed": 12.0,
                            "winddir": 190,
                            "cloudcover": 40.0,
                            "windgust": 20.0,
                            "precip": 0.02,
                        },
                    ],
                }
            ],
        }

        hourly = client._parse_hourly_forecast(data)

        assert len(hourly.periods) == 2
        assert hourly.periods[0].temperature == 72.0
        assert hourly.periods[1].temperature == 74.0
        assert hourly.periods[0].cloud_cover == 10.0
        assert hourly.periods[0].wind_gust_mph == 15.0
        assert hourly.periods[0].precipitation_amount == 0.0
        assert hourly.periods[1].cloud_cover == 40.0
        assert hourly.periods[1].wind_gust_mph == 20.0
        assert hourly.periods[1].precipitation_amount == 0.02

    def test_parse_hourly_forecast_falls_back_to_tzoffset_when_zoneinfo_fails(self, client):
        """ZoneInfo failures should still produce timezone-aware hourly timestamps."""
        data = {
            "timezone": "America/New_York",
            "tzoffset": -5,
            "days": [
                {
                    "datetime": "2024-01-01",
                    "hours": [
                        {
                            "datetime": "12:00:00",
                            "temp": 72.0,
                            "conditions": "Sunny",
                        }
                    ],
                }
            ],
        }

        with patch("zoneinfo.ZoneInfo", side_effect=Exception("tzdata unavailable")):
            hourly = client._parse_hourly_forecast(data)

        period = hourly.periods[0]
        assert period.start_time.tzinfo is not None
        assert period.start_time.utcoffset() == timedelta(hours=-5)

    def test_parse_hourly_forecast_attaches_zoneinfo_timezone(self, client):
        """Parsed hourly timestamps should use IANA location timezone when ZoneInfo is available."""
        data = {
            "timezone": "America/New_York",
            "days": [
                {
                    "datetime": "2024-01-01",
                    "hours": [{"datetime": "12:00:00", "temp": 72.0, "conditions": "Sunny"}],
                }
            ],
        }

        hourly = client._parse_hourly_forecast(data)

        first = hourly.periods[0]
        assert first.start_time.tzinfo is not None
        assert getattr(first.start_time.tzinfo, "key", None) == "America/New_York"

    def test_parse_hourly_forecast_uses_tzoffset_offset(self, client):
        """Tzoffset should be reflected in parsed timestamp offsets."""
        data = {
            "tzoffset": -5,
            "days": [
                {
                    "datetime": "2024-01-01",
                    "hours": [
                        {
                            "datetime": "06:00:00",
                            "temp": 55.0,
                            "conditions": "Clear",
                        }
                    ],
                }
            ],
        }

        hourly = client._parse_hourly_forecast(data)
        period = hourly.periods[0]
        assert period.start_time.tzinfo is not None
        assert period.start_time.utcoffset() == timedelta(hours=-5)

    def test_parse_hourly_forecast_unknown_timezone_falls_back_to_utc(self, client):
        """Unknown timezone names fall back to UTC (tzoffset=0) — timestamps are still aware."""
        data = {
            "timezone": "Invalid/Timezone",
            "days": [
                {
                    "datetime": "2024-01-01",
                    "hours": [{"datetime": "12:00:00", "temp": 72.0, "conditions": "Sunny"}],
                }
            ],
        }

        hourly = client._parse_hourly_forecast(data)

        first = hourly.periods[0]
        assert first.start_time.tzinfo is not None
        assert first.start_time.utcoffset() == timedelta(0)

    def test_get_next_hours_uses_epoch_with_mixed_timezones(self):
        """Mixed timezone periods should be ordered/filtered by absolute time."""
        now_utc = datetime.now(UTC)
        pst = timezone(timedelta(hours=-8))

        periods = [
            HourlyForecastPeriod(
                start_time=(now_utc - timedelta(minutes=30)).astimezone(pst),
                temperature=1,
            ),
            HourlyForecastPeriod(
                start_time=now_utc + timedelta(minutes=10),
                temperature=2,
            ),
            HourlyForecastPeriod(
                start_time=(now_utc + timedelta(minutes=70)).astimezone(pst),
                temperature=3,
            ),
            HourlyForecastPeriod(
                start_time=now_utc + timedelta(hours=2),
                temperature=4,
            ),
        ]
        hourly = HourlyForecast(periods=periods)

        next_hours = hourly.get_next_hours(3)
        assert [period.temperature for period in next_hours] == [1, 2, 3]

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

    def test_convert_f_to_c(self, client):  # noqa: ARG002
        """Test Fahrenheit to Celsius conversion."""
        assert convert_f_to_c(32.0) == 0.0
        assert convert_f_to_c(212.0) == 100.0
        assert convert_f_to_c(None) is None

    def test_degrees_to_cardinal(self, client):  # noqa: ARG002
        """Test wind direction conversion."""
        assert degrees_to_cardinal(0) == "N"
        assert degrees_to_cardinal(45) == "NE"
        assert degrees_to_cardinal(90) == "E"
        assert degrees_to_cardinal(180) == "S"
        assert degrees_to_cardinal(270) == "W"
        assert degrees_to_cardinal(None) is None


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
            called_url = mock_client.get.call_args.args[0]
            assert called_url.endswith(f"/{location.latitude},{location.longitude}")

    @pytest.mark.asyncio
    async def test_get_forecast_caps_days_to_visual_crossing_limit(self, client, location):
        """Forecast requests should clamp day range to Visual Crossing's 15-day limit."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"days": []}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await client.get_forecast(location, days=30)

            called_url = mock_client.get.call_args.args[0]
            expected_end = (datetime.now(UTC).date() + timedelta(days=14)).isoformat()
            assert called_url.endswith(f"/today/{expected_end}")

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

    @pytest.mark.asyncio
    async def test_get_air_quality(self):
        """Test fetching air quality data from Visual Crossing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "currentConditions": {
                "datetime": "12:00:00",
                "aqius": 42,
                "pm2p5": 10.5,
                "pm10": 22.0,
                "o3": 35.0,
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            client = VisualCrossingClient(api_key="test-key")
            result = await client.get_air_quality(Location("NYC", 40.7, -74.0))

        assert result is not None
        assert result["aqius"] == 42
        assert result["pm2p5"] == 10.5
        assert result["o3"] == 35.0

    @pytest.mark.asyncio
    async def test_get_air_quality_failure(self):
        """Test air quality returns None on API failure."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            client = VisualCrossingClient(api_key="test-key")
            result = await client.get_air_quality(Location("NYC", 40.7, -74.0))

        assert result is None


class TestVisualCrossingBatchQueries:
    """Tests for batch location queries."""

    @pytest.mark.asyncio
    async def test_get_forecast_batch(self):
        """Test batch forecast for multiple locations."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "locations": {
                "40.7,-74.0": {
                    "days": [
                        {
                            "datetime": "2024-01-01",
                            "tempmax": 75,
                            "tempmin": 55,
                            "conditions": "Sunny",
                        }
                    ]
                },
                "34.0,-118.2": {
                    "days": [
                        {
                            "datetime": "2024-01-01",
                            "tempmax": 80,
                            "tempmin": 60,
                            "conditions": "Clear",
                        }
                    ]
                },
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            client = VisualCrossingClient(api_key="test-key")
            locations = [
                Location("NYC", 40.7, -74.0),
                Location("LA", 34.0, -118.2),
            ]
            results = await client.get_forecast_batch(locations)

        assert len(results) == 2
        assert "40.7,-74.0" in results
        assert "34.0,-118.2" in results

    @pytest.mark.asyncio
    async def test_get_forecast_batch_empty(self):
        """Test batch forecast with empty list."""
        client = VisualCrossingClient(api_key="test-key")
        results = await client.get_forecast_batch([])
        assert results == {}

    @pytest.mark.asyncio
    async def test_batch_url_format(self):
        """Test that batch query uses pipe-separated coordinates."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"locations": {}}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            client = VisualCrossingClient(api_key="test-key")
            await client.get_forecast_batch(
                [
                    Location("A", 40.7, -74.0),
                    Location("B", 34.0, -118.2),
                ]
            )

        call_url = mock_client.get.call_args[0][0]
        assert "40.7,-74.0|34.0,-118.2" in call_url

    @pytest.mark.asyncio
    async def test_get_forecast_batch_non_200_returns_empty(self):
        """Batch forecast with non-200 response returns empty dict."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            client = VisualCrossingClient(api_key="test-key")
            locations = [Location("NYC", 40.7, -74.0)]
            results = await client.get_forecast_batch(locations)

        assert results == {}

    @pytest.mark.asyncio
    async def test_get_forecast_batch_single_location_fallback(self):
        """When response has no 'locations' key, fall back to single parse."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "days": [
                {
                    "datetime": "2024-01-01",
                    "tempmax": 75,
                    "tempmin": 55,
                    "conditions": "Sunny",
                }
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            client = VisualCrossingClient(api_key="test-key")
            locations = [Location("NYC", 40.7, -74.0)]
            results = await client.get_forecast_batch(locations)

        assert "NYC" in results
        assert results["NYC"] is not None
        assert len(results["NYC"].periods) == 1

    @pytest.mark.asyncio
    async def test_get_forecast_batch_exception_returns_empty(self):
        """Batch forecast returns empty dict on unexpected exception."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = Exception("network error")

            client = VisualCrossingClient(api_key="test-key")
            locations = [Location("NYC", 40.7, -74.0)]
            results = await client.get_forecast_batch(locations)

        assert results == {}

    @pytest.mark.asyncio
    async def test_get_air_quality_non_200_returns_none(self):
        """Air quality returns None on non-200 status code."""
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            client = VisualCrossingClient(api_key="test-key")
            result = await client.get_air_quality(Location("NYC", 40.7, -74.0))

        assert result is None

    @pytest.mark.asyncio
    async def test_get_air_quality_exception_returns_none(self):
        """Air quality returns None on exception."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = Exception("timeout")

            client = VisualCrossingClient(api_key="test-key")
            result = await client.get_air_quality(Location("NYC", 40.7, -74.0))

        assert result is None


# ── _parse_forecast – regression: duplicate day deduplication (Bug 3) ──


class TestParseForecastDeduplication:
    """Regression: duplicate calendar dates in VC response must be deduplicated."""

    @pytest.fixture
    def client(self):
        return VisualCrossingClient(api_key="test-key")

    def _make_day(self, date_str: str, tempmax: float = 75.0) -> dict:
        return {
            "datetime": date_str,
            "tempmax": tempmax,
            "tempmin": 55.0,
            "conditions": "Clear",
            "description": "A clear day.",
            "windspeed": 10.0,
            "winddir": 180,
            "precipprob": 0,
            "icon": "clear-day",
        }

    def test_unique_dates_all_kept(self, client):
        """Normal case: 7 unique days → 7 periods."""
        days = [self._make_day(f"2024-03-{d:02d}") for d in range(24, 31)]
        data = {"days": days}
        forecast = client._parse_forecast(data)
        assert len(forecast.periods) == 7

    def test_duplicate_date_produces_single_period(self, client):
        """Same date appearing twice → only one period for that date."""
        days = [
            self._make_day("2024-03-24"),  # Today
            self._make_day("2024-03-24"),  # Duplicate — must be dropped
            self._make_day("2024-03-25"),
            self._make_day("2024-03-26"),
        ]
        data = {"days": days}
        forecast = client._parse_forecast(data)
        assert len(forecast.periods) == 3

    def test_duplicate_sunday_in_extended_forecast(self, client):
        """15-day forecast wraps weekday names; both Sundays must appear."""
        # Start on a Sunday (2024-03-24 was a Sunday)
        dates = [
            f"2024-03-{d:02d}"
            for d in range(24, 31)  # 7 days
        ] + [
            f"2024-03-31",
            f"2024-04-01",
            f"2024-04-02",
            f"2024-04-03",
            f"2024-04-04",
            f"2024-04-05",
            f"2024-04-06",
            f"2024-04-07",
        ]  # 8 more = 15 total
        days = [self._make_day(d) for d in dates]
        data = {"days": days}
        forecast = client._parse_forecast(data)
        # All 15 unique dates must appear
        assert len(forecast.periods) == 15

    def test_duplicate_date_in_dst_boundary_scenario(self, client):
        """Two identical date strings (DST boundary edge case) → deduplicated to one."""
        days = [
            self._make_day("2024-03-31", tempmax=60.0),
            self._make_day("2024-03-31", tempmax=62.0),  # Duplicate — dropped
            self._make_day("2024-04-01", tempmax=65.0),
        ]
        data = {"days": days}
        forecast = client._parse_forecast(data)
        assert len(forecast.periods) == 2
        # First occurrence wins
        assert forecast.periods[0].temperature == 60.0

    def test_period_names_assigned_by_position_after_dedup(self, client):
        """After deduplication, Today/Tomorrow/weekday names use insertion order."""
        days = [
            self._make_day("2024-03-24"),  # pos 0 → Today
            self._make_day("2024-03-24"),  # duplicate, dropped
            self._make_day("2024-03-25"),  # pos 1 → Tomorrow
            self._make_day("2024-03-26"),  # pos 2 → Tuesday
        ]
        data = {"days": days}
        forecast = client._parse_forecast(data)
        assert len(forecast.periods) == 3
        assert forecast.periods[0].name == "Today"
        assert forecast.periods[1].name == "Tomorrow"
