"""System tray functionality for AccessiWeather.

This module provides the TaskBarIcon class for system tray integration.
"""

import logging
from typing import Any, Dict, List, Optional

import wx
import wx.adv

from accessiweather.dynamic_format_manager import DynamicFormatManager
from accessiweather.format_string_parser import FormatStringParser

from .system_tray_formatter import SystemTrayFormatter
from .system_tray_utils import cleanup_taskbar_icon, load_tray_icon

logger = logging.getLogger(__name__)

# Note: We rely on Windows' built-in system tray accessibility instead of global hotkeys
# This provides better compatibility with screen readers and system navigation


class TaskBarIcon(wx.adv.TaskBarIcon):
    """System tray icon for AccessiWeather."""

    # Class variable to track if an instance already exists
    _instance: Optional["TaskBarIcon"] = None
    _instance_count = 0

    def __init__(self, frame):
        """Initialize the TaskBarIcon.

        Args:
            frame: The main application frame (WeatherApp)
        """
        # Check if we already have an instance
        if TaskBarIcon._instance is not None:
            logger.warning(
                "TaskBarIcon instance already exists. This may cause multiple tray icons."
            )

        # Ensure we have a wx.App instance
        app = wx.App.Get()
        if not app:
            raise RuntimeError("No wx.App instance found. TaskBarIcon requires an active wx.App.")

        super().__init__()

        # Track this instance
        TaskBarIcon._instance = self
        TaskBarIcon._instance_count += 1
        logger.debug(f"Creating TaskBarIcon instance #{TaskBarIcon._instance_count}")

        self.frame = frame
        self.format_parser = FormatStringParser()
        self.dynamic_format_manager = DynamicFormatManager()
        self.formatter = SystemTrayFormatter(self.format_parser, self.dynamic_format_manager)
        self.current_weather_data = {}
        self.current_alerts_data: Optional[List[Dict[str, Any]]] = None
        self._is_destroyed = False

        # Set the icon
        self.set_icon()

        # Bind events
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, self.on_left_dclick)
        self.Bind(wx.adv.EVT_TASKBAR_RIGHT_UP, self.on_right_click)

        # Bind additional events for better accessibility
        # These events are sent by Windows when users access the tray icon via keyboard
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_UP, self.on_left_click)
        self.Bind(wx.adv.EVT_TASKBAR_RIGHT_DOWN, self.on_right_down)

        # Note: We no longer register global hotkeys as they interfere with
        # Windows' built-in system tray accessibility (Windows+B navigation)

        logger.debug("TaskBarIcon initialized successfully")

    def on_left_click(self, event):
        """Handle left click event (including keyboard activation).

        This event is triggered when users activate the tray icon via keyboard
        (e.g., pressing Enter when the icon is selected in system tray navigation).

        Args:
            event: The event object
        """
        # For keyboard accessibility, left click should show/hide the main window
        logger.debug("Tray icon activated (left click or keyboard Enter)")
        self.on_show_hide(event)

    def on_right_down(self, event):
        """Handle right mouse button down event.

        This can be triggered by keyboard (Applications key) when the tray icon is focused.

        Args:
            event: The event object
        """
        # This event can be triggered by Applications key for accessibility
        logger.debug("Right mouse down event (may be from Applications key)")
        # Let the event continue to be processed normally
        event.Skip()

    def cleanup(self):
        """Properly cleanup the TaskBarIcon to prevent multiple icons."""
        cleanup_taskbar_icon(self)

        # Clear class reference
        if TaskBarIcon._instance is self:
            TaskBarIcon._instance = None

    @classmethod
    def get_instance(cls):
        """Get the current TaskBarIcon instance if it exists."""
        return cls._instance

    @classmethod
    def cleanup_existing_instance(cls):
        """Cleanup any existing TaskBarIcon instance."""
        if cls._instance is not None:
            logger.debug("Cleaning up existing TaskBarIcon instance")
            cls._instance.cleanup()

    def set_icon(self, tooltip_text=None):
        """Set the taskbar icon.

        Args:
            tooltip_text: Optional text to display in the taskbar icon tooltip.
                          If None, uses the default "AccessiWeather".
        """
        icon = load_tray_icon()
        tooltip = tooltip_text if tooltip_text else "AccessiWeather"
        self.SetIcon(icon, tooltip)

    def on_left_dclick(self, event):
        """Handle left double-click event.

        Args:
            event: The event object
        """
        self.on_show_hide(event)

    def on_right_click(self, event):
        """Handle right-click event.

        Args:
            event: The event object
        """
        # Create and show the popup menu with proper accessibility focus
        menu = self.CreatePopupMenu()
        if menu:
            # Use PopupMenu which properly handles focus for screen readers
            # This ensures the menu gets keyboard focus and is accessible
            self.PopupMenu(menu)
            menu.Destroy()

    def CreatePopupMenu(self):
        """Create the popup menu.

        Returns:
            wx.Menu: The popup menu
        """
        # Use the menu handler from the frame to create the menu
        menu, items = self.frame.CreateTaskBarMenu()

        # Check if we have debug items
        if len(items) > 4:
            show_hide_item, refresh_item, settings_item, exit_item, *debug_items = items

            # Bind debug menu events if present
            if debug_items:
                test_alerts_item, verify_interval_item = debug_items
                self.Bind(wx.EVT_MENU, self.on_test_alerts, test_alerts_item)
                self.Bind(wx.EVT_MENU, self.on_verify_interval, verify_interval_item)
        else:
            show_hide_item, refresh_item, settings_item, exit_item = items

        # Bind standard menu events
        self.Bind(wx.EVT_MENU, self.on_show_hide, show_hide_item)
        self.Bind(wx.EVT_MENU, self.on_refresh, refresh_item)
        self.Bind(wx.EVT_MENU, self.on_settings, settings_item)
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)

        return menu

    def on_show_hide(self, event):
        """Handle show/hide menu item.

        Args:
            event: The event object
        """
        # Use the menu handler from the frame
        self.frame.OnTaskBarShowHide(event)

    def on_refresh(self, event):
        """Handle refresh menu item.

        Args:
            event: The event object
        """
        # Call the frame's OnRefresh method
        self.frame.OnRefresh(event)

    def on_settings(self, event):
        """Handle settings menu item.

        Args:
            event: The event object
        """
        # Call the frame's OnSettings method
        self.frame.OnSettings(event)

    def on_exit(self, event):
        """Handle exit menu item.

        Args:
            event: The event object
        """
        # Use the menu handler from the frame
        self.frame.OnTaskBarExit(event)

    def on_test_alerts(self, event):
        """Handle test alerts menu item.

        Args:
            event: The event object
        """
        # Call the frame's test_alert_update method
        if hasattr(self.frame, "test_alert_update"):
            self.frame.test_alert_update()
        else:
            logger.error("Frame does not have test_alert_update method")

    def on_verify_interval(self, event):
        """Handle verify interval menu item.

        Args:
            event: The event object
        """
        # Call the frame's verify_alert_interval method
        if hasattr(self.frame, "verify_alert_interval"):
            self.frame.verify_alert_interval()
        else:
            logger.error("Frame does not have verify_alert_interval method")

    def update_weather_data(self, weather_data: Dict[str, Any]):
        """Update the current weather data and refresh the taskbar icon text.

        Args:
            weather_data: Dictionary containing current weather data
        """
        self.current_weather_data = weather_data
        self.update_icon_text()

    def update_alerts_data(self, alerts_data: Optional[List[Dict[str, Any]]]):
        """Update the current alerts data and refresh the taskbar icon text.

        Args:
            alerts_data: List of current weather alerts or None
        """
        self.current_alerts_data = alerts_data
        self.update_icon_text()

    def update_icon_text(self):
        """Update the taskbar icon text based on current settings and weather data."""
        # Get settings from the frame's config
        settings = self.frame.config.get("settings", {})

        # Use the formatter to get the formatted text
        formatted_text = self.formatter.format_weather_data_for_tray(
            self.current_weather_data, self.current_alerts_data, settings
        )

        if formatted_text:
            self.set_icon(formatted_text)
            logger.debug(f"Updated taskbar icon text: {formatted_text}")
        else:
            # Fall back to default icon
            self.set_icon()
