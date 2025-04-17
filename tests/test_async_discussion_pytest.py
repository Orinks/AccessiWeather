import queue
import threading
import time  # Import time for the wait loop
from unittest.mock import MagicMock, patch  # Import patch

import pytest
import wx  # type: ignore

from accessiweather.api_client import ApiClientError, NoaaApiClient
from accessiweather.gui.dialogs import WeatherDiscussionDialog
from accessiweather.gui.weather_app import WeatherApp

# Removed unused import: DiscussionFetcher


@pytest.fixture
def wx_app():
    # Ensure an app exists for wx.CallAfter processing
    app = wx.App(False)  # Redirect stdout/stderr if needed
    yield app
    # Allow pending events to process before destroying
    # Sometimes needed, especially on slower systems or complex tests
    for _ in range(5):  # Process pending events a few times
        wx.YieldIfNeeded()
        time.sleep(0.01)
    app.Destroy()
    # Clean up any leftover top-level windows
    # for win in wx.GetTopLevelWindows():
    #     win.Destroy()


@pytest.fixture
def frame(wx_app):
    frame = wx.Frame(None)
    # Frame needs to be shown for event loop processing in some cases
    # frame.Show() # Optional: Show frame if needed, but usually not required
    yield frame
    frame.Destroy()


@pytest.fixture
def mock_api_client():
    mock_client = MagicMock(spec=NoaaApiClient)
    # Configure default return value, can be overridden in tests
    mock_client.get_discussion.return_value = "Sample discussion text"
    return mock_client


@pytest.fixture
def mock_location_manager():
    manager = MagicMock()
    manager.get_current_location.return_value = ("Test Location", 35.0, -80.0)
    return manager


@pytest.fixture
def event_queue():
    return queue.Queue()


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

    # Mock MessageBox - Keep as is
    def mock_message_box(*args, **kwargs):
        event_queue.put(("error_shown", args[0]))
        return None

    monkeypatch.setattr(wx, "MessageBox", mock_message_box)

    # Mock WeatherDiscussionDialog - Keep as is
    discussion_dialog_mock = MagicMock()
    discussion_dialog_mock.ShowModal.return_value = None
    discussion_dialog_mock.Destroy.return_value = None

    def mock_discussion_dialog_init(self, parent, title, text):
        event_queue.put(("dialog_shown", text))
        # Simulate basic attributes needed if accessed later
        self.text = text
        self.parent = parent
        self.title = title
        # Assign mock methods
        self.ShowModal = discussion_dialog_mock.ShowModal
        self.Destroy = discussion_dialog_mock.Destroy

    # Patch __init__ to capture text
    monkeypatch.setattr(WeatherDiscussionDialog, "__init__", mock_discussion_dialog_init)
    # Patch class methods directly to avoid RuntimeError from uninitialized base class
    monkeypatch.setattr(WeatherDiscussionDialog, "ShowModal", discussion_dialog_mock.ShowModal)
    monkeypatch.setattr(WeatherDiscussionDialog, "Destroy", discussion_dialog_mock.Destroy)

    # No longer mocking safe_call_after - let wx.CallAfter run

    # Return the main mock objects if needed elsewhere (though factory/patching is primary)
    # Find a way to return the instance created by mock_progress_factory if needed
    # For now, returning the class mock might suffice if static methods were mocked
    return {"progress_dialog_class": wx.ProgressDialog, "discussion_dialog": discussion_dialog_mock}


