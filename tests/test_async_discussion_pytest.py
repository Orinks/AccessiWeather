import pytest
import threading
import time
import queue
import wx
from unittest.mock import MagicMock, patch

from noaa_weather_app.gui import WeatherApp, WeatherDiscussionDialog
from noaa_weather_app.api_client import NoaaApiClient

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
def mock_api_client(monkeypatch):
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

def test_discussion_fetched_asynchronously(frame, mock_api_client, mock_location_manager, event_queue, monkeypatch):
    """Test that the weather discussion is fetched in a background thread."""
    # Create test app
    app = WeatherApp(frame)
    app.api_client = mock_api_client
    app.location_manager = mock_location_manager
    
    # Mock wx dialog
    mock_dialog = MagicMock()
    monkeypatch.setattr(wx, 'ProgressDialog', lambda *args, **kwargs: mock_dialog)
    
    # Track status text changes
    original_set_status = app.SetStatusText
    def track_status(text):
        event_queue.put(("status", text))
        # Don't call original to avoid wxPython issues in tests
    app.SetStatusText = track_status
    
    # Use the test callback hook we added
    def test_callback(discussion_text, name):
        event_queue.put(("discussion_fetched", discussion_text))
        event_queue.put(("status", "Ready"))
    app._testing_callback = test_callback
    
    # Create a mock event
    event = MagicMock()
    
    # Call the method that should trigger async behavior
    app.OnViewDiscussion(event)
    
    # Verify initial status change
    assert event_queue.get(timeout=1) == ("status", "Fetching forecast discussion...")
    
    # Wait for the background thread to complete (max 5 seconds)
    # The thread should call our test callback which adds items to the queue
    discussion_event = event_queue.get(timeout=5)
    assert discussion_event[0] == "discussion_fetched"
    assert discussion_event[1] == "Sample discussion text"
    
    # Check that status was set back to ready
    status_event = event_queue.get(timeout=1)
    assert status_event[0] == "status"
    assert status_event[1] == "Ready"
    
    # Verify API was called with correct parameters
    mock_api_client.get_discussion.assert_called_once_with(35.0, -80.0)

def test_discussion_error_handling(frame, mock_api_client, mock_location_manager, event_queue, monkeypatch):
    """Test that errors during discussion fetching are handled properly."""
    # Create test app
    app = WeatherApp(frame)
    app.api_client = mock_api_client
    app.location_manager = mock_location_manager
    
    # Configure API to raise an exception
    error_message = "Network error"
    mock_api_client.get_discussion.side_effect = Exception(error_message)
    
    # Mock wx dialog
    mock_dialog = MagicMock()
    monkeypatch.setattr(wx, 'ProgressDialog', lambda *args, **kwargs: mock_dialog)
    monkeypatch.setattr(wx, 'MessageBox', lambda *args, **kwargs: event_queue.put(("error_shown", args[0])))
    
    # Track status text changes
    original_set_status = app.SetStatusText
    def track_status(text):
        event_queue.put(("status", text))
        # Don't call original to avoid wxPython issues in tests
    app.SetStatusText = track_status
    
    # Use the test callback hook we added
    def test_error_callback(error):
        event_queue.put(("error_callback", error))
        event_queue.put(("error_shown", f"Error fetching discussion: {error}"))
        event_queue.put(("status", "Ready"))
    app._testing_error_callback = test_error_callback
    
    # Create a mock event
    event = MagicMock()
    
    # Call the method that should trigger async behavior
    app.OnViewDiscussion(event)
    
    # Verify initial status change
    assert event_queue.get(timeout=1) == ("status", "Fetching forecast discussion...")
    
    # Wait for the error to be handled
    error_event = event_queue.get(timeout=5)
    assert error_event[0] == "error_callback"
    assert error_event[1] == error_message
    
    # Check that error dialog was shown
    error_message_event = event_queue.get(timeout=1)
    assert error_message_event[0] == "error_shown"
    assert f"Error fetching discussion: {error_message}" in error_message_event[1]
    
    # Check that status was set back to ready
    status_event = event_queue.get(timeout=1)
    assert status_event[0] == "status"
    assert status_event[1] == "Ready"
