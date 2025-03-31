import pytest
import threading
import time  # Import time for the loop timeout
import queue
import wx
from unittest.mock import MagicMock, patch

from accessiweather.gui.weather_app import WeatherApp
# NoaaApiClient imported below
from accessiweather.api_client import NoaaApiClient, ApiClientError
# Removed duplicate import of NoaaApiClient


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
    # Configure specific return values within each test as needed
    mock_client.get_forecast.return_value = {"properties": {
        "periods": [{"name": "Today", "temperature": 72}]
    }}
    mock_client.get_alerts.return_value = {"features": [
        {"properties": {
            "headline": "Test Alert", "description": "Test Description"
        }}
    ]}
    return mock_client


@pytest.fixture
def mock_location_manager():
    manager = MagicMock()
    manager.get_current_location.return_value = ("Test Location", 35.0, -80.0)
    return manager


@pytest.fixture
def event_queue():
    return queue.Queue()


# Remove mock_wx_callafter fixture, let wx.CallAfter run normally


def test_forecast_fetched_asynchronously(
    frame, mock_api_client, mock_location_manager, event_queue, monkeypatch
):
    """Test that the forecast is fetched in a background thread."""
    # Prevent UpdateWeatherData during __init__
    with patch.object(WeatherApp, 'UpdateWeatherData', return_value=None):
        app = WeatherApp(
            frame, 
            location_manager=mock_location_manager, 
            api_client=mock_api_client, 
            notifier=MagicMock()
        )
    # Original method restored after 'with' block
    
    # Track status text changes
    def track_status(text):
        event_queue.put(("status", text))
    app.SetStatusText = track_status
    
    # Set expected API return value
    expected_forecast = {"properties": {
        "periods": [{"name": "Today", "temperature": 72}]
    }}
    mock_api_client.get_forecast.return_value = expected_forecast

    # Event to signal completion
    forecast_callback_finished = threading.Event()

    # Patch the callback
    original_on_forecast = app._on_forecast_fetched

    def patched_on_forecast(forecast_data):
        try:
            # Put data in queue *before* calling original to check it later
            event_queue.put(("forecast_fetched", forecast_data))
            original_on_forecast(forecast_data)
        finally:
            forecast_callback_finished.set()
    monkeypatch.setattr(app, '_on_forecast_fetched', patched_on_forecast)
    
    # Trigger the update which should start the process
    app.updating = False  # Make sure we can start an update
    app.UpdateWeatherData()  # This call should now be the *only* one
    
    # Process wx events until the callback finishes or timeout
    start_time = time.time()
    while not forecast_callback_finished.is_set():
        wx.Yield()
        if time.time() - start_time > 10:  # 10 second timeout
            break
            
    assert forecast_callback_finished.is_set(), (
        "Forecast callback did not finish within timeout"
    )

    # Verify API call
    mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0)

    # Verify status updates and fetched data via queue
    status_events = []  # Collect all status events
    forecast_event = None
    while not event_queue.empty():
        event_item = event_queue.get(block=False)
        if event_item[0] == "status":
            status_events.append(event_item[1])  # Append status text
        elif event_item[0] == "forecast_fetched":
            forecast_event = event_item

    assert status_events, "No status update events found"
    assert "Updating weather data for Test Location" in status_events[0], \
        f"First status was '{status_events[0]}'"
    # Check for completion status update as well
    assert "Ready" in status_events[-1], \
        f"Last status was '{status_events[-1]}'"

    assert forecast_event is not None, "Forecast fetched event not found"
    assert forecast_event[1] == expected_forecast


def test_alerts_fetched_asynchronously(
    frame, mock_api_client, mock_location_manager, event_queue, monkeypatch
):
    """Test that alerts are fetched in a background thread."""
    # Prevent UpdateWeatherData during __init__
    with patch.object(WeatherApp, 'UpdateWeatherData', return_value=None):
        app = WeatherApp(
            frame, 
            location_manager=mock_location_manager, 
            api_client=mock_api_client, 
            notifier=MagicMock()
        )
    # Original method restored after 'with' block
    
    # Track status text changes
    def track_status(text):
        event_queue.put(("status", text))
    app.SetStatusText = track_status
    
    # Set expected API return value
    expected_alerts = {"features": [
        {"properties": {
            "headline": "Test Alert", "description": "Test Description"
        }}
    ]}
    mock_api_client.get_alerts.return_value = expected_alerts

    # Event to signal completion
    alerts_callback_finished = threading.Event()

    # Patch the callback
    original_on_alerts = app._on_alerts_fetched

    def patched_on_alerts(alerts_data):
        try:
            # Put data in queue *before* calling original
            event_queue.put(("alerts_fetched", alerts_data))
            original_on_alerts(alerts_data)
        finally:
            alerts_callback_finished.set()
    monkeypatch.setattr(app, '_on_alerts_fetched', patched_on_alerts)
    
    # Trigger the update which should start the process
    app.updating = False  # Make sure we can start an update
    app.UpdateWeatherData()  # This call should now be the *only* one
    
    # Process wx events until the callback finishes or timeout
    start_time = time.time()
    while not alerts_callback_finished.is_set():
        wx.Yield()
        if time.time() - start_time > 10:  # 10 second timeout
            break

    assert alerts_callback_finished.is_set(), (
        "Alerts callback did not finish within timeout"
    )

    # Verify API call
    mock_api_client.get_alerts.assert_called_once_with(35.0, -80.0)

    # Verify status updates and fetched data via queue
    status_events = []  # Collect all status events
    alerts_event = None
    while not event_queue.empty():
        event_item = event_queue.get(block=False)
        if event_item[0] == "status":
            status_events.append(event_item[1])  # Append status text
        elif event_item[0] == "alerts_fetched":
            alerts_event = event_item

    assert status_events, "No status update events found"
    assert "Updating weather data for Test Location" in status_events[0], \
        f"First status was '{status_events[0]}'"
    # Check for completion status update as well
    assert "Ready" in status_events[-1], \
        f"Last status was '{status_events[-1]}'"

    assert alerts_event is not None, "Alerts fetched event not found"
    assert alerts_event[1] == expected_alerts


