import logging  # Added for potential logging in UI updates
from typing import Any, Dict, List, Optional

import wx

from .ui_components import (
    AccessibleButton,
    AccessibleChoice,
    AccessibleListCtrl,
    AccessibleStaticText,
    AccessibleTextCtrl,
)

# Import dialogs if event handlers that use them are moved here later
# from .dialogs import LocationDialog, WeatherDiscussionDialog

logger = logging.getLogger(__name__)


class UIManager:
    """Manages the UI setup and event bindings for the WeatherApp frame."""

    # Modified __init__ to accept notifier
    def __init__(self, frame, notifier):
        """
        Initializes the UI Manager.

        Args:
            frame: The main WeatherApp frame instance.
        """
        self.frame = frame  # Reference to the main WeatherApp frame
        self.notifier = notifier  # Store notifier instance
        self._setup_ui()
        self._bind_events()

    def _setup_ui(self):
        """Initialize the user interface components."""
        panel = wx.Panel(self.frame)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Location Controls ---
        location_sizer = wx.BoxSizer(wx.HORIZONTAL)
        location_label = AccessibleStaticText(panel, label="Location:")
        location_sizer.Add(location_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        # Store UI elements directly on the frame object for access by handlers
        self.frame.location_choice = AccessibleChoice(panel, choices=[], label="Location Selection")
        location_sizer.Add(self.frame.location_choice, 1, wx.ALL | wx.EXPAND, 5)

        self.frame.add_btn = AccessibleButton(panel, wx.ID_ANY, "Add")
        self.frame.remove_btn = AccessibleButton(panel, wx.ID_ANY, "Remove")
        self.frame.refresh_btn = AccessibleButton(panel, wx.ID_ANY, "Refresh")
        self.frame.settings_btn = AccessibleButton(
            panel, wx.ID_ANY, "Settings"
        )  # Added Settings button
        location_sizer.Add(self.frame.add_btn, 0, wx.ALL, 5)
        location_sizer.Add(self.frame.remove_btn, 0, wx.ALL, 5)
        location_sizer.Add(self.frame.refresh_btn, 0, wx.ALL, 5)
        location_sizer.Add(self.frame.settings_btn, 0, wx.ALL, 5)  # Added Settings button to sizer
        main_sizer.Add(location_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # --- Forecast Panel ---
        forecast_label = AccessibleStaticText(panel, label="Forecast:")
        main_sizer.Add(forecast_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.frame.forecast_text = AccessibleTextCtrl(
            panel,
            value="Select a location to view the forecast",
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            size=(-1, 200),
            label="Forecast Content",
        )
        main_sizer.Add(self.frame.forecast_text, 1, wx.ALL | wx.EXPAND, 10)

        # --- Forecast Discussion Button ---
        self.frame.discussion_btn = AccessibleButton(panel, wx.ID_ANY, "View Forecast Discussion")
        main_sizer.Add(self.frame.discussion_btn, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        # --- Alerts Section ---
        alerts_label = AccessibleStaticText(panel, label="Weather Alerts:")
        main_sizer.Add(alerts_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.frame.alerts_list = AccessibleListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
            label="Weather Alerts List",
            size=(-1, 150),
        )
        # Set up columns for alerts list
        self.frame.alerts_list.InsertColumn(0, "Alert Type")
        self.frame.alerts_list.InsertColumn(1, "Severity")
        self.frame.alerts_list.InsertColumn(2, "Headline")
        self.frame.alerts_list.SetColumnWidth(0, 150)
        self.frame.alerts_list.SetColumnWidth(1, 100)
        self.frame.alerts_list.SetColumnWidth(2, 500)
        main_sizer.Add(self.frame.alerts_list, 0, wx.ALL | wx.EXPAND, 10)

        # --- Alert Details Button ---
        self.frame.alert_btn = AccessibleButton(panel, wx.ID_ANY, "View Alert Details")
        main_sizer.Add(self.frame.alert_btn, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        # --- Finalize Panel Setup ---
        panel.SetSizer(main_sizer)
        self.frame.panel = panel  # Store panel reference if needed

    def _bind_events(self):
        """Bind UI events to their handlers in the main frame."""
        # Bind events to methods defined in WeatherApp
        self.frame.Bind(wx.EVT_CHOICE, self.frame.OnLocationChange, self.frame.location_choice)
        self.frame.Bind(wx.EVT_BUTTON, self.frame.OnAddLocation, self.frame.add_btn)
        self.frame.Bind(wx.EVT_BUTTON, self.frame.OnRemoveLocation, self.frame.remove_btn)
        self.frame.Bind(wx.EVT_BUTTON, self.frame.OnRefresh, self.frame.refresh_btn)
        self.frame.Bind(wx.EVT_BUTTON, self.frame.OnViewDiscussion, self.frame.discussion_btn)
        self.frame.Bind(wx.EVT_BUTTON, self.frame.OnViewAlert, self.frame.alert_btn)
        self.frame.Bind(
            wx.EVT_LIST_ITEM_ACTIVATED, self.frame.OnAlertActivated, self.frame.alerts_list
        )
        self.frame.Bind(  # Added binding for Settings button
            wx.EVT_BUTTON, self.frame.OnSettings, self.frame.settings_btn
        )
        # KeyDown is bound here as it relates to general UI interaction
        self.frame.Bind(wx.EVT_KEY_DOWN, self.frame.OnKeyDown)
        # Note: EVT_CLOSE and EVT_TIMER remain bound in WeatherApp.__init__
        # as they relate more to the application lifecycle than specific UI
        # elements.

    def _UpdateForecastDisplay(self, forecast_data):
        """Update the forecast display with data

        Args:
            forecast_data: Dictionary with forecast data
        """
        if not forecast_data or "properties" not in forecast_data:
            self.frame.forecast_text.SetValue("No forecast data available")
            return

        periods = forecast_data.get("properties", {}).get("periods", [])
        if not periods:
            self.frame.forecast_text.SetValue("No forecast periods available")
            return

        # Format forecast text
        text = ""
        for period in periods[:5]:  # Show first 5 periods
            name = period.get("name", "Unknown")
            temp = period.get("temperature", "?")
            unit = period.get("temperatureUnit", "F")
            details = period.get("detailedForecast", "No details available")

            text += f"{name}: {temp}°{unit}\n"
            text += f"{details}\n\n"

        self.frame.forecast_text.SetValue(text)

    def _UpdateAlertsDisplay(self, alerts_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Update the alerts display with data and return processed alerts.

        Args:
            alerts_data: Dictionary with alerts data

        Returns:
            List of alert properties dictionaries.
        """
        # Clear current alerts display
        alerts_list_ctrl = self.frame.alerts_list
        alerts_list_ctrl.DeleteAllItems()
        processed_alerts: List[Dict[str, Any]] = []  # List to store alert properties

        if not alerts_data or "features" not in alerts_data:
            return processed_alerts  # Return empty list

        features = alerts_data.get("features", [])
        for feature in features:
            props = feature.get("properties", {})
            event = props.get("event", "Unknown")
            severity = props.get("severity", "Unknown")
            headline = props.get("headline", "No headline")  # Shortened

            index = alerts_list_ctrl.InsertItem(alerts_list_ctrl.GetItemCount(), event)
            alerts_list_ctrl.SetItem(index, 1, severity)
            alerts_list_ctrl.SetItem(index, 2, headline)
            processed_alerts.append(props)  # Save alert data

        return processed_alerts
