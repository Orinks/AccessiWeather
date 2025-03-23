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
    # Set up mock returns for forecast and alerts
    mock_client.get_forecast.return_value = {
        "properties": {
            "periods": [
                {
                    "name": "Today",
                    "temperature": 75,
                    "temperatureUnit": "F",
                    "detailedForecast": "Sunny and clear"
                },
                {
                    "name": "Tonight",
                    "temperature": 55,
                    "temperatureUnit": "F",
                    "detailedForecast": "Clear skies"
                }
            ]
        }
    }
    
    mock_client.get_alerts.return_value = {
        "features": [
            {
                "properties": {
                    "headline": "Test Alert",
                    "description": "This is a test alert",
                    "severity": "Moderate",
                    "event": "Weather Alert Test"
                }
            }
        ]
    }
    
    return mock_client

@pytest.fixture
def mock_location_manager():
    manager = MagicMock()
    manager.get_current_location.return_value = ("Test Location", 35.0, -80.0)
    return manager

@pytest.fixture
def event_queue():
    return queue.Queue()


def test_forecast_fetched_asynchronously(frame, mock_api_client, mock_location_manager, event_queue, monkeypatch):
    """Test that the forecast is fetched in a background thread."""
    # Create test app
    app = WeatherApp(frame)
    app.api_client = mock_api_client
    app.location_manager = mock_location_manager
    
    # Track status text changes
    original_set_status = app.SetStatusText
    def track_status(text):
        event_queue.put(("status", text))
    app.SetStatusText = track_status
    
    # Add testing callback
    def test_callback(forecast_data):
        event_queue.put(("forecast_fetched", forecast_data))
    app._testing_forecast_callback = test_callback
    
    # Trigger the update which should start the threads
    app.updating = False  # Make sure we can start an update
    app.UpdateWeatherData()
    
    # First we'll get a status update
    status_event = event_queue.get(timeout=5)
    assert status_event[0] == "status"
    
    # Then we should get the forecast data
    forecast_event = event_queue.get(timeout=5)
    assert forecast_event[0] == "forecast_fetched"
    assert "properties" in forecast_event[1]
    assert len(forecast_event[1]["properties"]["periods"]) == 2
    assert forecast_event[1]["properties"]["periods"][0]["name"] == "Today"
    
    # Verify API was called with correct parameters
    mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0)


def test_alerts_fetched_asynchronously(frame, mock_api_client, mock_location_manager, event_queue, monkeypatch):
    """Test that alerts are fetched in a background thread."""
    # Create test app
    app = WeatherApp(frame)
    app.api_client = mock_api_client
    app.location_manager = mock_location_manager
    
    # Track status text changes
    original_set_status = app.SetStatusText
    def track_status(text):
        event_queue.put(("status", text))
    app.SetStatusText = track_status
    
    # Add testing callback
    def test_callback(alerts_data):
        event_queue.put(("alerts_fetched", alerts_data))
    app._testing_alerts_callback = test_callback
    
    # Trigger the update which should start the threads
    app.updating = False  # Make sure we can start an update
    app.UpdateWeatherData()
    
    # First we'll get a status update
    status_event = event_queue.get(timeout=5)
    assert status_event[0] == "status"
    
    # Then we should get the alerts data
    alerts_event = event_queue.get(timeout=5)
    assert alerts_event[0] == "alerts_fetched"
    assert "features" in alerts_event[1]
    assert len(alerts_event[1]["features"]) == 1
    assert alerts_event[1]["features"][0]["properties"]["headline"] == "Test Alert"
    
    # Verify API was called with correct parameters
    mock_api_client.get_alerts.assert_called_once_with(35.0, -80.0)


def test_forecast_error_handling(frame, mock_api_client, mock_location_manager, event_queue, monkeypatch):
    """Test that errors during forecast fetching are handled properly."""
    # Create test app
    app = WeatherApp(frame)
    app.api_client = mock_api_client
    app.location_manager = mock_location_manager
    
    # Configure API to raise an exception
    error_message = "Network error in forecast"
    mock_api_client.get_forecast.side_effect = Exception(error_message)
    
    # Track status text changes
    original_set_status = app.SetStatusText
    def track_status(text):
        event_queue.put(("status", text))
    app.SetStatusText = track_status
    
    # Add testing callback
    def test_error_callback(error):
        event_queue.put(("forecast_error", error))
    app._testing_forecast_error_callback = test_error_callback
    
    # Trigger the update which should start the threads
    app.updating = False  # Make sure we can start an update
    app.UpdateWeatherData()
    
    # First we'll get a status update
    status_event = event_queue.get(timeout=5)
    assert status_event[0] == "status"
    
    # Then we should get the error
    error_event = event_queue.get(timeout=5)
    assert error_event[0] == "forecast_error"
    assert "Unable to retrieve forecast data: Network error in forecast" == error_event[1]
    
    # Verify API was called with correct parameters
    mock_api_client.get_forecast.assert_called_once_with(35.0, -80.0)


