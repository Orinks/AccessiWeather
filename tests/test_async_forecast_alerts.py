import queue
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import wx  # type: ignore

from accessiweather.api_client import ApiClientError, NoaaApiClient
from accessiweather.gui.weather_app import WeatherApp

# Import fetcher to patch callbacks if needed, though patching app methods here
# from accessiweather.gui.async_fetchers import ForecastFetcher


@pytest.fixture
def wx_app():
    # Ensure an app exists for wx.CallAfter processing
    app = wx.App(False)  # Redirect stdout/stderr if needed
    yield app
    # Allow pending events to process before destroying
    for _ in range(5):  # Process pending events a few times
        wx.YieldIfNeeded()
        time.sleep(0.01)
    app.Destroy()


@pytest.fixture
def frame(wx_app):
    frame = wx.Frame(None)
    yield frame
    frame.Destroy()


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

    callback_finished_event = threading.Event()

    # Patch the app's callback method
    original_on_forecast = app._on_forecast_fetched

    def patched_on_forecast(forecast_data):
        try:
            event_queue.put(("forecast_fetched", forecast_data))
            original_on_forecast(forecast_data)
        finally:
            callback_finished_event.set()

    monkeypatch.setattr(app, "_on_forecast_fetched", patched_on_forecast)

    app.updating = False
    app.UpdateWeatherData()

    start_time = time.time()
    timeout = 10  # seconds
    processed_event = False
    while time.time() - start_time < timeout:
        if callback_finished_event.wait(timeout=0.01):
            processed_event = True
            break
        wx.YieldIfNeeded()

    assert processed_event, "Forecast callback did not finish within timeout."

    mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0)

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

    callback_finished_event = threading.Event()

    # Patch the app's callback method
    original_on_alerts = app._on_alerts_fetched

    def patched_on_alerts(alerts_data):
        try:
            event_queue.put(("alerts_fetched", alerts_data))
            original_on_alerts(alerts_data)
        finally:
            callback_finished_event.set()

    monkeypatch.setattr(app, "_on_alerts_fetched", patched_on_alerts)

    app.updating = False
    app.UpdateWeatherData()

    start_time = time.time()
    timeout = 10  # seconds
    processed_event = False
    while time.time() - start_time < timeout:
        if callback_finished_event.wait(timeout=0.01):
            processed_event = True
            break
        wx.YieldIfNeeded()

    assert processed_event, "Alerts callback did not finish within timeout."

    mock_api_client.get_alerts.assert_called_once_with(35.0, -80.0)

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
    # Check completion status (might be 'Ready' or alert info)
    assert any(
        "Ready" in s or "Async Alert" in s for s in status_events
    ), f"Completion status not found in {status_events}"

    assert alerts_event is not None, "Alerts fetched event not found"
    assert alerts_event[1] == expected_alerts


def test_forecast_error_handling(
    wx_app, frame, mock_api_client, mock_location_manager, event_queue, monkeypatch
):
    """Test forecast error handling via wx.CallAfter."""
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
    mock_api_client.get_forecast.side_effect = ApiClientError(error_message)

    callback_finished_event = threading.Event()

    # Patch the app's error callback method
    original_on_error = app._on_forecast_error

    def patched_on_error(error):
        try:
            # Check error type if needed: isinstance(error, ApiClientError)
            # Store string representation
            event_queue.put(("forecast_error", str(error)))
            original_on_error(error)
        finally:
            callback_finished_event.set()

    monkeypatch.setattr(app, "_on_forecast_error", patched_on_error)

    with patch("wx.MessageBox") as mock_message_box:
        app.updating = False
        app.UpdateWeatherData()

        start_time = time.time()
        timeout = 10  # seconds
        processed_event = False
        while time.time() - start_time < timeout:
            if callback_finished_event.wait(timeout=0.01):
                processed_event = True
                break
            wx.YieldIfNeeded()

        assert processed_event, "Forecast error callback did not finish."

    mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0)

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
    assert any(
        "Error fetching forecast" in s for s in status_events
    ), f"Error status not found in {status_events}"

    assert error_event is not None, "Forecast error event not found"
    # Check original message in stored string
    assert error_message in error_event[1]

    mock_message_box.assert_called_once()
    # Check message box content if needed
    args, kwargs = mock_message_box.call_args
    assert error_message in args[0]


