"""UI setup and layout management for AccessiWeather.

This module provides functions for setting up the user interface components
and managing their layout.
"""

import logging

import wx

from .ui_components import (
    AccessibleButton,
    AccessibleChoice,
    AccessibleListCtrl,
    AccessibleStaticText,
    AccessibleTextCtrl,
)

logger = logging.getLogger(__name__)


def setup_ui_components(frame):
    """Initialize the user interface components.

    Args:
        frame: The main WeatherApp frame instance

    Returns:
        tuple: (panel, openmeteo_hidden_elements) - The main panel and list of elements to hide for Open-Meteo
    """
    panel = wx.Panel(frame)
    main_sizer = wx.BoxSizer(wx.VERTICAL)

    # --- Location Dropdown (separated from buttons) ---
    location_sizer = wx.BoxSizer(wx.HORIZONTAL)
    location_label = AccessibleStaticText(panel, label="Location:")
    location_sizer.Add(location_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

    # Store UI elements directly on the frame object for access by handlers
    frame.location_choice = AccessibleChoice(panel, choices=[], label="Location Selection")
    location_sizer.Add(frame.location_choice, 1, wx.ALL | wx.EXPAND, 5)
    main_sizer.Add(location_sizer, 0, wx.EXPAND | wx.ALL, 10)

    # --- Current Conditions Panel ---
    current_conditions_label = AccessibleStaticText(panel, label="Current Conditions:")
    main_sizer.Add(current_conditions_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
    frame.current_conditions_text = AccessibleTextCtrl(
        panel,
        value="Select a location to view current conditions",
        style=wx.TE_MULTILINE | wx.TE_READONLY,
        size=(-1, 100),
        label="Current Conditions Content",
    )
    main_sizer.Add(frame.current_conditions_text, 0, wx.ALL | wx.EXPAND, 10)

    # --- Forecast Panel ---
    forecast_label = AccessibleStaticText(panel, label="Forecast:")
    main_sizer.Add(forecast_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
    frame.forecast_text = AccessibleTextCtrl(
        panel,
        value="Select a location to view the forecast",
        style=wx.TE_MULTILINE | wx.TE_READONLY,
        size=(-1, 200),
        label="Forecast Content",
    )
    main_sizer.Add(frame.forecast_text, 1, wx.ALL | wx.EXPAND, 10)

    # --- Forecast Discussion Button ---
    frame.discussion_btn = AccessibleButton(panel, wx.ID_ANY, "View Forecast Discussion")
    main_sizer.Add(frame.discussion_btn, 0, wx.ALL | wx.ALIGN_CENTER, 5)

    # --- Alerts Section ---
    alerts_label = AccessibleStaticText(panel, label="Weather Alerts:")
    main_sizer.Add(alerts_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
    frame.alerts_list = AccessibleListCtrl(
        panel,
        style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
        label="Weather Alerts List",
        size=(-1, 150),
    )
    # Set up columns for alerts list
    frame.alerts_list.InsertColumn(0, "Alert Type")
    frame.alerts_list.InsertColumn(1, "Severity")
    frame.alerts_list.InsertColumn(2, "Headline")
    frame.alerts_list.SetColumnWidth(0, 150)
    frame.alerts_list.SetColumnWidth(1, 100)
    frame.alerts_list.SetColumnWidth(2, 500)
    main_sizer.Add(frame.alerts_list, 0, wx.ALL | wx.EXPAND, 10)

    # --- Alert Details Button ---
    frame.alert_btn = AccessibleButton(panel, wx.ID_ANY, "View Alert Details")
    main_sizer.Add(frame.alert_btn, 0, wx.ALL | wx.ALIGN_CENTER, 5)

    # --- Control Buttons (moved to bottom) ---
    buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

    # Create all the buttons
    frame.add_btn = AccessibleButton(panel, wx.ID_ANY, "Add")
    frame.remove_btn = AccessibleButton(panel, wx.ID_ANY, "Remove")
    frame.refresh_btn = AccessibleButton(panel, wx.ID_ANY, "Refresh")
    frame.settings_btn = AccessibleButton(panel, wx.ID_ANY, "Settings")

    # Add buttons to the horizontal sizer
    buttons_sizer.Add(frame.add_btn, 0, wx.ALL, 5)
    buttons_sizer.Add(frame.remove_btn, 0, wx.ALL, 5)
    buttons_sizer.Add(frame.refresh_btn, 0, wx.ALL, 5)
    buttons_sizer.Add(frame.settings_btn, 0, wx.ALL, 5)

    # Add the buttons sizer to the main sizer
    main_sizer.Add(buttons_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

    # --- Finalize Panel Setup ---
    panel.SetSizer(main_sizer)
    frame.panel = panel  # Store panel reference if needed

    # Store references to UI elements that may need to be hidden for Open-Meteo
    openmeteo_hidden_elements = [
        (frame.discussion_btn, "discussion_btn"),
        (alerts_label, "alerts_label"),
        (frame.alerts_list, "alerts_list"),
        (frame.alert_btn, "alert_btn"),
    ]

    return panel, openmeteo_hidden_elements


def bind_ui_events(frame, ui_manager):
    """Bind UI events to their handlers in the main frame.

    Args:
        frame: The main WeatherApp frame instance
        ui_manager: The UIManager instance for event handling
    """
    # Bind events to methods defined in WeatherApp
    frame.Bind(wx.EVT_CHOICE, frame.OnLocationChange, frame.location_choice)
    frame.Bind(wx.EVT_BUTTON, frame.OnAddLocation, frame.add_btn)

    # Add a direct handler for the remove button that respects debug_mode
    def on_remove_test(event):
        # Only show debug message if debug_mode is enabled
        if hasattr(frame, "debug_mode") and frame.debug_mode:
            wx.MessageBox(
                "Remove button clicked - Direct handler",
                "Debug Info",
                wx.OK | wx.ICON_INFORMATION,
            )
        # Now call the actual handler
        frame.OnRemoveLocation(event)

    # Bind the test handler to the remove button
    frame.Bind(wx.EVT_BUTTON, on_remove_test, frame.remove_btn)

    frame.Bind(wx.EVT_BUTTON, frame.OnRefresh, frame.refresh_btn)
    frame.Bind(wx.EVT_BUTTON, frame.OnViewDiscussion, frame.discussion_btn)
    frame.Bind(wx.EVT_BUTTON, frame.OnViewAlert, frame.alert_btn)
    frame.Bind(wx.EVT_LIST_ITEM_ACTIVATED, frame.OnAlertActivated, frame.alerts_list)
    # Add binding for list item selection to enable the alert button
    frame.Bind(wx.EVT_LIST_ITEM_SELECTED, ui_manager.OnAlertSelected, frame.alerts_list)
    frame.Bind(wx.EVT_BUTTON, frame.OnSettings, frame.settings_btn)
    # KeyDown is bound here as it relates to general UI interaction
    frame.Bind(wx.EVT_KEY_DOWN, frame.OnKeyDown)


def update_ui_for_weather_source(frame, openmeteo_hidden_elements, is_openmeteo):
    """Update UI elements based on the current weather source.

    Args:
        frame: The main WeatherApp frame instance
        openmeteo_hidden_elements: List of UI elements to hide for Open-Meteo
        is_openmeteo: Whether the current weather source is Open-Meteo
    """
    try:
        logger.debug(f"Updating UI for weather source, is_openmeteo: {is_openmeteo}")

        # Show or hide elements based on weather source
        for element, name in openmeteo_hidden_elements:
            if element and hasattr(element, "Show"):
                element.Show(not is_openmeteo)
                logger.debug(f"{'Hiding' if is_openmeteo else 'Showing'} {name}")

        # Force layout update
        if hasattr(frame, "panel") and frame.panel:
            frame.panel.Layout()

    except Exception as e:
        logger.error(f"Error updating UI for weather source: {e}")
