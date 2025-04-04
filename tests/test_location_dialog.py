"""Tests for the location dialog UI components."""

import os
from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.gui.async_fetchers import safe_call_after

# Import project components early
from accessiweather.gui.dialogs import AdvancedLocationDialog, LocationDialog

# Skip GUI tests only on non-Windows CI environments
should_skip = os.environ.get("ACCESSIWEATHER_TESTING") == "1" and os.name != "nt"  # Not Windows


# Create a wx App fixture for testing
@pytest.fixture(scope="function")
def wx_app():
    """Create a wx App for testing."""
    app = wx.App(False)
    yield app


# Fixture to safely destroy wx objects
@pytest.fixture
def safe_destroy():
    """Fixture to safely destroy wx objects even without an app."""
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


# Skip GUI tests only on non-Windows CI environments
@pytest.mark.skipif(
    should_skip,
    reason="GUI test skipped in non-Windows CI environment",
)
class TestAdvancedLocationDialog:
    """Test suite for AdvancedLocationDialog."""

    def test_init(self, wx_app, safe_destroy):
        """Test initialization."""
        frame = safe_destroy(wx.Frame(None))  # Create and register frame
        dialog = safe_destroy(AdvancedLocationDialog(frame, lat=35.0, lon=-80.0))
        try:
            # Check initial values
            assert dialog.lat_ctrl.GetValue() == "35.0"
            assert dialog.lon_ctrl.GetValue() == "-80.0"
        finally:
            pass  # Cleanup handled by safe_destroy

    def test_get_values(self, wx_app, safe_destroy):
        """Test getting values from dialog."""
        frame = safe_destroy(wx.Frame(None))  # Create and register frame
        dialog = safe_destroy(AdvancedLocationDialog(frame))
        try:
            # Set values
            dialog.lat_ctrl.SetValue("35.5")
            dialog.lon_ctrl.SetValue("-80.5")

            # Get values
            lat, lon = dialog.GetValues()
            assert lat == 35.5
            assert lon == -80.5
        finally:
            pass  # Cleanup handled by safe_destroy

    def test_validation_success(self, wx_app, safe_destroy):
        """Test validation with valid inputs."""
        frame = safe_destroy(wx.Frame(None))  # Create and register frame
        dialog = safe_destroy(AdvancedLocationDialog(frame))
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
            pass  # Cleanup handled by safe_destroy

    def test_validation_invalid_lat(self, wx_app, safe_destroy):
        """Test validation with invalid latitude."""
        with patch("wx.MessageBox") as mock_message_box:
            frame = safe_destroy(wx.Frame(None))  # Create and register frame
            dialog = safe_destroy(AdvancedLocationDialog(frame))
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
                pass  # Cleanup handled by safe_destroy

    def test_validation_invalid_lon(self, wx_app, safe_destroy):
        """Test validation with invalid longitude."""
        with patch("wx.MessageBox") as mock_message_box:
            frame = safe_destroy(wx.Frame(None))  # Create and register frame
            dialog = safe_destroy(AdvancedLocationDialog(frame))
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
                pass  # Cleanup handled by safe_destroy