def test_forecast_error_handling(
    frame, mock_api_client, mock_location_manager, event_queue, monkeypatch
):
    """Test forecast error handling, patching MessageBox."""
    # Patch wx.MessageBox to prevent GUI dialog during test
    # Prevent UpdateWeatherData during __init__
    with patch.object(WeatherApp, 'UpdateWeatherData', return_value=None):
        app = WeatherApp(
            frame, 
            location_manager=mock_location_manager, 
            api_client=mock_api_client, 
            notifier=MagicMock()
        )
    # Original method restored after 'with' block
    
    # Track status text changes
    def track_status(text):
        event_queue.put(("status", text))
    app.SetStatusText = track_status
    
    # Configure API client to raise an error
    error_message = "API forecast error"
    mock_api_client.get_forecast.side_effect = ApiClientError(error_message)

    # Event to signal completion
    forecast_error_callback_finished = threading.Event()

    # Patch the error callback
    original_on_error = app._on_forecast_error

    def patched_on_error(error):
        try:
            # Put error in queue *before* calling original
            event_queue.put(("forecast_error", error))
            original_on_error(error)
        finally:
            forecast_error_callback_finished.set()
    monkeypatch.setattr(app, '_on_forecast_error', patched_on_error)
    
    # Trigger the update which should start the process
    # Use patch context manager for MessageBox
    with patch('wx.MessageBox') as mock_message_box:
        app.updating = False  # Make sure we can start an update
        app.UpdateWeatherData()  # This call should now be the *only* one
        
        # Process wx events until the callback finishes or timeout
        start_time = time.time()
        while not forecast_error_callback_finished.is_set():
            wx.Yield()
            if time.time() - start_time > 10:  # 10 second timeout
                break

        assert forecast_error_callback_finished.is_set(), (
            "Forecast error callback did not finish within timeout"
        )

    # Verify API call
    mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0)

    # Verify status updates and error message via queue
    status_events = []  # Collect all status events
    error_event = None
    while not event_queue.empty():
        event_item = event_queue.get(block=False)
        if event_item[0] == "status":
            status_events.append(event_item[1])  # Append status text
        elif event_item[0] == "forecast_error":
            error_event = event_item

    assert status_events, "No status update events found"
    assert "Updating weather data for Test Location" in status_events[0], \
        f"First status was '{status_events[0]}'"
    # Check for error status update as well
    assert any("Error fetching forecast" in s for s in status_events), \
        f"Error status not found in {status_events}"

    assert error_event is not None, "Forecast error event not found"
    # The callback prepends text, check if original message is included
    assert error_message in error_event[1]
    
    # Verify MessageBox was called (or would have been)
    mock_message_box.assert_called_once()


