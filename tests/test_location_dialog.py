"""Tests for the location dialog UI components"""

from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.gui.dialogs import AdvancedLocationDialog, LocationDialog
from tests.gui_test_fixtures import process_ui_events, ui_component_frame


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
                    # Process events to ensure UI updates are applied
                    process_ui_events()
                except Exception:
                    # If direct destroy fails, try wxPython's safe way
                    try:
                        from accessiweather.gui.async_fetchers import safe_call_after

                        safe_call_after(obj.Destroy)
                        process_ui_events()
                    except Exception:
                        pass  # Last resort, just ignore
        except Exception:
            pass  # Ignore any errors in cleanup


class TestAdvancedLocationDialog:
    """Test suite for AdvancedLocationDialog"""

    @pytest.fixture(autouse=True)
    def setup_frame(self, ui_component_frame):
        """Set up test fixture with a frame for the dialog.

        Args:
            ui_component_frame: The frame fixture from gui_test_fixtures
        """
        self.frame = ui_component_frame

    def test_init(self, safe_destroy):
        """Test initialization"""
        dialog = safe_destroy(AdvancedLocationDialog(self.frame, lat=35.0, lon=-80.0))
        try:
            # Check initial values
            assert dialog.lat_ctrl.GetValue() == "35.0"
            assert dialog.lon_ctrl.GetValue() == "-80.0"

            # Process events to ensure UI updates are applied
            process_ui_events()
        finally:
            dialog.Destroy()
            process_ui_events()

    def test_get_values(self, safe_destroy):
        """Test getting values from dialog"""
        dialog = safe_destroy(AdvancedLocationDialog(self.frame))
        try:
            # Set values
            dialog.lat_ctrl.SetValue("35.5")
            dialog.lon_ctrl.SetValue("-80.5")

            # Process events to ensure UI updates are applied
            process_ui_events()

            # Get values
            lat, lon = dialog.GetValues()
            assert lat == 35.5
            assert lon == -80.5
        finally:
            dialog.Destroy()
            process_ui_events()

    def test_validation_success(self, safe_destroy):
        """Test validation with valid inputs"""
        dialog = safe_destroy(AdvancedLocationDialog(self.frame))
        try:
            # Set values
            dialog.lat_ctrl.SetValue("35.0")
            dialog.lon_ctrl.SetValue("-80.0")

            # Process events to ensure UI updates are applied
            process_ui_events()

            # Create mock event
            event = MagicMock()
            event.Skip = MagicMock()

            # Call OnOK
            dialog.OnOK(event)

            # Check that event.Skip was called
            event.Skip.assert_called_once()
        finally:
            dialog.Destroy()
            process_ui_events()

    def test_validation_invalid_lat(self, safe_destroy):
        """Test validation with invalid latitude"""
        with patch("wx.MessageBox") as mock_message_box:
            dialog = safe_destroy(AdvancedLocationDialog(self.frame))
            try:
                # Set values
                dialog.lat_ctrl.SetValue("invalid")
                dialog.lon_ctrl.SetValue("-80.0")

                # Process events to ensure UI updates are applied
                process_ui_events()

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
                dialog.Destroy()
                process_ui_events()

    def test_validation_invalid_lon(self, safe_destroy):
        """Test validation with invalid longitude"""
        with patch("wx.MessageBox") as mock_message_box:
            dialog = safe_destroy(AdvancedLocationDialog(self.frame))
            try:
                # Set values
                dialog.lat_ctrl.SetValue("35.0")
                dialog.lon_ctrl.SetValue("invalid")

                # Process events to ensure UI updates are applied
                process_ui_events()

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
                dialog.Destroy()
                process_ui_events()


