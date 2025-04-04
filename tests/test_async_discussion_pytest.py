"""Tests for asynchronous discussion fetching."""

import queue
import threading
import time
from unittest.mock import MagicMock, patch

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
    # Allow pending events to process before destroying
    # Sometimes needed, especially on slower systems or complex tests
    for _ in range(5):  # Process pending events a few times
        wx.YieldIfNeeded()
        time.sleep(0.01)
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


def test_discussion_fetch_success(wx_app):
    """Test successful discussion fetch."""
    # Create a frame using the fixture
    with frame(wx_app) as frm:
        # Set up mocks using fixtures
        mock_client = mock_api_client()
        mock_location = mock_location_manager()
        # Configure API mock response for this specific test
        expected_discussion = "Async discussion success!"
        mock_client.get_discussion.return_value = expected_discussion

        # Create the DiscussionFetcher instance instead of WeatherApp
        fetcher = DiscussionFetcher(
            frm,
            location_manager=mock_location,
            api_client=mock_client,
            notifier=MagicMock(),
        )
        fetcher.discussion_btn = MagicMock()  # Mock the button

        # Event to signal completion of the callback via wx.CallAfter
        callback_finished_event = threading.Event()

        # --- Patch the callback method on the fetcher instance ---
        assert hasattr(fetcher, "_on_discussion_fetched"), "No _on_discussion_fetched"
        original_success_callback = fetcher._on_discussion_fetched

        def wrapper_on_success(discussion_text, name, loading_dialog):
            original_success_callback(discussion_text, name, loading_dialog)
            callback_finished_event.set()

        with patch.object(fetcher, "_on_discussion_fetched", new=wrapper_on_success):
            fetcher.OnViewDiscussion(None)
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
        fetcher.discussion_btn.Enable.assert_called_once()


def test_discussion_fetch_error(wx_app):
    """Test discussion fetch error handling."""
    with frame(wx_app) as frm:
        mock_client = mock_api_client()
        # Configure API mock to raise an error
        error_message = "Network error fetching discussion"
        mock_client.get_discussion.side_effect = ApiClientError(error_message)
        mock_location = mock_location_manager()

        fetcher = DiscussionFetcher(
            frm,
            location_manager=mock_location,
            api_client=mock_client,
            notifier=MagicMock(),
        )
        fetcher.discussion_btn = MagicMock()

        callback_finished_event = threading.Event()

        assert hasattr(fetcher, "_on_discussion_error"), "Missing _on_discussion_error"
        original_error_callback = fetcher._on_discussion_error

        def wrapper_on_error(error, name, loading_dialog):
            original_error_callback(error, name, loading_dialog)
            callback_finished_event.set()

        with patch.object(fetcher, "_on_discussion_error", new=wrapper_on_error):
            fetcher.OnViewDiscussion(None)
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
        fetcher.discussion_btn.Enable.assert_called_once()


def test_discussion_fetch_cancel(wx_app):
    """Test discussion fetch cancellation."""
    with frame(wx_app) as frm:
        mock_client = mock_api_client()
        # For cancellation, ensure that the API client does not return any valid discussion text
        mock_client.get_discussion.return_value = "Should not appear"
        mock_location = mock_location_manager()

        fetcher = DiscussionFetcher(
            frm,
            location_manager=mock_location,
            api_client=mock_client,
            notifier=MagicMock(),
        )
        fetcher.discussion_btn = MagicMock()

        # Simulate cancellation by invoking a cancellation mechanism if available.
        if hasattr(fetcher, "cancel"):
            fetcher.cancel()

        # Trigger the discussion fetch; cancellation should prevent any API call.
        fetcher.OnViewDiscussion(None)

        mock_client.get_discussion.assert_not_called()
        fetcher.discussion_btn.Enable.assert_called_once()
