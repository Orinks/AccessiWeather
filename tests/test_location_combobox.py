"""Tests for LocationDialog with AccessibleTextCtrl and search history integration"""

from unittest.mock import MagicMock, patch

import unittest
from unittest.mock import MagicMock, patch
import wx
<<<<<<< Updated upstream

from accessiweather.gui.dialogs import LocationDialog
from accessiweather.gui.ui_components import AccessibleComboBox


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


class TestLocationDialogWithComboBox:
    """Test suite for LocationDialog with AccessibleComboBox integration"""

    def setup_method(self):
        """Set up test fixture"""
=======
from accessiweather.gui.dialogs import LocationDialog
from accessiweather.gui.ui_components import AccessibleTextCtrl

class TestLocationDialogWithTextCtrl(unittest.TestCase):
    """Test suite for LocationDialog with AccessibleTextCtrl and search history"""

    def setUp(self):
>>>>>>> Stashed changes
        # Ensure wx.App exists
        if not wx.App.Get():
            self.app = wx.App(False)
        else:
            self.app = wx.App.Get()
        # Create parent frame
        self.frame = wx.Frame(None)
        # Create patch for geocoding service
        self.geocoding_patcher = patch("accessiweather.gui.dialogs.GeocodingService")
        self.mock_geocoding_class = self.geocoding_patcher.start()
        self.mock_geocoding = MagicMock()
        self.mock_geocoding_class.return_value = self.mock_geocoding

    def tearDown(self):
        # Stop geocoding patch
        self.geocoding_patcher.stop()
        # Destroy frame safely
        try:
            from accessiweather.gui.async_fetchers import safe_call_after
            safe_call_after(self.frame.Destroy)
        except Exception:
            pass  # Ignore any errors in cleanup

    def test_search_field_is_text_ctrl(self):
        dialog = LocationDialog(self.frame)
        self.assertIsInstance(dialog.search_field, AccessibleTextCtrl)
        self.assertEqual(dialog.search_field.GetName(), "Search by Address or ZIP Code")
        dialog.Destroy()

    def test_search_history_persistence(self):
        dialog = LocationDialog(self.frame)
        self.mock_geocoding.geocode_address.return_value = (35.0, -80.0, "123 Main St, City, State")
        dialog.search_field.SetValue("123 Main St")
        with patch("wx.MessageBox"):
            dialog._perform_search("123 Main St")
            dialog._search_thread_func("123 Main St")
            result = self.mock_geocoding.geocode_address.return_value
            dialog._update_search_result(result, "123 Main St")
        self.assertEqual(len(dialog.search_history), 1)
        self.assertEqual(dialog.search_history[0], "123 Main St")
        dialog.search_field.SetValue("456 Oak Ave")
        self.mock_geocoding.geocode_address.return_value = (36.0, -81.0, "456 Oak Ave, City, State")
        with patch("wx.MessageBox"):
            dialog._perform_search("456 Oak Ave")
            dialog._search_thread_func("456 Oak Ave")
            result = self.mock_geocoding.geocode_address.return_value
            dialog._update_search_result(result, "456 Oak Ave")
        self.assertEqual(len(dialog.search_history), 2)
        self.assertEqual(dialog.search_history[0], "456 Oak Ave")
        self.assertEqual(dialog.search_history[1], "123 Main St")
        dialog.Destroy()

<<<<<<< Updated upstream
        # Check that both search terms are in the dropdown
        assert dialog.search_field.GetCount() == 2
        # Most recent should be first in the list
        assert dialog.search_field.GetString(0) == "456 Oak Ave"
        assert dialog.search_field.GetString(1) == "123 Main St"

    def test_combo_selection_triggers_search(self, wx_app, safe_destroy):
        """Test that selecting an item from the dropdown triggers a search"""
        dialog = safe_destroy(LocationDialog(self.frame))

        # Mock the _perform_search method
        dialog._perform_search = MagicMock()

        # Add some history items
        dialog.search_field.Append(["123 Main St", "456 Oak Ave"])

        # Simulate selection from dropdown
        dialog.search_field.SetSelection(0)  # Select "123 Main St"

        # Create a dummy event
        event = wx.CommandEvent(wx.wxEVT_COMBOBOX, dialog.search_field.GetId())

        # Trigger the combobox selection event
        dialog._on_combobox_select(event)

        # Verify that _perform_search was called with the selected value
        dialog._perform_search.assert_called_once_with("123 Main St")

    def test_duplicate_search_terms_not_added(self, wx_app, safe_destroy):
        """Test that duplicate search terms aren't added to history"""
        dialog = safe_destroy(LocationDialog(self.frame))
        self.mock_geocoding.geocode_address.return_value = (35.0, -80.0, "123 Main St, City, State")

        # First search
=======
    def test_duplicate_search_terms_not_added(self):
        dialog = LocationDialog(self.frame)
        self.mock_geocoding.geocode_address.return_value = (35.0, -80.0, "123 Main St, City, State")
>>>>>>> Stashed changes
        dialog.search_field.SetValue("123 Main St")
        with patch("wx.MessageBox"):
            dialog._perform_search("123 Main St")
            dialog._search_thread_func("123 Main St")
            result = self.mock_geocoding.geocode_address.return_value
            dialog._update_search_result(result, "123 Main St")
        self.assertEqual(len(dialog.search_history), 1)
        dialog.search_field.SetValue("123 Main St")
        with patch("wx.MessageBox"):
            dialog._perform_search("123 Main St")
            dialog._search_thread_func("123 Main St")
            result = self.mock_geocoding.geocode_address.return_value
            dialog._update_search_result(result, "123 Main St")
        self.assertEqual(len(dialog.search_history), 1)
        self.assertEqual(dialog.search_history[0], "123 Main St")
        dialog.Destroy()

    def test_max_history_items(self):
        dialog = LocationDialog(self.frame)
        self.mock_geocoding.geocode_address.return_value = (35.0, -80.0, "Address")
        max_items = getattr(dialog, "MAX_HISTORY_ITEMS", 10)
        for i in range(max_items + 2):
            search_term = f"Search {i}"
            dialog.search_field.SetValue(search_term)
            with patch("wx.MessageBox"):
                dialog._perform_search(search_term)
                dialog._search_thread_func(search_term)
                result = self.mock_geocoding.geocode_address.return_value
                dialog._update_search_result(result, search_term)
        self.assertEqual(len(dialog.search_history), max_items)
        self.assertNotIn("Search 0", dialog.search_history)
        self.assertEqual(dialog.search_history[0], f"Search {max_items + 1}")
        dialog.Destroy()

    def test_search_triggers_geocode_and_result(self):
        dialog = LocationDialog(self.frame)
        self.mock_geocoding.geocode_address.return_value = (35.0, -80.0, "123 Main St, City, State")
        dialog.search_field.SetValue("123 Main St")
        with patch("wx.MessageBox"):
            dialog._perform_search("123 Main St")
            dialog._search_thread_func("123 Main St")
            result = self.mock_geocoding.geocode_address.return_value
            dialog._update_search_result(result, "123 Main St")
        self.mock_geocoding.geocode_address.assert_called_with("123 Main St")
        self.assertIn("Found: 123 Main St, City, State", dialog.result_text.GetValue())
        self.assertEqual(dialog.latitude, 35.0)
        self.assertEqual(dialog.longitude, -80.0)
        dialog.Destroy()

if __name__ == "__main__":
    unittest.main()
