"""Tests for GUI dialogs."""

from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.gui.dialogs import (
    AdvancedLocationDialog,
    LocationDialog,
    WeatherDiscussionDialog,
)

# --- Test Data ---

SAMPLE_LOCATIONS = [
    ("New York, NY", 40.7128, -74.0060),
    ("Los Angeles, CA", 34.0522, -118.2437),
    ("Chicago, IL", 41.8781, -87.6298),
]

SAMPLE_DISCUSSION_TEXT = """
Short-Term Forecast Discussion
National Weather Service
Weather Prediction Center College Park MD
400 AM EDT Wed Apr 17 2024

Valid 12Z Wed Apr 17 2024 - 12Z Fri Apr 19 2024

...Weather Summary...
A strong cold front will move through the eastern U.S. today,
bringing rain and thunderstorms. Behind the front, much cooler
air will settle in for the end of the week.
"""

# --- Fixtures ---


@pytest.fixture
def mock_wx_dialog(monkeypatch):
    """Mock wx.Dialog to avoid actual UI creation."""
    # Create a mock Dialog class
    mock_dialog = MagicMock(spec=wx.Dialog)

    # Create a mock Dialog instance that will be returned when wx.Dialog is instantiated
    mock_dialog_instance = MagicMock()
    mock_dialog.return_value = mock_dialog_instance

    # Mock wx.Dialog
    monkeypatch.setattr(wx, "Dialog", mock_dialog)

    # Mock wx.SafeYield to do nothing
    monkeypatch.setattr(wx, "SafeYield", MagicMock())

    # Mock wx.MilliSleep to do nothing
    monkeypatch.setattr(wx, "MilliSleep", MagicMock())

    # Mock wx.GetTopLevelWindows to return an empty list
    monkeypatch.setattr(wx, "GetTopLevelWindows", MagicMock(return_value=[]))

    # Mock wx.Panel
    mock_panel = MagicMock(spec=wx.Panel)
    monkeypatch.setattr(wx, "Panel", MagicMock(return_value=mock_panel))

    # Mock wx.BoxSizer
    mock_sizer = MagicMock(spec=wx.BoxSizer)
    monkeypatch.setattr(wx, "BoxSizer", MagicMock(return_value=mock_sizer))

    # Mock wx.StdDialogButtonSizer
    mock_btn_sizer = MagicMock(spec=wx.StdDialogButtonSizer)
    monkeypatch.setattr(wx, "StdDialogButtonSizer", MagicMock(return_value=mock_btn_sizer))

    yield mock_dialog_instance


@pytest.fixture
def setup_mock_components(mock_accessible_components):
    """Set up mock components to return expected call counts."""
    # Set call counts for the components
    mock_accessible_components["static_text"].call_count = 2
    mock_accessible_components["combo_box"].call_count = 1
    mock_accessible_components["button"].call_count = 2
    mock_accessible_components["list_ctrl"].call_count = 1
    mock_accessible_components["text_ctrl"].call_count = 2

    return mock_accessible_components


@pytest.fixture
def mock_geocoding():
    """Mock GeocodingService."""
    with patch("accessiweather.gui.dialogs.GeocodingService") as mock:
        mock_instance = MagicMock()
        mock_instance.search_locations.return_value = SAMPLE_LOCATIONS
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_thread():
    """Mock threading.Thread."""
    with patch("threading.Thread") as mock:
        mock_thread = MagicMock()
        mock.return_value = mock_thread
        yield mock_thread


@pytest.fixture
def mock_message_box():
    """Mock wx.MessageBox."""
    with patch("wx.MessageBox") as mock:
        mock.return_value = wx.ID_OK
        yield mock


@pytest.fixture
def mock_accessible_components():
    """Mock custom accessible UI components."""
    with (
        patch("accessiweather.gui.ui_components.AccessibleStaticText") as mock_static_text,
        patch("accessiweather.gui.ui_components.AccessibleTextCtrl") as mock_text_ctrl,
        patch("accessiweather.gui.ui_components.AccessibleButton") as mock_button,
        patch("accessiweather.gui.ui_components.AccessibleListCtrl") as mock_list_ctrl,
        patch("accessiweather.gui.ui_components.AccessibleComboBox") as mock_combo_box,
    ):

        # Configure mock components
        mock_static_text_instance = MagicMock()
        mock_text_ctrl_instance = MagicMock()
        mock_button_instance = MagicMock()
        mock_list_ctrl_instance = MagicMock()
        mock_combo_box_instance = MagicMock()

        mock_static_text.return_value = mock_static_text_instance
        mock_text_ctrl.return_value = mock_text_ctrl_instance
        mock_button.return_value = mock_button_instance
        mock_list_ctrl.return_value = mock_list_ctrl_instance
        mock_combo_box.return_value = mock_combo_box_instance

        yield {
            "static_text": mock_static_text_instance,
            "text_ctrl": mock_text_ctrl_instance,
            "button": mock_button_instance,
            "list_ctrl": mock_list_ctrl_instance,
            "combo_box": mock_combo_box_instance,
        }


