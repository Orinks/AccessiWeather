"""Tests for the GUI components"""

import pytest
import wx
from unittest.mock import patch, MagicMock

from noaa_weather_app.gui import LocationDialog, WeatherDiscussionDialog


# We need a wx App for testing wx components
@pytest.fixture(scope="module")
def wx_app():
    """Create a wx App for testing"""
    app = wx.App()
    yield app


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