# Skip GUI tests only on non-Windows CI environments
@pytest.mark.skipif(
    should_skip,
    reason="GUI test skipped in non-Windows CI environment",
)
class TestLocationDialog:
    """Test suite for LocationDialog."""

    def setup_method(self, wx_app):
        """Set up test fixture for patching."""
        patch_target = "accessiweather.gui.dialogs.GeocodingService"
        self.geocoding_patcher = patch(patch_target)
        self.mock_geocoding_class = self.geocoding_patcher.start()
        self.mock_geocoding = MagicMock()
        self.mock_geocoding_class.return_value = self.mock_geocoding

    def teardown_method(self):
        """Tear down test fixture for patching."""
        self.geocoding_patcher.stop()

    def test_init(self, wx_app, safe_destroy):
        """Test initialization."""
        frame = safe_destroy(wx.Frame(None))  # Create and register frame
        dialog = safe_destroy(LocationDialog(frame, location_name="Home", lat=35.0, lon=-80.0))
        try:
            # Check initial values
            assert dialog.name_ctrl.GetValue() == "Home"
            assert dialog.latitude == 35.0
            assert dialog.longitude == -80.0
            assert dialog.result_text.GetValue() == ("Custom coordinates: 35.0, -80.0")
        finally:
            pass  # Cleanup handled by safe_destroy

    def test_get_values(self, wx_app, safe_destroy):
        """Test getting values from dialog."""
        frame = safe_destroy(wx.Frame(None))  # Create and register frame
        dialog = safe_destroy(LocationDialog(frame, location_name="Home", lat=35.0, lon=-80.0))
        try:
            # Get values
            name, lat, lon = dialog.GetValues()
            assert name == "Home"
            assert lat == 35.0
            assert lon == -80.0
        finally:
            pass  # Cleanup handled by safe_destroy

    def test_search_success(self, wx_app, safe_destroy):
        """Test successful location search."""
        # Set up mock geocoding service
        self.mock_geocoding.geocode_address.return_value = (
            35.0,
            -80.0,
            "123 Main St, City, State",
        )

        # Mock MessageBox to prevent UI interaction
        with patch("wx.MessageBox"):
            frame = safe_destroy(wx.Frame(None))  # Create and register frame
            dialog = safe_destroy(LocationDialog(frame))
            try:
                # Set search query
                dialog.search_field.SetValue("123 Main St")

                # Call _perform_search directly to avoid event loop issues
                dialog._perform_search("123 Main St")

                # Check that geocoding service was called
                self.mock_geocoding.geocode_address.assert_called_once_with("123 Main St")

                # Check result
                assert dialog.latitude == 35.0
                assert dialog.longitude == -80.0
                assert "Found: 123 Main St, City, State" in (dialog.result_text.GetValue())
            finally:
                pass  # Cleanup handled by safe_destroy

    def test_search_not_found(self, wx_app, safe_destroy):
        """Test location search with no results."""
        # Set up mock geocoding service
        self.mock_geocoding.geocode_address.return_value = None

        # Mock MessageBox to prevent UI interaction
        with patch("wx.MessageBox"):
            frame = safe_destroy(wx.Frame(None))  # Create and register frame
            dialog = safe_destroy(LocationDialog(frame))
            try:
                # Set search query
                dialog.search_field.SetValue("Nonexistent Address")

                # Call _perform_search directly to avoid event loop issues
                dialog._perform_search("Nonexistent Address")

                # Check that geocoding service was called
                self.mock_geocoding.geocode_address.assert_called_once_with("Nonexistent Address")

                # Check result
                assert "No results found" in dialog.result_text.GetValue()
            finally:
                pass  # Cleanup handled by safe_destroy

    def test_search_auto_name(self, wx_app, safe_destroy):
        """Test auto-population of name field when search is successful."""
        # Set up mock geocoding service
        self.mock_geocoding.geocode_address.return_value = (
            35.0,
            -80.0,
            "123 Main St, City, State",
        )

        # Mock MessageBox to prevent UI interaction
        with patch("wx.MessageBox"):
            frame = safe_destroy(wx.Frame(None))  # Create and register frame
            dialog = safe_destroy(LocationDialog(frame))
            try:
                # Set search query but leave name empty
                dialog.search_field.SetValue("123 Main St")
                dialog.name_ctrl.SetValue("")

                # Call _perform_search directly to avoid event loop issues
                dialog._perform_search("123 Main St")

                # Check that name field was auto-populated with search query
                assert dialog.name_ctrl.GetValue() == "123 Main St"
            finally:
                pass  # Cleanup handled by safe_destroy

    def test_advanced_dialog(self, wx_app, safe_destroy):
        """Test advanced dialog integration."""
        patch_target = "accessiweather.gui.dialogs.AdvancedLocationDialog"
        with patch(patch_target) as mock_dialog_class:
            # Create mock dialog
            mock_dialog = MagicMock()
            mock_dialog.ShowModal.return_value = wx.ID_OK
            mock_dialog.GetValues.return_value = (40.0, -75.0)
            mock_dialog_class.return_value = mock_dialog

            with patch("wx.MessageBox"):  # Prevent MessageBox from showing
                # Create and register frame
                frame = safe_destroy(wx.Frame(None))
                dialog = safe_destroy(LocationDialog(frame))
                try:
                    # Call advanced button handler
                    dialog.OnAdvanced(None)

                    # Check that advanced dialog was created and shown
                    mock_dialog_class.assert_called_once()
                    mock_dialog.ShowModal.assert_called_once()

                    # Check that values were updated
                    assert dialog.latitude == 40.0
                    assert dialog.longitude == -75.0
                    assert "Custom coordinates: 40.0, -75.0" in (dialog.result_text.GetValue())
                finally:
                    pass  # Cleanup handled by safe_destroy

    def test_validation_success(self, wx_app, safe_destroy):
        """Test validation with valid inputs."""
        frame = safe_destroy(wx.Frame(None))  # Create and register frame
        dialog = safe_destroy(LocationDialog(frame))
        try:
            # Set values
            dialog.name_ctrl.SetValue("Home")
            dialog.latitude = 35.0
            dialog.longitude = -80.0
            dialog.result_text.SetValue("Custom coordinates: 35.0, -80.0")

            # Create mock event
            event = MagicMock()
            event.Skip = MagicMock()

            # Call OnOK
            dialog.OnOK(event)

            # Check that event.Skip was called
            event.Skip.assert_called_once()
        finally:
            pass  # Cleanup handled by safe_destroy

    def test_validation_no_name(self, wx_app, safe_destroy):
        """Test validation with no name."""
        with patch("wx.MessageBox") as mock_message_box:
            frame = safe_destroy(wx.Frame(None))  # Create and register frame
            dialog = safe_destroy(LocationDialog(frame))
            try:
                # Set values but leave name empty
                dialog.name_ctrl.SetValue("")
                dialog.latitude = 35.0
                dialog.longitude = -80.0

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
                pass  # Cleanup handled by safe_destroy

    def test_validation_no_location(self, wx_app, safe_destroy):
        """Test validation with no location data."""
        with patch("wx.MessageBox") as mock_message_box:
            frame = safe_destroy(wx.Frame(None))  # Create and register frame
            dialog = safe_destroy(LocationDialog(frame))
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
                pass  # Cleanup handled by safe_destroy
