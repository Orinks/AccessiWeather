from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.geocoding import GeocodingService
from accessiweather.gui.dialogs import LocationDialog
from accessiweather.gui.ui_components import WeatherLocationAutocomplete


@pytest.fixture(autouse=True)
def setup_wx_testing():
    """Set up wx testing mode for autocomplete testing"""
    # Set testing flag for wx
    wx.testing = True
    yield
    # Clean up
    if hasattr(wx, "testing"):
        delattr(wx, "testing")


@pytest.fixture
def wx_app():
    app = wx.App()
    yield app
    app.Destroy()


@pytest.fixture
def parent_frame(wx_app):
    frame = wx.Frame(None)
    yield frame
    frame.Destroy()


@pytest.fixture
def mock_geocoding_service():
    geocoding_service = MagicMock(spec=GeocodingService)
    # Mock the function that will suggest locations
    geocoding_service.suggest_locations.return_value = [
        "New York, NY",
        "New Orleans, LA",
        "Newark, NJ",
    ]
    # Mock geocode_address for search functionality
    geocoding_service.geocode_address.return_value = (40.7128, -74.0060, "New York, NY")
    return geocoding_service


@pytest.mark.skip(reason="Autocomplete functionality has been removed for accessibility reasons")
def test_location_dialog_has_autocomplete(parent_frame):
    """Test that LocationDialog now uses WeatherLocationAutocomplete"""
    # This test is skipped because autocomplete functionality has been removed
    # for accessibility reasons and replaced with a list-based approach
    pass


@pytest.mark.skip(reason="Autocomplete functionality has been removed for accessibility reasons")
def test_location_dialog_search_triggers_autocomplete(parent_frame, mock_geocoding_service):
    """Test that typing in search field shows autocomplete suggestions"""
    # This test is skipped because autocomplete functionality has been removed
    # for accessibility reasons and replaced with a list-based approach
    pass


@pytest.mark.skip(reason="Autocomplete functionality has been removed for accessibility reasons")
def test_autocomplete_selection_performs_search(parent_frame, mock_geocoding_service):
    """Test that selecting an autocomplete suggestion performs the search"""
    # This test is skipped because autocomplete functionality has been removed
    # for accessibility reasons and replaced with a list-based approach
    pass
