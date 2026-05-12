"""
Integration test configuration with VCR cassette recording.

This module provides:
- VCR configuration for recording/replaying HTTP interactions
- API key filtering to prevent secret leakage
- Fixtures for test locations and API clients
- Support for both live and recorded test modes

Best Practices for API Integration Testing:
1. Use VCR cassettes to record and replay HTTP interactions
2. Filter sensitive data (API keys) from recorded cassettes
3. Match provider request query strings when non-secret parameters affect payload shape.
4. Set record_mode="none" in CI to ensure tests only use recorded cassettes
5. Use record_mode="new_episodes" when adding new tests
6. Run live tests periodically to catch API changes
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlsplit

import pytest

try:
    import vcr
except ImportError:  # pragma: no cover - optional test dependency fallback

    class _FallbackVcrInstance:
        def __init__(self, **_kwargs):
            pass

        def use_cassette(self, *_args, **_kwargs):
            def decorator(func):
                return func

            return decorator

        def register_matcher(self, *_args, **_kwargs):
            pass

    class _FallbackVcrModule:
        VCR = _FallbackVcrInstance

    vcr = _FallbackVcrModule()  # type: ignore[assignment]

if TYPE_CHECKING:
    from accessiweather.models import Location

# =============================================================================
# Configuration
# =============================================================================

CASSETTE_DIR = Path(__file__).parent / "cassettes"
CASSETTE_DIR.mkdir(exist_ok=True)

# Environment variables for test mode control
# - "once": Record if cassette doesn't exist, replay if it does (default for dev)
# - "new_episodes": Record new requests, replay existing ones (good for adding tests)
# - "none": Only replay, fail if cassette missing (good for CI)
# - "all": Always record (use sparingly, rewrites cassettes)
RECORD_MODE = os.environ.get("VCR_RECORD_MODE", "none")
LIVE_TESTS = os.environ.get("LIVE_TESTS", "false").lower() == "true"

# API keys from environment (for live tests or recording new cassettes)
PIRATE_WEATHER_API_KEY = os.environ.get("PIRATE_WEATHER_API_KEY", "test-api-key")


# =============================================================================
# VCR Configuration
# =============================================================================


# Create custom VCR instance with our configuration
# Note: We use filter_query_parameters and filter_headers instead of
# before_record_request to avoid compatibility issues with different VCR versions
def _scrub_pw_key_from_uri(request):
    """Replace Pirate Weather API key in URL path with a placeholder."""
    import re

    request.uri = re.sub(
        r"(api\.pirateweather\.net/forecast/)[^/]+(/)",
        r"\1FILTERED_API_KEY\2",
        request.uri,
    )
    return request


def _is_openmeteo_forecast(uri: str) -> bool:
    parts = urlsplit(uri)
    return parts.netloc.endswith("open-meteo.com") and parts.path.endswith("/v1/forecast")


def _is_query_sensitive_provider(uri: str) -> bool:
    parts = urlsplit(uri)
    host = parts.netloc.lower()
    if _is_openmeteo_forecast(uri):
        return True
    return host.endswith(("api.weather.gov", "api.pirateweather.net"))


def _scrubbed_query_items(uri: str) -> list[tuple[str, str]]:
    sensitive = {"key", "api_key", "apikey", "token", "appid", "app_id", "password"}
    list_parameters = {"current", "daily", "hourly"}
    items = []
    for key, value in parse_qsl(urlsplit(uri).query, keep_blank_values=True):
        normalized_key = key.lower()
        if normalized_key in sensitive:
            continue
        if normalized_key in list_parameters:
            items.extend((normalized_key, item) for item in value.split(",") if item)
        else:
            items.append((normalized_key, value))
    return sorted(items)


def _match_provider_query(request_1, request_2):
    """Require query equality for provider endpoints whose query changes the response."""
    if not (
        _is_query_sensitive_provider(request_1.uri) or _is_query_sensitive_provider(request_2.uri)
    ):
        return

    query_1 = _scrubbed_query_items(request_1.uri)
    query_2 = _scrubbed_query_items(request_2.uri)
    if query_1 != query_2:
        raise AssertionError(f"{query_1} != {query_2}")


integration_vcr = vcr.VCR(
    cassette_library_dir=str(CASSETTE_DIR),
    record_mode=RECORD_MODE,
    # Query-sensitive matching prevents payload mixups when params drive provider response shape.
    match_on=["method", "scheme", "host", "port", "path", "provider_query"],
    # Filter sensitive data from recorded cassettes
    filter_query_parameters=["key", "api_key", "apikey", "token"],
    filter_headers=["authorization", "x-api-key", "api-key", "user-agent"],
    # Scrub PW API keys from URL paths before recording
    before_record_request=_scrub_pw_key_from_uri,
    # Decode compressed responses for readable cassettes
    decode_compressed_response=True,
)
integration_vcr.register_matcher(
    "provider_query",
    _match_provider_query,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def vcr_cassette_dir() -> Path:
    """Return the cassette directory path."""
    return CASSETTE_DIR


@pytest.fixture
def us_location() -> Location:
    """Return a US location for testing (New York City)."""
    from accessiweather.models import Location

    return Location(
        name="New York, NY",
        latitude=40.7128,
        longitude=-74.0060,
        country_code="US",
    )


@pytest.fixture
def international_location() -> Location:
    """Return an international location for testing (London, UK)."""
    from accessiweather.models import Location

    return Location(
        name="London, UK",
        latitude=51.5074,
        longitude=-0.1278,
        country_code="GB",
    )


@pytest.fixture
def alaska_location() -> Location:
    """Return an Alaska location for testing (Anchorage)."""
    from accessiweather.models import Location

    return Location(
        name="Anchorage, AK",
        latitude=61.2181,
        longitude=-149.9003,
        country_code="US",
    )


@pytest.fixture
def norway_location() -> Location:
    """Return a Norwegian location for testing (Tromsø)."""
    from accessiweather.models import Location

    return Location(
        name="Tromsø, Norway",
        latitude=69.6489,
        longitude=18.9551,
        country_code="NO",
    )


@pytest.fixture
def pirate_weather_api_key() -> str:
    """Return the Pirate Weather API key."""
    return PIRATE_WEATHER_API_KEY


@pytest.fixture
def skip_if_no_pw_api_key():
    """Skip test if no Pirate Weather API key is configured."""
    if PIRATE_WEATHER_API_KEY == "test-api-key" and RECORD_MODE == "all":
        pytest.skip("Pirate Weather API key required for recording")


@pytest.fixture
def skip_if_not_live():
    """Skip test if not running in live mode."""
    if not LIVE_TESTS:
        pytest.skip("Live tests disabled (set LIVE_TESTS=true to enable)")
