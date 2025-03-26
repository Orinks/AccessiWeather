import pytest
import wx
from unittest.mock import MagicMock, patch

# Import the class we'll be creating
from accessiweather.gui.ui_components import WeatherLocationAutocomplete
from accessiweather.geocoding import GeocodingService

@pytest.fixture(autouse=True)
def setup_wx_testing():
    """Set up wx testing mode for autocomplete testing"""
    # Set testing flag for wx
    wx.testing = True
    yield
    # Clean up
    if hasattr(wx, 'testing'):
        delattr(wx, 'testing')

@pytest.fixture
def wx_app():
    app = wx.App()
    yield app
    app.Destroy()

@pytest.fixture
def frame(wx_app):
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
        "Newark, NJ"
    ]
    return geocoding_service

def test_autocomplete_creation(frame):
    """Test that the autocomplete control can be instantiated properly"""
    autocomplete = WeatherLocationAutocomplete(frame, label="Test Autocomplete")
    
    # Check basic properties
    assert autocomplete is not None
    assert autocomplete.GetName() == "Test Autocomplete"
    assert autocomplete.IsEditable() == True

def test_autocomplete_suggestions(frame, mock_geocoding_service):
    """Test that autocomplete shows suggestions based on typed text"""
    # Create the autocomplete control with mock service
    autocomplete = WeatherLocationAutocomplete(frame, label="Test Autocomplete")
    autocomplete.set_geocoding_service(mock_geocoding_service)
    
    # Simulate typing 'New'
    with patch.object(autocomplete, 'AutoComplete') as mock_auto_complete:
        autocomplete.SetValue("New")
        autocomplete.on_text_changed(None)  # Simulate text change event
        
        # Check that suggestions were requested
        mock_geocoding_service.suggest_locations.assert_called_once_with("New")
        
        # Check that results were loaded into the completer
        assert mock_auto_complete.called

def test_autocomplete_min_chars(frame, mock_geocoding_service):
    """Test that autocomplete only triggers after minimum character count"""
    # Create the autocomplete control with mock service
    autocomplete = WeatherLocationAutocomplete(frame, label="Test Autocomplete", min_chars=3)
    autocomplete.set_geocoding_service(mock_geocoding_service)
    
    # Simulate typing 'Ne' (less than min chars)
    autocomplete.SetValue("Ne")
    autocomplete.on_text_changed(None)  # Simulate text change event
    
    # Check that no suggestions were requested
    mock_geocoding_service.suggest_locations.assert_not_called()
    
    # Now type one more character to reach min_chars
    autocomplete.SetValue("New")
    autocomplete.on_text_changed(None)  # Simulate text change event
    
    # Check that suggestions were requested
    mock_geocoding_service.suggest_locations.assert_called_once_with("New")

def test_autocomplete_completer_integration(frame):
    """Test that the TextCompleterSimple is properly integrated"""
    autocomplete = WeatherLocationAutocomplete(frame, label="Test Autocomplete")
    
    # Get the completer
    completer = autocomplete.get_completer()
    
    # Test with some sample data
    autocomplete.update_choices(["Apple", "Banana", "Apricot"])
    
    # Check completions
    assert set(completer.GetCompletions("A")) == {"Apple", "Apricot"}
    assert set(completer.GetCompletions("B")) == {"Banana"}
    assert set(completer.GetCompletions("C")) == set()
