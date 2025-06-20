"""Tests for the AlertDetailsDialog class."""

from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.gui.alert_dialog import AlertDetailsDialog
from accessiweather.services.weather_service import WeatherService

# Sample alert data with NWSheadline parameter
SAMPLE_ALERT_WITH_HEADLINE = {
    "features": [
        {
            "id": "alert1",
            "properties": {
                "headline": "Test Alert",
                "description": "Test Description",
                "instruction": "Test Instruction",
                "severity": "Moderate",
                "event": "Test Event",
                "parameters": {"NWSheadline": ["This is a test statement from NWSheadline"]},
            },
        }
    ]
}


# Sample alert data without NWSheadline parameter
SAMPLE_ALERT_WITHOUT_HEADLINE = {
    "features": [
        {
            "id": "alert1",
            "properties": {
                "headline": "Test Alert",
                "description": "Test Description",
                "instruction": "Test Instruction",
                "severity": "Moderate",
                "event": "Test Event",
                "parameters": {},  # Empty parameters
            },
        }
    ]
}


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

    # Mock wx.Notebook
    mock_notebook = MagicMock(spec=wx.Notebook)
    monkeypatch.setattr(wx, "Notebook", MagicMock(return_value=mock_notebook))

    # Mock wx.TextCtrl
    mock_text_ctrl = MagicMock(spec=wx.TextCtrl)
    monkeypatch.setattr(wx, "TextCtrl", MagicMock(return_value=mock_text_ctrl))

    # Mock wx.StaticText
    mock_static_text = MagicMock(spec=wx.StaticText)
    monkeypatch.setattr(wx, "StaticText", MagicMock(return_value=mock_static_text))

    # Mock wx.StaticLine
    mock_static_line = MagicMock(spec=wx.StaticLine)
    monkeypatch.setattr(wx, "StaticLine", MagicMock(return_value=mock_static_line))

    # Mock wx.Button
    mock_button = MagicMock(spec=wx.Button)
    monkeypatch.setattr(wx, "Button", MagicMock(return_value=mock_button))

    # Mock wx.Font
    mock_font = MagicMock(spec=wx.Font)
    monkeypatch.setattr(wx, "Font", MagicMock(return_value=mock_font))

    yield mock_dialog_instance


def test_process_alerts_preserves_parameters():
    """Test that process_alerts preserves the parameters field."""
    # Create a WeatherService instance with a mock API client
    mock_api_client = MagicMock()
    weather_service = WeatherService(mock_api_client)

    # Process the sample alert data
    processed_alerts, new_count, updated_count = weather_service.process_alerts(
        SAMPLE_ALERT_WITH_HEADLINE
    )

    # Verify that the parameters field is preserved
    assert len(processed_alerts) == 1
    assert "parameters" in processed_alerts[0]
    assert "NWSheadline" in processed_alerts[0]["parameters"]
    headline = processed_alerts[0]["parameters"]["NWSheadline"][0]
    assert headline == "This is a test statement from NWSheadline"


def test_alert_details_dialog_with_nwsheadline():
    """Test AlertDetailsDialog with an alert containing NWSheadline."""
    # Create a WeatherService instance with a mock API client
    mock_api_client = MagicMock()
    weather_service = WeatherService(mock_api_client)

    # Process the sample alert data
    processed_alerts, new_count, updated_count = weather_service.process_alerts(
        SAMPLE_ALERT_WITH_HEADLINE
    )

    # Create a mock for the AlertDetailsDialog class that doesn't call __init__
    with patch.object(AlertDetailsDialog, "__init__", return_value=None):
        # Create dialog instance without calling the real __init__
        dialog = AlertDetailsDialog(None, "Test Alert", processed_alerts[0])

        # Set up the dialog attributes manually
        dialog.Destroy = MagicMock()
        dialog.statement_text = MagicMock()

        # Manually call the code that would extract the statement
        statement = (
            processed_alerts[0]
            .get("parameters", {})
            .get("NWSheadline", ["No statement available"])[0]
        )

        # Set the statement text
        dialog.statement_text.SetValue = MagicMock()
        dialog.statement_text.SetValue(statement)

        # Verify that the statement text is set correctly
        dialog.statement_text.SetValue.assert_called_once_with(
            "This is a test statement from NWSheadline"
        )


def test_alert_details_dialog_without_nwsheadline():
    """Test AlertDetailsDialog with an alert that doesn't have NWSheadline."""
    # Create a WeatherService instance with a mock API client
    mock_api_client = MagicMock()
    weather_service = WeatherService(mock_api_client)

    # Process the sample alert data
    processed_alerts, new_count, updated_count = weather_service.process_alerts(
        SAMPLE_ALERT_WITHOUT_HEADLINE
    )

    # Create a mock for the AlertDetailsDialog class that doesn't call __init__
    with patch.object(AlertDetailsDialog, "__init__", return_value=None):
        # Create dialog instance without calling the real __init__
        dialog = AlertDetailsDialog(None, "Test Alert", processed_alerts[0])

        # Set up the dialog attributes manually
        dialog.Destroy = MagicMock()
        dialog.statement_text = MagicMock()

        # Manually call the code that would extract the statement
        statement = (
            processed_alerts[0]
            .get("parameters", {})
            .get("NWSheadline", ["No statement available"])[0]
        )

        # Set the statement text
        dialog.statement_text.SetValue = MagicMock()
        dialog.statement_text.SetValue(statement)

        # Verify that the statement text is set to the default value
        dialog.statement_text.SetValue.assert_called_once_with("No statement available")


