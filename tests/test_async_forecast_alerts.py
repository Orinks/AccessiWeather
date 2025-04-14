# Import faulthandler setup first to enable faulthandler
import tests.faulthandler_setup

import queue
from unittest.mock import MagicMock, patch

import pytest
import wx  # type: ignore

from accessiweather.api_client import ApiClientError, NoaaApiClient
from accessiweather.gui.weather_app import WeatherApp

# Import our test utilities
from tests.wx_test_utils import AsyncEventWaiter

# Use the wx_app fixture from conftest.py


@pytest.fixture
def frame(wx_app):
    frame = wx.Frame(None)
    yield frame
    # Hide the window first
    wx.CallAfter(frame.Hide)
    wx.SafeYield()
    # Then destroy it
    wx.CallAfter(frame.Destroy)
    wx.SafeYield()


@pytest.fixture
def mock_api_client():
    mock_client = MagicMock(spec=NoaaApiClient)
    # Default values, tests can override
    mock_client.get_forecast.return_value = {
        "properties": {"periods": [{"name": "Default", "temperature": 0}]}
    }
    mock_client.get_alerts.return_value = {"features": []}
    return mock_client


@pytest.fixture
def mock_location_manager():
    manager = MagicMock()
    manager.get_current_location.return_value = ("Test Location", 35.0, -80.0)
    return manager


@pytest.fixture
def event_queue():
    return queue.Queue()


# No mock_wx_callafter needed


def test_forecast_fetched_asynchronously(
    wx_app, frame, mock_api_client, mock_location_manager, event_queue, monkeypatch
):
    """Test forecast fetch and UI update via wx.CallAfter."""
    with patch.object(WeatherApp, "UpdateWeatherData", return_value=None):
        app = WeatherApp(
            frame,
            location_manager=mock_location_manager,
            api_client=mock_api_client,
            notifier=MagicMock(),
        )

    def track_status(text):
        event_queue.put(("status", text))

    app.SetStatusText = track_status

    expected_forecast = {"properties": {"periods": [{"name": "Async Today", "temperature": 75}]}}
    mock_api_client.get_forecast.return_value = expected_forecast

    # Create an event waiter to track when the callback completes
    waiter = AsyncEventWaiter()

    # Patch the app's callback method
    original_on_forecast = app._on_forecast_fetched

    def patched_on_forecast(forecast_data):
        # Store the data in the event queue for later verification
        event_queue.put(("forecast_fetched", forecast_data))
        # Call the original callback
        original_on_forecast(forecast_data)
        # Signal that the callback has completed
        waiter.callback(forecast_data)

    monkeypatch.setattr(app, "_on_forecast_fetched", patched_on_forecast)

    app.updating = False
    app.UpdateWeatherData()

    # Wait for the callback to complete (with timeout)
    result = waiter.wait(timeout_ms=5000)

    # Verify the result matches what we expected
    assert result == expected_forecast

    # Verify the API call was made correctly
    mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0)

    # Process the events from the queue
    status_events = []
    forecast_event = None
    while not event_queue.empty():
        event_item = event_queue.get(block=False)
        if event_item[0] == "status":
            status_events.append(event_item[1])
        elif event_item[0] == "forecast_fetched":
            forecast_event = event_item

    assert status_events, "No status update events found"
    assert (
        "Updating weather data for Test Location" in status_events[0]
    ), f"First status was '{status_events[0]}'"
    # Check completion status (might be 'Ready' or specific forecast info)
    assert any(
        "Ready" in s or "Async Today" in s for s in status_events
    ), f"Completion status not found in {status_events}"

    assert forecast_event is not None, "Forecast fetched event not found"
    assert forecast_event[1] == expected_forecast