def test_alerts_error_handling(
    frame, mock_api_client, mock_location_manager, event_queue, monkeypatch
):
    """Test alerts error handling, patching MessageBox."""
    # Patch wx.MessageBox to prevent GUI dialog during test
    # Prevent UpdateWeatherData during __init__
    with patch.object(WeatherApp, 'UpdateWeatherData', return_value=None):
        app = WeatherApp(
            frame, 
            location_manager=mock_location_manager, 
            api_client=mock_api_client, 
            notifier=MagicMock()
        )
    # Original method restored after 'with' block
    
    # Track status text changes
    def track_status(text):
        event_queue.put(("status", text))
    app.SetStatusText = track_status
    
    # Configure API client to raise an error
    error_message = "API alerts error"
    mock_api_client.get_alerts.side_effect = ApiClientError(error_message)

    # Event to signal completion
    alerts_error_callback_finished = threading.Event()

    # Patch the error callback
    original_on_error = app._on_alerts_error

    def patched_on_error(error):
        try:
            # Put error in queue *before* calling original
            event_queue.put(("alerts_error", error))
            original_on_error(error)
        finally:
            alerts_error_callback_finished.set()
    monkeypatch.setattr(app, '_on_alerts_error', patched_on_error)
    
    # Trigger the update which should start the process
    # Use patch context manager for MessageBox
    with patch('wx.MessageBox') as mock_message_box:
        app.updating = False  # Make sure we can start an update
        app.UpdateWeatherData()  # This call should now be the *only* one
        
        # Process wx events until the callback finishes or timeout
        start_time = time.time()
        while not alerts_error_callback_finished.is_set():
            wx.Yield()
            if time.time() - start_time > 10:  # 10 second timeout
                break

        assert alerts_error_callback_finished.is_set(), (
            "Alerts error callback did not finish within timeout"
        )

    # Verify API call
    mock_api_client.get_alerts.assert_called_once_with(35.0, -80.0)

    # Verify status updates and error message via queue
    status_events = []  # Collect all status events
    error_event = None
    while not event_queue.empty():
        event_item = event_queue.get(block=False)
        if event_item[0] == "status":
            status_events.append(event_item[1])  # Append status text
        elif event_item[0] == "alerts_error":
            error_event = event_item  # Corrected typo: item -> event_item

    assert status_events, "No status update events found"
    assert "Updating weather data for Test Location" in status_events[0], \
        f"First status was '{status_events[0]}'"
    # Check for error status update as well
    assert any("Error fetching alerts" in s for s in status_events), \
        f"Error status not found in {status_events}"

    assert error_event is not None, "Alerts error event not found"
    # The callback prepends text, check if original message is included
    assert error_message in error_event[1]
    
    # Verify MessageBox was called (or would have been)
    mock_message_box.assert_called_once()


def test_concurrent_fetching(
    frame, mock_api_client, mock_location_manager, event_queue, monkeypatch
):
    """Test that forecast and alerts are fetched concurrently."""
    # Prevent UpdateWeatherData during __init__
    with patch.object(WeatherApp, 'UpdateWeatherData', return_value=None):
        app = WeatherApp(
            frame, 
            location_manager=mock_location_manager, 
            api_client=mock_api_client, 
            notifier=MagicMock()
        )
    # Original method restored after 'with' block

    # ADDED: Track status text changes
    def track_status(text):
        event_queue.put(("status", text))
    app.SetStatusText = track_status
    
    # Set expected API return values
    mock_api_client.get_forecast.return_value = {"properties": {
        "periods": [{"name": "Today", "temperature": 72}]
    }}
    mock_api_client.get_alerts.return_value = {"features": [
        {"properties": {
            "headline": "Test Alert", "description": "Test Description"
        }}
    ]}

    # Events to signal completion of both callbacks
    forecast_callback_finished = threading.Event()
    alerts_callback_finished = threading.Event()

    # Patch forecast callback
    original_on_forecast = app._on_forecast_fetched

    def patched_on_forecast(*args, **kwargs):
        try:
            original_on_forecast(*args, **kwargs)
        finally:
            forecast_callback_finished.set()
    monkeypatch.setattr(app, '_on_forecast_fetched', patched_on_forecast)

    # Patch alerts callback
    original_on_alerts = app._on_alerts_fetched

    def patched_on_alerts(*args, **kwargs):
        try:
            original_on_alerts(*args, **kwargs)
        finally:
            alerts_callback_finished.set()
    monkeypatch.setattr(app, '_on_alerts_fetched', patched_on_alerts)
    
    # Trigger the update which should start both fetches
    app.updating = False  # Make sure we can start an update
    app.UpdateWeatherData()  # This call should now be the *only* one
    
    # Process wx events until both callbacks finish or timeout
    start_time = time.time()
    both_finished = (forecast_callback_finished.is_set() and 
                     alerts_callback_finished.is_set())
    while not both_finished:
        wx.Yield()  # Process pending events like CallAfter callbacks
        if time.time() - start_time > 10:  # 10 second timeout
            break
        both_finished = (forecast_callback_finished.is_set() and 
                         alerts_callback_finished.is_set())

    # Assert that both events were set within the timeout
    assert forecast_callback_finished.is_set(), (
        "Forecast callback did not finish within timeout"
    )
    assert alerts_callback_finished.is_set(), (
        "Alerts callback did not finish within timeout"
    )

    # Verify both API calls were made
    mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0)
    mock_api_client.get_alerts.assert_called_once_with(35.0, -80.0)

    # Verify status update indicates completion
    status_event = None
    while not event_queue.empty():
        event_item = event_queue.get(block=False)
        if event_item[0] == "status":
            status_event = event_item  # Keep the last status update

    assert status_event is not None, "Status update event not found"
    assert "Ready" in status_event[1]  # Check for final 'Ready' status