class TestLocationDialog:
    """Test suite for LocationDialog"""

    @pytest.fixture(autouse=True)
    def setup_frame_and_mocks(self, ui_component_frame):
        """Set up test fixture with a frame and mocks for the dialog.

        Args:
            ui_component_frame: The frame fixture from gui_test_fixtures
        """
        # Store the frame
        self.frame = ui_component_frame

        # Create patch for geocoding service
        self.geocoding_patcher = patch("accessiweather.gui.dialogs.GeocodingService")
        self.mock_geocoding_class = self.geocoding_patcher.start()
        self.mock_geocoding = MagicMock()
        self.mock_geocoding_class.return_value = self.mock_geocoding

        # Yield to allow tests to run
        yield

        # Stop geocoding patch
        self.geocoding_patcher.stop()

    def test_init(self, safe_destroy):
        """Test initialization"""
        dialog = safe_destroy(LocationDialog(self.frame, location_name="Home", lat=35.0, lon=-80.0))
        try:
            # Check initial values
            assert dialog.name_ctrl.GetValue() == "Home"
            assert dialog.latitude == 35.0
            assert dialog.longitude == -80.0
            assert dialog.result_text.GetValue() == "Custom coordinates: 35.0, -80.0"

            # Process events to ensure UI updates are applied
            process_ui_events()
        finally:
            dialog.Destroy()
            process_ui_events()

    def test_get_values(self, safe_destroy):
        """Test getting values from dialog"""
        dialog = safe_destroy(LocationDialog(self.frame, location_name="Home", lat=35.0, lon=-80.0))
        try:
            # Process events to ensure UI updates are applied
            process_ui_events()

            # Get values
            name, lat, lon = dialog.GetValues()
            assert name == "Home"
            assert lat == 35.0
            assert lon == -80.0
        finally:
            dialog.Destroy()
            process_ui_events()

    def test_search_success(self, safe_destroy):
        """Test successful location search"""
        # Set up mock geocoding service
        self.mock_geocoding.geocode_address.return_value = (35.0, -80.0, "123 Main St, City, State")

        with patch("wx.MessageBox"):  # Mock MessageBox to prevent UI interaction
            dialog = safe_destroy(LocationDialog(self.frame))
            try:
                # Set search query
                dialog.search_field.SetValue("123 Main St")
                process_ui_events()

                # Reset the mock to clear any previous calls
                self.mock_geocoding.geocode_address.reset_mock()

                # Skip the _perform_search and directly call the thread function
                # to avoid duplicate geocoding calls
                dialog._search_thread_func("123 Main St")

                # Manually update the search result
                result = (35.0, -80.0, "123 Main St, City, State")
                dialog._update_search_result(result, "123 Main St")
                process_ui_events()

                # Check that geocoding service was called
                self.mock_geocoding.geocode_address.assert_called_once_with("123 Main St")

                # Check result
                assert dialog.latitude == 35.0
                assert dialog.longitude == -80.0
                assert "Found: 123 Main St, City, State" in dialog.result_text.GetValue()
            finally:
                dialog.Destroy()
                process_ui_events()

    def test_search_not_found(self, safe_destroy):
        """Test location search with no results"""
        # Set up mock geocoding service
        self.mock_geocoding.geocode_address.return_value = None

        with patch("wx.MessageBox"):  # Mock MessageBox to prevent UI interaction
            dialog = safe_destroy(LocationDialog(self.frame))
            try:
                # Set search query
                dialog.search_field.SetValue("Nonexistent Address")
                process_ui_events()

                # Reset the mock to clear any previous calls
                self.mock_geocoding.geocode_address.reset_mock()

                # Skip the _perform_search and directly call the thread function
                # to avoid duplicate geocoding calls
                dialog._search_thread_func("Nonexistent Address")

                # Manually update the search result
                dialog._update_search_result(None, "Nonexistent Address")
                process_ui_events()

                # Check that geocoding service was called
                self.mock_geocoding.geocode_address.assert_called_once_with("Nonexistent Address")

                # Check result
                assert "No results found" in dialog.result_text.GetValue()
            finally:
                dialog.Destroy()
                process_ui_events()

    def test_search_auto_name(self, safe_destroy):
        """Test auto-population of name field when search is successful"""
        # Set up mock geocoding service
        self.mock_geocoding.geocode_address.return_value = (35.0, -80.0, "123 Main St, City, State")

        with patch("wx.MessageBox"):  # Mock MessageBox to prevent UI interaction
            dialog = safe_destroy(LocationDialog(self.frame))
            try:
                # Set search query but leave name empty
                dialog.search_field.SetValue("123 Main St")
                dialog.name_ctrl.SetValue("")
                process_ui_events()

                # Reset the mock to clear any previous calls
                self.mock_geocoding.geocode_address.reset_mock()

                # Skip the _perform_search and directly call the thread function
                # to avoid duplicate geocoding calls
                dialog._search_thread_func("123 Main St")

                # Manually update the search result
                result = (35.0, -80.0, "123 Main St, City, State")
                dialog._update_search_result(result, "123 Main St")
                process_ui_events()

                # Check that name field was auto-populated with search query
                assert dialog.name_ctrl.GetValue() != ""
            finally:
                dialog.Destroy()
                process_ui_events()

    def test_advanced_dialog(self, safe_destroy):
        """Test advanced dialog integration"""
        with patch("accessiweather.gui.dialogs.AdvancedLocationDialog") as mock_dialog_class:
            # Create mock dialog
            mock_dialog = MagicMock()
            mock_dialog.ShowModal.return_value = wx.ID_OK
            mock_dialog.GetValues.return_value = (40.0, -75.0)
            mock_dialog_class.return_value = mock_dialog

            with patch("wx.MessageBox"):  # Prevent MessageBox from showing
                dialog = safe_destroy(LocationDialog(self.frame))
                try:
                    # Call advanced button handler
                    dialog.OnAdvanced(None)
                    process_ui_events()

                    # Check that advanced dialog was created and shown
                    mock_dialog_class.assert_called_once()
                    mock_dialog.ShowModal.assert_called_once()

                    # Check that values were updated
                    assert dialog.latitude == 40.0
                    assert dialog.longitude == -75.0
                    assert "Custom coordinates: 40.0, -75.0" in dialog.result_text.GetValue()
                finally:
                    dialog.Destroy()
                    process_ui_events()

    def test_validation_success(self, safe_destroy):
        """Test validation with valid inputs"""
        dialog = safe_destroy(LocationDialog(self.frame))
        try:
            # Set values
            dialog.name_ctrl.SetValue("Home")
            dialog.latitude = 35.0
            dialog.longitude = -80.0
            dialog.result_text.SetValue("Custom coordinates: 35.0, -80.0")
            process_ui_events()

            # Create mock event
            event = MagicMock()
            event.Skip = MagicMock()

            # Call OnOK
            dialog.OnOK(event)

            # Check that event.Skip was called
            event.Skip.assert_called_once()
        finally:
            dialog.Destroy()
            process_ui_events()

    def test_validation_no_name(self, safe_destroy):
        """Test validation with no name"""
        with patch("wx.MessageBox") as mock_message_box:
            dialog = safe_destroy(LocationDialog(self.frame))
            try:
                # Set values but leave name empty
                dialog.name_ctrl.SetValue("")
                dialog.latitude = 35.0
                dialog.longitude = -80.0
                process_ui_events()

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
                dialog.Destroy()
                process_ui_events()

    def test_validation_no_location(self, safe_destroy):
        """Test validation with no location data"""
        with patch("wx.MessageBox") as mock_message_box:
            dialog = safe_destroy(LocationDialog(self.frame))
            try:
                # Set name but no location
                dialog.name_ctrl.SetValue("Home")
                dialog.latitude = None
                dialog.longitude = None
                process_ui_events()

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
                dialog.Destroy()
                process_ui_events()