def test_alerts_fetched_asynchronously(
    wx_app, frame, mock_api_client, mock_location_manager, event_queue, monkeypatch
):
    """Test alerts fetch and UI update via wx.CallAfter."""
    # Create a mock for the UI manager to avoid UI-related issues
    with patch("accessiweather.gui.ui_manager.UIManager"):
        # Patch UpdateWeatherData to avoid it being called during initialization
        with patch.object(WeatherApp, "UpdateWeatherData", return_value=None):
            app = WeatherApp(
                frame,
                location_manager=mock_location_manager,
                api_client=mock_api_client,
                notifier=MagicMock(),
            )

    def track_status(text):
        event_queue.put(("status", text))

    app.SetStatusText = track_status

    expected_alerts = {
        "features": [
            {"properties": {"headline": "Async Alert", "description": "Async Description"}}
        ]
    }
    mock_api_client.get_alerts.return_value = expected_alerts

    # Create an event waiter to track when the callback completes
    waiter = AsyncEventWaiter()

    # Patch the app's callback method
    original_on_alerts = app._on_alerts_fetched

    def patched_on_alerts(alerts_data):
        # Store the data in the event queue for later verification
        event_queue.put(("alerts_fetched", alerts_data))
        # Call the original callback
        original_on_alerts(alerts_data)
        # Signal that the callback has completed
        waiter.callback(alerts_data)

    monkeypatch.setattr(app, "_on_alerts_fetched", patched_on_alerts)

    # Mock the UI manager's _UpdateAlertsDisplay method to avoid UI-related issues
    app.ui_manager._UpdateAlertsDisplay = MagicMock(return_value=[])

    # Also patch the alerts fetcher to directly call our callback
    def mock_fetch(lat, lon, on_success=None, on_error=None, precise_location=True, radius=25):
        if on_success:
            on_success(expected_alerts)
        return True

    app.alerts_fetcher.fetch = mock_fetch

    app.updating = False
    app.UpdateWeatherData()

    # Wait for the callback to complete (with timeout)
    result = waiter.wait(timeout_ms=5000)

    # Verify the result matches what we expected
    assert result == expected_alerts

    # Process the events from the queue
    status_events = []
    alerts_event = None
    while not event_queue.empty():
        event_item = event_queue.get(block=False)
        if event_item[0] == "status":
            status_events.append(event_item[1])
        elif event_item[0] == "alerts_fetched":
            alerts_event = event_item

    assert status_events, "No status update events found"
    assert (
        "Updating weather data for Test Location" in status_events[0]
    ), f"First status was '{status_events[0]}'"

    assert alerts_event is not None, "Alerts fetched event not found"
    assert alerts_event[1] == expected_alerts


def test_forecast_error_handling(
    wx_app, frame, mock_api_client, mock_location_manager, event_queue, monkeypatch
):
    """Test forecast error handling via wx.CallAfter."""
    # Create a mock for the UI manager to avoid UI-related issues
    with patch("accessiweather.gui.ui_manager.UIManager"):
        # Patch UpdateWeatherData to avoid it being called during initialization
        with patch.object(WeatherApp, "UpdateWeatherData", return_value=None):
            app = WeatherApp(
                frame,
                location_manager=mock_location_manager,
                api_client=mock_api_client,
                notifier=MagicMock(),
            )

    def track_status(text):
        event_queue.put(("status", text))

    app.SetStatusText = track_status

    error_message = "API forecast network error"
    expected_error = ApiClientError(error_message)

    # Create an event waiter to track when the error callback completes
    waiter = AsyncEventWaiter()

    # Patch the app's error callback method
    original_on_error = app._on_forecast_error

    def patched_on_error(error):
        # Store error information in the event queue
        event_queue.put(("forecast_error", str(error)))
        # Call the original error handler
        original_on_error(error)
        # Signal that the callback has completed with the error
        waiter.callback(error)

    monkeypatch.setattr(app, "_on_forecast_error", patched_on_error)

    # Patch the forecast fetcher to directly call our error callback
    def mock_fetch(lat, lon, on_success=None, on_error=None):
        if on_error:
            on_error(error_message)
        return True

    app.forecast_fetcher.fetch = mock_fetch

    with patch("wx.MessageBox") as mock_message_box:
        app.updating = False
        app.UpdateWeatherData()

        # Wait for the callback to complete (with timeout)
        result = waiter.wait(timeout_ms=5000)

        # Verify we got an error message back
        assert result is not None
        assert error_message in str(result)

    # Process the events from the queue
    status_events = []
    error_event = None
    while not event_queue.empty():
        event_item = event_queue.get(block=False)
        if event_item[0] == "status":
            status_events.append(event_item[1])
        elif event_item[0] == "forecast_error":
            error_event = event_item

    assert status_events, "No status update events found"
    assert (
        "Updating weather data for Test Location" in status_events[0]
    ), f"First status was '{status_events[0]}'"

    assert error_event is not None, "Forecast error event not found"
    # Check original message in stored string
    assert error_message in error_event[1]


