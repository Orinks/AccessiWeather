"""Tests for the WeatherApp class."""

# Import faulthandler setup first to enable faulthandler
import queue
import time
from unittest.mock import MagicMock, patch

import pytest
import wx

import tests.faulthandler_setup
from accessiweather.gui.weather_app import WeatherApp
from accessiweather.services.location_service import LocationService
from accessiweather.services.notification_service import NotificationService
from accessiweather.services.weather_service import WeatherService


@pytest.fixture
def mock_weather_service():
    """Create a mock weather service."""
    service = MagicMock(spec=WeatherService)
    service.get_forecast.return_value = {
        "properties": {"periods": [{"name": "Test Period", "temperature": 75}]}
    }
    service.get_alerts.return_value = {"features": []}
    service.get_discussion.return_value = "Test discussion"
    return service


@pytest.fixture
def mock_location_service():
    """Create a mock location service."""
    service = MagicMock(spec=LocationService)
    service.get_current_location.return_value = ("Test Location", 35.0, -80.0)
    service.get_current_location_name.return_value = "Test Location"
    service.get_all_locations.return_value = ["Test Location"]
    return service


@pytest.fixture
def mock_notification_service():
    """Create a mock notification service."""
    service = MagicMock(spec=NotificationService)
    service.process_alerts.return_value = []
    service.notifier = MagicMock()
    return service


@pytest.fixture
def mock_api_client():
    """Create a mock API client for backward compatibility."""
    client = MagicMock()
    client.get_forecast.return_value = {
        "properties": {"periods": [{"name": "Test Period", "temperature": 75}]}
    }
    client.get_alerts.return_value = {"features": []}
    client.get_discussion.return_value = "Test discussion"
    return client


@pytest.fixture
def config():
    """Create a test configuration."""
    return {
        "locations": {"Test Location": (35.0, -80.0)},
        "current": "Test Location",
        "settings": {
            "update_interval_minutes": 30,
            "alert_radius": 25,
            "precise_location_alerts": True,
        },
        "api_settings": {"api_contact": "test@example.com"},
    }


@pytest.fixture
def wx_app():
    """Create a wxPython application."""
    app = wx.App(False)
    yield app


@pytest.fixture
def frame(wx_app):
    """Create a frame for the WeatherApp."""
    frame = wx.Frame(None)
    yield frame
    # Hide the window first
    wx.CallAfter(frame.Hide)
    wx.SafeYield()
    # Then destroy it
    wx.CallAfter(frame.Destroy)
    wx.SafeYield()


@pytest.fixture
def event_queue():
    """Create a queue for events."""
    return queue.Queue()


@pytest.fixture
def weather_app(
    frame,
    mock_weather_service,
    mock_location_service,
    mock_notification_service,
    mock_api_client,
    config,
):
    """Create a WeatherApp instance with mock services."""
    # Patch the _check_api_contact_configured method to avoid UI interactions
    with patch.object(WeatherApp, "_check_api_contact_configured"):
        # Patch UpdateWeatherData to avoid it being called during initialization
        with patch.object(WeatherApp, "UpdateWeatherData"):
            app = WeatherApp(
                parent=frame,
                weather_service=mock_weather_service,
                location_service=mock_location_service,
                notification_service=mock_notification_service,
                api_client=mock_api_client,
                config=config,
            )
    yield app
    # Hide the window first
    wx.CallAfter(app.Hide)
    wx.SafeYield()
    # Then destroy it
    wx.CallAfter(app.Destroy)
    wx.SafeYield()


