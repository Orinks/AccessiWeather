"""Tests for LocationDialog with search functionality"""

# Import faulthandler setup first to enable faulthandler
import tests.faulthandler_setup

import time
from unittest.mock import MagicMock, patch

import pytest
import wx

# Import modules
from accessiweather.gui.dialogs import LocationDialog
from accessiweather.gui.ui_components import AccessibleListCtrl, AccessibleTextCtrl


# Create a wx App fixture for testing
@pytest.fixture(scope="module")
def wx_app():
    """Create a wx App for testing"""
    app = wx.App(False)
    yield app


# Fixture to safely destroy wx objects
@pytest.fixture
def safe_destroy():
    """Fixture to safely destroy wx objects even without an app"""
    objs_to_destroy = []

    def _register(obj):
        objs_to_destroy.append(obj)
        return obj

    yield _register

    for obj in reversed(objs_to_destroy):
        try:
            if hasattr(obj, "Destroy") and callable(obj.Destroy):
                # Try direct destroy first
                try:
                    obj.Destroy()
                except Exception:
                    # If direct destroy fails, try wxPython's safe way
                    try:
                        from accessiweather.gui.async_fetchers import safe_call_after

                        safe_call_after(obj.Destroy)
                    except Exception:
                        pass  # Last resort, just ignore
        except Exception:
            pass  # Ignore any errors in cleanup


