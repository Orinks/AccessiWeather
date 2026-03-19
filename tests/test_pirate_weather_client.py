"""
Tests for PirateWeatherClient.

Tests the Pirate Weather API client (https://pirateweather.net).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.models import Location
from accessiweather.pirate_weather_client import (
    PirateWeatherApiError,
    PirateWeatherClient,
    _build_alert_id,
    _icon_to_condition,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return PirateWeatherClient(api_key="test-key", units="us")


@pytest.fixture
def sample_forecast_payload():
    """Return a minimal but realistic Pirate Weather payload."""
    return {
        "latitude": 40.7128,
        "longitude": -74.006,
        "timezone": "America/New_York",
        "offset": -5,
        "currently": {
            "time": 1700000000,
            "summary": "Partly Cloudy",
            "icon": "partly-cloudy-day",
            "temperature": 68.0,
            "apparentTemperature": 66.5,
            "humidity": 0.65,
            "dewPoint": 55.0,
            "windSpeed": 10.0,
            "windGust": 18.0,
            "windBearing": 180,
            "pressure": 1013.0,
            "uvIndex": 3,
            "cloudCover": 0.45,
            "visibility": 10.0,
            "precipIntensity": 0.0,
        },
        "minutely": {
            "data": [{"time": 1700000060, "precipIntensity": 0.0, "precipProbability": 0.0}]
        },
        "hourly": {
            "data": [
                {
                    "time": 1700000000,
                    "summary": "Partly Cloudy",
                    "icon": "partly-cloudy-day",
                    "temperature": 68.0,
                    "apparentTemperature": 66.5,
                    "humidity": 0.65,
                    "dewPoint": 55.0,
                    "windSpeed": 10.0,
                    "windGust": 18.0,
                    "windBearing": 180,
                    "pressure": 1013.0,
                    "uvIndex": 3,
                    "cloudCover": 0.45,
                    "visibility": 10.0,
                    "precipIntensity": 0.0,
                    "precipProbability": 0.1,
                }
            ]
        },
        "daily": {
            "data": [
                {
                    "time": 1699999200,
                    "summary": "Mostly cloudy throughout the day.",
                    "icon": "cloudy",
                    "sunriseTime": 1700020000,
                    "sunsetTime": 1700055000,
                    "temperatureHigh": 75.0,
                    "temperatureLow": 55.0,
                    "temperatureMax": 75.0,
                    "temperatureMin": 55.0,
                    "windSpeed": 8.0,
                    "windGust": 14.0,
                    "windBearing": 200,
                    "uvIndex": 4,
                    "cloudCover": 0.6,
                    "precipProbability": 0.2,
                    "precipIntensity": 0.01,
                }
            ]
        },
        "alerts": [],
    }


@pytest.fixture
def sample_payload_with_alerts(sample_forecast_payload):
    payload = dict(sample_forecast_payload)
    payload["alerts"] = [
        {
            "title": "Winter Storm Warning",
            "severity": "severe",
            "time": 1700000000,
            "expires": 1700050000,
            "description": "Heavy snow expected.",
            "uri": "https://alerts.weather.gov/cap/123",
            "regions": ["New York"],
        }
    ]
    return payload


# ---------------------------------------------------------------------------
# Unit tests – icon / condition mapping
# ---------------------------------------------------------------------------


class TestIconToCondition:
    def test_known_icon(self):
        assert _icon_to_condition("clear-day") == "Clear"
        assert _icon_to_condition("rain") == "Rain"
        assert _icon_to_condition("partly-cloudy-night") == "Partly Cloudy"

    def test_unknown_icon_title_cases(self):
        result = _icon_to_condition("sleet-hail")
        assert result == "Sleet Hail"

    def test_none_returns_none(self):
        assert _icon_to_condition(None) is None

    def test_empty_string_returns_none(self):
        assert _icon_to_condition("") is None


# ---------------------------------------------------------------------------
# Unit tests – client initialization
# ---------------------------------------------------------------------------


class TestPirateWeatherClientInit:
    def test_default_init(self):
        c = PirateWeatherClient(api_key="abc123")
        assert c.api_key == "abc123"
        assert c.units == "us"
        assert c.user_agent == "AccessiWeather/1.0"

    def test_custom_units(self):
        c = PirateWeatherClient(api_key="key", units="si")
        assert c.units == "si"

    def test_build_url(self):
        c = PirateWeatherClient(api_key="mykey")
        url = c._build_url(40.71, -74.01)
        assert "mykey" in url
        assert "40.71" in url
        assert "-74.01" in url


# ---------------------------------------------------------------------------
# Unit tests – _parse_current_conditions
# ---------------------------------------------------------------------------


class TestParseCurrentConditions:
    def test_basic_parse(self, client, sample_forecast_payload):
        result = client._parse_current_conditions(sample_forecast_payload)
        assert result.temperature_f == 68.0
        assert result.humidity == 65
        assert result.condition == "Partly Cloudy"
        assert result.wind_speed_mph == 10.0
        assert result.pressure_mb == 1013.0
        assert result.cloud_cover == 45
        assert result.uv_index == 3
        assert result.wind_gust_mph == 18.0

    def test_temperature_conversions(self, client, sample_forecast_payload):
        result = client._parse_current_conditions(sample_forecast_payload)
        assert result.temperature_f is not None
        assert result.temperature_c is not None
        assert abs(result.temperature_c - (68.0 - 32) * 5 / 9) < 0.1

    def test_pressure_conversion(self, client, sample_forecast_payload):
        result = client._parse_current_conditions(sample_forecast_payload)
        assert result.pressure_mb == 1013.0
        assert result.pressure_in is not None
        assert abs(result.pressure_in - 1013.0 / 33.8639) < 0.01

    def test_visibility_us_units(self, client, sample_forecast_payload):
        result = client._parse_current_conditions(sample_forecast_payload)
        assert result.visibility_miles == 10.0
        assert result.visibility_km is not None

    def test_wind_direction_cardinal(self, client, sample_forecast_payload):
        result = client._parse_current_conditions(sample_forecast_payload)
        # 180 degrees = South
        assert result.wind_direction == "S"

    def test_sunrise_sunset_populated(self, client, sample_forecast_payload):
        result = client._parse_current_conditions(sample_forecast_payload)
        # daily block has sunriseTime / sunsetTime
        assert result.sunrise_time is not None
        assert result.sunset_time is not None

    def test_missing_currently_block(self, client):
        data = {"offset": 0, "daily": {"data": []}}
        result = client._parse_current_conditions(data)
        assert result.temperature_f is None
        assert result.condition is None

    def test_si_units_temperature(self):
        si_client = PirateWeatherClient(api_key="key", units="si")
        data = {
            "currently": {"temperature": 20.0, "humidity": 0.5},
            "offset": 0,
            "daily": {"data": []},
        }
        result = si_client._parse_current_conditions(data)
        # In SI mode, temperature is Celsius
        assert result.temperature_c == 20.0
        assert result.temperature_f is not None
        assert abs(result.temperature_f - (20.0 * 9 / 5 + 32)) < 0.1


# ---------------------------------------------------------------------------
# Unit tests – _parse_forecast
# ---------------------------------------------------------------------------


class TestParseForecast:
    def test_basic_forecast(self, client, sample_forecast_payload):
        result = client._parse_forecast(sample_forecast_payload)
        assert len(result.periods) == 1
        period = result.periods[0]
        assert period.name == "Today"
        assert period.temperature == 75.0
        assert period.temperature_low == 55.0
        assert period.temperature_unit == "F"
        assert period.cloud_cover == 60
        assert period.uv_index == 4
        assert period.precipitation_probability == 20

    def test_second_day_name_tomorrow(self, client, sample_forecast_payload):
        # Clone the day entry and add a second one
        day2 = dict(sample_forecast_payload["daily"]["data"][0])
        day2["time"] = sample_forecast_payload["daily"]["data"][0]["time"] + 86400
        payload = dict(sample_forecast_payload)
        payload["daily"] = {"data": [sample_forecast_payload["daily"]["data"][0], day2]}
        result = client._parse_forecast(payload)
        assert result.periods[1].name == "Tomorrow"

    def test_days_cap_respected(self, client, sample_forecast_payload):
        # Add 10 days worth of data
        base_day = sample_forecast_payload["daily"]["data"][0]
        days = [dict(base_day, time=base_day["time"] + i * 86400) for i in range(10)]
        payload = dict(sample_forecast_payload)
        payload["daily"] = {"data": days}
        result = client._parse_forecast(payload, days=3)
        assert len(result.periods) == 3

    def test_wind_string_us_units(self, client, sample_forecast_payload):
        result = client._parse_forecast(sample_forecast_payload)
        assert result.periods[0].wind_speed is not None
        assert "mph" in result.periods[0].wind_speed

    def test_wind_string_si_units(self, sample_forecast_payload):
        si_client = PirateWeatherClient(api_key="key", units="si")
        result = si_client._parse_forecast(sample_forecast_payload)
        assert result.periods[0].wind_speed is not None
        assert "m/s" in result.periods[0].wind_speed

    def test_daily_summary_parsed(self, client):
        """Summary field is populated from data['daily']['summary']."""
        payload = {
            "offset": 0,
            "daily": {
                "summary": "Light rain throughout the week.",
                "data": [
                    {
                        "time": 1700000000,
                        "temperatureHigh": 70.0,
                        "temperatureLow": 50.0,
                        "summary": "Rain",
                        "icon": "rain",
                        "windSpeed": 5.0,
                        "windBearing": 90,
                        "precipProbability": 0.8,
                        "precipIntensity": 0.05,
                        "cloudCover": 0.9,
                        "uvIndex": 1,
                    }
                ],
            },
        }
        result = client._parse_forecast(payload)
        assert result.summary == "Light rain throughout the week."

    def test_daily_summary_none_when_missing(self, client, sample_forecast_payload):
        """Summary is None when the daily block has no 'summary' key."""
        payload = dict(sample_forecast_payload)
        payload["daily"] = {"data": sample_forecast_payload["daily"]["data"]}
        result = client._parse_forecast(payload)
        assert result.summary is None

    def test_daily_summary_preserved_in_forecast_model(self, client):
        """Forecast dataclass stores summary independently of period summaries."""
        payload = {
            "offset": 0,
            "daily": {
                "summary": "Possible drizzle on Thursday.",
                "data": [],
            },
        }
        result = client._parse_forecast(payload)
        assert result.summary == "Possible drizzle on Thursday."
        assert result.periods == []


# ---------------------------------------------------------------------------
# Unit tests – _parse_hourly_forecast
# ---------------------------------------------------------------------------


class TestParseHourlyForecast:
    def test_basic_hourly(self, client, sample_forecast_payload):
        result = client._parse_hourly_forecast(sample_forecast_payload)
        assert len(result.periods) == 1
        period = result.periods[0]
        assert period.temperature == 68.0
        assert period.temperature_unit == "F"
        assert period.humidity == 65
        assert period.dewpoint_f == 55.0
        assert period.pressure_mb == 1013.0
        assert period.cloud_cover == 45
        assert period.uv_index == 3
        assert period.precipitation_probability == 10

    def test_hourly_dewpoint_calculated_when_missing(self, client, sample_forecast_payload):
        payload = dict(sample_forecast_payload)
        payload["hourly"] = {
            "data": [dict(sample_forecast_payload["hourly"]["data"][0], dewPoint=None)]
        }

        result = client._parse_hourly_forecast(payload)

        assert result.periods[0].humidity == 65
        assert result.periods[0].dewpoint_f is not None
        assert result.periods[0].dewpoint_c is not None

    def test_hourly_block_summary_parsed(self, client, sample_forecast_payload):
        sample_forecast_payload["hourly"]["summary"] = "Partly cloudy until late afternoon."
        result = client._parse_hourly_forecast(sample_forecast_payload)
        assert result.summary == "Partly cloudy until late afternoon."

    def test_timezone_aware_start_time(self, client, sample_forecast_payload):
        result = client._parse_hourly_forecast(sample_forecast_payload)
        assert result.periods[0].start_time.tzinfo is not None

    def test_pressure_conversion(self, client, sample_forecast_payload):
        result = client._parse_hourly_forecast(sample_forecast_payload)
        period = result.periods[0]
        assert period.pressure_in is not None
        assert abs(period.pressure_in - 1013.0 / 33.8639) < 0.01

    def test_empty_hourly_block(self, client, sample_forecast_payload):
        payload = dict(sample_forecast_payload)
        payload["hourly"] = {"data": []}
        result = client._parse_hourly_forecast(payload)
        assert result.periods == []


# ---------------------------------------------------------------------------
# Unit tests – _parse_alerts
# ---------------------------------------------------------------------------


class TestParseAlerts:
    def test_no_alerts(self, client, sample_forecast_payload):
        result = client._parse_alerts(sample_forecast_payload)
        assert result.alerts == []

    def test_single_alert(self, client, sample_payload_with_alerts):
        result = client._parse_alerts(sample_payload_with_alerts)
        assert len(result.alerts) == 1
        alert = result.alerts[0]
        assert alert.title == "Winter Storm Warning"
        assert alert.severity == "Severe"
        assert alert.source == "PirateWeather"
        assert "New York" in alert.areas

    def test_alert_id_is_deterministic_wmo_fingerprint(self, client, sample_payload_with_alerts):
        result = client._parse_alerts(sample_payload_with_alerts)
        alert_data = sample_payload_with_alerts["alerts"][0]
        assert result.alerts[0].id == _build_alert_id(alert_data)

    def test_alert_id_ignores_uri_revision_changes(self, client, sample_payload_with_alerts):
        first = dict(sample_payload_with_alerts["alerts"][0], uri="https://example.com/v1.xml")
        second = dict(sample_payload_with_alerts["alerts"][0], uri="https://example.com/v2.xml")
        assert _build_alert_id(first) == _build_alert_id(second)

    def test_alert_id_ignores_expiry_extension(self, client, sample_payload_with_alerts):
        first = dict(sample_payload_with_alerts["alerts"][0], expires=1700050000)
        second = dict(sample_payload_with_alerts["alerts"][0], expires=1700060000)
        assert _build_alert_id(first) == _build_alert_id(second)

    def test_alert_times_parsed(self, client, sample_payload_with_alerts):
        result = client._parse_alerts(sample_payload_with_alerts)
        alert = result.alerts[0]
        assert alert.onset is not None
        assert alert.expires is not None
        assert alert.expires > alert.onset

    def test_severity_mapping(self, client):
        for raw, expected in [
            ("extreme", "Extreme"),
            ("severe", "Severe"),
            ("moderate", "Moderate"),
            ("minor", "Minor"),
            ("advisory", "Minor"),
            ("watch", "Moderate"),
            ("warning", "Severe"),
            ("unknown_value", "Unknown"),
            (None, "Unknown"),
        ]:
            assert client._map_severity(raw) == expected


# ---------------------------------------------------------------------------
# Async tests – HTTP layer
# ---------------------------------------------------------------------------


class TestPirateWeatherHttpLayer:
    @pytest.mark.asyncio
    async def test_get_current_conditions_success(self, client, sample_forecast_payload):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = sample_forecast_payload

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_http
            mock_http.get.return_value = mock_resp

            result = await client.get_current_conditions(Location("NYC", 40.7128, -74.006))

        assert result is not None
        assert result.temperature_f == 68.0

    @pytest.mark.asyncio
    async def test_get_forecast_success(self, client, sample_forecast_payload):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = sample_forecast_payload

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_http
            mock_http.get.return_value = mock_resp

            result = await client.get_forecast(Location("NYC", 40.7128, -74.006))

        assert result is not None
        assert len(result.periods) >= 1

    @pytest.mark.asyncio
    async def test_get_hourly_forecast_success(self, client, sample_forecast_payload):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = sample_forecast_payload

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_http
            mock_http.get.return_value = mock_resp

            result = await client.get_hourly_forecast(Location("NYC", 40.7128, -74.006))

        assert result is not None
        assert len(result.periods) >= 1

    @pytest.mark.asyncio
    async def test_get_alerts_success(self, client, sample_payload_with_alerts):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = sample_payload_with_alerts

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_http
            mock_http.get.return_value = mock_resp

            result = await client.get_alerts(Location("NYC", 40.7128, -74.006))

        assert result is not None
        assert len(result.alerts) == 1

    @pytest.mark.asyncio
    async def test_unauthorized_raises_error(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_http
            mock_http.get.return_value = mock_resp

            with pytest.raises(PirateWeatherApiError) as exc_info:
                await client.get_forecast_data(Location("NYC", 40.7128, -74.006))

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rate_limit_raises_error(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 429

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_http
            mock_http.get.return_value = mock_resp

            with pytest.raises(PirateWeatherApiError) as exc_info:
                await client.get_forecast_data(Location("NYC", 40.7128, -74.006))

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_http_500_raises_error(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_http
            mock_http.get.return_value = mock_resp

            with pytest.raises(PirateWeatherApiError) as exc_info:
                await client.get_forecast_data(Location("NYC", 40.7128, -74.006))

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_alerts_returns_empty_on_error(self, client):
        """get_alerts should not raise — it returns empty alerts on failure."""
        with patch.object(client, "get_forecast_data", side_effect=PirateWeatherApiError("fail")):
            result = await client.get_alerts(Location("NYC", 40.7128, -74.006))

        assert result.alerts == []

    @pytest.mark.asyncio
    async def test_timeout_raises_error(self, client):
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_http
            mock_http.get.side_effect = httpx.TimeoutException("timeout")

            with pytest.raises(PirateWeatherApiError) as exc_info:
                await client.get_forecast_data(Location("NYC", 40.7128, -74.006))

        assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_request_error_raises_error(self, client):
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_http = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_http
            mock_http.get.side_effect = httpx.RequestError("connection refused")

            with pytest.raises(PirateWeatherApiError) as exc_info:
                await client.get_forecast_data(Location("NYC", 40.7128, -74.006))

        assert "Request failed" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Tests for WeatherClient integration
# ---------------------------------------------------------------------------


class TestWeatherClientPirateWeatherIntegration:
    """Tests for WeatherClient's Pirate Weather integration."""

    def test_pirate_weather_client_property_created_with_key(self):
        from accessiweather.weather_client import WeatherClient

        wc = WeatherClient(pirate_weather_api_key="test-key")
        assert wc.pirate_weather_client is not None
        assert wc.pirate_weather_client.api_key == "test-key"

    def test_pirate_weather_client_property_none_without_key(self):
        from accessiweather.weather_client import WeatherClient

        wc = WeatherClient(pirate_weather_api_key="")
        assert wc.pirate_weather_client is None

    def test_pirate_weather_client_setter(self):
        from accessiweather.weather_client import WeatherClient

        wc = WeatherClient()
        mock_client = MagicMock()
        wc.pirate_weather_client = mock_client
        assert wc.pirate_weather_client is mock_client

    def test_determine_api_choice_pirateweather(self):
        from accessiweather.weather_client import WeatherClient

        wc = WeatherClient(data_source="pirateweather", pirate_weather_api_key="key")
        loc = Location("London", 51.5, -0.12, country_code="GB")
        assert wc._determine_api_choice(loc) == "pirateweather"

    def test_determine_api_choice_pirateweather_falls_back_without_key(self):
        from accessiweather.weather_client import WeatherClient

        wc = WeatherClient(data_source="pirateweather", pirate_weather_api_key="")
        loc = Location("London", 51.5, -0.12, country_code="GB")
        # Falls back to openmeteo for international
        assert wc._determine_api_choice(loc) == "openmeteo"

    def test_forecast_days_cap_pirateweather(self):
        from accessiweather.weather_client import WeatherClient

        wc = WeatherClient()
        loc = Location("NYC", 40.7, -74.0, country_code="US")
        days = wc._get_forecast_days_for_source(loc, source="pirateweather")
        assert days <= 8
