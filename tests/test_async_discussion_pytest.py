import pytest
import threading
# import time # Unused
import queue
import wx
from unittest.mock import MagicMock  # Removed unused patch and ANY

from accessiweather.gui.weather_app import WeatherApp
from accessiweather.gui.dialogs import WeatherDiscussionDialog
from accessiweather.api_client import NoaaApiClient, ApiClientError


@pytest.fixture
def wx_app():
    app = wx.App()
    yield app
    app.Destroy()


@pytest.fixture
def frame(wx_app):
    frame = wx.Frame(None)
    yield frame
    frame.Destroy()


@pytest.fixture
def mock_api_client():
    mock_client = MagicMock(spec=NoaaApiClient)
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
    # Mock ProgressDialog
    progress_dialog_mock = MagicMock()
    progress_dialog_mock.Pulse.return_value = None
    progress_dialog_mock.Destroy.return_value = None
    monkeypatch.setattr(
        wx, 'ProgressDialog', 
        lambda *args, **kwargs: progress_dialog_mock
    )
    
    # Mock MessageBox to put an event in our queue instead of showing dialog
    def mock_message_box(*args, **kwargs):
        event_queue.put(("error_shown", args[0]))
        return None
    monkeypatch.setattr(wx, 'MessageBox', mock_message_box)
    
    # Mock WeatherDiscussionDialog
    discussion_dialog_mock = MagicMock()
    discussion_dialog_mock.ShowModal.return_value = None
    discussion_dialog_mock.Destroy.return_value = None
    
    def mock_discussion_dialog_init(self, parent, title, text):
        event_queue.put(("dialog_shown", text))
        self.text = text
        self.parent = parent
        self.title = title
        self.ShowModal = discussion_dialog_mock.ShowModal
        self.Destroy = discussion_dialog_mock.Destroy
    
    monkeypatch.setattr(
        WeatherDiscussionDialog, 
        '__init__', 
        mock_discussion_dialog_init
    )
    monkeypatch.setattr(
        WeatherDiscussionDialog, 
        'ShowModal', 
        lambda self: None
    )
    monkeypatch.setattr(
        WeatherDiscussionDialog, 
        'Destroy', 
        lambda self: None
    )
    
    # We want wx.CallAfter to run normally in the main thread now
    
    return {
        "progress_dialog": progress_dialog_mock,
        "discussion_dialog": discussion_dialog_mock
    }


def test_discussion_fetched_asynchronously(
    frame, mock_api_client, mock_location_manager, event_queue, 
    monkeypatch, mock_dialogs
):
    """Test that the weather discussion is fetched in a background thread."""
    # Create test app
    app = WeatherApp(
        frame, 
        location_manager=mock_location_manager, 
        api_client=mock_api_client, 
        notifier=MagicMock()
    )
    
    # Mock discussion button
    app.discussion_btn = MagicMock()
    
    # Create a mock event
    event = MagicMock()
    
    # Ensure the mock API client returns the expected data
    mock_api_client.get_discussion.return_value = "Sample discussion text"

    # Event to signal completion of the callback
    callback_finished = threading.Event()

    # Add a test hook to the app
    app._testing_discussion_callback = lambda *args: callback_finished.set()

    # Mock safe_call_after to directly execute callbacks
    def mock_safe_call_after(callback, *args, **kwargs):
        """Directly execute the callback without wx.CallAfter"""
        callback(*args, **kwargs)
    
    monkeypatch.setattr(
        'accessiweather.gui.async_fetchers.safe_call_after',
        mock_safe_call_after
    )
    
    # Call the method that triggers fetching
    app.OnViewDiscussion(event)
    
    # Wait for the callback to finish (with a timeout)
    assert callback_finished.wait(timeout=10), (
        "Callback did not finish in time"
    )

    # Verify the API call was made
    mock_api_client.get_discussion.assert_called_once_with(35.0, -80.0)

    # Verify dialog creation was triggered through our event queue
    dialog_event = None
    try:
        # Use timeout to avoid hanging if event never arrives
        dialog_event = event_queue.get(block=True, timeout=1)
    except queue.Empty:
        pass  # dialog_event remains None

    assert dialog_event is not None, "Dialog event not found in queue"
    assert dialog_event[0] == "dialog_shown", (
        f"Expected 'dialog_shown', got {dialog_event[0]}"
    )
    assert dialog_event[1] == "Sample discussion text", (
        f"Expected 'Sample discussion text', got {dialog_event[1]}"
    )

    # Check that button was enabled
    app.discussion_btn.Enable.assert_called_once()


def test_discussion_error_handling(
    frame, mock_api_client, mock_location_manager, event_queue, 
    monkeypatch, mock_dialogs
):
    """Test that errors during discussion fetching are handled properly."""
    # Create test app
    app = WeatherApp(
        frame, 
        location_manager=mock_location_manager, 
        api_client=mock_api_client, 
        notifier=MagicMock()
    )
    
    # Mock discussion button
    app.discussion_btn = MagicMock()
    
    # Create a mock event
    event = MagicMock()
    
    # Mock the API client to raise an error
    error_message = "Network error fetching discussion"
    mock_api_client.get_discussion.side_effect = ApiClientError(error_message)

    # Event to signal completion of the callback
    callback_finished = threading.Event()

    # Add a test hook to the app
    app._testing_discussion_error_callback = lambda *args: \
        callback_finished.set()

    # Mock safe_call_after to directly execute callbacks
    def mock_safe_call_after(callback, *args, **kwargs):
        """Directly execute the callback without wx.CallAfter"""
        callback(*args, **kwargs)
    
    monkeypatch.setattr(
        'accessiweather.gui.async_fetchers.safe_call_after',
        mock_safe_call_after
    )
    
    # Call the method that triggers fetching
    app.OnViewDiscussion(event)
    
    # Wait for the callback to finish (with a timeout)
    assert callback_finished.wait(timeout=10), (
        "Callback did not finish in time"
    )

    # Verify the API call was made
    mock_api_client.get_discussion.assert_called_once_with(35.0, -80.0)

    # Verify error message was shown via the event queue
    error_event = None
    try:
        # Use timeout to avoid hanging if event never arrives
        error_event = event_queue.get(block=True, timeout=1)
    except queue.Empty:
        pass  # error_event remains None

    assert error_event is not None, "Error event not found in queue"
    assert error_event[0] == "error_shown", (
        f"Expected 'error_shown', got {error_event[0]}"
    )
    # The error callback prepends text, so check if our original message
    # is included
    assert error_message in error_event[1], (
        f"Expected '{error_message}' in '{error_event[1]}'"
    )
    
    # Check that button was enabled
    app.discussion_btn.Enable.assert_called_once()
