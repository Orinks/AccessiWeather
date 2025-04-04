"""Tests for the integration of autocomplete in LocationDialog."""

import os  # Import os module
from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.geocoding import GeocodingService
from accessiweather.gui.dialogs import LocationDialog
from accessiweather.gui.location_autocomplete import WeatherLocationAutocomplete


@pytest.fixture(autouse=True)
def setup_wx_testing():
    """Set up wx testing mode for autocomplete testing."""
    # Set testing flag for wx
    wx.testing = True
    yield
    # Clean up
    if hasattr(wx, "testing"):
        delattr(wx, "testing")


@pytest.fixture
def wx_app():
    """Fixture for creating a wx.App instance."""
    app = wx.App()
    yield app
    app.Destroy()


@pytest.fixture
def parent_frame(wx_app):
    """Fixture for creating a parent wx.Frame."""
    frame = wx.Frame(None)
    yield frame
    frame.Destroy()


@pytest.fixture
def mock_geocoding_service():
    """Fixture for creating a mock GeocodingService."""
    geocoding_service = MagicMock(spec=GeocodingService)
    # Mock the function that will suggest locations
    geocoding_service.suggest_locations.return_value = [
        "New York, NY",
        "New Orleans, LA",
        "Newark, NJ",
    ]
    # Mock geocode_address for search functionality
    geocoding_service.geocode_address.return_value = (
        40.7128,
        -74.0060,
        "New York, NY",
    )
    return geocoding_service


@pytest.mark.skipif(
    os.environ.get("ACCESSIWEATHER_TESTING") == "1",
    reason="GUI test skipped in CI",
)
def test_location_dialog_has_autocomplete(parent_frame):
    """Test that LocationDialog now uses WeatherLocationAutocomplete."""
    # Create the dialog
    dialog = LocationDialog(parent_frame)

    # Check that the search field is now a WeatherLocationAutocomplete
    assert isinstance(dialog.search_field, WeatherLocationAutocomplete)
    assert dialog.search_field.IsEditable() is True


@pytest.mark.skipif(
    os.environ.get("ACCESSIWEATHER_TESTING") == "1",
    reason="GUI test skipped in CI",
)
def test_location_dialog_search_triggers_autocomplete(parent_frame, mock_geocoding_service):
    """Test that typing in search field shows autocomplete suggestions."""
    # Create the dialog and assign mock service
    patch_target = "accessiweather.gui.dialogs.GeocodingService"
    with patch(patch_target, return_value=mock_geocoding_service):
        dialog = LocationDialog(parent_frame)

        # Verify the geocoding service is properly set
        assert dialog.search_field.geocoding_service is not None

        # Directly patch the suggest_locations method to verify it gets called
        dialog.search_field.SetValue("New")
        # Simulate the text changed event manually since it's mocked in tests
        dialog.search_field.on_text_changed(None)

        # Verify suggest_locations was called
        assert mock_geocoding_service.suggest_locations.called


@pytest.mark.skipif(
    os.environ.get("ACCESSIWEATHER_TESTING") == "1",
    reason="GUI test skipped in CI",
)
def test_autocomplete_selection_performs_search(parent_frame, mock_geocoding_service):
    """Test that selecting an autocomplete suggestion performs the search."""
    # Create the dialog and assign mock service
    patch_target = "accessiweather.gui.dialogs.GeocodingService"
    with patch(patch_target, return_value=mock_geocoding_service):
        dialog = LocationDialog(parent_frame)

        # Set a value first so GetValue() returns something
        dialog.search_field.SetValue("New York")

        # Patch the _perform_search method to check if it's called
        with patch.object(dialog, "_perform_search") as mock_perform_search:
            # Simulate selecting an item from autocomplete
            dialog.on_autocomplete_selection(None)

            # Verify search is performed with the selected value
            mock_perform_search.assert_called_once_with("New York")
