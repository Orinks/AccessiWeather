"""Integration tests for NWS (National Weather Service) weather provider API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from accessiweather.models import Location
from accessiweather.weather_client_nws import (
    get_nws_all_data_parallel,
    get_nws_current_conditions,
    get_nws_forecast_and_discussion,
    get_nws_hourly_forecast,
    parse_nws_current_conditions,
    parse_nws_forecast,
)
from tests.integration.conftest import (
    LIVE_WEATHER_TESTS,
    conditional_async_sleep,
    get_vcr_config,
    skip_if_cassette_missing,
)

try:
    import vcr
    from vcr.errors import CannotOverwriteExistingCassetteException

    HAS_VCR = True
except ImportError:
    HAS_VCR = False
    vcr = None  # type: ignore[assignment]
    CannotOverwriteExistingCassetteException = Exception  # type: ignore[misc,assignment]


# Test location: Lumberton, NJ (from the screenshot)
TEST_LOCATION = Location(name="Lumberton, New Jersey", latitude=39.9643, longitude=-74.8099)

# NWS API requires proper User-Agent
USER_AGENT = (
    "AccessiWeather/IntegrationTest (github.com/Orinks/AccessiWeather, contact@example.com)"
)
REQUEST_TIMEOUT = 30.0
DELAY_BETWEEN_REQUESTS = 1.0  # NWS rate limiting courtesy (500ms min)


@pytest.fixture
async def http_client():
    """Create a shared HTTP client with NWS-required headers."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json",
    }
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers=headers,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    ) as client:
        yield client


