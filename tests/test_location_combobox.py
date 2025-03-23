"""Tests for LocationDialog with AccessibleComboBox integration"""

import pytest
import wx
from unittest.mock import patch, MagicMock

# Create a wx App fixture for testing
@pytest.fixture(scope="module", autouse=True)
def wx_app():
    """Create a wx App for testing"""
    app = wx.App(False)
    yield app

# Import after wx.App is created
from noaa_weather_app.gui import LocationDialog
from noaa_weather_app.gui.ui_components import AccessibleComboBox


class TestLocationDialogWithComboBox:
    """Test suite for LocationDialog with AccessibleComboBox integration"""
    
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
    
    def test_search_combo_initialization(self):
        """Test that the search control is an AccessibleComboBox"""
        dialog = LocationDialog(self.frame)
        try:
            # Verify that search_ctrl is an AccessibleComboBox
            assert isinstance(dialog.search_ctrl, AccessibleComboBox)
            assert dialog.search_ctrl.GetName() == "Search by Address or ZIP Code"
            
            # Check that the combobox is empty initially
            assert dialog.search_ctrl.GetCount() == 0
        finally:
            wx.CallAfter(dialog.Destroy)
    
    def test_search_history_persistence(self):
        """Test that search history is persisted between searches"""
        dialog = LocationDialog(self.frame)
        self.mock_geocoding.geocode_address.return_value = (35.0, -80.0, "123 Main St, City, State")
        
        try:
            # Perform first search
            dialog.search_ctrl.SetValue("123 Main St")
            dialog.OnSearch(None)
            
            # Check that the search term is in the dropdown
            assert dialog.search_ctrl.GetCount() == 1
            assert dialog.search_ctrl.GetString(0) == "123 Main St"
            
            # Perform second search
            dialog.search_ctrl.SetValue("456 Oak Ave")
            self.mock_geocoding.geocode_address.return_value = (36.0, -81.0, "456 Oak Ave, City, State")
            dialog.OnSearch(None)
            
            # Check that both search terms are in the dropdown
            assert dialog.search_ctrl.GetCount() == 2
            # Most recent should be first in the list
            assert dialog.search_ctrl.GetString(0) == "456 Oak Ave"
            assert dialog.search_ctrl.GetString(1) == "123 Main St"
        finally:
            wx.CallAfter(dialog.Destroy)
    
    def test_combo_selection_triggers_search(self):
        """Test that selecting an item from the dropdown triggers a search"""
        dialog = LocationDialog(self.frame)
        self.mock_geocoding.geocode_address.return_value = (35.0, -80.0, "123 Main St, City, State")
        
        try:
            # Add some history items
            dialog.search_ctrl.Append(["123 Main St", "456 Oak Ave"])
            
            # Simulate selection from dropdown
            dialog.search_ctrl.SetSelection(0)  # Select "123 Main St"
            
            # Create and process a selection event
            event = wx.CommandEvent(wx.wxEVT_COMBOBOX, dialog.search_ctrl.GetId())
            dialog.search_ctrl.GetEventHandler().ProcessEvent(event)
            
            # Verify that search was triggered with the selected value
            self.mock_geocoding.geocode_address.assert_called_with("123 Main St")
            
            # Check results are displayed
            assert "Found: 123 Main St, City, State" in dialog.result_text.GetValue()
            assert dialog.latitude == 35.0
            assert dialog.longitude == -80.0
        finally:
            wx.CallAfter(dialog.Destroy)
    
    def test_duplicate_search_terms_not_added(self):
        """Test that duplicate search terms aren't added to history"""
        dialog = LocationDialog(self.frame)
        self.mock_geocoding.geocode_address.return_value = (35.0, -80.0, "123 Main St, City, State")
        
        try:
            # First search
            dialog.search_ctrl.SetValue("123 Main St")
            dialog.OnSearch(None)
            assert dialog.search_ctrl.GetCount() == 1
            
            # Same search again
            dialog.search_ctrl.SetValue("123 Main St")
            dialog.OnSearch(None)
            
            # Should still only have one item
            assert dialog.search_ctrl.GetCount() == 1
            assert dialog.search_ctrl.GetString(0) == "123 Main St"
        finally:
            wx.CallAfter(dialog.Destroy)
    
    def test_max_history_items(self):
        """Test that only a limited number of search terms are kept"""
        dialog = LocationDialog(self.frame)
        self.mock_geocoding.geocode_address.return_value = (35.0, -80.0, "Address")
        
        try:
            # Add max_history_items + 1 searches
            max_items = dialog.MAX_HISTORY_ITEMS  # This should be defined in the LocationDialog class
            
            for i in range(max_items + 2):
                search_term = f"Search {i}"
                dialog.search_ctrl.SetValue(search_term)
                dialog.OnSearch(None)
            
            # Check that only max_items are kept
            assert dialog.search_ctrl.GetCount() == max_items
            
            # Check that oldest item was removed (first one)
            assert dialog.search_ctrl.GetString(max_items - 1) != "Search 0"
            # Check that newest is at the top
            assert dialog.search_ctrl.GetString(0) == f"Search {max_items + 1}"
        finally:
            wx.CallAfter(dialog.Destroy)
