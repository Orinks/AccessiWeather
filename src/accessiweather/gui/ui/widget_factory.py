"""Widget Factory for AccessiWeather UI.

This module provides the WidgetFactory class which handles creation and layout
of UI components for the main weather application window.
"""

import logging

import wx

from ..ui_components import (
    AccessibleButton,
    AccessibleChoice,
    AccessibleListCtrl,
    AccessibleStaticText,
)

logger = logging.getLogger(__name__)


class WidgetFactory:
    """Factory class for creating and laying out UI widgets."""

    def __init__(self, frame):
        """Initialize the widget factory.

        Args:
            frame: The main WeatherApp frame instance.

        """
        self.frame = frame

    def create_main_panel(self):
        """Create the main panel and layout for the application.

        Returns:
            wx.Panel: The main panel with all UI components

        """
        panel = wx.Panel(self.frame)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create and add all UI sections
        self._create_location_section(panel, main_sizer)
        self._create_current_conditions_section(panel, main_sizer)
        self._create_forecast_section(panel, main_sizer)
        self._create_discussion_section(panel, main_sizer)
        self._create_alerts_section(panel, main_sizer)
        self._create_buttons_section(panel, main_sizer)

        # Finalize panel setup
        panel.SetSizer(main_sizer)
        self.frame.panel = panel

        return panel

    def _create_location_section(self, panel, main_sizer):
        """Create the location dropdown section.

        Args:
            panel: Parent panel
            main_sizer: Main sizer to add components to

        """
        location_sizer = wx.BoxSizer(wx.HORIZONTAL)
        location_label = AccessibleStaticText(panel, label="Location:")
        location_sizer.Add(location_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        # Store UI elements directly on the frame object for access by handlers
        self.frame.location_choice = AccessibleChoice(panel, choices=[], label="Location Selection")
        location_sizer.Add(self.frame.location_choice, 1, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(location_sizer, 0, wx.EXPAND | wx.ALL, 10)

    def _create_current_conditions_section(self, panel, main_sizer):
        """Create the current conditions display section.

        Args:
            panel: Parent panel
            main_sizer: Main sizer to add components to

        """
        current_conditions_label = AccessibleStaticText(panel, label="Current Conditions:")
        main_sizer.Add(current_conditions_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.frame.current_conditions_text = wx.TextCtrl(
            panel,
            value="Select a location to view current conditions",
            style=wx.TE_MULTILINE | wx.TE_READONLY,  # Removed wx.TE_RICH2 for better accessibility
            size=(-1, 100),
        )

        # Set system default font for better accessibility and visual consistency
        font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        self.frame.current_conditions_text.SetFont(font)

        # Set accessible name and role for screen readers
        self.frame.current_conditions_text.SetName("Current Conditions Content")
        accessible = self.frame.current_conditions_text.GetAccessible()
        if accessible:
            accessible.SetName("Current Weather Conditions Text")
            accessible.SetRole(wx.ACC_ROLE_TEXT)

        main_sizer.Add(self.frame.current_conditions_text, 0, wx.ALL | wx.EXPAND, 10)

    def _create_forecast_section(self, panel, main_sizer):
        """Create the forecast display section.

        Args:
            panel: Parent panel
            main_sizer: Main sizer to add components to

        """
        forecast_label = AccessibleStaticText(panel, label="Forecast:")
        main_sizer.Add(forecast_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.frame.forecast_text = wx.TextCtrl(
            panel,
            value="Select a location to view the forecast",
            style=wx.TE_MULTILINE | wx.TE_READONLY,  # Removed wx.TE_RICH2 for better accessibility
            size=(-1, 200),
        )

        # Set system default font for better accessibility and visual consistency
        font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        self.frame.forecast_text.SetFont(font)

        # Set accessible name and role for screen readers
        self.frame.forecast_text.SetName("Forecast Content")
        accessible = self.frame.forecast_text.GetAccessible()
        if accessible:
            accessible.SetName("Weather Forecast Text")
            accessible.SetRole(wx.ACC_ROLE_TEXT)

        main_sizer.Add(self.frame.forecast_text, 1, wx.ALL | wx.EXPAND, 10)

    def _create_discussion_section(self, panel, main_sizer):
        """Create the forecast discussion button section.

        Args:
            panel: Parent panel
            main_sizer: Main sizer to add components to

        """
        self.frame.discussion_btn = AccessibleButton(panel, wx.ID_ANY, "View Forecast Discussion")
        main_sizer.Add(self.frame.discussion_btn, 0, wx.ALL | wx.ALIGN_CENTER, 5)

    def _create_alerts_section(self, panel, main_sizer):
        """Create the weather alerts section.

        Args:
            panel: Parent panel
            main_sizer: Main sizer to add components to

        Returns:
            wx.StaticText: The alerts label for potential hiding with Open-Meteo

        """
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

        # Alert Details Button
        self.frame.alert_btn = AccessibleButton(panel, wx.ID_ANY, "View Alert Details")
        main_sizer.Add(self.frame.alert_btn, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        return alerts_label

    def _create_buttons_section(self, panel, main_sizer):
        """Create the control buttons section.

        Args:
            panel: Parent panel
            main_sizer: Main sizer to add components to

        """
        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Create all the buttons
        self.frame.add_btn = AccessibleButton(panel, wx.ID_ANY, "Add")
        self.frame.remove_btn = AccessibleButton(panel, wx.ID_ANY, "Remove")
        self.frame.refresh_btn = AccessibleButton(panel, wx.ID_ANY, "Refresh")
        self.frame.settings_btn = AccessibleButton(panel, wx.ID_ANY, "Settings")

        # Add buttons to the horizontal sizer
        buttons_sizer.Add(self.frame.add_btn, 0, wx.ALL, 5)
        buttons_sizer.Add(self.frame.remove_btn, 0, wx.ALL, 5)
        buttons_sizer.Add(self.frame.refresh_btn, 0, wx.ALL, 5)
        buttons_sizer.Add(self.frame.settings_btn, 0, wx.ALL, 5)

        # Add the buttons sizer to the main sizer
        main_sizer.Add(buttons_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

    def get_openmeteo_hidden_elements(self):
        """Get list of UI elements that should be hidden for Open-Meteo.

        Returns:
            list: List of (element, name) tuples for elements to hide

        """
        # Note: alerts_label needs to be retrieved from the created section
        # This is a limitation of the current design that could be improved
        alerts_label = None
        if hasattr(self.frame, "panel"):
            # Find the alerts label in the panel's children
            for child in self.frame.panel.GetChildren():
                if isinstance(child, wx.StaticText) and child.GetLabel() == "Weather Alerts:":
                    alerts_label = child
                    break

        return [
            (self.frame.discussion_btn, "discussion_btn"),
            (alerts_label, "alerts_label"),
            (self.frame.alerts_list, "alerts_list"),
            (self.frame.alert_btn, "alert_btn"),
        ]