class TestLocationDialog:
    """Test suite for LocationDialog search functionality"""

    def setup_method(self):
        """Set up test fixture"""
        # Ensure wx.App exists
        try:
            app = wx.GetApp()
            if app is None:
                self.app = wx.App(False)
        except Exception:
            self.app = wx.App(False)

        # Create parent frame
        self.frame = wx.Frame(None)

        # Create patch for geocoding service
        self.geocoding_patcher = patch("accessiweather.gui.dialogs.GeocodingService")
        self.mock_geocoding_class = self.geocoding_patcher.start()
        self.mock_geocoding = MagicMock()
        self.mock_geocoding_class.return_value = self.mock_geocoding

    def teardown_method(self):
        """Tear down test fixture"""
        # Stop geocoding patch
        self.geocoding_patcher.stop()

        # Destroy frame safely
        # Hide the window first
        wx.CallAfter(self.frame.Hide)
        wx.SafeYield()
        # Then destroy it
        wx.CallAfter(self.frame.Destroy)
        wx.SafeYield()

    def test_search_field_initialization(self, safe_destroy):
        """Test that the search control is an AccessibleTextCtrl"""
        dialog = safe_destroy(LocationDialog(self.frame))
        # Verify that search_field is an AccessibleTextCtrl
        assert isinstance(dialog.search_field, AccessibleTextCtrl)
        assert dialog.search_field.GetName() == "Search by Address or ZIP Code"

    def test_search_results_list_initialization(self, safe_destroy):
        """Test that the search results list is properly initialized"""
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

        # Configure mock
        self.mock_geocoding.suggest_locations.return_value = [
            "New York, NY",
            "New Orleans, LA",
            "Newark, NJ",
        ]

        # Set search text
        dialog.search_field.SetValue("New")

        # Trigger search button click
        with patch.object(dialog, "_fetch_search_suggestions") as mock_fetch:
            dialog.OnSearch(None)  # None for the event
            mock_fetch.assert_called_once_with("New")

        # Directly call the update function
        suggestions = self.mock_geocoding.suggest_locations.return_value
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
        self.mock_geocoding.geocode_address.return_value = (40.7128, -74.0060, "New York, NY, USA")

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
        result = self.mock_geocoding.geocode_address.return_value
        dialog._update_search_result(result, "New York, NY")

        # Check that the location data was updated
        assert dialog.latitude == 40.7128
        assert dialog.longitude == -74.0060
        assert (
            dialog.result_text.GetValue()
            == "Found: New York, NY, USA\nCoordinates: 40.7128, -74.006"
        )

    def test_search_history_persistence(self, safe_destroy):
        """Test that search history is persisted between searches"""
        dialog = safe_destroy(LocationDialog(self.frame))
        self.mock_geocoding.geocode_address.return_value = (35.0, -80.0, "123 Main St, City, State")

        # Perform first search
        dialog.search_field.SetValue("123 Main St")
        with patch("wx.MessageBox"):  # Prevent MessageBox from showing
            # Call directly instead of OnSearch
            dialog._perform_search("123 Main St")
            # Directly call the thread function to simulate synchronous behavior for testing
            dialog._search_thread_func("123 Main St")
            # Directly call the update function to simulate the CallAfter
            result = self.mock_geocoding.geocode_address.return_value
            dialog._update_search_result(result, "123 Main St")

        # Check that the search term is in the history
        assert "123 Main St" in dialog.search_history
        assert dialog.search_history[0] == "123 Main St"

        # Perform second search
        dialog.search_field.SetValue("456 Oak Ave")
        self.mock_geocoding.geocode_address.return_value = (36.0, -81.0, "456 Oak Ave, City, State")
        with patch("wx.MessageBox"):  # Prevent MessageBox from showing
            # Call directly instead of OnSearch
            dialog._perform_search("456 Oak Ave")
            # Directly call the thread function to simulate synchronous behavior for testing
            dialog._search_thread_func("456 Oak Ave")
            # Directly call the update function to simulate the CallAfter
            result = self.mock_geocoding.geocode_address.return_value
            dialog._update_search_result(result, "456 Oak Ave")

        # Check that both search terms are in the history
        assert len(dialog.search_history) == 2
        # Most recent should be first in the list
        assert dialog.search_history[0] == "456 Oak Ave"
        assert dialog.search_history[1] == "123 Main St"

    def test_duplicate_search_terms_not_added(self, safe_destroy):
        """Test that duplicate search terms aren't added to history"""
        dialog = safe_destroy(LocationDialog(self.frame))
        self.mock_geocoding.geocode_address.return_value = (35.0, -80.0, "123 Main St, City, State")

        # First search
        dialog.search_field.SetValue("123 Main St")
        with patch("wx.MessageBox"):  # Prevent MessageBox from showing
            # Call directly instead of OnSearch
            dialog._perform_search("123 Main St")
            dialog._search_thread_func("123 Main St")
            result = self.mock_geocoding.geocode_address.return_value
            dialog._update_search_result(result, "123 Main St")
        assert len(dialog.search_history) == 1

        # Same search again
        dialog.search_field.SetValue("123 Main St")
        with patch("wx.MessageBox"):  # Prevent MessageBox from showing
            # Call directly instead of OnSearch
            dialog._perform_search("123 Main St")
            dialog._search_thread_func("123 Main St")
            result = self.mock_geocoding.geocode_address.return_value
            dialog._update_search_result(result, "123 Main St")

        # Should still only have one item
        assert len(dialog.search_history) == 1
        assert dialog.search_history[0] == "123 Main St"

    def test_max_history_items(self, safe_destroy):
        """Test that only a limited number of search terms are kept"""
        dialog = safe_destroy(LocationDialog(self.frame))
        self.mock_geocoding.geocode_address.return_value = (35.0, -80.0, "Address")

        # Add max_history_items + 1 searches
        max_items = dialog.MAX_HISTORY_ITEMS  # This should be defined in the LocationDialog class

        for i in range(max_items + 2):
            search_term = f"Search {i}"
            dialog.search_field.SetValue(search_term)
            with patch("wx.MessageBox"):  # Prevent MessageBox from showing
                # Call directly instead of OnSearch
                dialog._perform_search(search_term)
                dialog._search_thread_func(search_term)
                result = self.mock_geocoding.geocode_address.return_value
                dialog._update_search_result(result, search_term)

        # Check that only max_items are kept
        assert len(dialog.search_history) == max_items

        # Check that oldest item was removed (first one)
        assert "Search 0" not in dialog.search_history
        # Check that newest is at the top
        assert dialog.search_history[0] == f"Search {max_items + 1}"

    def test_detailed_location_name(self, safe_destroy):
        """Test that the detailed location name is created correctly"""
        dialog = safe_destroy(LocationDialog(self.frame))

        # Test full address
        full_address = "Scottsburg, Scott County, Indiana, USA"
        detailed_name = dialog._create_detailed_location_name(full_address, "Scottsburg")
        assert detailed_name == full_address

        # Test international address
        intl_address = "Paris, Île-de-France, France"
        detailed_name = dialog._create_detailed_location_name(intl_address, "Paris")
        assert detailed_name == intl_address

        # Test simple address with only two parts
        simple_address = "London, UK"
        detailed_name = dialog._create_detailed_location_name(simple_address, "London")
        assert detailed_name == simple_address

        # Test address with no commas
        no_comma_address = "Somewhere"
        detailed_name = dialog._create_detailed_location_name(no_comma_address, "Somewhere")
        assert detailed_name == "Somewhere"

    def test_detailed_name_used_in_search_result(self, safe_destroy):
        """Test that the detailed location name is used when a search result is selected"""
        dialog = safe_destroy(LocationDialog(self.frame))

        # Mock the geocode_address method to return a full address
        self.mock_geocoding.geocode_address.return_value = (
            38.6851, -85.7702, "Scottsburg, Scott County, Indiana, USA"
        )

        # Perform search
        dialog.search_field.SetValue("Scottsburg")
        with patch("wx.MessageBox"):  # Prevent MessageBox from showing
            # Call directly instead of OnSearch
            dialog._perform_search("Scottsburg")
            dialog._search_thread_func("Scottsburg")
            result = self.mock_geocoding.geocode_address.return_value
            dialog._update_search_result(result, "Scottsburg")

        # Check that the name field was populated with the detailed name
        assert dialog.name_ctrl.GetValue() == "Scottsburg, Scott County, Indiana, USA"
