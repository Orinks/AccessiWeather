"""Tests for LocationDialog with AccessibleComboBox integration"""

import os
from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.gui.accessible_widgets import AccessibleComboBox
from accessiweather.gui.async_fetchers import safe_call_after
from accessiweather.gui.dialogs import LocationDialog


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
                        # Import moved to top
                        safe_call_after(obj.Destroy)
                    except Exception:
                        pass  # Last resort, just ignore
        except Exception:
            pass  # Ignore any errors in cleanup


# Skip GUI tests in CI environment
@pytest.mark.skipif(
    os.environ.get("ACCESSIWEATHER_TESTING") == "1",
    reason="GUI test skipped in CI",
)
class TestLocationDialogWithComboBox:
    """Test suite for LocationDialog with AccessibleComboBox integration"""

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
        patch_target = "accessiweather.gui.dialogs.GeocodingService"
        self.geocoding_patcher = patch(patch_target)

        self.mock_geocoding_class = self.geocoding_patcher.start()
        self.mock_geocoding = MagicMock()
        self.mock_geocoding_class.return_value = self.mock_geocoding

    def teardown_method(self):
        """Tear down test fixture"""
        # Stop geocoding patch
        self.geocoding_patcher.stop()

        # Destroy frame safely
        try:
            # Import moved to top
            safe_call_after(self.frame.Destroy)
        except Exception:
            pass  # Ignore any errors in cleanup

    def test_search_combo_initialization(self, wx_app, safe_destroy):
        """Test that the search control is an AccessibleComboBox"""
        dialog = safe_destroy(LocationDialog(self.frame))
        # Verify that search_field is an AccessibleComboBox
        assert isinstance(dialog.search_field, AccessibleComboBox)
        assert dialog.search_field.GetName() == "Search by Address or ZIP Code"

        # Check that the combobox is empty initially
        assert dialog.search_field.GetCount() == 0

    def test_search_history_persistence(self, wx_app, safe_destroy):
        """Test that search history is persisted between searches"""
        dialog = safe_destroy(LocationDialog(self.frame))
        self.mock_geocoding.geocode_address.return_value = (
            35.0,
            -80.0,
            "123 Main St, City, State",
        )

        # Perform first search
        dialog.search_field.SetValue("123 Main St")
        with patch("wx.MessageBox"):  # Prevent MessageBox from showing
            # Call directly instead of OnSearch
            dialog._perform_search("123 Main St")

        # Check that the search term is in the dropdown
        assert dialog.search_field.GetCount() == 1
        assert dialog.search_field.GetString(0) == "123 Main St"

        # Perform second search
        dialog.search_field.SetValue("456 Oak Ave")
        self.mock_geocoding.geocode_address.return_value = (
            36.0,
            -81.0,
            "456 Oak Ave, City, State",
        )
        with patch("wx.MessageBox"):  # Prevent MessageBox from showing
            # Call directly instead of OnSearch
            dialog._perform_search("456 Oak Ave")

        # Check that both search terms are in the dropdown
        assert dialog.search_field.GetCount() == 2
        # Most recent should be first in the list
        assert dialog.search_field.GetString(0) == "456 Oak Ave"
        assert dialog.search_field.GetString(1) == "123 Main St"

    def test_combo_selection_triggers_search(self, wx_app, safe_destroy):
        """Test that selecting an item from the dropdown triggers a search"""
        dialog = safe_destroy(LocationDialog(self.frame))
        self.mock_geocoding.geocode_address.return_value = (
            35.0,
            -80.0,
            "123 Main St, City, State",
        )

        # Add some history items
        dialog.search_field.Append(["123 Main St", "456 Oak Ave"])

        # Simulate selection from dropdown
        dialog.search_field.SetSelection(0)  # Select "123 Main St"

        # Create and process a selection event
        event = wx.CommandEvent(wx.wxEVT_COMBOBOX, dialog.search_field.GetId())
        with patch("wx.MessageBox"):  # Prevent MessageBox from showing
            dialog.search_field.GetEventHandler().ProcessEvent(event)

        # Verify that search was triggered with the selected value
        self.mock_geocoding.geocode_address.assert_called_with("123 Main St")

        # Check results are displayed
        assert (
            "Found: 123 Main St, City, State" in dialog.result_text.GetValue()
        )
        assert dialog.latitude == 35.0
        assert dialog.longitude == -80.0

    def test_duplicate_search_terms_not_added(self, wx_app, safe_destroy):
        """Test that duplicate search terms aren't added to history"""
        dialog = safe_destroy(LocationDialog(self.frame))
        self.mock_geocoding.geocode_address.return_value = (
            35.0,
            -80.0,
            "123 Main St, City, State",
        )

        # First search
        dialog.search_field.SetValue("123 Main St")
        with patch("wx.MessageBox"):  # Prevent MessageBox from showing
            # Call directly instead of OnSearch
            dialog._perform_search("123 Main St")
        assert dialog.search_field.GetCount() == 1

        # Same search again
        dialog.search_field.SetValue("123 Main St")
        with patch("wx.MessageBox"):  # Prevent MessageBox from showing
            # Call directly instead of OnSearch
            dialog._perform_search("123 Main St")

        # Should still only have one item
        assert dialog.search_field.GetCount() == 1
        assert dialog.search_field.GetString(0) == "123 Main St"

    def test_max_history_items(self, wx_app, safe_destroy):
        """Test that only a limited number of search terms are kept"""
        dialog = safe_destroy(LocationDialog(self.frame))
        self.mock_geocoding.geocode_address.return_value = (
            35.0,
            -80.0,
            "Address",
        )

        # Add max_history_items + 1 searches
        # MAX_HISTORY_ITEMS should be defined in LocationDialog
        max_items = dialog.MAX_HISTORY_ITEMS

        for i in range(max_items + 2):
            search_term = f"Search {i}"
            dialog.search_field.SetValue(search_term)
            with patch("wx.MessageBox"):  # Prevent MessageBox from showing
                # Call directly instead of OnSearch
                dialog._perform_search(search_term)

        # Check that only max_items are kept
        assert dialog.search_field.GetCount() == max_items

        # Check that oldest item was removed (first one)
        assert dialog.search_field.GetString(max_items - 1) != "Search 0"
        # Check that newest is at the top
        assert dialog.search_field.GetString(0) == f"Search {max_items + 1}"