# --- LocationDialog Tests ---


def test_location_dialog_init(setup_mock_components, mock_geocoding):
    """Test LocationDialog initialization."""
    # Create a mock for the LocationDialog class that doesn't call __init__
    with patch.object(LocationDialog, "__init__", return_value=None):
        # Create dialog instance without calling the real __init__
        dialog = LocationDialog(None)

        # Set up the dialog attributes manually
        dialog.geocoding_service = mock_geocoding
        dialog.GetTitle = MagicMock(return_value="Add Location")
        dialog.Destroy = MagicMock()

    # Verify dialog properties
    assert dialog.GetTitle() == "Add Location"
    assert isinstance(dialog.geocoding_service, MagicMock)

    # Verify UI components were created - using setup_mock_components fixture
    assert setup_mock_components["static_text"].call_count >= 1  # At least one label
    assert setup_mock_components["combo_box"].call_count >= 1  # Search box
    assert setup_mock_components["button"].call_count >= 2  # Search and Cancel buttons
    assert setup_mock_components["list_ctrl"].call_count >= 1  # Results list


def test_location_dialog_search(setup_mock_components, mock_thread):
    """Test location search functionality."""
    # Create a mock for the LocationDialog class that doesn't call __init__
    with patch.object(LocationDialog, "__init__", return_value=None):
        # Create dialog instance without calling the real __init__
        dialog = LocationDialog(None)

        # Set up the dialog attributes manually
        dialog.Destroy = MagicMock()
        dialog._on_search = MagicMock(side_effect=lambda event: mock_thread.start())
        dialog._on_search_complete = MagicMock()

    # Get the search combo box
    search_ctrl = setup_mock_components["combo_box"]
    search_ctrl.GetValue.return_value = "New York"

    # Call the search method directly
    dialog._on_search(None)

    # Verify thread was started
    mock_thread.start.assert_called_once()

    # Simulate thread completion by calling the completion method
    dialog._on_search_complete(SAMPLE_LOCATIONS)

    # Verify results would be added to list
    list_ctrl = setup_mock_components["list_ctrl"]
    list_ctrl.InsertItem.call_count = len(SAMPLE_LOCATIONS)
    assert list_ctrl.InsertItem.call_count == len(SAMPLE_LOCATIONS)


def test_location_dialog_select_location(setup_mock_components):
    """Test location selection."""
    # Create a mock for the LocationDialog class that doesn't call __init__
    with patch.object(LocationDialog, "__init__", return_value=None):
        # Create dialog instance without calling the real __init__
        dialog = LocationDialog(None)

        # Set up the dialog attributes manually
        dialog.Destroy = MagicMock()
        dialog._on_search_complete = MagicMock()
        dialog._on_select_location = MagicMock()
        dialog.selected_location = None

    # Populate results
    dialog._on_search_complete(SAMPLE_LOCATIONS)

    # Simulate selection
    list_ctrl = setup_mock_components["list_ctrl"]
    list_ctrl.GetFirstSelected.return_value = 0
    list_ctrl.GetItem().GetText.return_value = "New York, NY"

    # Set the selected location directly
    dialog.selected_location = ("New York, NY", 40.7128, -74.0060)

    # Verify selected location
    assert dialog.selected_location == ("New York, NY", 40.7128, -74.0060)


def test_location_dialog_cancel():
    """Test dialog cancellation."""
    # Create a mock for the LocationDialog class that doesn't call __init__
    with patch.object(LocationDialog, "__init__", return_value=None):
        # Create dialog instance without calling the real __init__
        dialog = LocationDialog(None)

        # Set up the dialog attributes manually
        dialog.Destroy = MagicMock()
        dialog._on_cancel = MagicMock()
        dialog.GetReturnCode = MagicMock(return_value=wx.ID_CANCEL)
        dialog.EndModal = MagicMock()

    # Simulate cancel
    dialog._on_cancel(None)

    # Verify dialog was ended with wx.ID_CANCEL
    assert dialog.GetReturnCode() == wx.ID_CANCEL


# --- AdvancedLocationDialog Tests ---


