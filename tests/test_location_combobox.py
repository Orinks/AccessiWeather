"""Tests for LocationDialog with AccessibleTextCtrl and search history integration"""

from unittest.mock import MagicMock, patch
import unittest
import wx

from accessiweather.gui.dialogs import LocationDialog
# AccessibleTextCtrl is no longer used in the updated implementation
# from accessiweather.gui.ui_components import AccessibleTextCtrl


class TestLocationDialogWithTextCtrl(unittest.TestCase):
    """Test suite for LocationDialog with AccessibleTextCtrl and search history"""

    def setUp(self):
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

    @unittest.skip("Search field is no longer a TextCtrl in the updated implementation")
    def test_search_field_is_text_ctrl(self):
        dialog = LocationDialog(self.frame)
        # This test is skipped because the search field is no longer a TextCtrl
        # in the updated implementation that uses a list-based search approach
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

    def test_duplicate_search_terms_not_added(self):
        dialog = LocationDialog(self.frame)
        self.mock_geocoding.geocode_address.return_value = (35.0, -80.0, "123 Main St, City, State")
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
