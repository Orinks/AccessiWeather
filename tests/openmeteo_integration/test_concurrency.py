"""Concurrency and thread safety tests for Open-Meteo integration."""

import threading
import time

import pytest

from .conftest import SAMPLE_OPENMETEO_CURRENT_RESPONSE


@pytest.mark.integration
def test_concurrent_requests_thread_safety(weather_service_with_openmeteo, mock_openmeteo_client):
    """Test thread safety with concurrent requests."""
    # London coordinates
    lat, lon = 51.5074, -0.1278

    # Mock response with delay to simulate real API
    def mock_response(*args, **kwargs):
        time.sleep(0.1)  # Small delay
        return SAMPLE_OPENMETEO_CURRENT_RESPONSE

    mock_openmeteo_client.get_current_weather.side_effect = mock_response

    results = []
    errors = []

    def make_request():
        try:
            result = weather_service_with_openmeteo.get_current_conditions(lat, lon)
            results.append(result)
        except Exception as e:
            errors.append(e)

    # Create multiple threads
    threads = []
    for _ in range(5):
        thread = threading.Thread(target=make_request)
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # All requests should succeed
    assert len(errors) == 0
    assert len(results) == 5
    assert all(result is not None for result in results)