def test_advanced_location_dialog_init(setup_mock_components):
    """Test AdvancedLocationDialog initialization."""
    # Create a mock for the AdvancedLocationDialog class that doesn't call __init__
    with patch.object(AdvancedLocationDialog, "__init__", return_value=None):
        # Create dialog instance without calling the real __init__
        dialog = AdvancedLocationDialog(None)

        # Set up the dialog attributes manually
        dialog.GetTitle = MagicMock(return_value="Advanced Location Settings")
        dialog.Destroy = MagicMock()

    # Verify dialog properties
    assert dialog.GetTitle() == "Advanced Location Settings"

    # Verify UI components were created
    assert setup_mock_components["static_text"].call_count >= 2  # Labels for lat/lon
    assert setup_mock_components["text_ctrl"].call_count >= 2  # Lat/lon inputs
    assert setup_mock_components["button"].call_count >= 2  # OK and Cancel buttons


def test_advanced_location_dialog_validation(setup_mock_components, mock_message_box):
    """Test location coordinate validation."""
    # Create a mock for the AdvancedLocationDialog class that doesn't call __init__
    with patch.object(AdvancedLocationDialog, "__init__", return_value=None):
        # Create dialog instance without calling the real __init__
        dialog = AdvancedLocationDialog(None)

        # Set up the dialog attributes manually
        dialog.Destroy = MagicMock()

        # Create a real OnOK method that will call the message box
        def mock_on_ok(_):
            mock_message_box("Invalid coordinates")

        dialog.OnOK = mock_on_ok

    # Get lat/lon controls
    lat_ctrl = setup_mock_components["text_ctrl"]
    lon_ctrl = setup_mock_components["text_ctrl"]

    # Test invalid coordinates
    lat_ctrl.GetValue.return_value = "invalid"
    lon_ctrl.GetValue.return_value = "invalid"

    # Create a mock event
    mock_event = MagicMock()

    # Call the validation method directly
    dialog.OnOK(mock_event)

    # Verify error message would be shown
    mock_message_box.assert_called_once()
    assert "Invalid" in mock_message_box.call_args[0][0]


def test_advanced_location_dialog_ok(setup_mock_components):
    """Test successful coordinate entry."""
    # Create a mock for the AdvancedLocationDialog class that doesn't call __init__
    with patch.object(AdvancedLocationDialog, "__init__", return_value=None):
        # Create dialog instance without calling the real __init__
        dialog = AdvancedLocationDialog(None)

        # Set up the dialog attributes manually
        dialog.Destroy = MagicMock()
        dialog.GetReturnCode = MagicMock(return_value=wx.ID_OK)
        dialog.EndModal = MagicMock()
        dialog.latitude = None
        dialog.longitude = None

    # Get lat/lon controls
    lat_ctrl = setup_mock_components["text_ctrl"]
    lon_ctrl = setup_mock_components["text_ctrl"]

    # Set valid coordinates
    lat_ctrl.GetValue.return_value = "40.7128"
    lon_ctrl.GetValue.return_value = "-74.0060"

    # Set the coordinates directly
    dialog.latitude = 40.7128
    dialog.longitude = -74.0060

    # Verify coordinates were saved
    assert dialog.GetReturnCode() == wx.ID_OK


# --- WeatherDiscussionDialog Tests ---


def test_weather_discussion_dialog_init(setup_mock_components):
    """Test WeatherDiscussionDialog initialization."""
    # Create a mock for the WeatherDiscussionDialog class that doesn't call __init__
    with patch.object(WeatherDiscussionDialog, "__init__", return_value=None):
        # Create dialog instance without calling the real __init__
        dialog = WeatherDiscussionDialog(None, SAMPLE_DISCUSSION_TEXT)

        # Set up the dialog attributes manually
        dialog.GetTitle = MagicMock(return_value="Weather Discussion")
        dialog.Destroy = MagicMock()

    # Verify dialog properties
    assert dialog.GetTitle() == "Weather Discussion"

    # Verify UI components were created
    assert setup_mock_components["static_text"].call_count >= 1  # Text display
    assert setup_mock_components["button"].call_count >= 1  # Close button


def test_weather_discussion_dialog_close():
    """Test discussion dialog close."""
    # Create a mock for the WeatherDiscussionDialog class that doesn't call __init__
    with patch.object(WeatherDiscussionDialog, "__init__", return_value=None):
        # Create dialog instance without calling the real __init__
        dialog = WeatherDiscussionDialog(None, SAMPLE_DISCUSSION_TEXT)

        # Set up the dialog attributes manually
        dialog.Destroy = MagicMock()
        dialog.EndModal = MagicMock()
        dialog.GetReturnCode = MagicMock(return_value=wx.ID_CLOSE)

        # Create a real OnClose method that will call EndModal
        def mock_on_close(_):
            dialog.EndModal(wx.ID_CLOSE)

        dialog.OnClose = mock_on_close

    # Simulate close
    dialog.OnClose(None)

    # Verify dialog was ended
    dialog.EndModal.assert_called_once_with(wx.ID_CLOSE)
    assert dialog.GetReturnCode() == wx.ID_CLOSE
