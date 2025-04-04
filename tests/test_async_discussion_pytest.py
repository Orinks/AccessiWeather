"""Tests for asynchronous discussion fetching."""

import queue
import threading
import time
from unittest.mock import MagicMock

import pytest
import wx

from accessiweather.api_client import ApiClientError, NoaaApiClient
from accessiweather.gui.async_fetchers import DiscussionFetcher
from accessiweather.gui.dialogs import WeatherDiscussionDialog


@pytest.fixture
def wx_app():
    """Create a wx App for testing."""
    app = wx.App(False)  # Redirect stdout/stderr if needed
    yield app
    # Destroy the app directly during teardown
    app.Destroy()


@pytest.fixture
def frame(wx_app):
    """Create a frame for testing."""
    frame = wx.Frame(None)
    yield frame
    frame.Destroy()


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    mock_client = MagicMock(spec=NoaaApiClient)
    # Configure default return value, can be overridden in tests
    mock_client.get_discussion.return_value = "Sample discussion text"
    return mock_client


@pytest.fixture
def mock_location_manager():
    """Create a mock location manager."""
    manager = MagicMock()
    manager.get_current_location.return_value = ("Test Location", 35.0, -80.0)
    return manager


@pytest.fixture
def event_queue():
    """Create an event queue for testing."""
    return queue.Queue()


@pytest.fixture
def mock_dialogs(monkeypatch, event_queue):
    """Create mock dialogs for testing."""
    # Mock ProgressDialog - Keep as is, seems fine
    progress_dialog_mock = MagicMock()
    progress_dialog_mock.Pulse.return_value = None
    progress_dialog_mock.Destroy.return_value = None
    monkeypatch.setattr(wx, "ProgressDialog", lambda *args, **kwargs: progress_dialog_mock)

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

    # Patch __init__; this covers ShowModal/Destroy for instances created
    # via this mock init.
    monkeypatch.setattr(WeatherDiscussionDialog, "__init__", mock_discussion_dialog_init)

    return {
        "progress_dialog": progress_dialog_mock,
        "discussion_dialog": discussion_dialog_mock,
    }


def test_discussion_fetch_success(
    wx_app, frame, mock_api_client, mock_location_manager  # Inject fixtures
):
    """Test successful discussion fetch."""
    # Fixtures are now injected, no 'with' needed
    mock_client = mock_api_client  # Use injected fixture
    mock_location = mock_location_manager  # Use injected fixture
    # Configure API mock response for this specific test
    expected_discussion = "Async discussion success!"
    mock_client.get_discussion.return_value = expected_discussion

    # Create the DiscussionFetcher instance instead of WeatherApp
    fetcher = DiscussionFetcher(
        api_client=mock_client,
    )
    # Mock attributes previously set by WeatherApp or needed by callbacks
    fetcher.parent = frame  # Needed for dialogs potentially
    fetcher.discussion_btn = MagicMock()  # Mock the button
    fetcher.location_manager = mock_location  # Needed by OnViewDiscussion
    # fetcher.discussion_btn = MagicMock()  # Mock the button (moved up)

    # Event to signal completion of the callback via wx.CallAfter
    callback_finished_event = threading.Event()

    # --- Patch the callback method on the fetcher instance ---
    # We need to mock the callback methods as they are no longer part of the
    # fetcher itself but would be passed during 'fetch' call in real app
    fetcher._on_discussion_fetched = MagicMock()
    fetcher._on_discussion_error = MagicMock()
    # Wrap the mocked callback to set the event
    original_success_callback = fetcher._on_discussion_fetched

    def wrapper_on_success(*args, **kwargs):
        # Simulate the callback receiving (result, location_name)
        original_success_callback(*args, **kwargs)
        callback_finished_event.set()

    fetcher._on_discussion_fetched = wrapper_on_success

    # Call the actual fetch method
    name, lat, lon = mock_location.get_current_location()
    fetcher.fetch(
        lat=lat,
        lon=lon,
        on_success=wrapper_on_success,  # Pass the wrapped mock
        on_error=fetcher._on_discussion_error,  # Pass the other mock
        additional_data=(name,),  # Pass location name
    )
    start_time = time.time()
    timeout = 10  # seconds
    processed_event = False
    while time.time() - start_time < timeout:
        if callback_finished_event.wait(timeout=0.01):
            processed_event = True
            break
        wx.YieldIfNeeded()
    assert processed_event, "Callback did not finish within the timeout."

    mock_client.get_discussion.assert_called_once_with(35.0, -80.0)
    # Button enable logic might be in callback now
    # fetcher.discussion_btn.Enable.assert_called_once()
    # Verify the mocked callback was called
    original_success_callback.assert_called_once_with(expected_discussion, "Test Location")


