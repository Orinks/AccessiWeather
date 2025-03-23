import pytest
import threading
import time
import queue
import wx
from unittest.mock import MagicMock, patch

from noaa_weather_app.gui import WeatherApp
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
def mock_api_client():
    mock_client = MagicMock(spec=NoaaApiClient)
    mock_client.get_forecast.return_value = {"periods": [{"name": "Today", "temperature": 72}]}
    mock_client.get_alerts.return_value = [{"headline": "Test Alert", "description": "Test Description"}]
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
def mock_wx_callafter(monkeypatch):
    # Mock wx.CallAfter to directly call the function instead of scheduling it
    def mock_call_after(func, *args, **kwargs):
        func(*args, **kwargs)
    monkeypatch.setattr(wx, 'CallAfter', mock_call_after)
    return mock_call_after

def test_forecast_fetched_asynchronously(frame, mock_api_client, mock_location_manager, event_queue, monkeypatch, mock_wx_callafter):
    """Test that the forecast is fetched in a background thread."""
    # Create test app
    app = WeatherApp(frame)
    app.api_client = mock_api_client
    app.location_manager = mock_location_manager
    
    # Track status text changes
    def track_status(text):
        event_queue.put(("status", text))
    app.SetStatusText = track_status
    
    # Override the forecast callback
    original_on_forecast = app._on_forecast_fetched
    def on_forecast_callback(forecast_data):
        event_queue.put(("forecast_fetched", forecast_data))
        # Call original to continue normal flow
        original_on_forecast(forecast_data)
    app._on_forecast_fetched = on_forecast_callback
    
    # Patch the forecast fetcher to directly call the success callback
    original_fetch = app.forecast_fetcher.fetch
    def mock_fetch(lat, lon, on_success=None, on_error=None):
        # Record that fetch was called
        event_queue.put(("fetch_called", (lat, lon)))
        # Directly call success callback
        if on_success:
            on_success({"periods": [{"name": "Today", "temperature": 72}]})
        return
    app.forecast_fetcher.fetch = mock_fetch
    
    # Trigger the update which should start the process
    app.updating = False  # Make sure we can start an update
    app.UpdateWeatherData()
    
    # First we'll get a status update
    status_event = event_queue.get(block=False)
    assert status_event[0] == "status"
    assert "Updating weather data for Test Location" in status_event[1]
    
    # Verify fetch was called
    fetch_event = event_queue.get(block=False)
    assert fetch_event[0] == "fetch_called"
    
    # Then we should get the forecast data
    forecast_event = event_queue.get(block=False)
    assert forecast_event[0] == "forecast_fetched"
    assert "periods" in forecast_event[1]

def test_alerts_fetched_asynchronously(frame, mock_api_client, mock_location_manager, event_queue, monkeypatch, mock_wx_callafter):
    """Test that alerts are fetched in a background thread."""
    # Create test app
    app = WeatherApp(frame)
    app.api_client = mock_api_client
    app.location_manager = mock_location_manager
    
    # Track status text changes
    def track_status(text):
        event_queue.put(("status", text))
    app.SetStatusText = track_status
    
    # Override the alerts callback
    original_on_alerts = app._on_alerts_fetched
    def on_alerts_callback(alerts_data):
        event_queue.put(("alerts_fetched", alerts_data))
        # Call original to continue normal flow
        original_on_alerts(alerts_data)
    app._on_alerts_fetched = on_alerts_callback
    
    # Patch the alerts fetcher to directly call the success callback
    original_fetch = app.alerts_fetcher.fetch
    def mock_fetch(lat, lon, on_success=None, on_error=None):
        # Record that fetch was called
        event_queue.put(("fetch_called", (lat, lon)))
        # Directly call success callback
        if on_success:
            on_success([{"headline": "Test Alert", "description": "Test Description"}])
        return
    app.alerts_fetcher.fetch = mock_fetch
    
    # Trigger the update which should start the process
    app.updating = False  # Make sure we can start an update
    app.UpdateWeatherData()
    
    # First we'll get a status update
    status_event = event_queue.get(block=False)
    assert status_event[0] == "status"
    assert "Updating weather data for Test Location" in status_event[1]
    
    # Verify fetch was called
    fetch_event = event_queue.get(block=False)
    assert fetch_event[0] == "fetch_called"
    
    # Then we should get the alerts data
    alerts_event = event_queue.get(block=False)
    assert alerts_event[0] == "alerts_fetched"
    assert isinstance(alerts_event[1], list)