def test_alerts_error_handling(
    wx_app, frame, mock_api_client, mock_location_manager, event_queue, monkeypatch
):
    """Test alerts error handling via wx.CallAfter."""
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
    mock_api_client.get_alerts.side_effect = ApiClientError(error_message)

    callback_finished_event = threading.Event()

    # Patch the app's error callback method
    original_on_error = app._on_alerts_error

    def patched_on_error(error):
        try:
            event_queue.put(("alerts_error", str(error)))
            original_on_error(error)
        finally:
            callback_finished_event.set()

    monkeypatch.setattr(app, "_on_alerts_error", patched_on_error)

    with patch("wx.MessageBox") as mock_message_box:
        app.updating = False
        app.UpdateWeatherData()

        start_time = time.time()
        timeout = 10  # seconds
        processed_event = False
        while time.time() - start_time < timeout:
            if callback_finished_event.wait(timeout=0.01):
                processed_event = True
                break
            wx.YieldIfNeeded()

        assert processed_event, "Alerts error callback did not finish."

    mock_api_client.get_alerts.assert_called_once_with(35.0, -80.0)

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
    assert any(
        "Error fetching alerts" in s for s in status_events
    ), f"Error status not found in {status_events}"

    assert error_event is not None, "Alerts error event not found"
    assert error_message in error_event[1]

    mock_message_box.assert_called_once()
    args, kwargs = mock_message_box.call_args
    assert error_message in args[0]


def test_concurrent_fetching(
    wx_app, frame, mock_api_client, mock_location_manager, event_queue, monkeypatch
):
    """Test concurrent forecast and alerts fetch via wx.CallAfter."""
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

    # Set expected API return values
    mock_api_client.get_forecast.return_value = {
        "properties": {"periods": [{"name": "Concurrent Today", "temperature": 70}]}
    }
    mock_api_client.get_alerts.return_value = {
        "features": [{"properties": {"headline": "Concurrent Alert"}}]
    }

    forecast_callback_finished = threading.Event()
    alerts_callback_finished = threading.Event()

    # Patch forecast callback
    original_on_forecast = app._on_forecast_fetched

    def patched_on_forecast(*args, **kwargs):
        try:
            original_on_forecast(*args, **kwargs)
        finally:
            forecast_callback_finished.set()

    monkeypatch.setattr(app, "_on_forecast_fetched", patched_on_forecast)

    # Patch alerts callback
    original_on_alerts = app._on_alerts_fetched

    def patched_on_alerts(*args, **kwargs):
        try:
            original_on_alerts(*args, **kwargs)
        finally:
            alerts_callback_finished.set()

    monkeypatch.setattr(app, "_on_alerts_fetched", patched_on_alerts)

    app.updating = False
    app.UpdateWeatherData()

    start_time = time.time()
    timeout = 15  # Slightly longer timeout for concurrency
    while time.time() - start_time < timeout:
        # Check if both are done
        both_finished = forecast_callback_finished.is_set() and alerts_callback_finished.is_set()
        if both_finished:
            break
        # Wait briefly on *one* event, then yield.
        # Waiting on both simultaneously is tricky without extra logic.
        # This approach relies on YieldIfNeeded processing both eventually.
        forecast_callback_finished.wait(timeout=0.01)  # Non-blocking check
        wx.YieldIfNeeded()

    assert forecast_callback_finished.is_set(), "Forecast callback did not finish."
    assert alerts_callback_finished.is_set(), "Alerts callback did not finish."

    mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0)
    mock_api_client.get_alerts.assert_called_once_with(35.0, -80.0)

    status_events = []
    while not event_queue.empty():
        event_item = event_queue.get(block=False)
        if event_item[0] == "status":
            status_events.append(event_item[1])

    assert status_events, "No status update events found"
    # Check if 'Ready' or specific data from either call is present
    # in the *last* status update.
    assert (
        "Ready" in status_events[-1]
        or "Concurrent Today" in status_events[-1]
        or "Concurrent Alert" in status_events[-1]
    ), f"Final status '{status_events[-1]}' unexpected."
