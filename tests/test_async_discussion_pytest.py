import queue
import threading
import time
import unittest
from unittest.mock import MagicMock, patch
import wx
import logging

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

        self.event_queue = queue.Queue()

        # Start patches - these will be active for the duration of the test method
        self.patch_progress_dialog = patch("wx.ProgressDialog", new_callable=MagicMock)
        self.mock_progress_dialog = self.patch_progress_dialog.start()
        self.mock_progress_dialog.return_value.Pulse.return_value = None
        self.mock_progress_dialog.return_value.Destroy.return_value = None

        self.patch_message_box = patch("wx.MessageBox", side_effect=self._mock_message_box)
        self.mock_message_box = self.patch_message_box.start()

        self.patch_discussion_dialog_init = patch(
            "accessiweather.gui.dialogs.WeatherDiscussionDialog.__init__",
            side_effect=self._mock_discussion_dialog_init,
        )
        self.mock_discussion_dialog_init_patcher = (
            self.patch_discussion_dialog_init.start()
        )

        @pytest.fixture
        def mock_dialogs(monkeypatch, event_queue):
            # Mock ProgressDialog to behave more like a real window
            def mock_progress_factory(*args, **kwargs):
                # Create a mock specifically for ProgressDialog instances
                mock_instance = MagicMock(spec=wx.ProgressDialog)
                mock_instance.Pulse.return_value = (True, False) # Match real signature return
                mock_instance.Destroy.return_value = None
                mock_instance.IsShown.return_value = True # Assume shown initially for cleanup logic
                # Add Update method if needed by the code
                mock_instance.Update.return_value = (True, False)
                return mock_instance
            monkeypatch.setattr(wx, "ProgressDialog", mock_progress_factory)

            self.mock_discussion_dialog = MagicMock()

        # Add patch for wx.MessageDialog to handle the init check
        self.patch_message_dialog = patch("wx.MessageDialog", new_callable=MagicMock)
        self.mock_message_dialog = self.patch_message_dialog.start()
        # Configure the mock dialog instance returned by the patch
        mock_dialog_instance = self.mock_message_dialog.return_value
        mock_dialog_instance.ShowModal.return_value = wx.ID_NO # Simulate 'No' click
        mock_dialog_instance.Destroy.return_value = None

        self.mock_discussion_dialog.ShowModal.return_value = None
        self.mock_discussion_dialog.Destroy.return_value = None

        # Instance of the app under test
        self.app = WeatherApp(
            self.frame,
            weather_service=MagicMock(),
            location_service=self.mock_location_manager,
            api_client=self.mock_api_client,
            notification_service=MagicMock(),
            config={"skip_api_contact_check": True},  # Provide an empty config with skip flag
            config_path="dummy_path", # Provide a dummy path
        )
        self.app.discussion_btn = MagicMock()  # Mock the button
        # Mock the discussion_fetcher; set side_effect in each test
        self.app.discussion_fetcher = MagicMock()

    def tearDown(self):
        """Clean up after each test method."""
        # Stop patches in reverse order they were started
        self.patch_message_dialog.stop() # Stop the new patch
        self.patch_discussion_dialog_init.stop()
        self.patch_message_box.stop()
        self.patch_progress_dialog.stop()

        # Destroy the frame
        if self.frame:
            self.frame.Destroy()
        # Allow event loop processing for cleanup
        for _ in range(3):
             wx.YieldIfNeeded()
             time.sleep(0.01)

        # Shut down logging to close file handlers
        logging.shutdown()

    # --- Mock Implementations --- #

    def _mock_message_box(self, message, caption="", style=wx.OK, parent=None):
        self.event_queue.put(("error_shown", message))
        return wx.ID_OK # Or appropriate default return

    def _mock_discussion_dialog_init(self, parent, title, text):
        self.event_queue.put(("dialog_shown", text))
        # Simulate basic attributes needed if accessed later
        # Store the mock methods directly on the instance being initialized
        # This avoids issues if the mock target is the class __init__ itself.
        # We assign a shared mock instance's methods to the instance being created.
        instance = self # 'self' here refers to the WeatherDiscussionDialog instance
        instance.text = text
        instance.parent = parent
        instance.title = title
        instance.ShowModal = self.mock_discussion_dialog.ShowModal
        instance.Destroy = self.mock_discussion_dialog.Destroy
        instance.mock = self.mock_discussion_dialog # Assign the mock itself if needed

    # --- Test Methods --- #

    def test_discussion_fetched_asynchronously(self):
        """Test discussion fetch and UI update via wx.CallAfter."""
        # Access mocks and app via self
        mock_api_client = self.mock_api_client
        app = self.app
        event_queue = self.event_queue

        event = MagicMock()  # Mock the event object for the handler

        # Configure API mock response for this specific test
        expected_discussion = "Async discussion success!"
        mock_api_client.get_discussion.return_value = expected_discussion

        # Event to signal completion of the success callback
        callback_finished_event = threading.Event()

        # --- Patch the success callback method on the app instance ---
        original_success_callback = app._on_discussion_fetched

        # Define the wrapper function with the correct signature
        def wrapper_on_success(*args, **kwargs):
            # Call the original callback logic first
            original_success_callback(*args, **kwargs)
            # Signal that the callback has completed
            callback_finished_event.set()

        processed_event = False
        # Use patch.object as a context manager
        with patch.object(app, "_on_discussion_fetched", new=wrapper_on_success):
            # Patch discussion_fetcher.fetch to simulate success callback
            def fake_fetch_success(*args, **kwargs):
                # Extract latitude and longitude
                lat, lon = args
                # Trigger API call
                discussion = mock_api_client.get_discussion(lat, lon)
                on_success = kwargs.get('on_success')
                if on_success:
                    wx.CallAfter(on_success, discussion)
            app.discussion_fetcher.fetch.side_effect = fake_fetch_success

            # Call the method that triggers fetching
            app.OnViewDiscussion(event)

            # --- Wait for the callback to execute via wx event loop --- #
            start_time = time.time()
            timeout = 10  # seconds
            while time.time() - start_time < timeout:
                if callback_finished_event.wait(timeout=0.01): # Use wait with timeout
                    processed_event = True
                    break
                # Allow wxPython events to be processed
                wx.YieldIfNeeded()
                # time.sleep(0.01) # Optional small sleep

        self.assertTrue(processed_event, "Success callback did not finish within the timeout.")
        # ---------------------------------------------------------

        # Verify the API call was made correctly (in the background thread)
        mock_api_client.get_discussion.assert_called_once_with(TEST_LAT, TEST_LON)

        # Verify dialog creation was triggered (via callback on main thread)
        dialog_event = None
        try:
            # Should be there now
            dialog_event = event_queue.get(block=False)
        except queue.Empty:
            pass

        self.assertIsNotNone(dialog_event, "Dialog event not found in queue after callback")
        self.assertEqual(dialog_event[0], "dialog_shown", f"Expected 'dialog_shown', got {dialog_event[0]}")
        self.assertEqual(
            dialog_event[1], expected_discussion,
            f"Expected '{expected_discussion}', got {dialog_event[1]}"
        )

        # Check that button was re-enabled (in the callback)
        app.discussion_btn.Enable.assert_called_once()

    def test_discussion_error_handling(self):
        """Test discussion fetch error handling via wx.CallAfter."""
        mock_api_client = self.mock_api_client
        app = self.app
        event_queue = self.event_queue

        event = MagicMock()

        # Configure API mock to raise an error
        error_message = "Network error fetching discussion"
        mock_api_client.get_discussion.side_effect = ApiClientError(error_message)

        # Event to signal completion of the error callback
        callback_finished_event = threading.Event()

        # --- Patch the error callback method on the app instance ---
        original_error_callback = app._on_discussion_error

        # Define the wrapper function with the correct signature
        def wrapper_on_error(*args, **kwargs):
            # Call the original callback logic first
            original_error_callback(*args, **kwargs)
            # Signal that the callback has completed
            callback_finished_event.set()

        processed_event = False
        # Use patch.object as a context manager with the CORRECT method name
        with patch.object(app, "_on_discussion_error", new=wrapper_on_error):
            # Patch discussion_fetcher.fetch to simulate error callback
            def fake_fetch_error(*args, **kwargs):
                # Extract latitude and longitude
                lat, lon = args
                try:
                    mock_api_client.get_discussion(lat, lon)
                except ApiClientError as e:
                    on_error = kwargs.get('on_error')
                    if on_error:
                        wx.CallAfter(on_error, str(e))
            app.discussion_fetcher.fetch.side_effect = fake_fetch_error

            # Call the method that triggers fetching
            app.OnViewDiscussion(event)

            # --- Wait for the callback to execute via wx event loop --- #
            start_time = time.time()
            timeout = 10  # seconds
            while time.time() - start_time < timeout:
                if callback_finished_event.wait(timeout=0.01):
                    processed_event = True
                    break
                wx.YieldIfNeeded()
                # time.sleep(0.01)

        self.assertTrue(processed_event, "Error callback did not finish within the timeout.")
        # ---------------------------------------------------------

        # Verify the API call was made
        mock_api_client.get_discussion.assert_called_once_with(TEST_LAT, TEST_LON)

        # Verify error message was shown via event queue (triggered by callback)
        error_event = None
        try:
            error_event = event_queue.get(block=False)
        except queue.Empty:
            pass

        self.assertIsNotNone(error_event, "Error event not found in queue after callback")
        self.assertEqual(error_event[0], "error_shown", f"Expected 'error_shown', got {error_event[0]}")
        # Check if the original error message is part of the displayed message
        self.assertIn(error_message, error_event[1], f"Expected '{error_message}' in '{error_event[1]}'")

        # Check that button was re-enabled (in the error callback)
        app.discussion_btn.Enable.assert_called_once()


# Add standard unittest execution block
if __name__ == "__main__":
    unittest.main()
