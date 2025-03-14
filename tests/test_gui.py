"""Tests for the GUI components"""

import pytest
import wx
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

from noaa_weather_app.gui import LocationDialog, WeatherDiscussionDialog, WeatherApp
from noaa_weather_app.api_client import NoaaApiClient


# We need a wx App for testing wx components
@pytest.fixture(scope="module")
def wx_app():
    """Create a wx App for testing"""
    app = wx.App()
    yield app


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing"""
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a temporary config file
        config_path = os.path.join(temp_dir, "config.json")
        config_data = {
            "locations": {
                "Test City": {"lat": 35.0, "lon": -80.0}
            },
            "current": "Test City",
            "settings": {
                "update_interval_minutes": 30
            },
            "api_settings": {
                "contact_info": "test@example.com"
            }
        }
        
        with open(config_path, "w") as f:
            json.dump(config_data, f)
        
        yield config_path


class TestLocationDialog:
    """Test suite for LocationDialog"""
    
    def setup_method(self):
        """Set up test fixture"""
        # Create geocoding service mock
        self.geocoding_patcher = patch('noaa_weather_app.gui.GeocodingService')
        self.mock_geocoding_class = self.geocoding_patcher.start()
        self.mock_geocoding = MagicMock()
        self.mock_geocoding_class.return_value = self.mock_geocoding
    
    def teardown_method(self):
        """Tear down test fixture"""
        # Stop geocoding patch
        self.geocoding_patcher.stop()
    
    def test_init(self, wx_app):
        """Test initialization"""
        dialog = LocationDialog(None, title="Test Dialog", location_name="Test", lat=35.0, lon=-80.0)
        try:
            assert dialog.name_ctrl.GetValue() == "Test"
            assert dialog.latitude == 35.0
            assert dialog.longitude == -80.0
            assert "Custom coordinates: 35.0" in dialog.result_text.GetValue()
        finally:
            dialog.Destroy()
    
    def test_validation(self, wx_app):
        """Test input validation"""
        dialog = LocationDialog(None)
        try:
            # Set initial state with valid coordinates
            dialog.latitude = 35.0
            dialog.longitude = -80.0
            dialog.result_text.SetValue("Custom coordinates: 35.0, -80.0")
            
            # Test with valid inputs
            dialog.name_ctrl.SetValue("Test")
            
            # Mock the event
            event = MagicMock()
            dialog.OnOK(event)
            
            # Skip should have been called for valid inputs
            event.Skip.assert_called_once()
            
            # Test with empty name
            event.reset_mock()
            dialog.name_ctrl.SetValue("")
            
            # Need to patch MessageBox
            with patch('wx.MessageBox') as mock_message_box:
                dialog.OnOK(event)
                
                # Skip should not have been called
                assert not event.Skip.called
                
                # MessageBox should have been called
                mock_message_box.assert_called_once()
                args = mock_message_box.call_args[0]
                assert "name" in args[0].lower()
        finally:
            dialog.Destroy()
    
    def test_get_values(self, wx_app):
        """Test getting values from the dialog"""
        dialog = LocationDialog(None)
        try:
            dialog.name_ctrl.SetValue("Test")
            dialog.latitude = 35.0
            dialog.longitude = -80.0
            
            name, lat, lon = dialog.GetValues()
            assert name == "Test"
            assert lat == 35.0
            assert lon == -80.0
        finally:
            dialog.Destroy()


class TestWeatherDiscussionDialog:
    """Test suite for WeatherDiscussionDialog"""
    
    def test_init(self, wx_app):
        """Test initialization"""
        dialog = WeatherDiscussionDialog(None, title="Test Discussion", text="Test discussion text")
        try:
            assert dialog.text_ctrl.GetValue() == "Test discussion text"
        finally:
            dialog.Destroy()


class TestWeatherApp:
    """Test suite for WeatherApp"""
    
    @pytest.fixture
    def mock_components(self):
        """Mock the components used by WeatherApp"""
        with patch('noaa_weather_app.gui.NoaaApiClient') as mock_api_client_class, \
             patch('noaa_weather_app.gui.WeatherNotifier') as mock_notifier_class, \
             patch('noaa_weather_app.gui.LocationManager') as mock_location_manager_class:
            
            # Create mock instances
            mock_api_client = MagicMock()
            mock_notifier = MagicMock()
            mock_location_manager = MagicMock()
            
            # Configure mock location manager to return valid data
            mock_location_manager.get_all_locations.return_value = ["Test City"]
            mock_location_manager.get_current_location.return_value = ("Test City", 35.0, -80.0)
            
            # Configure mock classes to return mock instances
            mock_api_client_class.return_value = mock_api_client
            mock_notifier_class.return_value = mock_notifier
            mock_location_manager_class.return_value = mock_location_manager
            
            yield {
                'api_client_class': mock_api_client_class,
                'api_client': mock_api_client,
                'notifier_class': mock_notifier_class,
                'notifier': mock_notifier,
                'location_manager_class': mock_location_manager_class,
                'location_manager': mock_location_manager
            }
    
    def test_init_with_default_config(self, wx_app, mock_components, monkeypatch):
        """Test initialization with default config"""
        # Patch os.path.exists to return False for all config paths
        monkeypatch.setattr(os.path, 'exists', lambda path: False)
        
        # Create app
        app = None
        try:
            app = WeatherApp()
            
            # Check that NoaaApiClient was initialized with default values
            mock_components['api_client_class'].assert_called_once()
            args, kwargs = mock_components['api_client_class'].call_args
            assert kwargs.get('user_agent') == 'AccessiWeather'
            assert kwargs.get('contact_info') is None
        finally:
            if app:
                app.Destroy()
    
    def test_init_with_config_file(self, wx_app, mock_components, temp_config_file, monkeypatch):
        """Test initialization with config file"""
        # Patch os.path.exists to return True only for our temp config file
        original_exists = os.path.exists
        def mock_exists(path):
            if path == temp_config_file:
                return True
            return original_exists(path)
        
        monkeypatch.setattr(os.path, 'exists', mock_exists)
        
        # Patch open to return our temp config file content
        original_open = open
        def mock_open(file, *args, **kwargs):
            if file == temp_config_file:
                return original_open(temp_config_file, *args, **kwargs)
            return original_open(file, *args, **kwargs)
        
        monkeypatch.setattr('builtins.open', mock_open)
        
        # Create a new WeatherApp instance
        app = None
        try:
            # Patch os.getcwd to return the directory of our temp config
            monkeypatch.setattr(os, 'getcwd', lambda: os.path.dirname(temp_config_file))
            
            # Create app
            app = WeatherApp()
            
            # Check that NoaaApiClient was initialized with values from config
            mock_components['api_client_class'].assert_called_once()
            args, kwargs = mock_components['api_client_class'].call_args
            assert kwargs.get('user_agent') == 'AccessiWeather'
            assert kwargs.get('contact_info') == 'test@example.com'
        finally:
            if app:
                app.Destroy()
    
    @patch('wx.CallAfter')
    def test_fetch_weather_data_with_proper_headers(self, mock_call_after, wx_app, mock_components, monkeypatch):
        """Test that _FetchWeatherData uses proper headers from API client"""
        # Create real API client with contact info
        api_client = NoaaApiClient(user_agent="AccessiWeather", contact_info="test@example.com")
        
        # Set up the mock API client in our components
        mock_components['api_client_class'].return_value = api_client
        
        # Mock requests.get to check headers
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "properties": {
                "forecast": "https://api.example.com/forecast"
            }
        })
        
        mock_get = MagicMock(return_value=mock_response)
        monkeypatch.setattr("requests.get", mock_get)
        
        # Create a WeatherApp with our mocked components
        app = None
        try:
            app = WeatherApp()
            
            # Call the method with a test location
            location = ("Test City", 35.0, -80.0)
            app._FetchWeatherData(location)
            
            # Verify that requests.get was called with the proper User-Agent header
            mock_get.assert_called()
            args, kwargs = mock_get.call_args_list[0]
            assert kwargs.get("headers")["User-Agent"] == "AccessiWeather (test@example.com)"
        finally:
            if app:
                app.Destroy()
