"""Tests for the NationalForecastFetcher class."""
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.national_forecast_fetcher import NationalForecastFetcher


class TestNationalForecastFetcher:
    """Test suite for NationalForecastFetcher."""

    def test_fetch_success(self):
        """Test successful fetch of national forecast data."""
        # Create a mock weather service
        mock_service = MagicMock()
        mock_service.get_national_forecast_data.return_value = {"wpc": {"short_range": "WPC text"}}
        
        # Create the fetcher with the mock service
        fetcher = NationalForecastFetcher(mock_service)
        
        # Create a mock success callback
        mock_success = MagicMock()
        
        # Use patch.object to mock the threading behavior
        with patch.object(threading, 'Thread', autospec=True) as mock_thread:
            # Configure the mock thread to call the target function immediately
            def side_effect(target=None, args=(), kwargs=None, daemon=None):
                mock_thread_instance = MagicMock()
                if target:
                    target(*args)
                return mock_thread_instance
            
            mock_thread.side_effect = side_effect
            
            # Call the fetch method
            fetcher.fetch(on_success=mock_success)
            
            # Verify the success callback was called with the correct data
            mock_success.assert_called_once_with({"wpc": {"short_range": "WPC text"}})
            
            # Verify the service method was called
            mock_service.get_national_forecast_data.assert_called_once_with(force_refresh=False)

    def test_fetch_error(self):
        """Test error handling during fetch."""
        # Create a mock weather service that raises an exception
        mock_service = MagicMock()
        mock_service.get_national_forecast_data.side_effect = Exception("Test error")
        
        # Create the fetcher with the mock service
        fetcher = NationalForecastFetcher(mock_service)
        
        # Create a mock error callback
        mock_error = MagicMock()
        
        # Use patch.object to mock the threading behavior
        with patch.object(threading, 'Thread', autospec=True) as mock_thread:
            # Configure the mock thread to call the target function immediately
            def side_effect(target=None, args=(), kwargs=None, daemon=None):
                mock_thread_instance = MagicMock()
                if target:
                    target(*args)
                return mock_thread_instance
            
            mock_thread.side_effect = side_effect
            
            # Call the fetch method
            fetcher.fetch(on_error=mock_error)
            
            # Verify the error callback was called with an error message
            mock_error.assert_called_once()
            # Check that the error message contains the exception message
            assert "Test error" in mock_error.call_args[0][0]
            
            # Verify the service method was called
            mock_service.get_national_forecast_data.assert_called_once_with(force_refresh=False)

    def test_fetch_cancel(self):
        """Test cancellation of fetch operation."""
        # Create a mock weather service
        mock_service = MagicMock()
        
        # Create the fetcher with the mock service
        fetcher = NationalForecastFetcher(mock_service)
        
        # Use patch.object to mock the threading behavior and stop event
        with patch.object(threading, 'Thread', autospec=True) as mock_thread:
            # Create a mock thread instance
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance
            
            # Create a mock stop event
            mock_stop_event = MagicMock()
            mock_stop_event.is_set.return_value = True
            
            # Set the mock stop event
            with patch.object(fetcher, '_stop_event', mock_stop_event):
                # Call the fetch method
                fetcher.fetch()
                
                # Set the stop event
                fetcher._stop_event.set()
                
                # Verify the stop event was set
                assert fetcher._stop_event.is_set()
                
                # Verify the thread was started
                mock_thread_instance.start.assert_called_once()