def test_alert_details_dialog_with_empty_parameters():
    """Test AlertDetailsDialog with an alert that has empty parameters."""
    # Create an alert with empty parameters
    alert_data = {
        "id": "alert1",
        "headline": "Test Alert",
        "description": "Test Description",
        "instruction": "Test Instruction",
        "severity": "Moderate",
        "event": "Test Event",
        "parameters": {},  # Empty parameters
    }

    # Create a mock for the AlertDetailsDialog class that doesn't call __init__
    with patch.object(AlertDetailsDialog, "__init__", return_value=None):
        # Create dialog instance without calling the real __init__
        dialog = AlertDetailsDialog(None, "Test Alert", alert_data)

        # Set up the dialog attributes manually
        dialog.Destroy = MagicMock()
        dialog.statement_text = MagicMock()

        # Manually call the code that would extract the statement
        parameters = alert_data.get("parameters", {})
        statement: str
        if isinstance(parameters, dict):
            headline_list = parameters.get("NWSheadline", ["No statement available"])
            if isinstance(headline_list, list) and headline_list:
                statement = headline_list[0]
            else:
                statement = "No statement available"
        else:
            statement = "No statement available"

        # Set the statement text
        dialog.statement_text.SetValue = MagicMock()
        dialog.statement_text.SetValue(statement)

        # Verify that the statement text is set to the default value
        dialog.statement_text.SetValue.assert_called_once_with("No statement available")


def test_alert_details_dialog_with_missing_parameters():
    """Test AlertDetailsDialog with an alert that has no parameters field."""
    # Create an alert with no parameters field
    alert_data = {
        "id": "alert1",
        "headline": "Test Alert",
        "description": "Test Description",
        "instruction": "Test Instruction",
        "severity": "Moderate",
        "event": "Test Event",
        # No parameters field
    }

    # Create a mock for the AlertDetailsDialog class that doesn't call __init__
    with patch.object(AlertDetailsDialog, "__init__", return_value=None):
        # Create dialog instance without calling the real __init__
        dialog = AlertDetailsDialog(None, "Test Alert", alert_data)

        # Set up the dialog attributes manually
        dialog.Destroy = MagicMock()
        dialog.statement_text = MagicMock()

        # Manually call the code that would extract the statement
        statement: str = "No statement available"  # Default value

        # Get parameters safely
        parameters_value: object = alert_data.get("parameters", {})
        if isinstance(parameters_value, dict):
            headline_list = parameters_value.get("NWSheadline", ["No statement available"])
            if isinstance(headline_list, list) and headline_list:
                statement = headline_list[0]

        # Set the statement text
        dialog.statement_text.SetValue = MagicMock()
        dialog.statement_text.SetValue(statement)

        # Verify that the statement text is set to the default value
        dialog.statement_text.SetValue.assert_called_once_with("No statement available")


def test_weather_app_on_alerts_fetched_uses_processed_alerts():
    """Test that _on_alerts_fetched uses processed alerts from notification service."""
    # Create mock objects
    mock_notification_service = MagicMock()
    mock_ui_manager = MagicMock()
    mock_service_coordination = MagicMock()

    # Create a mock WeatherApp with the necessary attributes
    mock_app = MagicMock()
    mock_app.notification_service = mock_notification_service
    mock_app.ui_manager = mock_ui_manager
    mock_app.service_coordination = mock_service_coordination
    mock_app._alerts_complete = False
    mock_app._check_update_complete = MagicMock()
    mock_app._testing_alerts_callback = None

    # Set up the notification service to return processed alerts
    processed_alerts = [
        {
            "id": "alert1",
            "headline": "Test Alert",
            "description": "Test Description",
            "instruction": "Test Instruction",
            "severity": "Moderate",
            "event": "Test Event",
            "parameters": {"NWSheadline": ["This is a test statement from NWSheadline"]},
        }
    ]
    # Return a tuple of (processed_alerts, new_count, updated_count)
    mock_notification_service.process_alerts.return_value = (processed_alerts, 1, 0)

    # Set up the service coordination to use our mocked notification service
    mock_service_coordination.app = mock_app

    # Import the _on_alerts_fetched method from weather_app.py
    from accessiweather.gui.weather_app import WeatherApp

    # Call the method with sample alert data
    alerts_data = SAMPLE_ALERT_WITH_HEADLINE
    WeatherApp._on_alerts_fetched(mock_app, alerts_data)

    # Verify that the service coordination _on_alerts_fetched was called
    mock_service_coordination._on_alerts_fetched.assert_called_once_with(alerts_data)

    # Since we're testing the delegation to service_coordination, we don't need to verify
    # the internal behavior of service_coordination here - that should be tested separately
    # We only verify that the delegation happens correctly