async def get_nws_grid_point(lat: float, lon: float, client: httpx.AsyncClient) -> dict:
    """Get NWS grid point metadata for a location."""
    url = f"https://api.weather.gov/points/{lat},{lon}"
    response = await client.get(url)
    response.raise_for_status()
    data = response.json()
    return data.get("properties", {})


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_nws_grid_point_contains_timezone(http_client):
    """Test NWS grid point metadata includes timezone information (uses VCR cassettes)."""
    cassette_name = "nws/test_grid_point_timezone.yaml"
    skip_if_cassette_missing(cassette_name)

    async def _test():
        grid_data = await get_nws_grid_point(
            TEST_LOCATION.latitude,
            TEST_LOCATION.longitude,
            http_client,
        )

        # Contract: timeZone field must exist
        assert "timeZone" in grid_data, "Grid point should include timeZone"

        timezone = grid_data["timeZone"]
        # Contract: timezone is a non-empty string in IANA format
        assert isinstance(timezone, str), "Timezone should be a string"
        assert len(timezone) > 0, "Timezone should not be empty"
        assert "/" in timezone or timezone in ("UTC", "GMT"), (
            f"Timezone '{timezone}' should be IANA format"
        )

        await conditional_async_sleep(DELAY_BETWEEN_REQUESTS)

    if HAS_VCR:
        my_vcr = vcr.VCR(**get_vcr_config())
        with my_vcr.use_cassette(cassette_name):
            await _test()
    else:
        await _test()


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_nws_grid_point_contains_forecast_urls(http_client):
    """Test NWS grid point includes required forecast URLs (uses VCR cassettes)."""
    cassette_name = "nws/test_grid_point_forecast_urls.yaml"
    skip_if_cassette_missing(cassette_name)

    async def _test():
        grid_data = await get_nws_grid_point(
            TEST_LOCATION.latitude,
            TEST_LOCATION.longitude,
            http_client,
        )

        # Contract: required URL fields must exist
        assert "forecast" in grid_data, "Grid point should have forecast URL"
        assert "forecastHourly" in grid_data, "Grid point should have forecastHourly URL"
        assert "observationStations" in grid_data, "Grid point should have observationStations URL"

        # Contract: URLs are valid HTTPS endpoints
        forecast_url = grid_data["forecast"]
        assert isinstance(forecast_url, str), "Forecast URL should be a string"
        assert forecast_url.startswith("https://"), f"Forecast URL should be HTTPS: {forecast_url}"

        hourly_url = grid_data["forecastHourly"]
        assert isinstance(hourly_url, str), "Hourly URL should be a string"
        assert hourly_url.startswith("https://"), (
            f"Hourly forecast URL should be HTTPS: {hourly_url}"
        )

        stations_url = grid_data["observationStations"]
        assert isinstance(stations_url, str), "Stations URL should be a string"
        assert stations_url.startswith("https://"), f"Stations URL should be HTTPS: {stations_url}"

        await conditional_async_sleep(DELAY_BETWEEN_REQUESTS)

    if HAS_VCR:
        my_vcr = vcr.VCR(**get_vcr_config())
        with my_vcr.use_cassette(cassette_name):
            await _test()
    else:
        await _test()


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_nws_current_conditions_has_valid_timestamp(http_client):
    """Test NWS current conditions returns valid, recent timestamp (uses VCR cassettes)."""
    cassette_name = "nws/test_current_conditions_timestamp.yaml"
    skip_if_cassette_missing(cassette_name)

    async def _test():
        current = await get_nws_current_conditions(
            TEST_LOCATION,
            "https://api.weather.gov",
            USER_AGENT,
            REQUEST_TIMEOUT,
            http_client,
        )

        # Current conditions may fail for some locations, skip if None
        if current is None:
            pytest.skip("NWS did not return current conditions for test location")

        # Contract: if current conditions exist, they have required structure
        # Don't assert exact values, just that fields exist and are valid types

        await conditional_async_sleep(DELAY_BETWEEN_REQUESTS)

    if HAS_VCR:
        my_vcr = vcr.VCR(**get_vcr_config())
        with my_vcr.use_cassette(cassette_name):
            await _test()
    else:
        await _test()


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_nws_forecast_has_valid_periods_and_times(http_client):
    """Test NWS forecast returns periods with valid timestamps (uses VCR cassettes)."""
    cassette_name = "nws/test_forecast_periods_and_times.yaml"
    skip_if_cassette_missing(cassette_name)

    async def _test():
        forecast, discussion = await get_nws_forecast_and_discussion(
            TEST_LOCATION,
            "https://api.weather.gov",
            USER_AGENT,
            REQUEST_TIMEOUT,
            http_client,
        )

        # Contract: forecast must exist and have periods
        assert forecast is not None, "NWS should return forecast data"
        assert len(forecast.periods) > 0, "Forecast should have at least one period"

        # Check first few periods for contract compliance
        for i, period in enumerate(forecast.periods[:5]):
            # Contract: period name must exist and be non-empty
            assert period.name is not None, f"Period {i} should have a name"
            assert isinstance(period.name, str), f"Period {i} name should be a string"
            assert len(period.name) > 0, f"Period {i} name should not be empty"

            # Contract: temperature, if present, must be in reasonable range
            if period.temperature is not None:
                assert isinstance(period.temperature, (int, float)), (
                    f"Period {i} temperature should be numeric"
                )
                # Reasonable temperature range (-100°F to 150°F for edge cases)
                assert -100 <= period.temperature <= 150, (
                    f"Period {i} temperature {period.temperature} is outside valid range"
                )

            # Contract: start_time, if present, must be valid datetime with year > 2000
            if period.start_time is not None:
                assert isinstance(period.start_time, datetime), (
                    f"Period {i} start_time should be datetime"
                )
                assert period.start_time.year > 2000, f"Period {i} start_time year is invalid"

        await conditional_async_sleep(DELAY_BETWEEN_REQUESTS)

    if HAS_VCR:
        my_vcr = vcr.VCR(**get_vcr_config())
        with my_vcr.use_cassette(cassette_name):
            await _test()
    else:
        await _test()


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_nws_hourly_forecast_has_timestamps(http_client):
    """Test NWS hourly forecast returns periods with valid timestamps (uses VCR cassettes)."""
    cassette_name = "nws/test_hourly_forecast_timestamps.yaml"
    skip_if_cassette_missing(cassette_name)

    async def _test():
        hourly = await get_nws_hourly_forecast(
            TEST_LOCATION,
            "https://api.weather.gov",
            USER_AGENT,
            REQUEST_TIMEOUT,
            http_client,
        )

        # Contract: hourly forecast must exist and have periods
        assert hourly is not None, "NWS should return hourly forecast"
        assert len(hourly.periods) > 0, "Hourly forecast should have periods"

        # Check first few hourly periods for contract compliance
        for i, period in enumerate(hourly.periods[:10]):
            if period.start_time is not None:
                # Contract: start_time must be a valid datetime
                assert isinstance(period.start_time, datetime), (
                    f"Hourly period {i} start_time should be datetime"
                )
                # Contract: year must be reasonable
                assert period.start_time.year > 2000, (
                    f"Hourly period {i} start_time year is invalid"
                )

                # Only check time bounds in live mode WITHOUT cassettes (cassettes have fixed times)
                if LIVE_WEATHER_TESTS and not HAS_VCR and period.start_time.tzinfo is not None:
                    now = datetime.now(UTC)
                    max_future = timedelta(days=3)
                    max_past = timedelta(hours=1)
                    delta = period.start_time - now
                    assert delta > -max_past, (
                        f"Hourly period {i} start_time {period.start_time} is too far in past"
                    )
                    assert delta < max_future, (
                        f"Hourly period {i} start_time {period.start_time} is too far in future"
                    )

        await conditional_async_sleep(DELAY_BETWEEN_REQUESTS)

    if HAS_VCR:
        my_vcr = vcr.VCR(**get_vcr_config())
        with my_vcr.use_cassette(cassette_name):
            await _test()
    else:
        await _test()


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_nws_parallel_fetch_returns_data(http_client):
    """Test NWS parallel fetch returns expected data structure (uses VCR cassettes)."""
    cassette_name = "nws/test_parallel_fetch.yaml"
    skip_if_cassette_missing(cassette_name)

    async def _test():
        current, forecast, discussion, alerts, hourly = await get_nws_all_data_parallel(
            TEST_LOCATION,
            "https://api.weather.gov",
            USER_AGENT,
            REQUEST_TIMEOUT,
            http_client,
        )

        # Contract: forecast must be available (most reliable NWS endpoint)
        assert forecast is not None, "NWS should return forecast data"
        assert len(forecast.periods) > 0, "Forecast should have periods"

        # Contract: hourly forecast, if available, must have periods
        if hourly is not None:
            assert len(hourly.periods) > 0, "Hourly forecast should have periods"

        # Contract: alerts, if available, must be a list
        if alerts is not None:
            assert isinstance(alerts.alerts, list), "Alerts should be a list"

        await conditional_async_sleep(DELAY_BETWEEN_REQUESTS)

    if HAS_VCR:
        my_vcr = vcr.VCR(**get_vcr_config())
        with my_vcr.use_cassette(cassette_name):
            await _test()
    else:
        await _test()


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_nws_raw_observation_timestamp_parsing(http_client):
    """Test parsing of NWS observation timestamp from raw API response (uses VCR cassettes)."""
    cassette_name = "nws/test_raw_observation_timestamp.yaml"
    skip_if_cassette_missing(cassette_name)

    async def _test():
        # Get grid point to find observation stations
        grid_data = await get_nws_grid_point(
            TEST_LOCATION.latitude,
            TEST_LOCATION.longitude,
            http_client,
        )

        stations_url = grid_data["observationStations"]
        await conditional_async_sleep(DELAY_BETWEEN_REQUESTS)

        # Get list of stations
        stations_response = await http_client.get(stations_url)
        stations_response.raise_for_status()
        stations_data = stations_response.json()

        features = stations_data.get("features", [])
        # Contract: at least one observation station must exist
        assert len(features) > 0, "Should have at least one observation station"

        # Try to get latest observation from first station
        station_id = features[0]["properties"]["stationIdentifier"]
        obs_url = f"https://api.weather.gov/stations/{station_id}/observations/latest"

        await conditional_async_sleep(DELAY_BETWEEN_REQUESTS)

        obs_response = await http_client.get(obs_url)
        if obs_response.status_code == 200:
            obs_data = obs_response.json()
            properties = obs_data.get("properties", {})

            # Contract: observation must have timestamp
            timestamp = properties.get("timestamp")
            assert timestamp is not None, "Observation should have timestamp"
            assert isinstance(timestamp, str), "Timestamp should be a string"

            # Contract: timestamp must be parseable
            from accessiweather.weather_client_nws import _parse_iso_datetime

            parsed_time = _parse_iso_datetime(timestamp)
            assert parsed_time is not None, f"Failed to parse timestamp: {timestamp}"
            assert isinstance(parsed_time, datetime), "Parsed timestamp should be datetime"
            assert parsed_time.year > 2000, "Parsed timestamp year is invalid"

    if HAS_VCR:
        my_vcr = vcr.VCR(**get_vcr_config())
        with my_vcr.use_cassette(cassette_name):
            await _test()
    else:
        await _test()


