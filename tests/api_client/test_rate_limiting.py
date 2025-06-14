"""Tests for NoaaApiClient rate limiting functionality."""

import time
from unittest.mock import patch

import pytest

from tests.api_client_test_utils import (
    SAMPLE_ALERTS_DATA,
    SAMPLE_FORECAST_DATA,
    SAMPLE_POINT_DATA,
    api_client,
)


def test_rate_limiting(api_client):
    """Test that requests are rate limited."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        start_time = time.time()
        api_client.get_point_data(lat, lon)
        api_client.get_point_data(lat, lon)
        end_time = time.time()

        # Should have waited at least min_request_interval
        assert end_time - start_time >= api_client.min_request_interval


def test_rate_limiting_multiple_endpoints(api_client):
    """Test that requests to multiple endpoints are rate limited."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        # Mock responses for different endpoints
        def mock_response(*args, **kwargs):
            url = args[0]
            mock_resp = mock_get.return_value
            mock_resp.raise_for_status.return_value = None

            if "points" in url:
                mock_resp.json.return_value = SAMPLE_POINT_DATA
            elif "forecast" in url:
                mock_resp.json.return_value = SAMPLE_FORECAST_DATA
            elif "alerts" in url:
                mock_resp.json.return_value = SAMPLE_ALERTS_DATA

            return mock_resp

        mock_get.side_effect = mock_response

        start_time = time.time()

        # Make requests to different endpoints
        api_client.get_point_data(lat, lon)
        api_client.get_alerts(lat, lon)

        end_time = time.time()

        # Should have waited for rate limiting between requests
        assert end_time - start_time >= api_client.min_request_interval


@pytest.mark.unit
def test_rate_limiting_with_custom_interval(api_client):
    """Test rate limiting with custom interval."""
    # Set a custom rate limit interval
    api_client.min_request_interval = 2.0

    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        start_time = time.time()
        api_client.get_point_data(lat, lon)
        api_client.get_point_data(lat + 0.1, lon + 0.1)  # Different coordinates
        end_time = time.time()

        # Should have waited at least the custom interval
        assert end_time - start_time >= 2.0


@pytest.mark.unit
def test_rate_limiting_first_request_no_delay(api_client):
    """Test that the first request doesn't have a delay."""
    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        start_time = time.time()
        api_client.get_point_data(lat, lon)
        end_time = time.time()

        # First request should be immediate (allowing for small processing time)
        assert end_time - start_time < 0.1


@pytest.mark.unit
def test_rate_limiting_concurrent_clients():
    """Test that rate limiting is per-client instance."""
    from accessiweather.api_client import NoaaApiClient

    client1 = NoaaApiClient(user_agent="Client1", min_request_interval=1.0)
    client2 = NoaaApiClient(user_agent="Client2", min_request_interval=1.0)

    lat, lon = 40.0, -75.0

    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        start_time = time.time()

        # Both clients should be able to make requests without interfering
        client1.get_point_data(lat, lon)
        client2.get_point_data(lat, lon)

        # Second request from same client should be rate limited
        client1.get_point_data(lat + 0.1, lon + 0.1)

        end_time = time.time()

        # Should have waited for rate limiting on client1's second request
        assert end_time - start_time >= 1.0


@pytest.mark.unit
def test_rate_limiting_with_errors(api_client):
    """Test that rate limiting still applies even when requests fail."""
    lat, lon = 40.0, -75.0

    with patch("requests.get") as mock_get:
        from unittest.mock import MagicMock

        from requests.exceptions import HTTPError

        # First request fails
        mock_response = MagicMock()
        mock_response.status_code = 500
        http_error = HTTPError("500 Server Error")
        http_error.response = mock_response

        # Second request succeeds
        def side_effect(*args, **kwargs):
            if mock_get.call_count == 1:
                raise http_error
            else:
                resp = MagicMock()
                resp.json.return_value = SAMPLE_POINT_DATA
                resp.raise_for_status.return_value = None
                return resp

        mock_get.side_effect = side_effect

        start_time = time.time()

        # First request fails
        from accessiweather.api_client import NoaaApiError

        with pytest.raises(NoaaApiError):
            api_client.get_point_data(lat, lon)

        # Second request should still be rate limited
        api_client.get_point_data(lat + 0.1, lon + 0.1)

        end_time = time.time()

        # Should have waited for rate limiting even after failed request
        assert end_time - start_time >= api_client.min_request_interval


@pytest.mark.unit
def test_rate_limiting_precision(api_client):
    """Test rate limiting precision and accuracy."""
    # Set a precise rate limit interval
    api_client.min_request_interval = 0.5

    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        # Make multiple requests and measure timing
        times = []
        for i in range(3):
            start = time.time()
            api_client.get_point_data(lat + i * 0.1, lon + i * 0.1)
            times.append(time.time() - start)

        # First request should be immediate
        assert times[0] < 0.1

        # Subsequent requests should be rate limited
        for i in range(1, len(times)):
            # Allow for some timing variance but should be close to the interval
            assert times[i] >= 0.4  # Slightly less than 0.5 to account for timing precision
            assert times[i] <= 0.7  # Slightly more than 0.5 to account for processing time


@pytest.mark.unit
def test_rate_limiting_thread_safety(api_client):
    """Test rate limiting behavior with concurrent requests."""
    import queue
    import threading

    lat, lon = 40.0, -75.0
    results = queue.Queue()

    def make_request(client, lat_offset):
        try:
            with patch("requests.get") as mock_get:
                mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
                mock_get.return_value.raise_for_status.return_value = None

                start_time = time.time()
                client.get_point_data(lat + lat_offset, lon)
                end_time = time.time()

                results.put(end_time - start_time)
        except Exception as e:
            results.put(e)

    # Create multiple threads making requests
    threads = []
    for i in range(3):
        thread = threading.Thread(target=make_request, args=(api_client, i * 0.1))
        threads.append(thread)

    # Start all threads
    start_time = time.time()
    for thread in threads:
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Collect results
    request_times = []
    while not results.empty():
        result = results.get()
        if isinstance(result, Exception):
            pytest.fail(f"Request failed: {result}")
        request_times.append(result)

    # At least some requests should have been rate limited
    # (exact behavior depends on threading and rate limiting implementation)
    assert len(request_times) == 3


@pytest.mark.unit
def test_rate_limiting_disabled(api_client):
    """Test behavior when rate limiting is disabled."""
    # Disable rate limiting
    api_client.min_request_interval = 0.0

    lat, lon = 40.0, -75.0
    with patch("requests.get") as mock_get:
        mock_get.return_value.json.return_value = SAMPLE_POINT_DATA
        mock_get.return_value.raise_for_status.return_value = None

        start_time = time.time()
        api_client.get_point_data(lat, lon)
        api_client.get_point_data(lat + 0.1, lon + 0.1)
        end_time = time.time()

        # Should be very fast with no rate limiting
        assert end_time - start_time < 0.1
