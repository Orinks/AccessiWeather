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
    
    def test_init(self, wx_app):
        """Test initialization"""
        dialog = LocationDialog(None, title="Test Dialog", location_name="Test", lat=35.0, lon=-80.0)
        try:
            assert dialog.name_ctrl.GetValue() == "Test"
            assert dialog.lat_ctrl.GetValue() == "35.0"
            assert dialog.lon_ctrl.GetValue() == "-80.0"
        finally:
            dialog.Destroy()
    
    def test_validation(self, wx_app):
        """Test input validation"""
        dialog = LocationDialog(None)
        try:
            # Test with valid inputs
            dialog.name_ctrl.SetValue("Test")
            dialog.lat_ctrl.SetValue("35.0")
            dialog.lon_ctrl.SetValue("-80.0")
            
            # Mock the event
            event = MagicMock()
            dialog.OnOK(event)
            
            # Skip should have been called for valid inputs
            event.Skip.assert_called_once()
            
            # Test with invalid latitude
            event.reset_mock()
            dialog.lat_ctrl.SetValue("invalid")
            
            # Need to patch MessageBox
            with patch('wx.MessageBox') as mock_message_box:
                dialog.OnOK(event)
                
                # Skip should not have been called
                assert not event.Skip.called
                
                # MessageBox should have been called
                mock_message_box.assert_called_once()
                args = mock_message_box.call_args[0]
                assert "Invalid latitude" in args[0]
        finally:
            dialog.Destroy()
    
    def test_get_values(self, wx_app):
        """Test getting values from the dialog"""
        dialog = LocationDialog(None)
        try:
            dialog.name_ctrl.SetValue("Test")
            dialog.lat_ctrl.SetValue("35.0")
            dialog.lon_ctrl.SetValue("-80.0")
            
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
