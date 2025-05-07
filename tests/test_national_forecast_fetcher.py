"""Tests for the NationalForecastFetcher class."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.national_forecast_fetcher import NationalForecastFetcher
from accessiweather.services.weather_service import WeatherService
from accessiweather.utils.thread_manager import ThreadManager

# Sample data for testing
SAMPLE_NATIONAL_DATA = {
    "national_discussion_summaries": {
        "wpc": {
            "short_range_summary": "WPC Short Range Summary",
            "short_range_full": "WPC Full Discussion",
        },
        "spc": {"day1_summary": "SPC Day 1 Summary", "day1_full": "SPC Full Discussion"},
        "attribution": "Data from NOAA/NWS",
    }
}


@pytest.fixture
def mock_weather_service():
    """Create a mock WeatherService for testing."""
    service = MagicMock(spec=WeatherService)
    service.get_national_forecast_data.return_value = SAMPLE_NATIONAL_DATA
    return service


@pytest.fixture
def fetcher(mock_weather_service):
    """Create a NationalForecastFetcher instance for testing."""
    return NationalForecastFetcher(mock_weather_service)


@pytest.fixture
def app():
    """Create a wxPython app for testing."""
    app = wx.App()
    yield app
    app.Destroy()


def test_init(fetcher, mock_weather_service):
    """Test initialization of the NationalForecastFetcher."""
    assert fetcher.service == mock_weather_service
    assert fetcher.thread is None
    assert isinstance(fetcher._stop_event, threading.Event)
    assert not fetcher._stop_event.is_set()


def test_fetch_success(fetcher, mock_weather_service, app):
    """Test successful fetch operation."""
    # Mock the wx.CallAfter function
    with patch("wx.CallAfter") as mock_call_after:
        # Create a mock success callback
        on_success = MagicMock()

        # Call fetch
        fetcher.fetch(on_success=on_success)

        # Wait for the thread to complete
        time.sleep(0.1)

        # Verify the service method was called
        mock_weather_service.get_national_forecast_data.assert_called_once_with(force_refresh=False)

        # Verify the callback was called with the correct data
        mock_call_after.assert_called_once_with(on_success, SAMPLE_NATIONAL_DATA)


def test_fetch_error(fetcher, mock_weather_service, app):
    """Test fetch operation with an error."""
    # Set up the service to raise an exception
    mock_weather_service.get_national_forecast_data.side_effect = Exception("Test error")

    # Mock the wx.CallAfter function
    with patch("wx.CallAfter") as mock_call_after:
        # Create a mock error callback
        on_error = MagicMock()

        # Call fetch
        fetcher.fetch(on_error=on_error)

        # Wait for the thread to complete
        time.sleep(0.1)

        # Verify the service method was called
        mock_weather_service.get_national_forecast_data.assert_called_once_with(force_refresh=False)

        # Verify the error callback was called with the correct error message
        mock_call_after.assert_called_once()
        args = mock_call_after.call_args[0]
        assert args[0] == on_error
        assert "Test error" in args[1]


def test_fetch_with_force_refresh(fetcher, mock_weather_service, app):
    """Test fetch operation with force_refresh=True."""
    # Mock the wx.CallAfter function
    with patch("wx.CallAfter") as mock_call_after:
        # Create a mock success callback
        on_success = MagicMock()

        # Call fetch with force_refresh=True
        fetcher.fetch(on_success=on_success, force_refresh=True)

        # Wait for the thread to complete
        time.sleep(0.1)

        # Verify the service method was called with force_refresh=True
        mock_weather_service.get_national_forecast_data.assert_called_once_with(force_refresh=True)

        # Verify the callback was called with the correct data
        mock_call_after.assert_called_once_with(on_success, SAMPLE_NATIONAL_DATA)


def test_cancel(fetcher, mock_weather_service):
    """Test cancelling a fetch operation."""

    # Mock the service method to block until cancelled
    def blocking_get(*args, **kwargs):  # noqa: ARG001
        # Block until the stop event is set
        while not fetcher._stop_event.is_set():
            time.sleep(0.01)
        return SAMPLE_NATIONAL_DATA

    mock_weather_service.get_national_forecast_data.side_effect = blocking_get

    # Start a fetch operation in a separate thread so we don't block the test
    fetch_thread = threading.Thread(target=fetcher.fetch)
    fetch_thread.daemon = True
    fetch_thread.start()

    # Give the thread time to start
    time.sleep(0.1)

    # Cancel the operation
    fetcher.cancel()

    # Verify the stop event was set
    assert fetcher._stop_event.is_set()

    # Wait for the thread to complete
    fetch_thread.join(timeout=1.0)


def test_cleanup(fetcher, mock_weather_service):
    """Test cleanup method."""

    # Mock the service method to block until cancelled
    def blocking_get(*args, **kwargs):  # noqa: ARG001
        # Block until the stop event is set
        while not fetcher._stop_event.is_set():
            time.sleep(0.01)
        return SAMPLE_NATIONAL_DATA

    mock_weather_service.get_national_forecast_data.side_effect = blocking_get

    # Start a fetch operation in a separate thread so we don't block the test
    fetch_thread = threading.Thread(target=fetcher.fetch)
    fetch_thread.daemon = True
    fetch_thread.start()

    # Give the thread time to start
    time.sleep(0.1)

    # Call cleanup
    fetcher.cleanup()

    # Verify the stop event was set
    assert fetcher._stop_event.is_set()

    # Wait for the thread to complete
    fetch_thread.join(timeout=1.0)

    # Verify the thread was reset
    assert fetcher.thread is None


def test_thread_manager_integration(fetcher, mock_weather_service):  # noqa: ARG001
    """Test integration with ThreadManager."""
    # Get the ThreadManager instance
    thread_manager = ThreadManager.instance()

    # Clear any existing threads
    thread_manager.clear()

    # Mock the thread registration to verify it's called
    with patch.object(ThreadManager, "register_thread") as mock_register:
        with patch.object(ThreadManager, "unregister_thread") as mock_unregister:
            # Start a fetch operation
            fetcher.fetch()

            # Wait for the thread to start and complete
            time.sleep(0.2)

            # Verify register_thread was called
            assert mock_register.called

            # Verify unregister_thread was called
            assert mock_unregister.called
