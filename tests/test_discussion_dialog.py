"""Tests for the discussion dialog and loading dialog interaction."""

import logging
import threading
import time
from unittest.mock import MagicMock, patch

import wx

from accessiweather.api_client import NoaaApiClient
from accessiweather.gui.async_fetchers import DiscussionFetcher

# No need to import WeatherAppHandlers for this test

# Faulthandler is already enabled in conftest.py
logger = logging.getLogger(__name__)

# Sample discussion data for testing
SAMPLE_DISCUSSION_TEXT = (
    "This is a sample forecast discussion.\n"
    "Multiple lines of text.\n"
    "With weather information."
)


class TestDiscussionDialogClosing:
    """Tests for the discussion dialog and loading dialog interaction."""

    @patch("accessiweather.api_client.NoaaApiClient.get_discussion")
    def test_loading_dialog_closes_properly(self, mock_get_discussion, wx_app):
        """Test that the loading dialog is closed when the discussion is fetched."""
        # Mock the API client
        mock_get_discussion.return_value = SAMPLE_DISCUSSION_TEXT
        api_client = MagicMock(spec=NoaaApiClient)
        api_client.get_discussion = mock_get_discussion

        # Create a mock for the discussion fetcher
        fetcher = DiscussionFetcher(api_client)

        # Create a mock for the loading dialog
        loading_dialog = MagicMock()
        loading_dialog.IsShown.return_value = True

        # Create a flag to track if the loading dialog was destroyed
        loading_dialog_destroyed = threading.Event()
        loading_dialog.Destroy.side_effect = lambda: loading_dialog_destroyed.set()

        # Create a callback function that simulates the _on_discussion_fetched method
        def on_success(_discussion_text, _name=None, dialog=None):
            # This simulates what happens in _on_discussion_fetched
            if dialog and dialog.IsShown():
                dialog.Destroy()

            # Simulate showing and closing the discussion dialog
            # In a real app, this would show a modal dialog
            wx.CallLater(100, lambda: None)  # Simulate a delay

        # Fetch the discussion
        fetcher.fetch(
            37.7749,
            -122.4194,
            on_success=lambda text: on_success(text, "Test Location", loading_dialog),
            on_error=lambda _error: None,  # We don't use the error in this test
        )

        # Process events to allow callbacks to execute
        start_time = time.time()
        while not loading_dialog_destroyed.is_set() and time.time() - start_time < 5:
            wx.SafeYield()
            time.sleep(0.1)  # Add a delay to allow processing

        # Verify the loading dialog was destroyed
        assert (
            loading_dialog_destroyed.is_set()
        ), "Loading dialog was not destroyed after discussion was fetched"
        loading_dialog.Destroy.assert_called_once()

    @patch("accessiweather.api_client.NoaaApiClient.get_discussion")
    def test_loading_dialog_closes_when_discussion_dialog_closes(self, mock_get_discussion, wx_app):
        """Test that the loading dialog is closed when the discussion dialog is closed."""
        # Mock the API client
        mock_get_discussion.return_value = SAMPLE_DISCUSSION_TEXT
        api_client = MagicMock(spec=NoaaApiClient)
        api_client.get_discussion = mock_get_discussion

        # Create a mock for the discussion fetcher
        fetcher = DiscussionFetcher(api_client)

        # Create a mock for the loading dialog
        loading_dialog = MagicMock()
        loading_dialog.IsShown.return_value = True

        # Create a flag to track if the loading dialog was destroyed
        loading_dialog_destroyed = threading.Event()
        loading_dialog.Destroy.side_effect = lambda: loading_dialog_destroyed.set()

        # Create a mock for the discussion dialog
        discussion_dialog = MagicMock()
        discussion_dialog.ShowModal.return_value = wx.ID_CLOSE

        # Create a callback function that simulates the _on_discussion_fetched method
        # but doesn't destroy the loading dialog
        def on_success(_discussion_text, _name=None, dialog=None):
            # This simulates what happens in _on_discussion_fetched
            # but we intentionally DON'T destroy the loading dialog here
            # to simulate the bug where the loading dialog isn't closed

            # Instead, we'll show the discussion dialog
            # and then check if the loading dialog is destroyed when the discussion dialog is closed
            discussion_dialog.ShowModal()
            discussion_dialog.Destroy()

            # Now we should destroy the loading dialog
            if dialog and dialog.IsShown():
                dialog.Destroy()

        # Fetch the discussion
        fetcher.fetch(
            37.7749,
            -122.4194,
            on_success=lambda text: on_success(text, "Test Location", loading_dialog),
            on_error=lambda _error: None,  # We don't use the error in this test
        )

        # Process events to allow callbacks to execute
        start_time = time.time()
        while not loading_dialog_destroyed.is_set() and time.time() - start_time < 5:
            wx.SafeYield()
            time.sleep(0.1)  # Add a delay to allow processing

        # Verify the loading dialog was destroyed
        assert (
            loading_dialog_destroyed.is_set()
        ), "Loading dialog was not destroyed after discussion dialog was closed"
        loading_dialog.Destroy.assert_called_once()
