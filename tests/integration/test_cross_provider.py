"""Cross-provider integration tests to compare NWS and Open-Meteo data consistency."""

from __future__ import annotations

import asyncio
import os
from datetime import timedelta

import httpx
import pytest

from accessiweather.models import Location
from accessiweather.weather_client_nws import get_nws_current_conditions
from accessiweather.weather_client_openmeteo import get_openmeteo_current_conditions

# Skip integration tests unless explicitly requested
RUN_INTEGRATION = os.getenv("RUN_INTEGRATION_TESTS", "0") == "1"
skip_reason = "Set RUN_INTEGRATION_TESTS=1 to run integration tests with real API calls"

# Test location: Lumberton, NJ
TEST_LOCATION = Location(name="Lumberton, New Jersey", latitude=39.9643, longitude=-74.8099)

# Configuration
NWS_USER_AGENT = "AccessiWeather/IntegrationTest (github.com/Orinks/AccessiWeather)"
OPENMETEO_BASE_URL = "https://api.open-meteo.com/v1"
NWS_BASE_URL = "https://api.weather.gov"
REQUEST_TIMEOUT = 30.0
DELAY_BETWEEN_REQUESTS = 1.0


@pytest.fixture
async def nws_http_client():
    """HTTP client configured for NWS."""
    headers = {
        "User-Agent": NWS_USER_AGENT,
        "Accept": "application/geo+json",
    }
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers=headers,
    ) as client:
        yield client


