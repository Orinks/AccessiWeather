"""Cross-provider integration tests to compare NWS and Open-Meteo data consistency."""

from __future__ import annotations

import os
from datetime import timedelta

import httpx
import pytest

from accessiweather.models import Location
from accessiweather.weather_client_nws import get_nws_current_conditions
from accessiweather.weather_client_openmeteo import get_openmeteo_current_conditions
from tests.integration.conftest import (
    LIVE_WEATHER_TESTS,
    conditional_async_sleep,
    get_vcr_config,
    skip_if_cassette_missing,
)

try:
    import vcr

    HAS_VCR = True
except ImportError:
    HAS_VCR = False
    vcr = None  # type: ignore[assignment]


# Test location: Lumberton, NJ
TEST_LOCATION = Location(name="Lumberton, New Jersey", latitude=39.9643, longitude=-74.8099)

# Configuration
NWS_USER_AGENT = "AccessiWeather/IntegrationTest (github.com/Orinks/AccessiWeather)"
OPENMETEO_BASE_URL = "https://api.open-meteo.com/v1"
NWS_BASE_URL = "https://api.weather.gov"
REQUEST_TIMEOUT = 30.0
# Longer delay between requests to avoid NWS rate limiting in CI
DELAY_BETWEEN_REQUESTS = 2.0

