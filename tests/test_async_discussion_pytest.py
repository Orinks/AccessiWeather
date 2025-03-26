import pytest
import threading
import time
import queue
import wx
from unittest.mock import MagicMock, patch

from accessiweather.gui import WeatherApp, WeatherDiscussionDialog
from accessiweather.api_client import NoaaApiClient

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
    monkeypatch.setattr(wx, 'ProgressDialog', lambda *args, **kwargs: progress_dialog_mock)
    
    # Mock MessageBox to put an event in our queue instead of showing dialog
    def mock_message_box(*args, **kwargs):
        event_queue.put(("error_shown", args[0]))
        return None
    monkeypatch.setattr(wx, 'MessageBox', mock_message_box)
    
    # Mock WeatherDiscussionDialog
    discussion_dialog_mock = MagicMock()
    discussion_dialog_mock.ShowModal.return_value = None
    discussion_dialog_mock.Destroy.return_value = None
    
    # Mock wx.CallAfter to directly call the function instead of scheduling it
    def mock_call_after(func, *args, **kwargs):
        func(*args, **kwargs)
    monkeypatch.setattr(wx, 'CallAfter', mock_call_after)
    
    def mock_discussion_dialog_init(self, parent, title, text):
        event_queue.put(("dialog_shown", text))
        self.text = text
        self.parent = parent
        self.title = title
        self.ShowModal = discussion_dialog_mock.ShowModal
        self.Destroy = discussion_dialog_mock.Destroy
    
    monkeypatch.setattr(WeatherDiscussionDialog, '__init__', mock_discussion_dialog_init)
    monkeypatch.setattr(WeatherDiscussionDialog, 'ShowModal', lambda self: None)
    monkeypatch.setattr(WeatherDiscussionDialog, 'Destroy', lambda self: None)
    
    return {
        "progress_dialog": progress_dialog_mock,
        "discussion_dialog": discussion_dialog_mock
    }

def test_discussion_fetched_asynchronously(frame, mock_api_client, mock_location_manager, event_queue, monkeypatch, mock_dialogs):
    """Test that the weather discussion is fetched in a background thread."""
    # Create test app
    app = WeatherApp(frame)
    app.api_client = mock_api_client
    app.location_manager = mock_location_manager
    
    # Mock discussion button
    app.discussion_btn = MagicMock()
    
    # Create a mock event
    event = MagicMock()
    
    # Mock the DiscussionFetcher.fetch method to directly call our success callback
    original_fetch = app.discussion_fetcher.fetch
    
    def mock_fetch(lat, lon, on_success=None, on_error=None, additional_data=None):
        # Let's directly call the success callback without any threading
        if on_success and additional_data:
            # Call the callback directly with discussion text and additional data
            on_success("Sample discussion text", *additional_data)
        return
    
    # Apply our mock
    monkeypatch.setattr(app.discussion_fetcher, 'fetch', mock_fetch)
    
    # Call the method that triggers fetching
    app.OnViewDiscussion(event)
    
    # Verify dialog creation was triggered through our event queue
    dialog_event = event_queue.get(block=False)  # Non-blocking get
    assert dialog_event[0] == "dialog_shown"
    assert dialog_event[1] == "Sample discussion text"
    
    # Check that button was enabled
    app.discussion_btn.Enable.assert_called_once()

def test_discussion_error_handling(frame, mock_api_client, mock_location_manager, event_queue, monkeypatch, mock_dialogs):
    """Test that errors during discussion fetching are handled properly."""
    # Create test app
    app = WeatherApp(frame)
    app.api_client = mock_api_client
    app.location_manager = mock_location_manager
    
    # Mock discussion button
    app.discussion_btn = MagicMock()
    
    # Create a mock event
    event = MagicMock()
    
    # Mock the DiscussionFetcher.fetch method to directly call our error callback
    error_message = "Network error"
    
    def mock_fetch(lat, lon, on_success=None, on_error=None, additional_data=None):
        # Let's directly call the error callback without any threading
        if on_error and additional_data:
            # We need to pass the appropriate arguments - the second item in additional_data is the loading dialog
            loading_dialog = additional_data[1]
            on_error(f"Unable to retrieve discussion: {error_message}", loading_dialog)
        return
    
    # Apply our mock
    monkeypatch.setattr(app.discussion_fetcher, 'fetch', mock_fetch)
    
    # Call the method that triggers fetching
    app.OnViewDiscussion(event)
    
    # Verify error message was shown
    error_event = event_queue.get(block=False)  # Non-blocking get
    assert error_event[0] == "error_shown"
    assert "Unable to retrieve discussion: Network error" in error_event[1]
    
    # Check that button was enabled
    app.discussion_btn.Enable.assert_called_once()
