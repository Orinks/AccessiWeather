"""Event Handlers for AccessiWeather UI.

This module provides the EventHandlers class which manages event binding
and some UI-specific event handling for the main weather application.
"""

import logging

import wx

logger = logging.getLogger(__name__)


class EventHandlers:
    """Manages event binding and UI-specific event handling."""

    def __init__(self, frame):
        """Initialize the event handlers.

        Args:
            frame: The main WeatherApp frame instance.
        """
        self.frame = frame

    def bind_all_events(self):
        """Bind all UI events to their handlers in the main frame."""
        self._bind_location_events()
        self._bind_button_events()
        self._bind_list_events()
        self._bind_keyboard_events()

    def _bind_location_events(self):
        """Bind location-related events."""
        self.frame.Bind(wx.EVT_CHOICE, self.frame.OnLocationChange, self.frame.location_choice)

    def _bind_button_events(self):
        """Bind button click events."""
        self.frame.Bind(wx.EVT_BUTTON, self.frame.OnAddLocation, self.frame.add_btn)
        self.frame.Bind(wx.EVT_BUTTON, self._create_remove_handler(), self.frame.remove_btn)
        self.frame.Bind(wx.EVT_BUTTON, self.frame.OnRefresh, self.frame.refresh_btn)
        self.frame.Bind(wx.EVT_BUTTON, self.frame.OnViewDiscussion, self.frame.discussion_btn)
        self.frame.Bind(wx.EVT_BUTTON, self.frame.OnViewAlert, self.frame.alert_btn)
        self.frame.Bind(wx.EVT_BUTTON, self.frame.OnSettings, self.frame.settings_btn)

    def _bind_list_events(self):
        """Bind list control events."""
        self.frame.Bind(
            wx.EVT_LIST_ITEM_ACTIVATED, self.frame.OnAlertActivated, self.frame.alerts_list
        )
        # Add binding for list item selection to enable the alert button
        self.frame.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_alert_selected, self.frame.alerts_list)

    def _bind_keyboard_events(self):
        """Bind keyboard events."""
        # KeyDown is bound here as it relates to general UI interaction
        self.frame.Bind(wx.EVT_KEY_DOWN, self.frame.OnKeyDown)

    def _create_remove_handler(self):
        """Create a remove button handler that respects debug mode.

        Returns:
            function: Event handler function for remove button
        """

        def on_remove_test(event):
            # Only show debug message if debug_mode is enabled
            if hasattr(self.frame, "debug_mode") and self.frame.debug_mode:
                wx.MessageBox(
                    "Remove button clicked - Direct handler",
                    "Debug Info",
                    wx.OK | wx.ICON_INFORMATION,
                )
            # Now call the actual handler
            self.frame.OnRemoveLocation(event)

        return on_remove_test

    def on_alert_selected(self, event):
        """Handle alert list item selection event.

        Args:
            event: List item selected event
        """
        # Enable the alert button when an alert is selected
        if hasattr(self.frame, "alert_btn"):
            self.frame.alert_btn.Enable()
            # Set accessibility properties to ensure it's in the tab order
            self.frame.alert_btn.SetHelpText("View details for the selected alert")
            self.frame.alert_btn.SetToolTip("View details for the selected alert")

        # Allow the event to propagate
        event.Skip()