def test_discussion_fetched_asynchronously(
    wx_app, frame, mock_api_client, mock_location_manager, event_queue, mock_dialogs
):
    """Test discussion fetch and UI update via wx.CallAfter."""
    app = WeatherApp(
        frame,
        location_manager=mock_location_manager,
        api_client=mock_api_client,
        notifier=MagicMock(),
    )
    app.discussion_btn = MagicMock()  # Mock the button
    event = MagicMock()  # Mock the event object for the handler

    # Configure API mock response for this specific test
    expected_discussion = "Async discussion success!"
    mock_api_client.get_discussion.return_value = expected_discussion

    # Event to signal completion of the callback via wx.CallAfter
    callback_finished_event = threading.Event()

    # --- Patch the callback method on the app instance ---
    # Get the original bound method from the instance
    # Ensure the method exists before trying to access it
    assert hasattr(app, "_on_discussion_fetched"), "No _on_discussion_fetched"
    original_success_callback = app._on_discussion_fetched

    # Define the wrapper function with the correct signature
    def wrapper_on_success(discussion_text, name, loading_dialog):
        # Call the original callback logic first
        original_success_callback(discussion_text, name, loading_dialog)
        # Signal that the callback has completed
        callback_finished_event.set()

    processed_event = False
    # Use patch.object as a context manager with the CORRECT method name
    with patch.object(app, "_on_discussion_fetched", new=wrapper_on_success):
        # Call the method that triggers fetching
        app.OnViewDiscussion(event)

        # --- Wait for the callback to execute via wx event loop ---
        start_time = time.time()
        timeout = 10  # seconds
        while time.time() - start_time < timeout:
            # Wait briefly for the event, non-blocking
            if callback_finished_event.wait(timeout=0.01):
                processed_event = True
                break
            # Allow wxPython event loop to process pending CallAfter events
            wx.YieldIfNeeded()
            # time.sleep(0.01) # Optional small sleep

    assert processed_event, "Callback did not finish within the timeout."
    # ---------------------------------------------------------

    # Verify the API call was made correctly (in the background thread)
    mock_api_client.get_discussion.assert_called_once_with(35.0, -80.0)

    # Verify dialog creation was triggered (via callback on main thread)
    dialog_event = None
    try:
        # Should be there now
        dialog_event = event_queue.get(block=False)
    except queue.Empty:
        pass

    assert dialog_event is not None, "Dialog event not found in queue after callback"
    assert dialog_event[0] == "dialog_shown", f"Expected 'dialog_shown', got {dialog_event[0]}"
    assert (
        dialog_event[1] == expected_discussion
    ), f"Expected '{expected_discussion}', got {dialog_event[1]}"

    # Check that button was re-enabled (in the callback)
    app.discussion_btn.Enable.assert_called_once()

    # patch.object context manager handles cleanup automatically


def test_discussion_error_handling(
    wx_app, frame, mock_api_client, mock_location_manager, event_queue, mock_dialogs
):
    """Test discussion fetch error handling via wx.CallAfter."""
    app = WeatherApp(
        frame,
        location_manager=mock_location_manager,
        api_client=mock_api_client,
        notifier=MagicMock(),
    )
    app.discussion_btn = MagicMock()
    event = MagicMock()

    # Configure API mock to raise an error
    error_message = "Network error fetching discussion"
    mock_api_client.get_discussion.side_effect = ApiClientError(error_message)

    # Event to signal completion of the error callback
    callback_finished_event = threading.Event()

    # --- Patch the error callback method on the app instance ---
    # Get the original bound method from the instance
    # Ensure the method exists before trying to access it
    assert hasattr(app, "_on_discussion_error"), "Missing _on_discussion_error"
    original_error_callback = app._on_discussion_error

    # Define the wrapper function with the correct signature
    def wrapper_on_error(error, name, loading_dialog):
        # Call the original callback logic first
        original_error_callback(error, name, loading_dialog)
        # Signal that the callback has completed
        callback_finished_event.set()

    processed_event = False
    # Use patch.object as a context manager with the CORRECT method name
    with patch.object(app, "_on_discussion_error", new=wrapper_on_error):
        # Call the method that triggers fetching
        app.OnViewDiscussion(event)

        # --- Wait for the callback to execute via wx event loop ---
        start_time = time.time()
        timeout = 10  # seconds
        while time.time() - start_time < timeout:
            if callback_finished_event.wait(timeout=0.01):
                processed_event = True
                break
            wx.YieldIfNeeded()
            # time.sleep(0.01)

    assert processed_event, "Error callback did not finish within the timeout."
    # ---------------------------------------------------------

    # Verify the API call was made
    mock_api_client.get_discussion.assert_called_once_with(35.0, -80.0)

    # Verify error message was shown via event queue (triggered by callback)
    error_event = None
    try:
        error_event = event_queue.get(block=False)
    except queue.Empty:
        pass

    assert error_event is not None, "Error event not found in queue after callback"
    assert error_event[0] == "error_shown", f"Expected 'error_shown', got {error_event[0]}"
    # Check if the original error message is part of the displayed message
    assert error_message in error_event[1], f"Expected '{error_message}' in '{error_event[1]}'"

    # Check that button was re-enabled (in the error callback)
    app.discussion_btn.Enable.assert_called_once()

    # patch.object context manager handles cleanup automatically