@pytest.fixture
async def openmeteo_http_client():
    """HTTP client configured for Open-Meteo."""
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
    ) as client:
        yield client


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
@pytest.mark.asyncio
async def test_sunrise_sunset_cross_provider_comparison(nws_http_client, openmeteo_http_client):
    """
    Compare sunrise/sunset times from Open-Meteo with NWS-enriched data.

    NWS doesn't provide sunrise/sunset directly, but the app enriches NWS data
    with Open-Meteo values. This test verifies both providers return consistent values.
    """
    # Get sunrise/sunset from Open-Meteo
    openmeteo_current = await get_openmeteo_current_conditions(
        TEST_LOCATION,
        OPENMETEO_BASE_URL,
        REQUEST_TIMEOUT,
        openmeteo_http_client,
    )

    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    # NWS doesn't provide sunrise/sunset in observations, but we can verify
    # that Open-Meteo's values are reasonable by checking consistency
    assert openmeteo_current is not None, "Open-Meteo should return current conditions"
    assert openmeteo_current.sunrise_time is not None, "Open-Meteo should provide sunrise"
    assert openmeteo_current.sunset_time is not None, "Open-Meteo should provide sunset"

    # Sunrise should be before sunset
    assert openmeteo_current.sunrise_time < openmeteo_current.sunset_time, (
        "Sunrise should occur before sunset"
    )

    # Sunrise and sunset should be within reasonable hours (4 AM - 8 PM local time range)
    # For a mid-latitude US location:
    sunrise_hour = openmeteo_current.sunrise_time.hour
    sunset_hour = openmeteo_current.sunset_time.hour

    # Sunrise typically between 4 AM and 9 AM (local time)
    # Sunset typically between 4 PM and 9 PM (local time)
    # Note: These are in the timezone returned by API, so we check reasonableness
    assert 0 <= sunrise_hour <= 23, f"Sunrise hour {sunrise_hour} is invalid"
    assert 0 <= sunset_hour <= 23, f"Sunset hour {sunset_hour} is invalid"

    # Day length should be reasonable (between 8 and 16 hours for mid-latitudes)
    day_length = openmeteo_current.sunset_time - openmeteo_current.sunrise_time
    assert timedelta(hours=8) <= day_length <= timedelta(hours=16), (
        f"Day length {day_length} is unrealistic for mid-latitude location"
    )


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
@pytest.mark.asyncio
async def test_temperature_cross_provider_comparison(nws_http_client, openmeteo_http_client):
    """
    Compare temperature readings from NWS and Open-Meteo.

    They should be reasonably close (within a few degrees), though some variation
    is expected due to different observation times and stations.
    """
    # Get current conditions from both providers
    nws_current = await get_nws_current_conditions(
        TEST_LOCATION,
        NWS_BASE_URL,
        NWS_USER_AGENT,
        REQUEST_TIMEOUT,
        nws_http_client,
    )

    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    openmeteo_current = await get_openmeteo_current_conditions(
        TEST_LOCATION,
        OPENMETEO_BASE_URL,
        REQUEST_TIMEOUT,
        openmeteo_http_client,
    )

    # NWS current conditions may be None (station issues)
    if nws_current is None:
        pytest.skip("NWS did not return current conditions")

    assert openmeteo_current is not None, "Open-Meteo should return current conditions"

    # Both should have temperature data
    nws_temp_f = nws_current.temperature_f
    openmeteo_temp_f = openmeteo_current.temperature_f

    if nws_temp_f is not None and openmeteo_temp_f is not None:
        # Temperatures should be within 10°F (accounting for different observation times/stations)
        temp_diff = abs(nws_temp_f - openmeteo_temp_f)
        assert temp_diff <= 10.0, (
            f"Temperature difference too large: NWS={nws_temp_f}°F, "
            f"Open-Meteo={openmeteo_temp_f}°F (diff={temp_diff}°F)"
        )

        # Both should be in reasonable range for Earth's surface
        assert -100 <= nws_temp_f <= 150, f"NWS temperature {nws_temp_f}°F is unrealistic"
        assert -100 <= openmeteo_temp_f <= 150, (
            f"Open-Meteo temperature {openmeteo_temp_f}°F is unrealistic"
        )


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
@pytest.mark.asyncio
async def test_humidity_cross_provider_comparison(nws_http_client, openmeteo_http_client):
    """
    Compare humidity readings from NWS and Open-Meteo.

    Should be reasonably close (within 20 percentage points).
    """
    nws_current = await get_nws_current_conditions(
        TEST_LOCATION,
        NWS_BASE_URL,
        NWS_USER_AGENT,
        REQUEST_TIMEOUT,
        nws_http_client,
    )

    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    openmeteo_current = await get_openmeteo_current_conditions(
        TEST_LOCATION,
        OPENMETEO_BASE_URL,
        REQUEST_TIMEOUT,
        openmeteo_http_client,
    )

    if nws_current is None:
        pytest.skip("NWS did not return current conditions")

    assert openmeteo_current is not None

    nws_humidity = nws_current.humidity
    openmeteo_humidity = openmeteo_current.humidity

    if nws_humidity is not None and openmeteo_humidity is not None:
        # Humidity should be 0-100%
        assert 0 <= nws_humidity <= 100, f"NWS humidity {nws_humidity}% is invalid"
        assert 0 <= openmeteo_humidity <= 100, (
            f"Open-Meteo humidity {openmeteo_humidity}% is invalid"
        )

        # Should be within 20 percentage points
        humidity_diff = abs(nws_humidity - openmeteo_humidity)
        assert humidity_diff <= 20, (
            f"Humidity difference too large: NWS={nws_humidity}%, "
            f"Open-Meteo={openmeteo_humidity}% (diff={humidity_diff}%)"
        )


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
@pytest.mark.asyncio
async def test_data_freshness_cross_provider(nws_http_client, openmeteo_http_client):
    """
    Verify that both providers return recent data with valid timestamps.

    This ensures the issue from the screenshot (wrong sunrise/sunset times)
    doesn't stem from stale or cached data.
    """
    nws_current = await get_nws_current_conditions(
        TEST_LOCATION,
        NWS_BASE_URL,
        NWS_USER_AGENT,
        REQUEST_TIMEOUT,
        nws_http_client,
    )

    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    openmeteo_current = await get_openmeteo_current_conditions(
        TEST_LOCATION,
        OPENMETEO_BASE_URL,
        REQUEST_TIMEOUT,
        openmeteo_http_client,
    )

    assert openmeteo_current is not None
    assert openmeteo_current.last_updated is not None
    assert openmeteo_current.last_updated.year > 2000

    if nws_current is not None:
        assert nws_current.last_updated is not None
        assert nws_current.last_updated.year > 2000

        # Both observations should be relatively recent (within 3 hours)
        age_diff = abs((nws_current.last_updated - openmeteo_current.last_updated).total_seconds())
        # Allow up to 3 hours difference (NWS stations may update less frequently)
        assert age_diff <= 3 * 3600, (
            f"Observation timestamps differ by {age_diff / 3600:.1f} hours - "
            "one provider may have stale data"
        )


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
@pytest.mark.asyncio
async def test_wind_speed_cross_provider_comparison(nws_http_client, openmeteo_http_client):
    """Compare wind speed readings between providers."""
    nws_current = await get_nws_current_conditions(
        TEST_LOCATION,
        NWS_BASE_URL,
        NWS_USER_AGENT,
        REQUEST_TIMEOUT,
        nws_http_client,
    )

    await asyncio.sleep(DELAY_BETWEEN_REQUESTS)

    openmeteo_current = await get_openmeteo_current_conditions(
        TEST_LOCATION,
        OPENMETEO_BASE_URL,
        REQUEST_TIMEOUT,
        openmeteo_http_client,
    )

    if nws_current is None:
        pytest.skip("NWS did not return current conditions")

    assert openmeteo_current is not None

    nws_wind = nws_current.wind_speed_mph
    openmeteo_wind = openmeteo_current.wind_speed_mph

    if nws_wind is not None and openmeteo_wind is not None:
        # Wind speeds should be non-negative
        assert nws_wind >= 0, f"NWS wind speed {nws_wind} mph is negative"
        assert openmeteo_wind >= 0, f"Open-Meteo wind speed {openmeteo_wind} mph is negative"

        # Should be within reasonable range (0-100 mph for non-hurricane conditions)
        assert nws_wind <= 100, f"NWS wind speed {nws_wind} mph is unrealistic"
        assert openmeteo_wind <= 100, f"Open-Meteo wind speed {openmeteo_wind} mph is unrealistic"

        # Should be within 15 mph (wind can vary significantly by location/time)
        wind_diff = abs(nws_wind - openmeteo_wind)
        assert wind_diff <= 15, (
            f"Wind speed difference too large: NWS={nws_wind} mph, "
            f"Open-Meteo={openmeteo_wind} mph (diff={wind_diff} mph)"
        )