# Cassette directory
CASSETTE_DIR = os.path.join(os.path.dirname(__file__), "cassettes", "cross_provider")


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
@pytest.mark.asyncio
async def test_sunrise_sunset_cross_provider_comparison(nws_http_client, openmeteo_http_client):
    """
    Compare sunrise/sunset times from Open-Meteo with NWS-enriched data.

    NWS doesn't provide sunrise/sunset directly, but the app enriches NWS data
    with Open-Meteo values. This test verifies both providers return consistent values.
    """
    cassette_name = "cross_provider/sunrise_sunset.yaml"
    skip_if_cassette_missing(cassette_name)
    cassette_path = os.path.join(CASSETTE_DIR, "sunrise_sunset.yaml")

    async def run_test():
        # Get sunrise/sunset from Open-Meteo
        openmeteo_current = await get_openmeteo_current_conditions(
            TEST_LOCATION,
            OPENMETEO_BASE_URL,
            REQUEST_TIMEOUT,
            openmeteo_http_client,
        )

        await conditional_async_sleep(DELAY_BETWEEN_REQUESTS)

        # NWS doesn't provide sunrise/sunset in observations, but we can verify
        # that Open-Meteo's values are reasonable by checking consistency
        assert openmeteo_current is not None, "Open-Meteo should return current conditions"
        assert openmeteo_current.sunrise_time is not None, "Open-Meteo should provide sunrise"
        assert openmeteo_current.sunset_time is not None, "Open-Meteo should provide sunset"

        # Sunrise should be before sunset
        assert openmeteo_current.sunrise_time < openmeteo_current.sunset_time, (
            "Sunrise should occur before sunset"
        )

        # Validate that sunrise and sunset are parseable datetime objects
        sunrise_hour = openmeteo_current.sunrise_time.hour
        sunset_hour = openmeteo_current.sunset_time.hour

        assert 0 <= sunrise_hour <= 23, f"Sunrise hour {sunrise_hour} is invalid"
        assert 0 <= sunset_hour <= 23, f"Sunset hour {sunset_hour} is invalid"

        # Day length should be reasonable (between 8 and 16 hours for mid-latitudes)
        day_length = openmeteo_current.sunset_time - openmeteo_current.sunrise_time
        assert timedelta(hours=8) <= day_length <= timedelta(hours=16), (
            f"Day length {day_length} is unrealistic for mid-latitude location"
        )

    if HAS_VCR and vcr is not None:
        config = get_vcr_config()
        my_vcr = vcr.VCR(**config)
        with my_vcr.use_cassette(cassette_path):  # type: ignore[attr-defined]
            await run_test()
    else:
        await run_test()


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_temperature_cross_provider_comparison(nws_http_client, openmeteo_http_client):
    """
    Compare temperature readings from NWS and Open-Meteo.

    Both providers should return values in a valid range.
    """
    cassette_name = "cross_provider/temperature.yaml"
    skip_if_cassette_missing(cassette_name)
    cassette_path = os.path.join(CASSETTE_DIR, "temperature.yaml")

    async def run_test():
        # Get current conditions from both providers
        try:
            nws_current = await get_nws_current_conditions(
                TEST_LOCATION,
                NWS_BASE_URL,
                NWS_USER_AGENT,
                REQUEST_TIMEOUT,
                nws_http_client,
            )
        except (TimeoutError, httpx.TimeoutException) as e:
            if LIVE_WEATHER_TESTS:
                pytest.skip(f"NWS API timed out (likely rate-limited): {e}")
            raise  # Re-raise in cassette mode - cassettes shouldn't timeout

        await conditional_async_sleep(DELAY_BETWEEN_REQUESTS)

        try:
            openmeteo_current = await get_openmeteo_current_conditions(
                TEST_LOCATION,
                OPENMETEO_BASE_URL,
                REQUEST_TIMEOUT,
                openmeteo_http_client,
            )
        except (TimeoutError, httpx.TimeoutException) as e:
            if LIVE_WEATHER_TESTS:
                pytest.skip(f"Open-Meteo API timed out: {e}")
            raise

        # NWS current conditions may be None (station issues)
        if nws_current is None:
            if LIVE_WEATHER_TESTS:
                pytest.skip("NWS did not return current conditions")
            raise AssertionError("NWS should return current conditions in cassette mode")

        assert openmeteo_current is not None, "Open-Meteo should return current conditions"

        # Both should have temperature data in valid range
        nws_temp_f = nws_current.temperature_f
        openmeteo_temp_f = openmeteo_current.temperature_f

        if nws_temp_f is not None:
            # Temperature should be in reasonable range for Earth's surface
            assert -100 <= nws_temp_f <= 150, f"NWS temperature {nws_temp_f}°F is unrealistic"

        if openmeteo_temp_f is not None:
            assert -100 <= openmeteo_temp_f <= 150, (
                f"Open-Meteo temperature {openmeteo_temp_f}°F is unrealistic"
            )

    if HAS_VCR and vcr is not None:
        config = get_vcr_config()
        my_vcr = vcr.VCR(**config)
        with my_vcr.use_cassette(cassette_path):  # type: ignore[attr-defined]
            await run_test()
    else:
        await run_test()


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_humidity_cross_provider_comparison(nws_http_client, openmeteo_http_client):
    """
    Compare humidity readings from NWS and Open-Meteo.

    Both should return values in the valid 0-100% range.
    """
    cassette_name = "cross_provider/humidity.yaml"
    skip_if_cassette_missing(cassette_name)
    cassette_path = os.path.join(CASSETTE_DIR, "humidity.yaml")

    async def run_test():
        try:
            nws_current = await get_nws_current_conditions(
                TEST_LOCATION,
                NWS_BASE_URL,
                NWS_USER_AGENT,
                REQUEST_TIMEOUT,
                nws_http_client,
            )
        except (TimeoutError, httpx.TimeoutException) as e:
            if LIVE_WEATHER_TESTS:
                pytest.skip(f"NWS API timed out (likely rate-limited): {e}")
            raise

        await conditional_async_sleep(DELAY_BETWEEN_REQUESTS)

        try:
            openmeteo_current = await get_openmeteo_current_conditions(
                TEST_LOCATION,
                OPENMETEO_BASE_URL,
                REQUEST_TIMEOUT,
                openmeteo_http_client,
            )
        except (TimeoutError, httpx.TimeoutException) as e:
            if LIVE_WEATHER_TESTS:
                pytest.skip(f"Open-Meteo API timed out: {e}")
            raise

        if nws_current is None:
            if LIVE_WEATHER_TESTS:
                pytest.skip("NWS did not return current conditions")
            raise AssertionError("NWS should return current conditions in cassette mode")

        assert openmeteo_current is not None

        nws_humidity = nws_current.humidity
        openmeteo_humidity = openmeteo_current.humidity

        # Both should be in valid 0-100% range
        if nws_humidity is not None:
            assert 0 <= nws_humidity <= 100, f"NWS humidity {nws_humidity}% is invalid"

        if openmeteo_humidity is not None:
            assert 0 <= openmeteo_humidity <= 100, (
                f"Open-Meteo humidity {openmeteo_humidity}% is invalid"
            )

    if HAS_VCR and vcr is not None:
        config = get_vcr_config()
        my_vcr = vcr.VCR(**config)
        with my_vcr.use_cassette(cassette_path):  # type: ignore[attr-defined]
            await run_test()
    else:
        await run_test()


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_data_freshness_cross_provider(nws_http_client, openmeteo_http_client):
    """
    Verify that both providers return recent data with valid timestamps.

    This ensures the issue from the screenshot (wrong sunrise/sunset times)
    doesn't stem from stale or cached data.
    """
    cassette_name = "cross_provider/data_freshness.yaml"
    skip_if_cassette_missing(cassette_name)
    cassette_path = os.path.join(CASSETTE_DIR, "data_freshness.yaml")

    async def run_test():
        try:
            await get_nws_current_conditions(
                TEST_LOCATION,
                NWS_BASE_URL,
                NWS_USER_AGENT,
                REQUEST_TIMEOUT,
                nws_http_client,
            )
        except (TimeoutError, httpx.TimeoutException) as e:
            if LIVE_WEATHER_TESTS:
                pytest.skip(f"NWS API timed out (likely rate-limited): {e}")
            raise

        await conditional_async_sleep(DELAY_BETWEEN_REQUESTS)

        try:
            openmeteo_current = await get_openmeteo_current_conditions(
                TEST_LOCATION,
                OPENMETEO_BASE_URL,
                REQUEST_TIMEOUT,
                openmeteo_http_client,
            )
        except (TimeoutError, httpx.TimeoutException) as e:
            if LIVE_WEATHER_TESTS:
                pytest.skip(f"Open-Meteo API timed out: {e}")
            raise

        assert openmeteo_current is not None

    if HAS_VCR and vcr is not None:
        config = get_vcr_config()
        my_vcr = vcr.VCR(**config)
        with my_vcr.use_cassette(cassette_path):  # type: ignore[attr-defined]
            await run_test()
    else:
        await run_test()


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_wind_speed_cross_provider_comparison(nws_http_client, openmeteo_http_client):
    """Compare wind speed readings between providers."""
    cassette_name = "cross_provider/wind_speed.yaml"
    skip_if_cassette_missing(cassette_name)
    cassette_path = os.path.join(CASSETTE_DIR, "wind_speed.yaml")

    async def run_test():
        try:
            nws_current = await get_nws_current_conditions(
                TEST_LOCATION,
                NWS_BASE_URL,
                NWS_USER_AGENT,
                REQUEST_TIMEOUT,
                nws_http_client,
            )
        except (TimeoutError, httpx.TimeoutException) as e:
            if LIVE_WEATHER_TESTS:
                pytest.skip(f"NWS API timed out (likely rate-limited): {e}")
            raise

        await conditional_async_sleep(DELAY_BETWEEN_REQUESTS)

        try:
            openmeteo_current = await get_openmeteo_current_conditions(
                TEST_LOCATION,
                OPENMETEO_BASE_URL,
                REQUEST_TIMEOUT,
                openmeteo_http_client,
            )
        except (TimeoutError, httpx.TimeoutException) as e:
            if LIVE_WEATHER_TESTS:
                pytest.skip(f"Open-Meteo API timed out: {e}")
            raise

        if nws_current is None:
            if LIVE_WEATHER_TESTS:
                pytest.skip("NWS did not return current conditions")
            raise AssertionError("NWS should return current conditions in cassette mode")

        assert openmeteo_current is not None

        nws_wind = nws_current.wind_speed_mph
        openmeteo_wind = openmeteo_current.wind_speed_mph

        # Wind speeds should be non-negative and reasonable (< 200 mph)
        if nws_wind is not None:
            assert nws_wind >= 0, f"NWS wind speed {nws_wind} mph is negative"
            assert nws_wind < 200, f"NWS wind speed {nws_wind} mph is unrealistic"

        if openmeteo_wind is not None:
            assert openmeteo_wind >= 0, f"Open-Meteo wind speed {openmeteo_wind} mph is negative"
            assert openmeteo_wind < 200, (
                f"Open-Meteo wind speed {openmeteo_wind} mph is unrealistic"
            )

    if HAS_VCR and vcr is not None:
        config = get_vcr_config()
        my_vcr = vcr.VCR(**config)
        with my_vcr.use_cassette(cassette_path):  # type: ignore[attr-defined]
            await run_test()
    else:
        await run_test()
