"""Tests for thread cleanup in the NationalForecastFetcher class."""
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.national_forecast_fetcher import NationalForecastFetcher


class TestNationalForecastCleanup:
    """Test suite for NationalForecastFetcher thread cleanup."""

    def test_thread_cleanup_after_completion(self):
        """Test that threads are properly cleaned up after completion."""
        # Create a mock weather service
        mock_service = MagicMock()
        mock_service.get_national_forecast_data.return_value = {
            "national_discussion_summaries": {
                "wpc": {"short_range_summary": "Test summary"}
            }
        }
        
        # Create the fetcher with the mock service
        fetcher = NationalForecastFetcher(mock_service)
        
        # Track when the callback is called
        callback_called = threading.Event()
        
        def on_success_callback(data):
            callback_called.set()
        
        # Start a fetch operation
        fetcher.fetch(on_success=on_success_callback)
        
        # Wait for the callback to be called
        callback_called.wait(timeout=1.0)
        
        # Wait a bit more to ensure thread completes
        time.sleep(0.2)
        
        # Verify thread is not alive
        assert fetcher.thread is not None
        assert not fetcher.thread.is_alive()
        
        # Run the cleanup method
        fetcher.cleanup()
        
        # Verify thread is None
        assert fetcher.thread is None

    def test_thread_cleanup_after_cancel(self):
        """Test that threads are properly cleaned up after cancellation."""
        # Create a mock weather service that has a delay
        mock_service = MagicMock()
        def delayed_get(force_refresh=False):
            time.sleep(0.5)  # Add delay to ensure we can cancel
            return {"data": "value"}
        mock_service.get_national_forecast_data.side_effect = delayed_get
        
        # Create the fetcher with the mock service
        fetcher = NationalForecastFetcher(mock_service)
        
        # Start a fetch operation
        fetcher.fetch()
        
        # Ensure thread is started
        assert fetcher.thread is not None
        assert fetcher.thread.is_alive()
        
        # Cancel the operation
        fetcher.cancel()
        
        # Wait for the thread to complete
        time.sleep(0.2)
        
        # Run the cleanup method
        fetcher.cleanup()
        
        # Verify thread is None
        assert fetcher.thread is None

    def test_auto_cleanup_on_garbage_collection(self):
        """Test that threads are properly cleaned up when the fetcher is garbage collected."""
        # This is harder to test, but we can verify the __del__ method cleans up resources
        
        # Create a mock weather service
        mock_service = MagicMock()
        
        # Create the fetcher with the mock service
        fetcher = NationalForecastFetcher(mock_service)
        
        # Start a fetch operation
        fetcher.fetch()
        
        # Store the thread object
        thread = fetcher.thread
        
        # Call the __del__ method manually (which is what happens during garbage collection)
        # This is a bit of a hack, but it's the best way to test this
        fetcher.__del__()
        
        # Verify thread is None and stop_event is set
        assert fetcher.thread is None
        assert fetcher._stop_event.is_set()
