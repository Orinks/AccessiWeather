"""Tests for the location dialog UI components"""

import pytest
import wx
from unittest.mock import patch, MagicMock

# Create a wx App fixture for testing
@pytest.fixture(scope="module", autouse=True)
def wx_app():
    """Create a wx App for testing"""
    app = wx.App(False)
    yield app

from noaa_weather_app.gui import LocationDialog, AdvancedLocationDialog


class TestAdvancedLocationDialog:
    """Test suite for AdvancedLocationDialog"""
    
    def setup_method(self):
        """Set up test fixture"""
        # Create parent frame
        self.frame = wx.Frame(None)
        
    def teardown_method(self):
        """Tear down test fixture"""
        # Destroy frame
        wx.CallAfter(self.frame.Destroy)
    
    def test_init(self):
        """Test initialization"""
        dialog = AdvancedLocationDialog(self.frame, lat=35.0, lon=-80.0)
        try:
            # Check initial values
            assert dialog.lat_ctrl.GetValue() == "35.0"
            assert dialog.lon_ctrl.GetValue() == "-80.0"
        finally:
            wx.CallAfter(dialog.Destroy)
    
    def test_get_values(self):
        """Test getting values from dialog"""
        dialog = AdvancedLocationDialog(self.frame)
        try:
            # Set values
            dialog.lat_ctrl.SetValue("35.5")
            dialog.lon_ctrl.SetValue("-80.5")
            
            # Get values
            lat, lon = dialog.GetValues()
            assert lat == 35.5
            assert lon == -80.5
        finally:
            wx.CallAfter(dialog.Destroy)
    
    def test_validation_success(self):
        """Test validation with valid inputs"""
        dialog = AdvancedLocationDialog(self.frame)
        try:
            # Set values
            dialog.lat_ctrl.SetValue("35.0")
            dialog.lon_ctrl.SetValue("-80.0")
            
            # Create mock event
            event = MagicMock()
            event.Skip = MagicMock()
            
            # Call OnOK
            dialog.OnOK(event)
            
            # Check that event.Skip was called
            event.Skip.assert_called_once()
        finally:
            wx.CallAfter(dialog.Destroy)
    
    def test_validation_invalid_lat(self):
        """Test validation with invalid latitude"""
        with patch('wx.MessageBox') as mock_message_box:
            dialog = AdvancedLocationDialog(self.frame)
            try:
                # Set values
                dialog.lat_ctrl.SetValue("invalid")
                dialog.lon_ctrl.SetValue("-80.0")
                
                # Create mock event
                event = MagicMock()
                event.Skip = MagicMock()
                
                # Call OnOK
                dialog.OnOK(event)
                
                # Check that event.Skip was not called
                event.Skip.assert_not_called()
                
                # Check that MessageBox was called
                mock_message_box.assert_called_once()
            finally:
                wx.CallAfter(dialog.Destroy)
    
    def test_validation_invalid_lon(self):
        """Test validation with invalid longitude"""
        with patch('wx.MessageBox') as mock_message_box:
            dialog = AdvancedLocationDialog(self.frame)
            try:
                # Set values
                dialog.lat_ctrl.SetValue("35.0")
                dialog.lon_ctrl.SetValue("invalid")
                
                # Create mock event
                event = MagicMock()
                event.Skip = MagicMock()
                
                # Call OnOK
                dialog.OnOK(event)
                
                # Check that event.Skip was not called
                event.Skip.assert_not_called()
                
                # Check that MessageBox was called
                mock_message_box.assert_called_once()
            finally:
                wx.CallAfter(dialog.Destroy)


