"""Tests for the DiscussionFetcher class."""

import logging
import time
from unittest.mock import MagicMock, patch

import wx

from accessiweather.api_client import NoaaApiClient
from accessiweather.gui.async_fetchers import DiscussionFetcher

# Faulthandler is already enabled in conftest.py
logger = logging.getLogger(__name__)

# Sample discussion data for testing
SAMPLE_DISCUSSION_TEXT = (
    "This is a sample forecast discussion.\n"
    "Multiple lines of text.\n"
    "With weather information."
)


class TestDiscussionFetcher:
    """Tests for the DiscussionFetcher class."""

    def test_init(self):
        """Test initialization of DiscussionFetcher."""
        api_client = MagicMock(spec=NoaaApiClient)
        fetcher = DiscussionFetcher(api_client)

        assert fetcher.api_client == api_client

    @patch("accessiweather.api_client.NoaaApiClient.get_discussion")
    def test_fetch_success(self, mock_get_discussion, wx_app):
        """Test successful fetching of discussion data."""
        # Set up mocks
        api_client = MagicMock(spec=NoaaApiClient)
        mock_get_discussion.return_value = SAMPLE_DISCUSSION_TEXT
        api_client.get_discussion = mock_get_discussion

        # Set up success callback
        success_callback = MagicMock()
        error_callback = MagicMock()

        # Create fetcher and fetch data
        fetcher = DiscussionFetcher(api_client)
        fetcher.fetch(37.7749, -122.4194, success_callback, error_callback)

        # Process events to allow callbacks to execute
        for _ in range(10):
            wx.SafeYield()
            time.sleep(0.05)  # Add a small delay to allow thread to complete

        # Verify the API client was called correctly
        mock_get_discussion.assert_called_once_with(37.7749, -122.4194)

        # Verify the success callback was called with the correct data
        success_callback.assert_called_once_with(SAMPLE_DISCUSSION_TEXT)

        # Verify the error callback was not called
        error_callback.assert_not_called()

    @patch("accessiweather.api_client.NoaaApiClient.get_discussion")
    def test_fetch_error(self, mock_get_discussion, wx_app):
        """Test error handling when fetching discussion data."""
        # Set up mocks
        api_client = MagicMock(spec=NoaaApiClient)
        mock_get_discussion.side_effect = Exception("API error")
        api_client.get_discussion = mock_get_discussion

        # Set up callbacks
        success_callback = MagicMock()
        error_callback = MagicMock()

        # Create fetcher and fetch data
        fetcher = DiscussionFetcher(api_client)
        fetcher.fetch(37.7749, -122.4194, success_callback, error_callback)

        # Process events to allow callbacks to execute
        for _ in range(10):
            wx.SafeYield()
            time.sleep(0.05)  # Add a small delay to allow thread to complete

        # Verify the API client was called correctly
        mock_get_discussion.assert_called_once_with(37.7749, -122.4194)

        # Verify the error callback was called with the error message
        error_callback.assert_called_once()
        assert "API error" in error_callback.call_args[0][0]

        # Verify the success callback was not called
        success_callback.assert_not_called()

    def test_fetch_with_no_callbacks(self):
        """Test fetching with no callbacks provided."""
        api_client = MagicMock(spec=NoaaApiClient)
        fetcher = DiscussionFetcher(api_client)

        # This should not raise an exception
        fetcher.fetch(37.7749, -122.4194)

        # We're just testing that the method doesn't raise an exception
        # when no callbacks are provided
        # No need to verify anything else
        assert True