def test_alerts_error_handling(frame, mock_api_client, mock_location_manager, event_queue, monkeypatch):
    """Test that errors during alerts fetching are handled properly."""
    # Create test app
    app = WeatherApp(frame)
    app.api_client = mock_api_client
    app.location_manager = mock_location_manager
    
    # Configure API to raise an exception
    error_message = "Network error in alerts"
    mock_api_client.get_alerts.side_effect = Exception(error_message)
    
    # Track status text changes
    original_set_status = app.SetStatusText
    def track_status(text):
        event_queue.put(("status", text))
    app.SetStatusText = track_status
    
    # Add testing callback
    def test_error_callback(error):
        event_queue.put(("alerts_error", error))
    app._testing_alerts_error_callback = test_error_callback
    
    # Trigger the update which should start the threads
    app.updating = False  # Make sure we can start an update
    app.UpdateWeatherData()
    
    # First we'll get a status update
    status_event = event_queue.get(timeout=5)
    assert status_event[0] == "status"
    
    # Then we should get the error
    error_event = event_queue.get(timeout=5)
    assert error_event[0] == "alerts_error"
    assert "Network error in alerts" == error_event[1]
    
    # Verify API was called with correct parameters
    mock_api_client.get_alerts.assert_called_once_with(35.0, -80.0)


def test_concurrent_fetching(frame, mock_api_client, mock_location_manager, event_queue, monkeypatch):
    """Test that forecasts and alerts are fetched concurrently."""
    # Create test app
    app = WeatherApp(frame)
    app.api_client = mock_api_client
    app.location_manager = mock_location_manager
    
    # Track the time of API calls to verify concurrency
    call_times = {}
    original_get_forecast = mock_api_client.get_forecast
    original_get_alerts = mock_api_client.get_alerts
    
    def track_forecast_call(*args, **kwargs):
        call_times['forecast_start'] = time.time()
        # Add an artificial delay to simulate network call
        time.sleep(0.5)
        call_times['forecast_end'] = time.time()
        return original_get_forecast(*args, **kwargs)
    
    def track_alerts_call(*args, **kwargs):
        call_times['alerts_start'] = time.time()
        # Add an artificial delay to simulate network call
        time.sleep(0.5)
        call_times['alerts_end'] = time.time()
        return original_get_alerts(*args, **kwargs)
    
    mock_api_client.get_forecast = track_forecast_call
    mock_api_client.get_alerts = track_alerts_call
    
    # Track status text changes
    original_set_status = app.SetStatusText
    def track_status(text):
        event_queue.put(("status", text))
    app.SetStatusText = track_status
    
    # Add testing callbacks
    forecast_received = threading.Event()
    alerts_received = threading.Event()
    
    def forecast_callback(data):
        event_queue.put(("forecast_done", data))
        forecast_received.set()
    
    def alerts_callback(data):
        event_queue.put(("alerts_done", data))
        alerts_received.set()
    
    app._testing_forecast_callback = forecast_callback
    app._testing_alerts_callback = alerts_callback
    
    # Trigger the update
    app.updating = False
    app.UpdateWeatherData()
    
    # First we'll get a status update
    status_event = event_queue.get(timeout=5)
    assert status_event[0] == "status"
    
    # Wait for both to complete using the events (timeout of 5 seconds)
    assert forecast_received.wait(5) == True, "Forecast callback wasn't called"
    assert alerts_received.wait(5) == True, "Alerts callback wasn't called"
    
    # Get both items from the queue
    forecast_event = event_queue.get(timeout=1)
    alerts_event = event_queue.get(timeout=1)
    
    # Check that both calls were made
    assert 'forecast_start' in call_times
    assert 'forecast_end' in call_times
    assert 'alerts_start' in call_times
    assert 'alerts_end' in call_times
    
    # Check for concurrency - the calls should overlap in time
    assert call_times['forecast_start'] < call_times['alerts_end']
    assert call_times['alerts_start'] < call_times['forecast_end']
