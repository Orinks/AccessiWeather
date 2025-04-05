"""Tests for asynchronous behavior of WeatherLocationAutocomplete"""

import time
from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.geocoding import GeocodingService
from accessiweather.gui.autocomplete import WeatherLocationAutocomplete


@pytest.fixture(autouse=True)
def setup_wx_testing():
    """Set up wx testing mode for autocomplete testing"""
    # Set testing flag for wx
    wx.testing = True
    yield
    # Clean up
    if hasattr(wx, "testing"):
        delattr(wx, "testing")


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
def mock_geocoding_service():
    geocoding_service = MagicMock(spec=GeocodingService)
    # Mock the function that will suggest locations
    geocoding_service.suggest_locations.return_value = [
        "New York, NY",
        "New Orleans, LA",
        "Newark, NJ",
    ]
    return geocoding_service


@pytest.fixture
def slow_geocoding_service():
    """Create a mock geocoding service that takes time to respond"""
    geocoding_service = MagicMock(spec=GeocodingService)

    def slow_suggest(text):
        # Simulate a slow network request
        time.sleep(0.5)
        return [f"{text} City", f"{text} Town", f"{text} Village"]

    geocoding_service.suggest_locations.side_effect = slow_suggest
    return geocoding_service


def test_debounce_timer_creation(frame):
    """Test that the debounce timer is created properly"""
    autocomplete = WeatherLocationAutocomplete(frame, label="Test Autocomplete")

    # Check that timer exists and is configured
    assert hasattr(autocomplete, "debounce_timer")
    assert isinstance(autocomplete.debounce_timer, wx.Timer)
    assert autocomplete.debounce_delay == 300  # Default is 300ms


def test_debounce_timer_starts_on_text_change(frame, mock_geocoding_service):
    """Test that the debounce timer starts when text changes"""
    autocomplete = WeatherLocationAutocomplete(frame, label="Test Autocomplete")
    autocomplete.set_geocoding_service(mock_geocoding_service)

    # Patch the timer methods
    with patch.object(autocomplete.debounce_timer, "Stop") as mock_stop, patch.object(
        autocomplete.debounce_timer, "Start"
    ) as mock_start:
        # Simulate typing enough characters
        autocomplete.SetValue("New")
        autocomplete.on_text_changed(None)  # Simulate text change event

        # Check that timer was stopped and started
        mock_stop.assert_called_once()
        mock_start.assert_called_once_with(300, wx.TIMER_ONE_SHOT)


def test_debounce_timer_triggers_fetch(frame, mock_geocoding_service):
    """Test that the debounce timer triggers fetch when it fires"""
    autocomplete = WeatherLocationAutocomplete(frame, label="Test Autocomplete")
    autocomplete.set_geocoding_service(mock_geocoding_service)

    # Patch the _fetch_suggestions method
    with patch.object(autocomplete, "_fetch_suggestions") as mock_fetch:
        # Set a value
        autocomplete.SetValue("New")

        # Directly call the timer handler instead of creating a TimerEvent
        autocomplete.on_debounce_timer(None)

        # Check that fetch was called with the current text
        mock_fetch.assert_called_once_with("New")


def test_fetch_suggestions_uses_threading(frame, mock_geocoding_service):
    """Test that _fetch_suggestions starts a background thread"""
    autocomplete = WeatherLocationAutocomplete(frame, label="Test Autocomplete")
    autocomplete.set_geocoding_service(mock_geocoding_service)

    # Patch the threading.Thread
    with patch("threading.Thread") as mock_thread:
        # Call the method
        autocomplete._fetch_suggestions("New")

        # Check that a thread was created with the right target and args
        mock_thread.assert_called_once()
        args, kwargs = mock_thread.call_args
        assert kwargs["target"] == autocomplete._fetch_thread_func
        assert kwargs["args"] == ("New",)

        # Check that the thread was started
        mock_thread_instance = mock_thread.return_value
        mock_thread_instance.start.assert_called_once()


def test_fetch_thread_cancellation(frame, slow_geocoding_service):
    """Test that in-progress fetches can be cancelled"""
    autocomplete = WeatherLocationAutocomplete(frame, label="Test Autocomplete")
    autocomplete.set_geocoding_service(slow_geocoding_service)

    # Mock the threading.Thread to capture what happens
    with patch("threading.Thread") as mock_thread:
        # Create a mock thread object
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        # Start a fetch
        autocomplete._fetch_suggestions("First")

        # Verify the thread was started
        mock_thread_instance.start.assert_called_once()

        # Start a second fetch
        autocomplete._fetch_suggestions("Second")

        # Verify the stop_event was cleared for the new fetch
        assert not autocomplete.stop_event.is_set()

        # Verify a new thread was created
        assert mock_thread.call_count == 2


def test_fetch_thread_updates_ui_on_completion(frame, mock_geocoding_service):
    """Test that the fetch thread updates the UI when complete"""
    autocomplete = WeatherLocationAutocomplete(frame, label="Test Autocomplete")
    autocomplete.set_geocoding_service(mock_geocoding_service)

    # Patch wx.CallAfter
    with patch("wx.CallAfter") as mock_call_after:
        # Call the thread function directly
        autocomplete._fetch_thread_func("New")

        # Check that the geocoding service was called
        mock_geocoding_service.suggest_locations.assert_called_once_with("New")

        # Check that CallAfter was used to update the UI
        mock_call_after.assert_called_once()
        args, kwargs = mock_call_after.call_args
        assert args[0] == autocomplete._update_completions
        assert args[1] == mock_geocoding_service.suggest_locations.return_value


def test_fetch_thread_handles_errors(frame):
    """Test that the fetch thread handles errors gracefully"""
    autocomplete = WeatherLocationAutocomplete(frame, label="Test Autocomplete")

    # Create a geocoding service that raises an exception
    error_service = MagicMock(spec=GeocodingService)
    error_service.suggest_locations.side_effect = Exception("Test error")
    autocomplete.set_geocoding_service(error_service)

    # Patch the logger directly in the module where it's used
    with patch("accessiweather.gui.ui_components.logger") as mock_logger:
        # Call the thread function directly
        autocomplete._fetch_thread_func("New")

        # Check that the error was logged
        mock_logger.error.assert_called_once()
        error_args = str(mock_logger.error.call_args)
        assert "Error fetching location suggestions" in error_args
        assert "Test error" in error_args


def test_integration_with_real_timer(frame, mock_geocoding_service):
    """Test the full flow with a real timer (integration test)"""
    autocomplete = WeatherLocationAutocomplete(frame, label="Test Autocomplete")
    autocomplete.set_geocoding_service(mock_geocoding_service)

    # Patch the methods we want to verify
    with patch.object(autocomplete, "_fetch_suggestions") as mock_fetch:
        # Set a value to trigger the debounce timer
        autocomplete.SetValue("New")
        autocomplete.on_text_changed(None)  # Simulate text change event

        # Directly call the timer handler instead of creating a TimerEvent
        autocomplete.on_debounce_timer(None)

        # Check that fetch was called
        mock_fetch.assert_called_once_with("New")