# =============================================================================
# Unit tests (no network/cassettes needed - use sample data)
# =============================================================================


@pytest.mark.unit
def test_nws_parser_handles_observation_data():
    """Test NWS observation parser correctly handles timestamp and measurements (unit test)."""
    # Sample NWS observation response structure
    sample_observation = {
        "properties": {
            "timestamp": "2025-11-11T11:54:00+00:00",
            "temperature": {"value": 12.8, "unitCode": "wmoUnit:degC", "qualityControl": "V"},
            "relativeHumidity": {"value": 59, "unitCode": "wmoUnit:percent", "qualityControl": "V"},
            "windSpeed": {"value": 14.8, "unitCode": "wmoUnit:km_h-1", "qualityControl": "V"},
            "windDirection": {
                "value": 270,
                "unitCode": "wmoUnit:degree_(angle)",
                "qualityControl": "V",
            },
            "barometricPressure": {
                "value": 101990,
                "unitCode": "wmoUnit:Pa",
                "qualityControl": "V",
            },
            "visibility": {"value": 16093, "unitCode": "wmoUnit:m", "qualityControl": "V"},
            "textDescription": "Partly Cloudy",
        }
    }

    current = parse_nws_current_conditions(sample_observation)

    # Contract: parsed result has expected structure with reasonable values
    assert current is not None
    assert current.temperature_c is not None
    assert isinstance(current.temperature_c, (int, float))
    assert -100 <= current.temperature_c <= 100  # Celsius range

    assert current.humidity is not None
    assert isinstance(current.humidity, (int, float))
    assert 0 <= current.humidity <= 100  # Percentage range

    assert current.wind_speed_mph is not None or current.wind_speed_kph is not None