class TestLocationDialog:
    """Test suite for LocationDialog"""
    
    def setup_method(self):
        """Set up test fixture"""
        # Create parent frame
        self.frame = wx.Frame(None)
        
        # Create patch for geocoding service
        self.geocoding_patcher = patch('noaa_weather_app.gui.dialogs.GeocodingService')
        self.mock_geocoding_class = self.geocoding_patcher.start()
        self.mock_geocoding = MagicMock()
        self.mock_geocoding_class.return_value = self.mock_geocoding
        
    def teardown_method(self):
        """Tear down test fixture"""
        # Stop geocoding patch
        self.geocoding_patcher.stop()
        
        # Destroy frame
        wx.CallAfter(self.frame.Destroy)
    
    def test_init(self):
        """Test initialization"""
        dialog = LocationDialog(self.frame, location_name="Home", lat=35.0, lon=-80.0)
        try:
            # Check initial values
            assert dialog.name_ctrl.GetValue() == "Home"
            assert dialog.latitude == 35.0
            assert dialog.longitude == -80.0
            assert dialog.result_text.GetValue() == "Custom coordinates: 35.0, -80.0"
        finally:
            wx.CallAfter(dialog.Destroy)
    
    def test_get_values(self):
        """Test getting values from dialog"""
        dialog = LocationDialog(self.frame, location_name="Home", lat=35.0, lon=-80.0)
        try:
            # Get values
            name, lat, lon = dialog.GetValues()
            assert name == "Home"
            assert lat == 35.0
            assert lon == -80.0
        finally:
            wx.CallAfter(dialog.Destroy)
    
    def test_search_success(self):
        """Test successful location search"""
        # Set up mock geocoding service
        self.mock_geocoding.geocode_address.return_value = (35.0, -80.0, "123 Main St, City, State")
        
        dialog = LocationDialog(self.frame)
        try:
            # Set search query
            dialog.search_ctrl.SetValue("123 Main St")
            
            # Call search method
            dialog.OnSearch(None)
            
            # Check that geocoding service was called
            self.mock_geocoding.geocode_address.assert_called_once_with("123 Main St")
            
            # Check result
            assert dialog.latitude == 35.0
            assert dialog.longitude == -80.0
            assert "Found: 123 Main St, City, State" in dialog.result_text.GetValue()
        finally:
            wx.CallAfter(dialog.Destroy)
    
    def test_search_not_found(self):
        """Test location search with no results"""
        # Set up mock geocoding service
        self.mock_geocoding.geocode_address.return_value = None
        
        dialog = LocationDialog(self.frame)
        try:
            # Set search query
            dialog.search_ctrl.SetValue("Nonexistent Address")
            
            # Call search method
            dialog.OnSearch(None)
            
            # Check that geocoding service was called
            self.mock_geocoding.geocode_address.assert_called_once_with("Nonexistent Address")
            
            # Check result
            assert "No results found" in dialog.result_text.GetValue()
        finally:
            wx.CallAfter(dialog.Destroy)
    
    def test_search_auto_name(self):
        """Test that search automatically suggests a name"""
        # Set up mock geocoding service
        self.mock_geocoding.geocode_address.return_value = (35.0, -80.0, "123 Main St, City, State")
        
        dialog = LocationDialog(self.frame)
        try:
            # Set search query but leave name empty
            dialog.search_ctrl.SetValue("123 Main St")
            dialog.name_ctrl.SetValue("")
            
            # Call search method
            dialog.OnSearch(None)
            
            # Check that name was suggested
            assert dialog.name_ctrl.GetValue() == "123 Main St"
        finally:
            wx.CallAfter(dialog.Destroy)
    
    @patch('noaa_weather_app.gui.dialogs.AdvancedLocationDialog')
    def test_advanced_dialog(self, mock_advanced_dialog_class):
        """Test opening advanced dialog"""
        # Set up mock advanced dialog
        mock_advanced_dialog = MagicMock()
        mock_advanced_dialog.ShowModal.return_value = wx.ID_OK
        mock_advanced_dialog.GetValues.return_value = (40.0, -75.0)
        mock_advanced_dialog_class.return_value = mock_advanced_dialog
        
        dialog = LocationDialog(self.frame, lat=35.0, lon=-80.0)
        try:
            # Call advanced method
            dialog.OnAdvanced(None)
            
            # Check that advanced dialog was created with correct parameters
            mock_advanced_dialog_class.assert_called_once_with(dialog, lat=35.0, lon=-80.0)
            
            # Check that ShowModal was called
            mock_advanced_dialog.ShowModal.assert_called_once()
            
            # Check that GetValues was called
            mock_advanced_dialog.GetValues.assert_called_once()
            
            # Check that values were updated
            assert dialog.latitude == 40.0
            assert dialog.longitude == -75.0
            assert "Custom coordinates: 40.0" in dialog.result_text.GetValue()
        finally:
            wx.CallAfter(dialog.Destroy)
    
    def test_validation_success(self):
        """Test validation with valid inputs"""
        dialog = LocationDialog(self.frame, location_name="Home", lat=35.0, lon=-80.0)
        try:
            # Create mock event
            event = MagicMock()
            event.Skip = MagicMock()
            
            # Call OnOK
            dialog.OnOK(event)
            
            # Check that event.Skip was called
            event.Skip.assert_called_once()
        finally:
            wx.CallAfter(dialog.Destroy)
    
    def test_validation_no_name(self):
        """Test validation with no name"""
        with patch('wx.MessageBox') as mock_message_box:
            dialog = LocationDialog(self.frame, lat=35.0, lon=-80.0)
            try:
                # Set empty name
                dialog.name_ctrl.SetValue("")
                
                # Create mock event
                event = MagicMock()
                event.Skip = MagicMock()
                
                # Call OnOK
                dialog.OnOK(event)
                
                # Check that event.Skip was not called
                event.Skip.assert_not_called()
                
                # Check that MessageBox was called
                mock_message_box.assert_called_once()
                # Check that first argument mentions name
                assert "name" in mock_message_box.call_args[0][0].lower()
            finally:
                wx.CallAfter(dialog.Destroy)
    
    def test_validation_no_location(self):
        """Test validation with no location"""
        with patch('wx.MessageBox') as mock_message_box:
            dialog = LocationDialog(self.frame)
            try:
                # Set name but no location
                dialog.name_ctrl.SetValue("Home")
                dialog.latitude = None
                dialog.longitude = None
                
                # Create mock event
                event = MagicMock()
                event.Skip = MagicMock()
                
                # Call OnOK
                dialog.OnOK(event)
                
                # Check that event.Skip was not called
                event.Skip.assert_not_called()
                
                # Check that MessageBox was called
                mock_message_box.assert_called_once()
                # Check that first argument mentions location
                assert "location" in mock_message_box.call_args[0][0].lower()
            finally:
                wx.CallAfter(dialog.Destroy)
