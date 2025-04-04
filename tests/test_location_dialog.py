"""Tests for the location dialog UI components."""

import os  # Import os module
from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.gui.async_fetchers import safe_call_after

# Import project components early
from accessiweather.gui.dialogs import AdvancedLocationDialog, LocationDialog


# Create a wx App fixture for testing
@pytest.fixture(scope="module")
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


# Imports moved to top
# Removed duplicate import from line 48


# Skip GUI tests in CI environment
@pytest.mark.skipif(
    os.environ.get("ACCESSIWEATHER_TESTING") == "1",
    reason="GUI test skipped in CI",
)
class TestAdvancedLocationDialog:
    """Test suite for AdvancedLocationDialog."""

    def setup_method(self, wx_app):
        """Set up test fixture."""
        # Create parent frame
        self.frame = wx.Frame(None)

    def teardown_method(self):
        """Tear down test fixture."""
        # Destroy frame safely
        try:
            # Import moved to top
            safe_call_after(self.frame.Destroy)
        except Exception:
            pass  # Ignore any errors in cleanup

    def test_init(self, wx_app, safe_destroy):
        """Test initialization."""
        dialog = safe_destroy(AdvancedLocationDialog(self.frame, lat=35.0, lon=-80.0))
        try:
            # Check initial values
            assert dialog.lat_ctrl.GetValue() == "35.0"
            assert dialog.lon_ctrl.GetValue() == "-80.0"
        finally:
            wx.CallAfter(dialog.Destroy)

    def test_get_values(self, wx_app, safe_destroy):
        """Test getting values from dialog."""
        dialog = safe_destroy(AdvancedLocationDialog(self.frame))
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

    def test_validation_success(self, wx_app, safe_destroy):
        """Test validation with valid inputs."""
        dialog = safe_destroy(AdvancedLocationDialog(self.frame))
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

    def test_validation_invalid_lat(self, wx_app, safe_destroy):
        """Test validation with invalid latitude."""
        with patch("wx.MessageBox") as mock_message_box:
            dialog = safe_destroy(AdvancedLocationDialog(self.frame))
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

    def test_validation_invalid_lon(self, wx_app, safe_destroy):
        """Test validation with invalid longitude."""
        with patch("wx.MessageBox") as mock_message_box:
            dialog = safe_destroy(AdvancedLocationDialog(self.frame))
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


# Skip GUI tests in CI environment
@pytest.mark.skipif(
    os.environ.get("ACCESSIWEATHER_TESTING") == "1",
    reason="GUI test skipped in CI",
)
class TestLocationDialog:
    """Test suite for LocationDialog."""

    def setup_method(self, wx_app):
        """Set up test fixture."""
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
        """Tear down test fixture."""
        # Stop geocoding patch
        self.geocoding_patcher.stop()

        # Destroy frame safely
        try:
            # Import moved to top
            safe_call_after(self.frame.Destroy)
        except Exception:
            pass  # Ignore any errors in cleanup

    def test_init(self, wx_app, safe_destroy):
        """Test initialization."""
        dialog = safe_destroy(LocationDialog(self.frame, location_name="Home", lat=35.0, lon=-80.0))
        try:
            # Check initial values
            assert dialog.name_ctrl.GetValue() == "Home"
            assert dialog.latitude == 35.0
            assert dialog.longitude == -80.0
            assert dialog.result_text.GetValue() == ("Custom coordinates: 35.0, -80.0")
        finally:
            wx.CallAfter(dialog.Destroy)

    def test_get_values(self, wx_app, safe_destroy):
        """Test getting values from dialog."""
        dialog = safe_destroy(LocationDialog(self.frame, location_name="Home", lat=35.0, lon=-80.0))
        try:
            # Get values
            name, lat, lon = dialog.GetValues()
            assert name == "Home"
            assert lat == 35.0
            assert lon == -80.0
        finally:
            wx.CallAfter(dialog.Destroy)

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
            dialog = safe_destroy(LocationDialog(self.frame))
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
                wx.CallAfter(dialog.Destroy)

    def test_search_not_found(self, wx_app, safe_destroy):
        """Test location search with no results."""
        # Set up mock geocoding service
        self.mock_geocoding.geocode_address.return_value = None

        # Mock MessageBox to prevent UI interaction
        with patch("wx.MessageBox"):
            dialog = safe_destroy(LocationDialog(self.frame))
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
                wx.CallAfter(dialog.Destroy)

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
            dialog = safe_destroy(LocationDialog(self.frame))
            try:
                # Set search query but leave name empty
                dialog.search_field.SetValue("123 Main St")
                dialog.name_ctrl.SetValue("")

                # Call _perform_search directly to avoid event loop issues
                dialog._perform_search("123 Main St")

                # Check that name field was auto-populated with search query
                assert dialog.name_ctrl.GetValue() == "123 Main St"
            finally:
                wx.CallAfter(dialog.Destroy)

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
                dialog = safe_destroy(LocationDialog(self.frame))
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
                    wx.CallAfter(dialog.Destroy)

    def test_validation_success(self, wx_app, safe_destroy):
        """Test validation with valid inputs."""
        dialog = safe_destroy(LocationDialog(self.frame))
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
            wx.CallAfter(dialog.Destroy)

    def test_validation_no_name(self, wx_app, safe_destroy):
        """Test validation with no name."""
        with patch("wx.MessageBox") as mock_message_box:
            dialog = safe_destroy(LocationDialog(self.frame))
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
                wx.CallAfter(dialog.Destroy)

    def test_validation_no_location(self, wx_app, safe_destroy):
        """Test validation with no location data."""
        with patch("wx.MessageBox") as mock_message_box:
            dialog = safe_destroy(LocationDialog(self.frame))
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
