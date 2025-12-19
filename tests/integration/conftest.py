"""Pytest configuration for integration tests with VCR cassette infrastructure."""

from __future__ import annotations

import os
import re
from typing import Any

import pytest

LIVE_WEATHER_TESTS = os.getenv("LIVE_WEATHER_TESTS", "0") == "1"

try:
    import vcr

    HAS_VCR = True
except ImportError:
    HAS_VCR = False
    vcr = None  # type: ignore[assignment]


# Pytest markers
def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "network: mark test as requiring network access")
    config.addinivalue_line(
        "markers", "live_only: mark test as only running with real APIs (LIVE_WEATHER_TESTS=1)"
    )


# Headers to scrub from responses
SENSITIVE_HEADERS = [
    "Set-Cookie",
    "X-Request-Id",
    "X-Correlation-Id",
    "X-Amz-Request-Id",
    "X-Amz-Id-2",
    "CF-RAY",
    "CF-Cache-Status",
    "Report-To",
    "NEL",
]

# Patterns for API keys in URLs and bodies
API_KEY_PATTERNS = [
    (re.compile(r"api_key=[^&\s]+"), "api_key=REDACTED"),
    (re.compile(r"apikey=[^&\s]+", re.IGNORECASE), "apikey=REDACTED"),
    (re.compile(r"key=[^&\s]+"), "key=REDACTED"),
    (re.compile(r'"api_key"\s*:\s*"[^"]+"'), '"api_key": "REDACTED"'),
    (re.compile(r'"apiKey"\s*:\s*"[^"]+"'), '"apiKey": "REDACTED"'),
]


def scrub_response(response: dict[str, Any]) -> dict[str, Any]:
    """
    Scrub sensitive data from recorded responses.

    Args:
        response: The VCR response dictionary.

    Returns:
        The sanitized response dictionary.

    """
    # Scrub sensitive headers
    headers = response.get("headers", {})
    for header in SENSITIVE_HEADERS:
        # VCR stores headers as lists, handle both cases
        if header in headers:
            del headers[header]
        # Also check lowercase
        if header.lower() in headers:
            del headers[header.lower()]

    # Scrub body content
    body = response.get("body", {})
    if isinstance(body, dict) and "string" in body:
        body_str = body["string"]
        if isinstance(body_str, bytes):
            try:
                body_str = body_str.decode("utf-8")
                was_bytes = True
            except UnicodeDecodeError:
                was_bytes = False
                body_str = None
        else:
            was_bytes = False

        if body_str:
            # Scrub API keys from body
            for pattern, replacement in API_KEY_PATTERNS:
                body_str = pattern.sub(replacement, body_str)

            if was_bytes:
                body["string"] = body_str.encode("utf-8")
            else:
                body["string"] = body_str

    return response


def scrub_request(request: Any) -> Any:
    """
    Scrub sensitive data from recorded requests.

    Args:
        request: The VCR request object.

    Returns:
        The sanitized request object.

    """
    # Scrub API keys from URI
    if hasattr(request, "uri"):
        uri = request.uri
        for pattern, replacement in API_KEY_PATTERNS:
            uri = pattern.sub(replacement, uri)
        request.uri = uri

    return request


def get_vcr_config() -> dict[str, Any]:
    """
    Get VCR configuration dictionary.

    Returns:
        Configuration dictionary for VCR.

    """
    cassette_dir = os.path.join(os.path.dirname(__file__), "cassettes")

    # Determine record mode based on environment
    # In live mode: record new episodes
    # In replay mode: only play back existing cassettes
    record_mode = "new_episodes" if LIVE_WEATHER_TESTS else "none"

    return {
        "cassette_library_dir": cassette_dir,
        "record_mode": record_mode,
        "filter_headers": ["Authorization", "X-Api-Key", "Cookie"],
        "filter_post_data_parameters": ["api_key", "apikey", "key", "password", "secret"],
        "before_record_response": scrub_response,
        "before_record_request": scrub_request,
        "match_on": ["method", "scheme", "host", "port", "path", "query"],
        "decode_compressed_response": True,
    }


def cassette_exists(cassette_name: str) -> bool:
    """Check if a cassette file exists."""
    cassette_dir = os.path.join(os.path.dirname(__file__), "cassettes")
    cassette_path = os.path.join(cassette_dir, cassette_name)
    return os.path.exists(cassette_path)


def skip_if_cassette_missing(cassette_name: str) -> None:
    """Skip the test if cassette doesn't exist and not in live mode."""
    if not LIVE_WEATHER_TESTS and not cassette_exists(cassette_name):
        pytest.skip(f"Cassette {cassette_name} not found. Run with LIVE_WEATHER_TESTS=1 to record.")


@pytest.fixture
def vcr_config() -> dict[str, Any]:
    """
    Fixture providing VCR configuration.

    Returns:
        VCR configuration dictionary.

    """
    return get_vcr_config()


@pytest.fixture
def live_weather_mode() -> bool:
    """
    Fixture indicating if live weather tests are enabled.

    Returns:
        True if LIVE_WEATHER_TESTS=1, False otherwise.

    """
    return LIVE_WEATHER_TESTS


@pytest.fixture
def skip_if_no_live_mode() -> None:
    """
    Fixture that skips the test if not in live mode.

    Use this fixture for tests that should ONLY run with real APIs.
    """
    if not LIVE_WEATHER_TESTS:
        pytest.skip("Test requires LIVE_WEATHER_TESTS=1 to run with real APIs")


@pytest.fixture
def integration_vcr() -> Any:
    """
    Fixture providing a configured VCR instance.

    Returns:
        Configured VCR instance, or None if vcrpy is not installed.

    """
    if not HAS_VCR or vcr is None:
        pytest.skip("vcrpy is not installed")
        return None

    config = get_vcr_config()
    return vcr.VCR(**config)


@pytest.fixture
def cassette_dir() -> str:
    """
    Fixture providing the path to the cassettes directory.

    Returns:
        Absolute path to the cassettes directory.

    """
    return os.path.join(os.path.dirname(__file__), "cassettes")