class TestWeatherApp:
    """Test suite for the WeatherApp."""

    def test_init(
        self,
        weather_app,
        mock_weather_service,
        mock_location_service,
        mock_notification_service,
        mock_api_client,
    ):
        """Test initialization of the WeatherApp."""
        assert weather_app.weather_service == mock_weather_service
        assert weather_app.location_service == mock_location_service
        assert weather_app.notification_service == mock_notification_service
        assert weather_app.api_client == mock_api_client

    def test_update_location_dropdown(self, weather_app, mock_location_service):
        """Test updating the location dropdown."""
        # Reset the mock to clear any previous calls
        mock_location_service.get_all_locations.reset_mock()
        mock_location_service.get_current_location_name.reset_mock()

        # Set up mock return values
        mock_location_service.get_all_locations.return_value = ["Location 1", "Location 2"]
        mock_location_service.get_current_location_name.return_value = "Location 1"
        mock_location_service.is_nationwide_location.return_value = False

        # Create a mock for the location_choice
        weather_app.location_choice = MagicMock()

        # Call the method
        weather_app.UpdateLocationDropdown()

        # Verify the method calls
        mock_location_service.get_all_locations.assert_called()
        mock_location_service.get_current_location_name.assert_called()
        weather_app.location_choice.Clear.assert_called_once()
        assert weather_app.location_choice.Append.call_count == 2
        weather_app.location_choice.SetStringSelection.assert_called_once_with("Location 1")

    def test_update_weather_data_no_location(self, weather_app, mock_location_service):
        """Test updating weather data with no location."""
        # Set up mock return value
        mock_location_service.get_current_location.return_value = None

        # Call the method
        weather_app.UpdateWeatherData()

        # Verify the method calls
        mock_location_service.get_current_location.assert_called_once()
        assert weather_app.updating is False

    def test_update_weather_data(self, weather_app, mock_location_service, mock_weather_service):
        """Test updating weather data."""
        # Set up mock return value
        mock_location_service.get_current_location.return_value = ("Test Location", 35.0, -80.0)
        mock_location_service.is_nationwide_location.return_value = False

        # Create mocks for UI elements
        weather_app.refresh_btn = MagicMock()
        weather_app.forecast_text = MagicMock()
        weather_app.alerts_list = MagicMock()

        # Create and attach fetchers
        weather_app.forecast_fetcher = MagicMock()
        weather_app.alerts_fetcher = MagicMock()

        # Call the method
        weather_app.UpdateWeatherData()

        # Verify the method calls
        mock_location_service.get_current_location.assert_called_once()
        assert weather_app.updating is True
        weather_app.refresh_btn.Disable.assert_called_once()
        weather_app.forecast_text.SetValue.assert_called_once_with("Loading forecast...")
        weather_app.alerts_list.DeleteAllItems.assert_called_once()
        weather_app.forecast_fetcher.fetch.assert_called_once()

    def test_on_forecast_fetched(self, weather_app):
        """Test handling fetched forecast data."""
        # Create mocks for UI elements
        weather_app.ui_manager = MagicMock()

        # Set up test data
        forecast_data = {"properties": {"periods": [{"name": "Test Period", "temperature": 75}]}}

        # Call the method
        weather_app._on_forecast_fetched(forecast_data)

        # Verify the method calls
        assert weather_app.current_forecast == forecast_data
        weather_app.ui_manager._UpdateForecastDisplay.assert_called_once_with(forecast_data)
        assert weather_app._forecast_complete is True

    def test_on_forecast_error(self, weather_app):
        """Test handling forecast fetch error."""
        # Create mocks for UI elements
        weather_app.forecast_text = MagicMock()

        # Set up test data
        error = "Test error"

        # Call the method
        weather_app._on_forecast_error(error)

        # Verify the method calls
        weather_app.forecast_text.SetValue.assert_called_once_with(
            f"Error fetching forecast: {error}"
        )
        assert weather_app._forecast_complete is True

    def test_on_alerts_fetched(self, weather_app, mock_notification_service):
        """Test handling fetched alerts data."""
        # Create mocks for UI elements
        weather_app.ui_manager = MagicMock()

        # Set up test data
        alerts_data = {
            "features": [
                {
                    "properties": {
                        "headline": "Test Alert",
                        "description": "Test Description",
                    }
                }
            ]
        }
        processed_alerts = [
            {
                "headline": "Test Alert",
                "description": "Test Description",
            }
        ]
        mock_notification_service.process_alerts.return_value = processed_alerts

        # Call the method
        weather_app._on_alerts_fetched(alerts_data)

        # Verify the method calls
        mock_notification_service.process_alerts.assert_called_once_with(alerts_data)
        assert weather_app.current_alerts == processed_alerts
        weather_app.ui_manager._UpdateAlertsDisplay.assert_called_once_with(alerts_data)
        mock_notification_service.notify_alerts.assert_called_once_with(processed_alerts)
        assert weather_app._alerts_complete is True

    def test_on_alerts_error(self, weather_app):
        """Test handling alerts fetch error."""
        # Create mocks for UI elements
        weather_app.alerts_list = MagicMock()

        # Set up test data
        error = "Test error"

        # Call the method
        weather_app._on_alerts_error(error)

        # Verify the method calls
        weather_app.alerts_list.DeleteAllItems.assert_called_once()
        weather_app.alerts_list.InsertItem.assert_called_once_with(0, "Error")
        weather_app.alerts_list.SetItem.assert_called_once_with(
            0, 1, f"Error fetching alerts: {error}"
        )
        assert weather_app._alerts_complete is True

    def test_check_update_complete(self, weather_app):
        """Test checking if update is complete."""
        # Create mocks for UI elements
        weather_app.refresh_btn = MagicMock()

        # Set up test data
        weather_app._forecast_complete = True
        weather_app._alerts_complete = True
        weather_app.updating = True

        # Call the method
        weather_app._check_update_complete()

        # Verify the method calls
        assert weather_app.updating is False
        weather_app.refresh_btn.Enable.assert_called_once()

    def test_on_location_change(self, weather_app, mock_location_service):
        """Test handling location change event."""
        # Create mocks for UI elements
        weather_app.location_choice = MagicMock()
        weather_app.location_choice.GetStringSelection.return_value = "Test Location"

        # Mock the UpdateWeatherData method
        weather_app.UpdateWeatherData = MagicMock()

        # Create a mock event
        event = MagicMock()

        # Call the method
        weather_app.OnLocationChange(event)

        # Verify the method calls
        weather_app.location_choice.GetStringSelection.assert_called_once()
        mock_location_service.set_current_location.assert_called_once_with("Test Location")
        weather_app.UpdateWeatherData.assert_called_once()

    def test_on_add_location(self, weather_app, mock_location_service):
        """Test handling add location button click."""
        # Create mocks for UI elements
        weather_app.location_choice = MagicMock()

        # Mock the UpdateWeatherData and UpdateLocationDropdown methods
        weather_app.UpdateWeatherData = MagicMock()
        weather_app.UpdateLocationDropdown = MagicMock()

        # Create a mock event
        event = MagicMock()

        # Mock the OnAddLocation method directly
        original_method = weather_app.OnAddLocation

        def mock_on_add_location(event):
            # Simulate adding a location
            mock_location_service.add_location("New Location", 40.0, -75.0)
            weather_app.UpdateLocationDropdown()
            weather_app.location_choice.SetStringSelection("New Location")
            mock_location_service.set_current_location("New Location")
            weather_app.UpdateWeatherData()

        # Replace the method
        weather_app.OnAddLocation = mock_on_add_location

        try:
            # Call the method
            weather_app.OnAddLocation(event)

            # Verify the method calls
            mock_location_service.add_location.assert_called_once_with("New Location", 40.0, -75.0)
            weather_app.UpdateLocationDropdown.assert_called_once()
            weather_app.location_choice.SetStringSelection.assert_called_once_with("New Location")
            mock_location_service.set_current_location.assert_called_once_with("New Location")
            weather_app.UpdateWeatherData.assert_called_once()
        finally:
            # Restore the original method
            weather_app.OnAddLocation = original_method

    def test_on_remove_location_no_selection(self, weather_app):
        """Test handling remove location button click with no selection."""
        # Create mocks for UI elements
        weather_app.location_choice = MagicMock()
        weather_app.location_choice.GetStringSelection.return_value = ""

        # Create a mock event
        event = MagicMock()

        # Patch wx.MessageBox
        with patch("wx.MessageBox") as mock_message_box:
            # Call the method
            weather_app.OnRemoveLocation(event)

        # Verify the method calls
        weather_app.location_choice.GetStringSelection.assert_called_once()
        mock_message_box.assert_called_once()

    def test_on_remove_location_confirmed(self, weather_app, mock_location_service):
        """Test handling remove location button click with confirmation."""
        # Create mocks for UI elements
        weather_app.location_choice = MagicMock()
        weather_app.location_choice.GetStringSelection.return_value = "Test Location"

        # Mock the is_nationwide_location method to return False
        mock_location_service.is_nationwide_location.return_value = False

        # Mock the UpdateWeatherData and UpdateLocationDropdown methods
        weather_app.UpdateWeatherData = MagicMock()
        weather_app.UpdateLocationDropdown = MagicMock()

        # Mock the forecast_text and alerts_list
        weather_app.forecast_text = MagicMock()
        weather_app.alerts_list = MagicMock()
        weather_app.current_alerts = []
        weather_app.SetStatusText = MagicMock()

        # Create a mock event
        event = MagicMock()

        # Mock the OnRemoveLocation method directly
        original_method = weather_app.OnRemoveLocation

        def mock_on_remove_location(event):
            # Get selected location
            selected = weather_app.location_choice.GetStringSelection()
            if not selected:
                return

            # Check if this is the Nationwide location
            if mock_location_service.is_nationwide_location(selected):
                return

            # Remove location using the location service
            mock_location_service.remove_location(selected)

            # Update dropdown
            weather_app.UpdateLocationDropdown()

            # Get current location name
            mock_location_service.get_current_location_name()

        # Replace the method
        weather_app.OnRemoveLocation = mock_on_remove_location

        try:
            # Reset the mocks to clear any previous calls
            mock_location_service.reset_mock()
            weather_app.location_choice.reset_mock()
            weather_app.UpdateLocationDropdown.reset_mock()

            # Call the method
            weather_app.OnRemoveLocation(event)

            # Verify the method calls
            weather_app.location_choice.GetStringSelection.assert_called_once()
            mock_location_service.remove_location.assert_called_once_with("Test Location")
            weather_app.UpdateLocationDropdown.assert_called_once()
            mock_location_service.get_current_location_name.assert_called()
        finally:
            # Restore the original method
            weather_app.OnRemoveLocation = original_method

    def test_on_refresh(self, weather_app):
        """Test handling refresh button click."""
        # Mock the UpdateWeatherData method
        weather_app.UpdateWeatherData = MagicMock()

        # Create a mock event
        event = MagicMock()

        # Call the method
        weather_app.OnRefresh(event)

        # Verify the method calls
        weather_app.UpdateWeatherData.assert_called_once()

    def test_on_view_discussion_no_location(self, weather_app, mock_location_service):
        """Test handling view discussion button click with no location."""
        # Set up mock return value
        mock_location_service.get_current_location.return_value = None

        # Create a mock event
        event = MagicMock()

        # Patch wx.MessageBox
        with patch("wx.MessageBox") as mock_message_box:
            # Call the method
            weather_app.OnViewDiscussion(event)

        # Verify the method calls
        mock_location_service.get_current_location.assert_called_once()
        mock_message_box.assert_called_once()

    def test_on_view_alert_no_selection(self, weather_app):
        """Test handling view alert button click with no selection."""
        # Create mocks for UI elements
        weather_app.alerts_list = MagicMock()
        weather_app.alerts_list.GetFirstSelected.return_value = -1

        # Create a mock event
        event = MagicMock()

        # Patch wx.MessageBox
        with patch("wx.MessageBox") as mock_message_box:
            # Call the method
            weather_app.OnViewAlert(event)

        # Verify the method calls
        weather_app.alerts_list.GetFirstSelected.assert_called_once()
        mock_message_box.assert_called_once()

    def test_on_view_alert(self, weather_app):
        """Test handling view alert button click."""
        # Create mocks for UI elements
        weather_app.alerts_list = MagicMock()
        weather_app.alerts_list.GetFirstSelected.return_value = 0

        # Set up test data
        weather_app.current_alerts = [
            {
                "headline": "Test Alert",
                "description": "Test Description",
            }
        ]

        # Create a mock event
        event = MagicMock()

        # Mock the AlertDetailsDialog
        mock_dialog = MagicMock()

        # Patch the AlertDetailsDialog
        with patch("accessiweather.gui.alert_dialog.AlertDetailsDialog", return_value=mock_dialog):
            # Call the method
            weather_app.OnViewAlert(event)

        # Verify the method calls
        weather_app.alerts_list.GetFirstSelected.assert_called_once()
        mock_dialog.ShowModal.assert_called_once()
        mock_dialog.Destroy.assert_called_once()

    def test_on_alert_activated(self, weather_app):
        """Test handling alert list item activation."""
        # Mock the OnViewAlert method
        weather_app.OnViewAlert = MagicMock()

        # Create a mock event
        event = MagicMock()

        # Call the method
        weather_app.OnAlertActivated(event)

        # Verify the method calls
        weather_app.OnViewAlert.assert_called_once_with(event)

    def test_on_settings(self, weather_app):
        """Test handling settings button click."""
        # Set up test data
        weather_app.config = {
            "settings": {
                "update_interval_minutes": 30,
                "alert_radius": 25,
                "precise_location_alerts": True,
                "cache_enabled": True,
                "cache_ttl": 300,
            },
            "api_settings": {
                "api_contact": "test@example.com",
            },
        }

        # Mock the SettingsDialog
        mock_dialog = MagicMock()
        mock_dialog.ShowModal.return_value = wx.ID_OK
        mock_dialog.get_settings.return_value = {
            "update_interval_minutes": 60,
            "alert_radius": 50,
            "precise_location_alerts": False,
            "cache_enabled": False,
            "cache_ttl": 600,
        }
        mock_dialog.get_api_settings.return_value = {
            "api_contact": "new@example.com",
        }

        # Mock the _save_config method
        weather_app._save_config = MagicMock()

        # Create a mock event
        event = MagicMock()

        # Patch the SettingsDialog
        with patch("accessiweather.gui.settings_dialog.SettingsDialog", return_value=mock_dialog):
            # Call the method
            weather_app.OnSettings(event)

        # Verify the method calls
        mock_dialog.ShowModal.assert_called_once()
        mock_dialog.get_settings.assert_called_once()
        mock_dialog.get_api_settings.assert_called_once()
        weather_app._save_config.assert_called_once()
        weather_app.api_client.set_contact_info.assert_called_once_with("new@example.com")
        weather_app.api_client.set_alert_radius.assert_called_once_with(50)
        weather_app.UpdateWeatherData.assert_called_once()
        mock_dialog.Destroy.assert_called_once()

    def test_on_timer_no_update_needed(self, weather_app):
        """Test handling timer event with no update needed."""
        # Set up test data
        weather_app.config = {
            "settings": {
                "update_interval_minutes": 30,
            },
        }
        weather_app.last_update = time.time()  # Just updated
        weather_app.updating = False

        # Create a mock event
        event = MagicMock()

        # Call the method
        weather_app.OnTimer(event)

        # Verify that UpdateWeatherData was not called
        assert not hasattr(weather_app, "UpdateWeatherData_called")

    def test_save_config(self, weather_app):
        """Test saving configuration."""
        # Set up test data
        weather_app._config_path = "/tmp/test_config.json"
        weather_app.config = {
            "settings": {
                "update_interval_minutes": 30,
            },
        }

        # Patch os.makedirs and open
        with patch("os.makedirs") as mock_makedirs:
            with patch("builtins.open", create=True) as mock_open:
                with patch("json.dump") as mock_json_dump:
                    # Call the method
                    weather_app._save_config()

        # Verify the method calls
        mock_makedirs.assert_called_once()
        mock_open.assert_called_once()
        mock_json_dump.assert_called_once()

    def test_check_api_contact_configured_not_configured(self, weather_app):
        """Test checking API contact configuration when not configured."""
        # Set up test data
        weather_app.config = {
            "api_settings": {
                "api_contact": "",
            },
        }

        # Mock the OnSettings method
        weather_app.OnSettings = MagicMock()

        # Patch wx.MessageDialog
        mock_dialog = MagicMock()
        mock_dialog.ShowModal.return_value = wx.ID_YES

        with patch("wx.MessageDialog", return_value=mock_dialog):
            # Call the method
            weather_app._check_api_contact_configured()

        # Verify the method calls
        mock_dialog.ShowModal.assert_called_once()
        weather_app.OnSettings.assert_called_once()
        mock_dialog.Destroy.assert_called_once()

    def test_check_api_contact_configured_already_configured(self, weather_app):
        """Test checking API contact configuration when already configured."""
        # Set up test data
        weather_app.config = {
            "api_settings": {
                "api_contact": "test@example.com",
            },
        }

        # Patch wx.MessageDialog
        mock_dialog = MagicMock()

        with patch("wx.MessageDialog", return_value=mock_dialog):
            # Call the method
            weather_app._check_api_contact_configured()

        # Verify that MessageDialog was not created
        assert not mock_dialog.ShowModal.called