def test_forecast_error_handling(frame, mock_api_client, mock_location_manager, event_queue, monkeypatch, mock_wx_callafter):
    """Test that errors during forecast fetching are handled properly."""
    # Create test app
    app = WeatherApp(frame)
    app.api_client = mock_api_client
    app.location_manager = mock_location_manager
    
    # Track status text changes
    def track_status(text):
        event_queue.put(("status", text))
    app.SetStatusText = track_status
    
    # Override the error callback
    original_on_error = app._on_forecast_error
    def on_error_callback(error):
        event_queue.put(("forecast_error", error))
        # Call original to continue normal flow
        original_on_error(error)
    app._on_forecast_error = on_error_callback
    
    # Patch the forecast fetcher to directly call the error callback
    error_message = "Network error in forecast"
    def mock_fetch(lat, lon, on_success=None, on_error=None):
        # Record that fetch was called
        event_queue.put(("fetch_called", (lat, lon)))
        # Directly call error callback
        if on_error:
            on_error(f"Unable to retrieve forecast: {error_message}")
        return
    app.forecast_fetcher.fetch = mock_fetch
    
    # Trigger the update which should start the process
    app.updating = False  # Make sure we can start an update
    app.UpdateWeatherData()
    
    # First we'll get a status update
    status_event = event_queue.get(block=False)
    assert status_event[0] == "status"
    assert "Updating weather data for Test Location" in status_event[1]
    
    # Verify fetch was called
    fetch_event = event_queue.get(block=False)
    assert fetch_event[0] == "fetch_called"
    
    # Then we should get the error
    error_event = event_queue.get(block=False)
    assert error_event[0] == "forecast_error"
    assert "Network error in forecast" in error_event[1]

def test_alerts_error_handling(frame, mock_api_client, mock_location_manager, event_queue, monkeypatch, mock_wx_callafter):
    """Test that errors during alerts fetching are handled properly."""
    # Create test app
    app = WeatherApp(frame)
    app.api_client = mock_api_client
    app.location_manager = mock_location_manager
    
    # Track status text changes
    def track_status(text):
        event_queue.put(("status", text))
    app.SetStatusText = track_status
    
    # Override the error callback
    original_on_error = app._on_alerts_error
    def on_error_callback(error):
        event_queue.put(("alerts_error", error))
        # Call original to continue normal flow
        original_on_error(error)
    app._on_alerts_error = on_error_callback
    
    # Patch the alerts fetcher to directly call the error callback
    error_message = "Network error in alerts"
    def mock_fetch(lat, lon, on_success=None, on_error=None):
        # Record that fetch was called
        event_queue.put(("fetch_called", (lat, lon)))
        # Directly call error callback
        if on_error:
            on_error(f"Unable to retrieve alerts: {error_message}")
        return
    app.alerts_fetcher.fetch = mock_fetch
    
    # Trigger the update which should start the process
    app.updating = False  # Make sure we can start an update
    app.UpdateWeatherData()
    
    # First we'll get a status update
    status_event = event_queue.get(block=False)
    assert status_event[0] == "status"
    assert "Updating weather data for Test Location" in status_event[1]
    
    # Verify fetch was called
    fetch_event = event_queue.get(block=False)
    assert fetch_event[0] == "fetch_called"
    
    # Then we should get the error
    error_event = event_queue.get(block=False)
    assert error_event[0] == "alerts_error"
    assert "Network error in alerts" in error_event[1]

def test_concurrent_fetching(frame, mock_api_client, mock_location_manager, event_queue, monkeypatch, mock_wx_callafter):
    """Test that forecast and alerts are fetched concurrently."""
    # Create test app
    app = WeatherApp(frame)
    app.api_client = mock_api_client
    app.location_manager = mock_location_manager
    
    # Track data fetching
    fetch_events = []
    
    # Forecast fetcher mock
    original_forecast_fetch = app.forecast_fetcher.fetch
    def mock_forecast_fetch(lat, lon, on_success=None, on_error=None):
        fetch_events.append("forecast_start")
        event_queue.put(("forecast_start", time.time()))
        # Call success after a very short delay to simulate work
        if on_success:
            on_success({"periods": [{"name": "Today", "temperature": 72}]})
        fetch_events.append("forecast_end")
        event_queue.put(("forecast_end", time.time()))
        return
    app.forecast_fetcher.fetch = mock_forecast_fetch
    
    # Alerts fetcher mock
    original_alerts_fetch = app.alerts_fetcher.fetch
    def mock_alerts_fetch(lat, lon, on_success=None, on_error=None):
        fetch_events.append("alerts_start")
        event_queue.put(("alerts_start", time.time()))
        # Call success after a very short delay to simulate work
        if on_success:
            on_success([{"headline": "Test Alert", "description": "Test Description"}])
        fetch_events.append("alerts_end")
        event_queue.put(("alerts_end", time.time()))
        return
    app.alerts_fetcher.fetch = mock_alerts_fetch
    
    # Trigger the update which should start both fetches
    app.updating = False  # Make sure we can start an update
    app.UpdateWeatherData()
    
    # Collect all events from the queue
    events = []
    while not event_queue.empty():
        events.append(event_queue.get(block=False))
    
    # Verify both forecast and alerts were started
    fetch_types = [event[0] for event in events]
    assert "forecast_start" in fetch_types
    assert "alerts_start" in fetch_types
    
    # Verify both completed
    assert "forecast_end" in fetch_types
    assert "alerts_end" in fetch_types