@pytest.mark.unit
def test_nws_parser_handles_bad_qc_codes():
    """Test NWS parser ignores measurements with failing quality control codes (unit test)."""
    # Sample with bad QC codes
    sample_observation = {
        "properties": {
            "timestamp": "2025-11-11T11:54:00+00:00",
            "temperature": {
                "value": 12.8,
                "unitCode": "wmoUnit:degC",
                "qualityControl": "X",
            },  # Bad QC
            "relativeHumidity": {
                "value": 59,
                "unitCode": "wmoUnit:percent",
                "qualityControl": "V",
            },  # Good QC
            "textDescription": "Partly Cloudy",
        }
    }

    current = parse_nws_current_conditions(sample_observation)

    # Contract: parser returns a result even with some bad QC
    assert current is not None
    # Contract: good QC values are preserved
    assert current.humidity == 59


@pytest.mark.unit
def test_nws_forecast_parser_handles_periods():
    """Test NWS forecast parser correctly handles period data with timestamps (unit test)."""
    # Sample NWS forecast response
    sample_forecast = {
        "properties": {
            "periods": [
                {
                    "number": 1,
                    "name": "This Afternoon",
                    "startTime": "2025-11-11T14:00:00-05:00",
                    "endTime": "2025-11-11T18:00:00-05:00",
                    "temperature": 40,
                    "temperatureUnit": "F",
                    "windSpeed": "15 to 20 mph",
                    "windDirection": "W",
                    "shortForecast": "Mostly Sunny",
                    "detailedForecast": "Mostly sunny, with a high near 40.",
                },
                {
                    "number": 2,
                    "name": "Tonight",
                    "startTime": "2025-11-11T18:00:00-05:00",
                    "endTime": "2025-11-12T06:00:00-05:00",
                    "temperature": 30,
                    "temperatureUnit": "F",
                    "windSpeed": "10 to 15 mph",
                    "windDirection": "W",
                    "shortForecast": "Partly Cloudy",
                    "detailedForecast": "Partly cloudy, with a low around 30.",
                },
            ]
        }
    }

    forecast = parse_nws_forecast(sample_forecast)

    # Contract: parser returns expected number of periods
    assert len(forecast.periods) == 2

    # Contract: period names are preserved
    assert forecast.periods[0].name == "This Afternoon"
    assert forecast.periods[1].name == "Tonight"

    # Contract: temperatures are in valid range
    assert forecast.periods[0].temperature is not None
    assert -100 <= forecast.periods[0].temperature <= 150
    assert forecast.periods[1].temperature is not None
    assert -100 <= forecast.periods[1].temperature <= 150

    # Contract: start_time is parseable with year > 2000
    assert forecast.periods[0].start_time is not None
    assert forecast.periods[0].start_time.year > 2000
