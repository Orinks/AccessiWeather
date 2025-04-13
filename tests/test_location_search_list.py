"""Tests for the location search list functionality

This module tests the location search list functionality in the LocationDialog.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.geocoding import GeocodingService
from accessiweather.gui.dialogs import LocationDialog
from accessiweather.gui.ui_components import AccessibleListCtrl, AccessibleTextCtrl


@pytest.fixture
def frame():
    """Create a frame for testing"""
    app = wx.App()
    frame = wx.Frame(None)
    yield frame
    wx.CallAfter(frame.Destroy)
    app.MainLoop()


@pytest.fixture
def mock_geocoding_service():
    """Create a mock geocoding service"""
    service = MagicMock(spec=GeocodingService)

    # Mock the geocode_address method
    service.geocode_address.return_value = (35.0, -80.0, "123 Main St, City, State")

    # Mock the suggest_locations method
    service.suggest_locations.return_value = [
        "New York, NY",
        "New Orleans, LA",
        "Newark, NJ",
    ]

    return service


@pytest.fixture
def safe_destroy():
    """Fixture to safely destroy wx objects"""
    objects = []

    def _safe_destroy(obj):
        objects.append(obj)
        return obj

    yield _safe_destroy

    # Destroy all objects
    for obj in objects:
        if obj and hasattr(obj, "Destroy"):
            try:
                wx.CallAfter(obj.Destroy)
            except Exception:
                pass  # Ignore errors in cleanup


class TestLocationSearchList:
    """Test the location search list functionality"""

    def setup_method(self):
        """Set up test fixture"""
        # Create a wx App if one doesn't exist
        self.app = wx.App() if not wx.GetApp() else wx.GetApp()
        self.frame = wx.Frame(None)

        # Patch the geocoding service
        self.geocoding_patcher = patch("accessiweather.gui.dialogs.GeocodingService")
        self.mock_geocoding = self.geocoding_patcher.start()

        # Configure the mock
        self.mock_geocoding.return_value.geocode_address.return_value = (
            35.0,
            -80.0,
            "123 Main St, City, State",
        )
        self.mock_geocoding.return_value.suggest_locations.return_value = [
            "New York, NY",
            "New Orleans, LA",
            "Newark, NJ",
        ]

    def teardown_method(self):
        """Tear down test fixture"""
        # Stop geocoding patch
        self.geocoding_patcher.stop()

        # Destroy frame safely
        try:
            from accessiweather.gui.async_fetchers import safe_call_after

            safe_call_after(self.frame.Destroy)
        except Exception:
            pass  # Ignore any errors in cleanup

    def test_search_field_is_text_ctrl(self, safe_destroy):
        """Test that the search field is an AccessibleTextCtrl"""
        dialog = safe_destroy(LocationDialog(self.frame))

        # Verify that search_field is an AccessibleTextCtrl
        assert isinstance(dialog.search_field, AccessibleTextCtrl)
        assert dialog.search_field.GetName() == "Search by Address or ZIP Code"

    def test_search_results_list_exists(self, safe_destroy):
        """Test that the search results list exists"""
        dialog = safe_destroy(LocationDialog(self.frame))

        # Verify that search_results_list is an AccessibleListCtrl
        assert isinstance(dialog.search_results_list, AccessibleListCtrl)
        assert dialog.search_results_list.GetName() == "Search Results"

        # Check that the list has the expected columns
        assert dialog.search_results_list.GetColumnCount() == 1
        assert dialog.search_results_list.column_headers[0] == "Location"

    def test_search_button_populates_list(self, safe_destroy):
        """Test that the search button populates the list"""
        dialog = safe_destroy(LocationDialog(self.frame))

        # Set search text
        dialog.search_field.SetValue("New")

        # Trigger search button click
        with patch.object(dialog, "_fetch_search_suggestions") as mock_fetch:
            dialog.OnSearch(None)  # None for the event
            mock_fetch.assert_called_once_with("New")

        # Directly call the search thread function to simulate synchronous behavior
        dialog._search_thread_func("New")

        # Directly call the update function to simulate the CallAfter
        mock_geocoding = self.mock_geocoding.return_value
        suggestions = mock_geocoding.suggest_locations.return_value
        dialog._update_search_results(suggestions)

        # Check that the list was populated
        assert dialog.search_results_list.GetItemCount() == 3
        assert dialog.search_results_list.GetItemText(0, 0) == "New York, NY"
        assert dialog.search_results_list.GetItemText(1, 0) == "New Orleans, LA"
        assert dialog.search_results_list.GetItemText(2, 0) == "Newark, NJ"

    def test_list_item_selection(self, safe_destroy):
        """Test that selecting an item from the list updates the location data"""
        dialog = safe_destroy(LocationDialog(self.frame))

        # Populate the list
        suggestions = ["New York, NY", "New Orleans, LA", "Newark, NJ"]
        dialog._update_search_results(suggestions)

        # Mock the geocode_address method
        mock_geocoding = self.mock_geocoding.return_value
        mock_geocoding.geocode_address.return_value = (40.7128, -74.0060, "New York, NY, USA")

        # Simulate list item selection
        with patch.object(dialog, "_perform_search") as mock_perform_search:
            # Create a list item activated event
            event = wx.ListEvent(wx.wxEVT_LIST_ITEM_ACTIVATED, dialog.search_results_list.GetId())
            event.SetIndex(0)  # Select the first item
            dialog.OnSearchResultSelected(event)

            # Check that search was performed with the selected item
            mock_perform_search.assert_called_once_with("New York, NY")

        # Directly call the search thread function
        dialog._search_thread_func("New York, NY")

        # Directly call the update function
        result = mock_geocoding.geocode_address.return_value
        dialog._update_search_result(result, "New York, NY")

        # Check that the location data was updated
        assert dialog.latitude == 40.7128
        assert dialog.longitude == -74.0060
        assert (
            dialog.result_text.GetValue()
            == "Found: New York, NY, USA\nCoordinates: 40.7128, -74.006"
        )
