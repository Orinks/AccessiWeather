import queue
import threading
import time
import unittest
from unittest.mock import MagicMock, patch
import wx
import logging
import pytest

from accessiweather.api_client import ApiClientError, NoaaApiClient
from accessiweather.gui.dialogs import WeatherDiscussionDialog
from accessiweather.gui.weather_app import WeatherApp
from accessiweather.gui.async_fetchers import DiscussionFetcher

# Constants for test location
TEST_LOCATION_NAME = "Test Location"
TEST_LAT, TEST_LON = 35.0, -80.0


class TestAsyncDiscussion(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        # Ensure an app exists for wx.CallAfter processing
        cls.app_instance = wx.App(False)  # Redirect stdout/stderr if needed
        cls.app_instance.SetAppName("TestApp")

    @classmethod
    def tearDownClass(cls):
        # Allow pending events to process before destroying
        for _ in range(5):  # Process pending events a few times
            wx.YieldIfNeeded()
            time.sleep(0.01)
        if cls.app_instance:
            cls.app_instance.Destroy()
        # Clean up any leftover top-level windows if necessary
        # for win in wx.GetTopLevelWindows():
        #     try:
        #         win.Destroy()
        #     except wx.PyDeadObjectError:
        #         pass # Window might already be destroyed

    def setUp(self):
        """Set up for each test method."""
        self.frame = wx.Frame(None)
        # self.frame.Show() # Optional: Show frame if needed

        self.mock_api_client = MagicMock(spec=NoaaApiClient)
        self.mock_api_client.get_discussion.return_value = "Sample discussion text"

        self.mock_location_manager = MagicMock()
        self.mock_location_manager.get_current_location.return_value = (
            TEST_LOCATION_NAME,
            TEST_LAT,
            TEST_LON,
        )

        # Start patches - these will be active for the duration of the test method
        self.patch_progress_dialog = patch("wx.ProgressDialog", new_callable=MagicMock)
        self.mock_progress_dialog = self.patch_progress_dialog.start()
        self.mock_progress_dialog.return_value.Pulse.return_value = None
        self.mock_progress_dialog.return_value.Destroy.return_value = None

        # Patch MessageBox to use a MagicMock directly
        self.patch_message_box = patch("wx.MessageBox", new_callable=MagicMock)
        self.mock_message_box = self.patch_message_box.start()
        # Configure the mock to return OK by default
        self.mock_message_box.return_value = wx.ID_OK

        self.patch_discussion_dialog_class = patch("accessiweather.gui.dialogs.WeatherDiscussionDialog", spec=True)
        self.MockWeatherDiscussionDialog = self.patch_discussion_dialog_class.start()
        mock_dialog_instance = self.MockWeatherDiscussionDialog.return_value
        mock_dialog_instance.ShowModal.return_value = wx.ID_OK
        mock_dialog_instance.Destroy.return_value = None

        self.patch_message_dialog = patch("wx.MessageDialog", new_callable=MagicMock)
        self.mock_message_dialog = self.patch_message_dialog.start()
        mock_dialog_instance = self.mock_message_dialog.return_value
        mock_dialog_instance.ShowModal.return_value = wx.ID_NO
        mock_dialog_instance.Destroy.return_value = None

        # Instance of the app under test
        self.app = WeatherApp(
            self.frame,
            weather_service=MagicMock(),
            location_service=self.mock_location_manager,
            api_client=self.mock_api_client,
            notification_service=MagicMock(),
            config={"skip_api_contact_check": True},
            config_path="dummy_path",
        )
        self.app.discussion_btn = MagicMock()
        self.app.discussion_fetcher = MagicMock()

    def tearDown(self):
        """Clean up after each test method."""
        self.patch_message_dialog.stop()
        self.patch_discussion_dialog_class.stop()
        self.patch_message_box.stop()
        self.patch_progress_dialog.stop()

        if self.frame:
            self.frame.Destroy()
        for _ in range(3):
            wx.YieldIfNeeded()
            time.sleep(0.01)

        logging.shutdown()

    def test_discussion_fetched_asynchronously(self):
        """Test discussion fetch and UI update via wx.CallAfter."""
        # Re-initialize queue for this test
        mock_api_client = self.mock_api_client
        app = self.app
        event = MagicMock()

        expected_discussion = "Async discussion success!"
        mock_api_client.get_discussion.return_value = expected_discussion

        def fake_fetch_success(*args, **kwargs):
            lat, lon = args
            discussion = mock_api_client.get_discussion(lat, lon)
            on_success = kwargs.get('on_success')
            if on_success:
                wx.CallAfter(on_success, discussion)
        app.discussion_fetcher.fetch.side_effect = fake_fetch_success

        app.OnViewDiscussion(event)

        # Assert API Call
        mock_api_client.get_discussion.assert_called_once_with(TEST_LAT, TEST_LON)

        # Assert Discussion Dialog was shown (using the class mock)
        self.MockWeatherDiscussionDialog.assert_called_once()
        args, kwargs = self.MockWeatherDiscussionDialog.call_args
        self.assertEqual(kwargs.get('discussion_text'), expected_discussion)

        # Assert dialog instance methods were called
        dialog_instance = self.MockWeatherDiscussionDialog.return_value
        dialog_instance.ShowModal.assert_called_once()
        dialog_instance.Destroy.assert_called_once()

        app.discussion_btn.Enable.assert_called_once()

    def test_discussion_error_handling(self):
        """Test discussion fetch error handling via wx.CallAfter."""
        mock_api_client = self.mock_api_client
        app = self.app
        event = MagicMock()

        error_message = "Network error fetching discussion"
        mock_api_client.get_discussion.side_effect = ApiClientError(error_message)

        def fake_fetch_error(*args, **kwargs):
            lat, lon = args
            try:
                mock_api_client.get_discussion(lat, lon)
            except ApiClientError as e:
                on_error = kwargs.get('on_error')
                if on_error:
                    wx.CallAfter(on_error, str(e))
        app.discussion_fetcher.fetch.side_effect = fake_fetch_error

        app.OnViewDiscussion(event)

        mock_api_client.get_discussion.assert_called_once_with(TEST_LAT, TEST_LON)

        # Verify error message box was shown via mock call args
        self.mock_message_box.assert_called_once()
        args, kwargs = self.mock_message_box.call_args
        # print(f"MessageBox args: {args}") # Debug print
        # print(f"MessageBox kwargs: {kwargs}") # Debug print
        # Expected message includes location info which might be None in test setup
        expected_base_message = f"Error fetching forecast discussion: {error_message}"
        expected_message_with_loc = f"Error fetching forecast discussion for {TEST_LOCATION_NAME}: {error_message}"

        # Allow for either message format depending on how name is passed
        actual_message = args[0] if args else ""
        self.assertTrue(
            actual_message == expected_base_message or actual_message == expected_message_with_loc,
            f"Actual message '{actual_message}' did not match expected formats."
        )
        self.assertEqual(args[1] if len(args) > 1 else "", "Fetch Error")
        self.assertEqual(args[2] if len(args) > 2 else 0, wx.OK | wx.ICON_ERROR)

        app.discussion_btn.Enable.assert_called_once()


if __name__ == "__main__":
    unittest.main()
