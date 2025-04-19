"""Tests for fetcher cancel methods.

This module contains tests that verify the fetcher cancel methods work properly.
"""

import threading
import unittest
from unittest.mock import MagicMock

from accessiweather.gui.async_fetchers import ForecastFetcher, AlertsFetcher, DiscussionFetcher
from accessiweather.national_forecast_fetcher import NationalForecastFetcher


class TestFetcherCancel(unittest.TestCase):
    """Test case for fetcher cancel methods."""

    def setUp(self):
        """Set up the test case."""
        # Create mock API client
        self.mock_api_client = MagicMock()
        
        # Create fetchers with the mock API client
        self.forecast_fetcher = ForecastFetcher(self.mock_api_client)
        self.alerts_fetcher = AlertsFetcher(self.mock_api_client)
        self.discussion_fetcher = DiscussionFetcher(self.mock_api_client)
        self.national_forecast_fetcher = NationalForecastFetcher(self.mock_api_client)

    def test_forecast_fetcher_cancel(self):
        """Test that ForecastFetcher.cancel works properly."""
        # Create a mock thread
        self.forecast_fetcher.thread = MagicMock()
        self.forecast_fetcher.thread.is_alive.return_value = True
        
        # Call the cancel method
        self.forecast_fetcher.cancel()
        
        # Verify the stop event was set
        self.assertTrue(self.forecast_fetcher._stop_event.is_set())
        
        # Verify the thread was joined
        self.forecast_fetcher.thread.join.assert_called_once()

    def test_alerts_fetcher_cancel(self):
        """Test that AlertsFetcher.cancel works properly."""
        # Create a mock thread
        self.alerts_fetcher.thread = MagicMock()
        self.alerts_fetcher.thread.is_alive.return_value = True
        
        # Call the cancel method
        self.alerts_fetcher.cancel()
        
        # Verify the stop event was set
        self.assertTrue(self.alerts_fetcher._stop_event.is_set())
        
        # Verify the thread was joined
        self.alerts_fetcher.thread.join.assert_called_once()

    def test_discussion_fetcher_cancel(self):
        """Test that DiscussionFetcher.cancel works properly."""
        # Create a mock thread
        self.discussion_fetcher.thread = MagicMock()
        self.discussion_fetcher.thread.is_alive.return_value = True
        
        # Call the cancel method
        self.discussion_fetcher.cancel()
        
        # Verify the stop event was set
        self.assertTrue(self.discussion_fetcher._stop_event.is_set())
        
        # Verify the thread was joined
        self.discussion_fetcher.thread.join.assert_called_once()

    def test_national_forecast_fetcher_cancel(self):
        """Test that NationalForecastFetcher.cancel works properly."""
        # Create a mock thread
        self.national_forecast_fetcher.thread = MagicMock()
        self.national_forecast_fetcher.thread.is_alive.return_value = True
        
        # Call the cancel method
        self.national_forecast_fetcher.cancel()
        
        # Verify the stop event was set
        self.assertTrue(self.national_forecast_fetcher._stop_event.is_set())
        
        # Verify the thread was joined
        self.national_forecast_fetcher.thread.join.assert_called_once()


if __name__ == "__main__":
    unittest.main()
