"""System tray functionality for AccessiWeather.

This module provides the TaskBarIcon class for system tray integration.
"""

import logging
import os
import platform
from typing import Any, Dict, List, Optional

import wx
import wx.adv

from accessiweather.dynamic_format_manager import DynamicFormatManager
from accessiweather.format_string_parser import FormatStringParser
from accessiweather.gui.settings_dialog import (
    DEFAULT_TEMPERATURE_UNIT,
    TASKBAR_ICON_DYNAMIC_ENABLED_KEY,
    TASKBAR_ICON_TEXT_ENABLED_KEY,
    TASKBAR_ICON_TEXT_FORMAT_KEY,
    TEMPERATURE_UNIT_KEY,
)
from accessiweather.utils.temperature_utils import TemperatureUnit, format_temperature
from accessiweather.utils.unit_utils import (
    format_precipitation,
    format_pressure,
    format_visibility,
    format_wind_speed,
)

logger = logging.getLogger(__name__)

# Note: We rely on Windows' built-in system tray accessibility instead of global hotkeys
# This provides better compatibility with screen readers and system navigation


def _get_windows_version():
    """Get Windows version information for system tray compatibility.

    Returns:
        tuple: (major_version, minor_version, build_number) or None if not Windows
    """
    try:
        if platform.system() != "Windows":
            return None

        # Get Windows version
        version = platform.version().split(".")
        if len(version) >= 3:
            return (int(version[0]), int(version[1]), int(version[2]))
        return None
    except Exception as e:
        logger.warning(f"Could not determine Windows version: {e}")
        return None


def _is_windows_11():
    """Check if running on Windows 11.

    Returns:
        bool: True if Windows 11, False otherwise
    """
    version = _get_windows_version()
    if version is None:
        return False

    # Windows 11 is build 22000 and above
    major, minor, build = version
    return major >= 10 and build >= 22000