def test_discussion_fetch_error(
    wx_app, frame, mock_api_client, mock_location_manager  # Inject fixtures
):
    """Test discussion fetch error handling."""
    # Fixtures are now injected, no 'with' needed
    mock_client = mock_api_client  # Use injected fixture
    # Configure API mock to raise an error
    error_message = "Network error fetching discussion"
    mock_client.get_discussion.side_effect = ApiClientError(error_message)
    mock_location = mock_location_manager  # Use injected fixture

    fetcher = DiscussionFetcher(
        api_client=mock_client,
    )
    # Mock attributes previously set by WeatherApp or needed by callbacks
    fetcher.parent = frame
    fetcher.discussion_btn = MagicMock()
    fetcher.location_manager = mock_location
    # fetcher.discussion_btn = MagicMock() # Moved up

    callback_finished_event = threading.Event()

    # Mock the callback methods
    fetcher._on_discussion_fetched = MagicMock()
    fetcher._on_discussion_error = MagicMock()

    # Wrap the mocked error callback

    original_error_callback = fetcher._on_discussion_error

    def wrapper_on_error(*args, **kwargs):
        # Simulate the callback receiving (error_msg, location_name)
        original_error_callback(*args, **kwargs)
        callback_finished_event.set()

    fetcher._on_discussion_error = wrapper_on_error  # Keep the mock wrapper

    # Call the actual fetch method
    name, lat, lon = mock_location.get_current_location()
    fetcher.fetch(
        lat=lat,
        lon=lon,
        on_success=fetcher._on_discussion_fetched,  # Pass the other mock
        on_error=wrapper_on_error,  # Pass the wrapped mock
        additional_data=(name,),  # Pass location name
    )
    start_time = time.time()
    timeout = 10  # seconds
    processed_event = False
    while time.time() - start_time < timeout:
        if callback_finished_event.wait(timeout=0.01):
            processed_event = True
            break
        wx.YieldIfNeeded()
    assert processed_event, "Error callback did not finish within the timeout."

    mock_client.get_discussion.assert_called_once_with(35.0, -80.0)
    # Button enable logic might be in callback now
    # fetcher.discussion_btn.Enable.assert_called_once()
    # Verify the mocked error callback was called
    expected_err_msg = f"Unable to retrieve forecast discussion: {error_message}"
    original_error_callback.assert_called_once_with(expected_err_msg, "Test Location")


def test_discussion_fetch_cancel(
    wx_app, frame, mock_api_client, mock_location_manager  # Inject fixtures
):
    """Test discussion fetch cancellation."""
    # Fixtures are now injected, no 'with' needed
    mock_client = mock_api_client  # Use injected fixture
    # For cancellation, ensure API client doesn't return valid discussion
    # (though it shouldn't be called anyway)
    mock_client.get_discussion.return_value = "Should not appear"
    mock_location = mock_location_manager  # Use injected fixture

    fetcher = DiscussionFetcher(
        api_client=mock_client,
    )
    # Mock attributes previously set by WeatherApp or needed by callbacks
    fetcher.parent = frame
    fetcher.discussion_btn = MagicMock()  # Mock button needed for fetcher init
    fetcher.location_manager = mock_location  # Needed by fetcher logic

    # Mock callbacks that should NOT be called
    mock_on_success = MagicMock()
    mock_on_error = MagicMock()

    # Call the actual fetch method to start the thread
    name, lat, lon = mock_location.get_current_location()
    fetcher.fetch(
        lat=lat, lon=lon, on_success=mock_on_success, on_error=mock_on_error, additional_data=None
    )

    # Simulate cancellation by setting the stop event *immediately* after
    # fetch is called, aiming to stop it before the API call in the thread.
    fetcher._stop_event.set()

    # Give the thread a brief moment to potentially start and check the event
    time.sleep(0.1)  # Small delay

    # Assertions
    # Core check: Ensure callbacks were not invoked due to cancellation
    # Success callback shouldn't run
    mock_on_success.assert_not_called()
    # Error callback shouldn't run
    mock_on_error.assert_not_called()
    # Button enabling is likely tied to callbacks, so it shouldn't be called
    # either.
    # fetcher.discussion_btn.Enable.assert_not_called()
    # Optional: Verify button state wasn't changed if needed