def test_alerts_error_handling(
    wx_app, frame, mock_api_client, mock_location_manager, event_queue, monkeypatch
):
    """Test alerts error handling via wx.CallAfter."""
    # Create a mock for the UI manager to avoid UI-related issues
    with patch("accessiweather.gui.ui_manager.UIManager"):
        # Patch UpdateWeatherData to avoid it being called during initialization
        with patch.object(WeatherApp, "UpdateWeatherData", return_value=None):
            app = WeatherApp(
                frame,
                location_manager=mock_location_manager,
                api_client=mock_api_client,
                notifier=MagicMock(),
            )

    def track_status(text):
        event_queue.put(("status", text))

    app.SetStatusText = track_status

    error_message = "API alerts network error"

    # Create an event waiter to track when the error callback completes
    waiter = AsyncEventWaiter()

    # Patch the app's error callback method
    original_on_error = app._on_alerts_error

    def patched_on_error(error):
        # Store error information in the event queue
        event_queue.put(("alerts_error", str(error)))
        # Call the original error handler
        original_on_error(error)
        # Signal that the callback has completed with the error
        waiter.callback(error)

    monkeypatch.setattr(app, "_on_alerts_error", patched_on_error)

    # Patch the alerts fetcher to directly call our error callback
    def mock_fetch(lat, lon, on_success=None, on_error=None, precise_location=True, radius=25):
        if on_error:
            on_error(error_message)
        return True

    app.alerts_fetcher.fetch = mock_fetch

    # Mock the alerts list to avoid UI-related issues
    app.alerts_list = MagicMock()
    app.alerts_list.DeleteAllItems = MagicMock()
    app.alerts_list.InsertItem = MagicMock(return_value=0)
    app.alerts_list.SetItem = MagicMock()

    app.updating = False
    app.UpdateWeatherData()

    # Wait for the callback to complete (with timeout)
    result = waiter.wait(timeout_ms=5000)

    # Verify we got an error message back
    assert result is not None
    assert error_message in str(result)

    # Process the events from the queue
    status_events = []
    error_event = None
    while not event_queue.empty():
        event_item = event_queue.get(block=False)
        if event_item[0] == "status":
            status_events.append(event_item[1])
        elif event_item[0] == "alerts_error":
            error_event = event_item

    assert status_events, "No status update events found"
    assert (
        "Updating weather data for Test Location" in status_events[0]
    ), f"First status was '{status_events[0]}'"

    assert error_event is not None, "Alerts error event not found"
    assert error_message in error_event[1]


def test_concurrent_fetching(
    wx_app, frame, mock_api_client, mock_location_manager, event_queue, monkeypatch
):
    """Test concurrent forecast and alerts fetch via wx.CallAfter."""
    # Create a mock for the UI manager to avoid UI-related issues
    with patch("accessiweather.gui.ui_manager.UIManager"):
        # Patch UpdateWeatherData to avoid it being called during initialization
        with patch.object(WeatherApp, "UpdateWeatherData", return_value=None):
            app = WeatherApp(
                frame,
                location_manager=mock_location_manager,
                api_client=mock_api_client,
                notifier=MagicMock(),
            )

    def track_status(text):
        event_queue.put(("status", text))

    app.SetStatusText = track_status

    # Set expected data
    forecast_data = {
        "properties": {"periods": [{"name": "Concurrent Today", "temperature": 70}]}
    }
    alerts_data = {
        "features": [{"properties": {"headline": "Concurrent Alert"}}]
    }

    # Create event waiters to track when the callbacks complete
    forecast_waiter = AsyncEventWaiter()
    alerts_waiter = AsyncEventWaiter()

    # Patch forecast callback
    original_on_forecast = app._on_forecast_fetched

    def patched_on_forecast(data):
        # Call the original callback
        original_on_forecast(data)
        # Signal that the callback has completed
        forecast_waiter.callback(data)

    monkeypatch.setattr(app, "_on_forecast_fetched", patched_on_forecast)

    # Patch alerts callback
    original_on_alerts = app._on_alerts_fetched

    def patched_on_alerts(data):
        # Call the original callback
        original_on_alerts(data)
        # Signal that the callback has completed
        alerts_waiter.callback(data)

    monkeypatch.setattr(app, "_on_alerts_fetched", patched_on_alerts)

    # Mock the UI manager's _UpdateForecastDisplay and _UpdateAlertsDisplay methods
    app.ui_manager._UpdateForecastDisplay = MagicMock()
    app.ui_manager._UpdateAlertsDisplay = MagicMock(return_value=[])

    # Patch the forecast fetcher to directly call our callback
    def mock_forecast_fetch(lat, lon, on_success=None, on_error=None):
        if on_success:
            on_success(forecast_data)
        return True

    # Patch the alerts fetcher to directly call our callback
    def mock_alerts_fetch(lat, lon, on_success=None, on_error=None, precise_location=True, radius=25):
        if on_success:
            on_success(alerts_data)
        return True

    app.forecast_fetcher.fetch = mock_forecast_fetch
    app.alerts_fetcher.fetch = mock_alerts_fetch

    app.updating = False
    app.UpdateWeatherData()

    # Wait for both callbacks to complete (with timeout)
    forecast_result = forecast_waiter.wait(timeout_ms=5000)
    alerts_result = alerts_waiter.wait(timeout_ms=5000)

    # Verify the results match what we expected
    assert forecast_result == forecast_data
    assert alerts_result == alerts_data

    status_events = []
    while not event_queue.empty():
        event_item = event_queue.get(block=False)
        if event_item[0] == "status":
            status_events.append(event_item[1])

    assert status_events, "No status update events found"
    # Check if 'Ready' is in the last status update
    assert "Ready" in status_events[-1], f"Final status '{status_events[-1]}' unexpected."