class TaskBarIcon(wx.adv.TaskBarIcon):
    """System tray icon for AccessiWeather."""

    # Class variable to track if an instance already exists
    _instance = None
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
        if self._is_destroyed:
            logger.debug("TaskBarIcon already cleaned up")
            return

        logger.debug("Cleaning up TaskBarIcon")

        # Check Windows version for compatibility
        windows_version = _get_windows_version()
        is_win11 = _is_windows_11()
        logger.debug(f"Windows version: {windows_version}, Windows 11: {is_win11}")

        try:
            # First, remove the icon from the system tray
            if self.IsOk():
                logger.debug("Removing icon from system tray")
                self.RemoveIcon()

                # On Windows 10, sometimes we need a small delay for proper cleanup
                if not is_win11:
                    import time

                    time.sleep(0.1)  # 100ms delay for Windows 10

            else:
                logger.warning("TaskBarIcon is not OK, cannot remove icon")
        except Exception as e:
            logger.error(f"Error removing taskbar icon: {e}", exc_info=True)

        try:
            # Then destroy the TaskBarIcon object
            logger.debug("Destroying TaskBarIcon object")
            self.Destroy()
        except Exception as e:
            logger.error(f"Error destroying taskbar icon: {e}", exc_info=True)
        finally:
            # Mark as destroyed and clear class reference
            self._is_destroyed = True
            if TaskBarIcon._instance is self:
                TaskBarIcon._instance = None
            logger.debug("TaskBarIcon cleanup completed")

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

        # Get the user's base format string, dynamic setting, and temperature unit preference
        user_format_string = settings.get(
            TASKBAR_ICON_TEXT_FORMAT_KEY, "{location} {temp} {condition}"
        )
        dynamic_enabled = settings.get(TASKBAR_ICON_DYNAMIC_ENABLED_KEY, True)
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
                # Use whole numbers (precision=0) when unit preference is 'both'
                precision = 0 if unit_pref == TemperatureUnit.BOTH else 1
                formatted_data["temp"] = format_temperature(
                    temp_f,
                    unit_pref,
                    temperature_c=temp_c,
                    precision=precision,
                    smart_precision=True,
                )

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
                pressure, unit_pref, pressure_mb=pressure_mb, precision=0
            )

        # Format visibility if available
        if "visibility" in formatted_data:
            visibility = formatted_data.get("visibility")
            visibility_km = visibility * 1.60934 if visibility is not None else None
            formatted_data["visibility"] = format_visibility(
                visibility, unit_pref, visibility_km=visibility_km, precision=1
            )

        # Format humidity if available
        if "humidity" in formatted_data:
            humidity = formatted_data.get("humidity")
            if humidity is not None:
                formatted_data["humidity"] = f"{humidity:.0f}"

        # Format feels like temperature if available
        if "feels_like_f" in formatted_data and "feels_like_c" in formatted_data:
            feels_like_f = formatted_data.get("feels_like_f")
            feels_like_c = formatted_data.get("feels_like_c")
            if feels_like_f is not None:
                # Use whole numbers (precision=0) when unit preference is 'both'
                precision = 0 if unit_pref == TemperatureUnit.BOTH else 1
                formatted_data["feels_like"] = format_temperature(
                    feels_like_f,
                    unit_pref,
                    temperature_c=feels_like_c,
                    precision=precision,
                    smart_precision=True,
                )

        # Format UV index if available
        if "uv" in formatted_data:
            uv = formatted_data.get("uv")
            if uv is not None:
                formatted_data["uv"] = f"{uv:.0f}"

        # Format precipitation if available
        if "precip" in formatted_data:
            precip = formatted_data.get("precip")
            if precip is not None:
                # Use format_precipitation function to handle units based on user preference
                formatted_data["precip"] = format_precipitation(precip, unit_pref, precision=1)

        # Format precipitation chance if available
        if "precip_chance" in formatted_data:
            precip_chance = formatted_data.get("precip_chance")
            if precip_chance is not None:
                formatted_data["precip_chance"] = f"{precip_chance:.0f}"

        try:
            # Determine which format string to use
            if dynamic_enabled:
                # Get dynamic format string based on current conditions
                format_string = self.dynamic_format_manager.get_dynamic_format_string(
                    self.current_weather_data,
                    self.current_alerts_data,
                    user_format=user_format_string,
                )
            else:
                # Use the user's static format string
                format_string = user_format_string

            # Add alert data to formatted_data if we have alerts
            if self.current_alerts_data:
                primary_alert = self._get_primary_alert(self.current_alerts_data)
                if primary_alert:
                    formatted_data.update(
                        {
                            "event": primary_alert.get("event", "Weather Alert"),
                            "severity": primary_alert.get("severity", "Unknown"),
                            "headline": primary_alert.get("headline", ""),
                        }
                    )

            # Format the string with formatted weather data
            formatted_text = self.format_parser.format_string(format_string, formatted_data)

            # Update the icon with the new text
            self.set_icon(formatted_text)
            logger.debug(f"Updated taskbar icon text: {formatted_text}")
        except Exception as e:
            logger.error(f"Error updating taskbar icon text: {e}")
            # Fall back to default icon
            self.set_icon()

    def _get_primary_alert(self, alerts_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Get the primary (highest severity) alert from alerts data.

        Args:
            alerts_data: List of alert dictionaries

        Returns:
            Primary alert dictionary or None if no alerts
        """
        if not alerts_data:
            return None

        # Priority mapping for alert severities
        severity_priority = {
            "Extreme": 4,
            "Severe": 3,
            "Moderate": 2,
            "Minor": 1,
            "Unknown": 0,
        }

        primary_alert = None
        max_priority = -1

        for alert in alerts_data:
            severity = alert.get("severity", "Unknown")
            priority = severity_priority.get(severity, 0)

            if priority > max_priority:
                max_priority = priority
                primary_alert = alert

        return primary_alert
