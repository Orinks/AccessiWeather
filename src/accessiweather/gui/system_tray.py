"""System tray functionality for AccessiWeather.

This module provides the TaskBarIcon class for system tray integration.
"""

import logging
import os
from typing import Any, Dict

import wx
import wx.adv

from accessiweather.format_string_parser import FormatStringParser
from accessiweather.gui.settings_dialog import (
    DEFAULT_TEMPERATURE_UNIT,
    TASKBAR_ICON_TEXT_ENABLED_KEY,
    TASKBAR_ICON_TEXT_FORMAT_KEY,
    TEMPERATURE_UNIT_KEY,
)
from accessiweather.utils.temperature_utils import TemperatureUnit, format_temperature
from accessiweather.utils.unit_utils import format_pressure, format_visibility, format_wind_speed

logger = logging.getLogger(__name__)


class TaskBarIcon(wx.adv.TaskBarIcon):
    """System tray icon for AccessiWeather."""

    def __init__(self, frame):
        """Initialize the TaskBarIcon.

        Args:
            frame: The main application frame (WeatherApp)
        """
        # Ensure we have a wx.App instance before initializing
        if not wx.App.Get():
            logger.warning("No wx.App instance found when creating TaskBarIcon. Creating one.")
            self._app = wx.App()
        else:
            self._app = wx.App.Get()

        super().__init__()
        self.frame = frame
        self.format_parser = FormatStringParser()
        self.current_weather_data = {}

        # Set the icon
        self.set_icon()

        # Bind events
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, self.on_left_dclick)
        self.Bind(wx.adv.EVT_TASKBAR_RIGHT_UP, self.on_right_click)

    def set_icon(self, tooltip_text=None):
        """Set the taskbar icon.

        Args:
            tooltip_text: Optional text to display in the taskbar icon tooltip.
                          If None, uses the default "AccessiWeather".
        """
        # Try to load the icon from the application's resources
        icon_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "resources", "icon.ico"
        )

        if not os.path.exists(icon_path):
            # If the icon doesn't exist, use a default icon
            icon = wx.Icon(wx.ArtProvider.GetIcon(wx.ART_INFORMATION))
        else:
            icon = wx.Icon(icon_path, wx.BITMAP_TYPE_ICO)

        # Use the provided tooltip text or default to "AccessiWeather"
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
        # Create and show the popup menu
        menu = self.CreatePopupMenu()
        if menu:
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

    def update_icon_text(self):
        """Update the taskbar icon text based on current settings and weather data."""
        # Check if we have weather data
        if not self.current_weather_data:
            logger.debug("No weather data available for taskbar icon text")
            return

        # Get settings from the frame's config
        settings = self.frame.config.get("settings", {})
        text_enabled = settings.get(TASKBAR_ICON_TEXT_ENABLED_KEY, False)

        if not text_enabled:
            # If text is not enabled, just set the default icon
            self.set_icon()
            return

        # Get the format string and temperature unit preference
        format_string = settings.get(TASKBAR_ICON_TEXT_FORMAT_KEY, "{temp}°F {condition}")
        unit_pref_str = settings.get(TEMPERATURE_UNIT_KEY, DEFAULT_TEMPERATURE_UNIT)

        # Convert string to enum
        if unit_pref_str == TemperatureUnit.FAHRENHEIT.value:
            unit_pref = TemperatureUnit.FAHRENHEIT
        elif unit_pref_str == TemperatureUnit.CELSIUS.value:
            unit_pref = TemperatureUnit.CELSIUS
        elif unit_pref_str == TemperatureUnit.BOTH.value:
            unit_pref = TemperatureUnit.BOTH
        else:
            unit_pref = TemperatureUnit.FAHRENHEIT

        # Create a copy of the weather data to format values based on unit preference
        formatted_data = self.current_weather_data.copy()

        # Format temperature if available
        if "temp_f" in formatted_data and "temp_c" in formatted_data:
            temp_f = formatted_data.get("temp_f")
            temp_c = formatted_data.get("temp_c")
            if temp_f is not None:
                formatted_data["temp"] = (
                    format_temperature(temp_f, unit_pref, temperature_c=temp_c, precision=1)
                    .replace("°F", "")
                    .replace("°C", "")
                )  # Remove unit symbols for cleaner display

        # Format wind speed if available
        if "wind_speed" in formatted_data:
            wind_speed = formatted_data.get("wind_speed")
            wind_speed_kph = wind_speed * 1.60934 if wind_speed is not None else None
            formatted_data["wind_speed"] = format_wind_speed(
                wind_speed, unit_pref, wind_speed_kph=wind_speed_kph, precision=1
            )

        # Format pressure if available
        if "pressure" in formatted_data:
            pressure = formatted_data.get("pressure")
            pressure_mb = pressure * 33.8639 if pressure is not None else None
            formatted_data["pressure"] = format_pressure(
                pressure, unit_pref, pressure_mb=pressure_mb, precision=2
            )

        # Format visibility if available
        if "visibility" in formatted_data:
            visibility = formatted_data.get("visibility")
            visibility_km = visibility * 1.60934 if visibility is not None else None
            formatted_data["visibility"] = format_visibility(
                visibility, unit_pref, visibility_km=visibility_km, precision=1
            )

        try:
            # Format the string with formatted weather data
            formatted_text = self.format_parser.format_string(format_string, formatted_data)

            # Update the icon with the new text
            self.set_icon(formatted_text)
            logger.debug(f"Updated taskbar icon text: {formatted_text}")
        except Exception as e:
            logger.error(f"Error updating taskbar icon text: {e}")
            # Fall back to default icon
            self.set_icon()
