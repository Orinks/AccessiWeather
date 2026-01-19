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
3. Match requests by method, host, path (not query params which may contain API keys)
4. Set record_mode="none" in CI to ensure tests only use recorded cassettes
5. Use record_mode="new_episodes" when adding new tests
6. Run live tests periodically to catch API changes
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import vcr

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
VISUAL_CROSSING_API_KEY = os.environ.get("VISUAL_CROSSING_API_KEY", "test-api-key")


# =============================================================================
# VCR Configuration
# =============================================================================

# Create custom VCR instance with our configuration
# Note: We use filter_query_parameters and filter_headers instead of
# before_record_request to avoid compatibility issues with different VCR versions
integration_vcr = vcr.VCR(
    cassette_library_dir=str(CASSETTE_DIR),
    record_mode=RECORD_MODE,
    # Match on method, scheme, host, port, path - NOT query params (API keys vary)
    match_on=["method", "scheme", "host", "port", "path"],
    # Filter sensitive data from recorded cassettes
    filter_query_parameters=["key", "api_key", "apikey", "token"],
    filter_headers=["authorization", "x-api-key", "api-key", "user-agent"],
    # Decode compressed responses for readable cassettes
    decode_compressed_response=True,
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
def visual_crossing_api_key() -> str:
    """Return the Visual Crossing API key."""
    return VISUAL_CROSSING_API_KEY


@pytest.fixture
def skip_if_no_api_key():
    """Skip test if no Visual Crossing API key is configured."""
    if VISUAL_CROSSING_API_KEY == "test-api-key" and RECORD_MODE == "all":
        pytest.skip("Visual Crossing API key required for recording")


@pytest.fixture
def skip_if_not_live():
    """Skip test if not running in live mode."""
    if not LIVE_TESTS:
        pytest.skip("Live tests disabled (set LIVE_TESTS=true to enable)")
