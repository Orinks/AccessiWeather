"""UI Manager for AccessiWeather.

This module provides the UIManager class which handles UI setup and updates.
"""

import logging  # Added for potential logging in UI updates
from typing import Any, Dict, List, Optional

import wx

from accessiweather.api_client import ApiClientError, NoaaApiError
from accessiweather.gui.settings_dialog import DEFAULT_TEMPERATURE_UNIT, TEMPERATURE_UNIT_KEY
from accessiweather.utils.temperature_utils import TemperatureUnit, format_temperature
from accessiweather.utils.unit_utils import format_pressure, format_wind_speed

from .ui_components import (
    AccessibleButton,
    AccessibleChoice,
    AccessibleListCtrl,
    AccessibleStaticText,
    AccessibleTextCtrl,
)

logger = logging.getLogger(__name__)


# Shared utility functions for consistent data extraction
def _convert_wind_direction_to_cardinal(degrees):
    """Convert wind direction from degrees to cardinal direction.

    Args:
        degrees: Wind direction in degrees (0-360)

    Returns:
        str: Cardinal direction (N, NE, E, SE, S, SW, W, NW)
    """
    if degrees is None:
        logger.debug("Wind direction conversion: degrees is None")
        return ""

    try:
        degrees = float(degrees)
        logger.debug(f"Wind direction conversion: input {degrees}°")

        # Normalize to 0-360 range
        degrees = degrees % 360

        # Define cardinal directions with their degree ranges
        directions = [
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        ]

        # Each direction covers 22.5 degrees (360/16)
        index = int((degrees + 11.25) / 22.5) % 16
        cardinal = directions[index]
        logger.debug(f"Wind direction conversion: {degrees}° -> {cardinal}")
        return cardinal
    except (ValueError, TypeError) as e:
        logger.warning(f"Wind direction conversion failed for value '{degrees}': {e}")
        return ""


def _format_combined_wind(wind_speed, wind_direction, speed_unit="mph"):
    """Format combined wind speed and direction for display.

    Args:
        wind_speed: Wind speed value
        wind_direction: Wind direction (degrees or cardinal)
        speed_unit: Unit for wind speed display

    Returns:
        str: Formatted wind string (e.g., "15 mph NW")
    """
    logger.debug(
        f"Wind formatting: speed={wind_speed}, direction={wind_direction}, unit={speed_unit}"
    )

    if wind_speed is None:
        logger.debug("Wind formatting: speed is None, returning empty string")
        return ""

    try:
        speed_val = float(wind_speed)
        logger.debug(f"Wind formatting: parsed speed value {speed_val}")

        if speed_val == 0:
            logger.debug("Wind formatting: speed is 0, returning 'Calm'")
            return "Calm"

        # Format speed to whole number
        speed_str = f"{int(round(speed_val))} {speed_unit}"
        logger.debug(f"Wind formatting: formatted speed '{speed_str}'")

        # Handle direction
        if isinstance(wind_direction, (int, float)):
            direction = _convert_wind_direction_to_cardinal(wind_direction)
        else:
            direction = str(wind_direction) if wind_direction else ""

        logger.debug(f"Wind formatting: processed direction '{direction}'")

        if direction:
            result = f"{speed_str} {direction}"
        else:
            result = speed_str

        logger.debug(f"Wind formatting: final result '{result}'")
        return result
    except (ValueError, TypeError) as e:
        logger.warning(
            f"Wind formatting failed for speed='{wind_speed}', direction='{wind_direction}': {e}"
        )
        return ""


def _safe_get_location_name(location_service=None, fallback=""):
    """Safely get location name with thread safety.

    Args:
        location_service: Location service instance
        fallback: Fallback value if location cannot be retrieved

    Returns:
        str: Location name or fallback value
    """
    logger.debug(
        f"Location name retrieval: service={location_service is not None}, fallback='{fallback}'"
    )

    if not location_service:
        logger.debug("Location name retrieval: no location service provided")
        return fallback

    try:
        # Use the proper method to get current location name
        if hasattr(location_service, "get_current_location_name"):
            location_name = location_service.get_current_location_name()
            logger.debug(
                f"Location name retrieval: got '{location_name}' from get_current_location_name()"
            )
            return location_name if location_name is not None else fallback
        else:
            logger.debug(
                "Location name retrieval: location service has no get_current_location_name method"
            )
            return fallback
    except Exception as e:
        logger.error(f"Location name retrieval failed: {e}")
        return fallback


class UIManager:
    """Manages the UI setup and event bindings for the WeatherApp frame."""

    def __init__(self, frame, notifier):
        """Initialize the UI Manager.

        Args:
            frame: The main WeatherApp frame instance.
            notifier: The notification service instance.
        """
        self.frame = frame  # Reference to the main WeatherApp frame
        self.notifier = notifier  # Store notifier instance
        self._setup_ui()
        self._bind_events()

    def _create_standardized_taskbar_data(self, **kwargs):
        """Create a standardized dictionary structure for taskbar data.

        This ensures all API extraction methods return the same keys with consistent data types.

        Args:
            **kwargs: Key-value pairs for weather data

        Returns:
            dict: Standardized dictionary with all expected keys
        """
        # Define the standard structure with default values
        standard_data = {
            # Temperature data
            "temp": None,
            "temp_f": None,
            "temp_c": None,
            "feels_like": None,
            "feels_like_f": None,
            "feels_like_c": None,
            # Weather condition
            "condition": "",
            "weather_code": None,  # Weather code for dynamic format management
            # Wind data
            "wind_speed": None,
            "wind_dir": "",
            "wind": "",  # Combined wind placeholder
            # Other weather data
            "humidity": None,
            "pressure": None,
            "uv": None,
            "visibility": None,
            "precip": None,
            # Location
            "location": "",
        }

        # Update with provided values
        for key, value in kwargs.items():
            if key in standard_data:
                standard_data[key] = value
            else:
                # Log unexpected keys for debugging
                logger.debug(f"Unexpected key in taskbar data: {key}")

        return standard_data

    def _get_temperature_unit_preference(self):
        """Get the user's temperature unit preference from config.

        Returns:
            TemperatureUnit: The user's temperature unit preference
        """
        if not hasattr(self.frame, "config"):
            return TemperatureUnit.FAHRENHEIT

        settings = self.frame.config.get("settings", {})
        unit_pref = settings.get(TEMPERATURE_UNIT_KEY, DEFAULT_TEMPERATURE_UNIT)

        # Convert string to enum
        if unit_pref == TemperatureUnit.FAHRENHEIT.value:
            return TemperatureUnit.FAHRENHEIT
        elif unit_pref == TemperatureUnit.CELSIUS.value:
            return TemperatureUnit.CELSIUS
        elif unit_pref == TemperatureUnit.BOTH.value:
            return TemperatureUnit.BOTH
        else:
            return TemperatureUnit.FAHRENHEIT

    def _get_temperature_precision(self, unit_pref: TemperatureUnit) -> int:
        """Get the appropriate precision for temperature formatting.

        Args:
            unit_pref: The temperature unit preference

        Returns:
            int: Precision (0 for whole numbers when 'both', 1 otherwise)
        """
        return 0 if unit_pref == TemperatureUnit.BOTH else 1

    def _setup_ui(self):
        """Initialize the user interface components."""
        panel = wx.Panel(self.frame)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Location Dropdown (separated from buttons) ---
        location_sizer = wx.BoxSizer(wx.HORIZONTAL)
        location_label = AccessibleStaticText(panel, label="Location:")
        location_sizer.Add(location_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

        # Store UI elements directly on the frame object for access by handlers
        self.frame.location_choice = AccessibleChoice(panel, choices=[], label="Location Selection")
        location_sizer.Add(self.frame.location_choice, 1, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(location_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # --- Current Conditions Panel ---
        current_conditions_label = AccessibleStaticText(panel, label="Current Conditions:")
        main_sizer.Add(current_conditions_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.frame.current_conditions_text = AccessibleTextCtrl(
            panel,
            value="Select a location to view current conditions",
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            size=(-1, 100),
            label="Current Conditions Content",
        )
        main_sizer.Add(self.frame.current_conditions_text, 0, wx.ALL | wx.EXPAND, 10)

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

        # --- Control Buttons (moved to bottom) ---
        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Create all the buttons
        self.frame.add_btn = AccessibleButton(panel, wx.ID_ANY, "Add")
        self.frame.remove_btn = AccessibleButton(panel, wx.ID_ANY, "Remove")
        self.frame.refresh_btn = AccessibleButton(panel, wx.ID_ANY, "Refresh")
        self.frame.settings_btn = AccessibleButton(panel, wx.ID_ANY, "Settings")
        self.frame.minimize_to_tray_btn = AccessibleButton(panel, wx.ID_ANY, "Minimize to Tray")

        # Add buttons to the horizontal sizer
        buttons_sizer.Add(self.frame.add_btn, 0, wx.ALL, 5)
        buttons_sizer.Add(self.frame.remove_btn, 0, wx.ALL, 5)
        buttons_sizer.Add(self.frame.refresh_btn, 0, wx.ALL, 5)
        buttons_sizer.Add(self.frame.settings_btn, 0, wx.ALL, 5)
        buttons_sizer.Add(self.frame.minimize_to_tray_btn, 0, wx.ALL, 5)

        # Add the buttons sizer to the main sizer
        main_sizer.Add(buttons_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        # --- Finalize Panel Setup ---
        panel.SetSizer(main_sizer)
        self.frame.panel = panel  # Store panel reference if needed

    def _bind_events(self):
        """Bind UI events to their handlers in the main frame."""
        # Bind events to methods defined in WeatherApp
        self.frame.Bind(wx.EVT_CHOICE, self.frame.OnLocationChange, self.frame.location_choice)
        self.frame.Bind(wx.EVT_BUTTON, self.frame.OnAddLocation, self.frame.add_btn)

        # Add a direct handler for the remove button that respects debug_mode
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

        # Bind the test handler to the remove button
        self.frame.Bind(wx.EVT_BUTTON, on_remove_test, self.frame.remove_btn)

        self.frame.Bind(wx.EVT_BUTTON, self.frame.OnRefresh, self.frame.refresh_btn)
        self.frame.Bind(wx.EVT_BUTTON, self.frame.OnViewDiscussion, self.frame.discussion_btn)
        self.frame.Bind(wx.EVT_BUTTON, self.frame.OnViewAlert, self.frame.alert_btn)
        self.frame.Bind(
            wx.EVT_LIST_ITEM_ACTIVATED, self.frame.OnAlertActivated, self.frame.alerts_list
        )
        # Add binding for list item selection to enable the alert button
        self.frame.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnAlertSelected, self.frame.alerts_list)
        self.frame.Bind(wx.EVT_BUTTON, self.frame.OnSettings, self.frame.settings_btn)
        self.frame.Bind(wx.EVT_BUTTON, self.frame.OnMinimizeToTray, self.frame.minimize_to_tray_btn)
        # KeyDown is bound here as it relates to general UI interaction
        self.frame.Bind(wx.EVT_KEY_DOWN, self.frame.OnKeyDown)

    def display_loading_state(self, location_name=None, is_nationwide=False):
        """Display loading state in the UI.

        Args:
            location_name: Optional location name for status text
            is_nationwide: Whether this is a nationwide forecast
        """
        # Disable refresh button
        self.frame.refresh_btn.Disable()

        # Set loading text based on type
        loading_text = "Loading nationwide forecast..." if is_nationwide else "Loading forecast..."
        self.frame.forecast_text.SetValue(loading_text)

        # Set loading text for current conditions
        if not is_nationwide:
            self.frame.current_conditions_text.SetValue("Loading current conditions...")
        else:
            self.frame.current_conditions_text.SetValue(
                "Current conditions not available for nationwide view"
            )

        # Clear and set loading text in alerts list
        self.frame.alerts_list.DeleteAllItems()
        self.frame.alerts_list.InsertItem(0, "Loading alerts...")

        # Set status text
        if location_name:
            status = f"Updating weather data for {location_name}..."
            if is_nationwide:
                status = "Updating nationwide weather data..."
        else:
            status = "Updating weather data..."
        self.frame.SetStatusText(status)

    def display_forecast(self, forecast_data, hourly_forecast_data=None):
        """Display forecast data in the UI.

        Args:
            forecast_data: Dictionary with forecast data
            hourly_forecast_data: Optional dictionary with hourly forecast data
        """
        logger.debug(f"display_forecast received: {forecast_data}")

        # Detect nationwide data by presence of national_discussion_summaries key
        if "national_discussion_summaries" in forecast_data:
            try:
                formatted = self._format_national_forecast(forecast_data)
                self.frame.forecast_text.SetValue(formatted)
                # Clear current conditions for nationwide view
                self.frame.current_conditions_text.SetValue(
                    "Current conditions not available for nationwide view"
                )
            except Exception as e:
                logger.exception("Error formatting national forecast")
                self.frame.forecast_text.SetValue(f"Error formatting national forecast: {e}")
            return

        # Check if this is WeatherAPI.com data
        if self._is_weatherapi_data(forecast_data):
            try:
                formatted = self._format_weatherapi_forecast(forecast_data, hourly_forecast_data)
                self.frame.forecast_text.SetValue(formatted)
                return
            except Exception as e:
                logger.exception("Error formatting WeatherAPI.com forecast")
                self.frame.forecast_text.SetValue(f"Error formatting forecast: {e}")
                return

        # Handle NWS API location forecast data
        if not forecast_data or "properties" not in forecast_data:
            self.frame.forecast_text.SetValue("No forecast data available")
            return

        periods = forecast_data.get("properties", {}).get("periods", [])
        if not periods:
            self.frame.forecast_text.SetValue("No forecast periods available")
            return

        # Format forecast text
        text = ""

        # Add hourly forecast summary if available
        if hourly_forecast_data and "properties" in hourly_forecast_data:
            hourly_periods = hourly_forecast_data.get("properties", {}).get("periods", [])
            if hourly_periods:
                text += "Next 6 Hours:\n"
                for period in hourly_periods[:6]:  # Show next 6 hours
                    start_time = period.get("startTime", "")
                    # Extract just the time portion (HH:MM)
                    if start_time:
                        try:
                            # Format: 2023-01-01T12:00:00-05:00
                            time_part = start_time.split("T")[1][:5]  # Get "12:00"
                            hour = int(time_part.split(":")[0])
                            am_pm = "AM" if hour < 12 else "PM"
                            if hour == 0:
                                hour = 12
                            elif hour > 12:
                                hour -= 12
                            formatted_time = f"{hour}:{time_part.split(':')[1]} {am_pm}"
                        except (IndexError, ValueError):
                            formatted_time = start_time
                    else:
                        formatted_time = "Unknown"

                    temp = period.get("temperature", "?")
                    unit = period.get("temperatureUnit", "F")
                    short_forecast = period.get("shortForecast", "")

                    # Convert temperature if needed
                    if unit == "F" and isinstance(temp, (int, float)):
                        temp_f = temp
                        temp_c = (temp - 32) * 5 / 9
                    elif unit == "C" and isinstance(temp, (int, float)):
                        temp_c = temp
                        temp_f = (temp * 9 / 5) + 32
                    else:
                        temp_f = temp
                        temp_c = None

                    # Format temperature based on user preference
                    unit_pref = self._get_temperature_unit_preference()
                    temp_str = format_temperature(
                        temp_f,
                        unit_pref,
                        temperature_c=temp_c,
                        precision=self._get_temperature_precision(unit_pref),
                    )

                    text += f"{formatted_time}: {temp_str}, {short_forecast}\n"

                text += "\n"

        # Add daily forecast
        text += "Extended Forecast:\n"
        for period in periods[:14]:  # Show up to 14 periods (7 days, day and night)
            name = period.get("name", "Unknown")
            temp = period.get("temperature", "?")
            unit = period.get("temperatureUnit", "F")
            details = period.get("detailedForecast", "No details available")

            # Convert temperature if needed
            if unit == "F" and isinstance(temp, (int, float)):
                temp_f = temp
                temp_c = (temp - 32) * 5 / 9
            elif unit == "C" and isinstance(temp, (int, float)):
                temp_c = temp
                temp_f = (temp * 9 / 5) + 32
            else:
                temp_f = temp
                temp_c = None

            # Format temperature based on user preference
            unit_pref = self._get_temperature_unit_preference()
            temp_str = format_temperature(
                temp_f,
                unit_pref,
                temperature_c=temp_c,
                precision=self._get_temperature_precision(unit_pref),
            )

            text += f"{name}: {temp_str}\n"
            text += f"{details}\n\n"

        self.frame.forecast_text.SetValue(text)

    def _format_national_forecast(self, forecast_data):
        """Format national forecast data for display.

        Args:
            forecast_data: Dictionary containing national forecast data from scraper
                         with structure: {"national_discussion_summaries": {"wpc": {...}, "spc": {...}}}

        Returns:
            str: Formatted forecast text
        """
        if not forecast_data or "national_discussion_summaries" not in forecast_data:
            return "No national forecast data available"

        summaries = forecast_data["national_discussion_summaries"]
        text = "National Weather Overview\n\n"

        # Add WPC summary if available
        wpc_data = summaries.get("wpc", {})
        if wpc_data:
            text += "Weather Prediction Center (WPC) Summary:\n"
            # Check for both "summary" and "short_range_summary" keys
            wpc_summary = wpc_data.get("summary") or wpc_data.get("short_range_summary")
            text += (wpc_summary or "No WPC summary available") + "\n\n"

        # Add SPC summary if available
        spc_data = summaries.get("spc", {})
        if spc_data:
            text += "Storm Prediction Center (SPC) Summary:\n"
            # Check for both "summary" and "day1_summary" keys
            spc_summary = spc_data.get("summary") or spc_data.get("day1_summary")
            text += (spc_summary or "No SPC summary available") + "\n\n"

        # Add attribution
        attribution = summaries.get("attribution", "")
        if attribution:
            text += "\n" + attribution

        return text

    def _format_weatherapi_forecast(self, forecast_data, hourly_forecast_data=None):
        """Format WeatherAPI.com forecast data for display.

        Args:
            forecast_data: Dictionary with WeatherAPI.com forecast data
            hourly_forecast_data: Optional dictionary with hourly forecast data

        Returns:
            str: Formatted forecast text
        """
        if not forecast_data:
            return "No forecast data available"

        # Get the forecast data
        forecast_days = forecast_data.get("forecast", [])
        if not forecast_days:
            return "No forecast periods available"

        # Format forecast text
        text = ""

        # Add location information if available
        location = forecast_data.get("location", {})
        if location:
            location_name = location.get("name", "")
            region = location.get("region", "")
            country = location.get("country", "")
            if location_name and country:
                if region:
                    text += f"Forecast for {location_name}, {region}, {country}\n\n"
                else:
                    text += f"Forecast for {location_name}, {country}\n\n"

        # Add hourly forecast if available
        hourly_data = forecast_data.get("hourly", []) or (hourly_forecast_data or {}).get(
            "hourly", []
        )
        if hourly_data:
            text += "Next 6 Hours:\n"
            for hour in hourly_data[:6]:  # Show next 6 hours
                time_str = hour.get("time", "Unknown")
                # Format time string (e.g., "2023-01-01 12:00")
                try:
                    # Extract just the time portion (HH:MM)
                    time_parts = time_str.split(" ")
                    if len(time_parts) > 1:
                        time_part = time_parts[1]
                        hour_val = int(time_part.split(":")[0])
                        am_pm = "AM" if hour_val < 12 else "PM"
                        if hour_val == 0:
                            hour_val = 12
                        elif hour_val > 12:
                            hour_val -= 12
                        formatted_time = f"{hour_val}:{time_part.split(':')[1]} {am_pm}"
                    else:
                        formatted_time = time_str
                except (IndexError, ValueError):
                    formatted_time = time_str

                temp_f = hour.get("temperature", hour.get("temp_f", "?"))
                temp_c = hour.get("temp_c", None)
                condition = hour.get("condition", "")
                if isinstance(condition, dict):
                    condition = condition.get("text", "")

                # Format temperature based on user preference
                unit_pref = self._get_temperature_unit_preference()
                temp_str = format_temperature(
                    temp_f,
                    unit_pref,
                    temperature_c=temp_c,
                    precision=self._get_temperature_precision(unit_pref),
                )

                text += f"{formatted_time}: {temp_str}, {condition}\n"

            text += "\n"

        # Add daily forecast
        text += "Extended Forecast:\n"
        for day in forecast_days:
            date = day.get("date", "Unknown")
            high = day.get("high", day.get("maxtemp_f", "?"))
            low = day.get("low", day.get("mintemp_f", "?"))
            condition = day.get("condition", "")
            if isinstance(condition, dict):
                condition = condition.get("text", "")

            # Format date (e.g., "2023-01-01" to "Monday, January 1")
            try:
                from datetime import datetime

                date_obj = datetime.strptime(date, "%Y-%m-%d")
                formatted_date = date_obj.strftime("%A, %B %d")
            except (ValueError, TypeError):
                formatted_date = date

            # Get high and low temperatures in both units if available
            high_f = high
            high_c = day.get("maxtemp_c", None)
            low_f = low
            low_c = day.get("mintemp_c", None)

            # Format temperatures based on user preference
            unit_pref = self._get_temperature_unit_preference()
            precision = self._get_temperature_precision(unit_pref)
            high_str = format_temperature(
                high_f, unit_pref, temperature_c=high_c, precision=precision
            )
            low_str = format_temperature(low_f, unit_pref, temperature_c=low_c, precision=precision)

            text += f"{formatted_date}: High {high_str}, Low {low_str}\n"
            text += f"{condition}\n"

            # Add precipitation chance if available
            precip_chance = day.get(
                "precipitation_probability", day.get("daily_chance_of_rain", "")
            )
            if precip_chance:
                text += f"Chance of precipitation: {precip_chance}%\n"

            # Add wind information if available
            wind_speed = day.get("max_wind_speed", day.get("maxwind_mph", ""))
            if wind_speed:
                text += f"Wind: {wind_speed} mph\n"

            text += "\n"

        return text

    def display_alerts(self, alerts_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Display alerts data in the UI and return processed alerts.

        Args:
            alerts_data: Dictionary with alerts data

        Returns:
            List of alert properties dictionaries.
        """
        # Clear current alerts display
        alerts_list_ctrl = self.frame.alerts_list
        alerts_list_ctrl.DeleteAllItems()
        processed_alerts: List[Dict[str, Any]] = []  # List to store alert properties

        # Check if this is WeatherAPI.com data
        if alerts_data and self._is_weatherapi_data(alerts_data):
            try:
                return self._display_weatherapi_alerts(alerts_data)
            except Exception as e:
                logger.exception("Error displaying WeatherAPI.com alerts")
                # Add error message to alerts list
                index = alerts_list_ctrl.InsertItem(0, "Error")
                alerts_list_ctrl.SetItem(index, 1, "")  # Empty severity
                alerts_list_ctrl.SetItem(index, 2, f"Error displaying alerts: {str(e)}")
                return []

        # Handle NWS API alerts
        if not alerts_data or "features" not in alerts_data:
            # Check if this is an Open-Meteo location (no alerts available)
            generator = alerts_data.get("generator", "") if alerts_data else ""
            if "Open-Meteo" in generator:
                # Show informative message for Open-Meteo locations
                index = alerts_list_ctrl.InsertItem(0, "No Alerts Available")
                alerts_list_ctrl.SetItem(index, 1, "Info")
                alerts_list_ctrl.SetItem(
                    index, 2, "Weather alerts are not available for international locations"
                )

            # Disable the alert button if there are no alerts
            if hasattr(self.frame, "alert_btn"):
                self.frame.alert_btn.Disable()
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

        # Enable the alert button if there are alerts
        if features and hasattr(self.frame, "alert_btn"):
            self.frame.alert_btn.Enable()
            # Set accessibility properties to ensure it's in the tab order
            self.frame.alert_btn.SetHelpText("View details for the selected alert")
            self.frame.alert_btn.SetToolTip("View details for the selected alert")

        return processed_alerts

    def _display_weatherapi_alerts(self, alerts_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Display WeatherAPI.com alerts data in the UI.

        Args:
            alerts_data: Dictionary with WeatherAPI.com alerts data

        Returns:
            List of processed alert dictionaries
        """
        alerts_list_ctrl = self.frame.alerts_list
        processed_alerts: List[Dict[str, Any]] = []

        # Get alerts from the data
        alerts = alerts_data.get("alerts", [])
        if not alerts:
            # Disable the alert button if there are no alerts
            if hasattr(self.frame, "alert_btn"):
                self.frame.alert_btn.Disable()
            return processed_alerts

        # Process each alert
        for alert in alerts:
            event = alert.get("event", "Unknown")
            severity = alert.get("severity", "Unknown")
            headline = alert.get("headline", "No headline")

            index = alerts_list_ctrl.InsertItem(alerts_list_ctrl.GetItemCount(), event)
            alerts_list_ctrl.SetItem(index, 1, severity)
            alerts_list_ctrl.SetItem(index, 2, headline)
            processed_alerts.append(alert)  # Save alert data

        # Enable the alert button if there are alerts
        if alerts and hasattr(self.frame, "alert_btn"):
            self.frame.alert_btn.Enable()
            # Set accessibility properties to ensure it's in the tab order
            self.frame.alert_btn.SetHelpText("View details for the selected alert")
            self.frame.alert_btn.SetToolTip("View details for the selected alert")

        return processed_alerts

    def display_alerts_processed(self, processed_alerts: List[Dict[str, Any]]) -> None:
        """Display already processed alerts data in the UI.

        Args:
            processed_alerts: List of processed alert dictionaries
        """
        # Clear current alerts display
        alerts_list_ctrl = self.frame.alerts_list
        alerts_list_ctrl.DeleteAllItems()

        if not processed_alerts:
            # Disable the alert button if there are no alerts
            if hasattr(self.frame, "alert_btn"):
                self.frame.alert_btn.Disable()
            return

        for props in processed_alerts:
            event = props.get("event", "Unknown")
            severity = props.get("severity", "Unknown")
            headline = props.get("headline", "No headline")

            index = alerts_list_ctrl.InsertItem(alerts_list_ctrl.GetItemCount(), event)
            alerts_list_ctrl.SetItem(index, 1, severity)
            alerts_list_ctrl.SetItem(index, 2, headline)

        # Enable the alert button if there are alerts
        if hasattr(self.frame, "alert_btn"):
            self.frame.alert_btn.Enable()
            # Set accessibility properties to ensure it's in the tab order
            self.frame.alert_btn.SetHelpText("View details for the selected alert")
            self.frame.alert_btn.SetToolTip("View details for the selected alert")

    def display_current_conditions(self, conditions_data):
        """Display current weather conditions in the UI.

        Args:
            conditions_data: Dictionary with current conditions data
        """
        logger.debug(f"display_current_conditions received: {conditions_data}")

        # Create a dictionary for taskbar icon data
        taskbar_data = {}

        # Check if this is WeatherAPI.com data
        if self._is_weatherapi_data(conditions_data):
            try:
                text = self._format_weatherapi_current_conditions(conditions_data)
                self.frame.current_conditions_text.SetValue(text)

                # Extract data for taskbar icon
                taskbar_data = self._extract_weatherapi_data_for_taskbar(conditions_data)

                # Update taskbar icon with weather data
                if hasattr(self.frame, "taskbar_icon") and self.frame.taskbar_icon:
                    self.frame.taskbar_icon.update_weather_data(taskbar_data)

                return
            except Exception as e:
                logger.exception("Error formatting WeatherAPI.com current conditions")
                self.frame.current_conditions_text.SetValue(
                    f"Error formatting current conditions: {e}"
                )
                return

        # Handle NWS API data
        if not conditions_data or "properties" not in conditions_data:
            self.frame.current_conditions_text.SetValue("No current conditions data available")
            return

        properties = conditions_data.get("properties", {})

        # Extract key weather data
        temperature = properties.get("temperature", {}).get("value")
        dewpoint = properties.get("dewpoint", {}).get("value")
        wind_speed = properties.get("windSpeed", {}).get("value")
        wind_direction = properties.get("windDirection", {}).get("value")
        barometric_pressure = properties.get("barometricPressure", {}).get("value")
        relative_humidity = properties.get("relativeHumidity", {}).get("value")
        description = properties.get("textDescription", "No description available")

        # Get user's temperature unit preference
        unit_pref = self._get_temperature_unit_preference()

        # Extract data for taskbar icon
        taskbar_data = self._extract_nws_data_for_taskbar(conditions_data)

        # Update taskbar icon with weather data
        if hasattr(self.frame, "taskbar_icon") and self.frame.taskbar_icon:
            self.frame.taskbar_icon.update_weather_data(taskbar_data)

        # Convert units if needed - check the actual unit codes from the API
        if temperature is not None:
            temp_unit_code = properties.get("temperature", {}).get("unitCode", "")
            if "degF" in temp_unit_code:
                # Temperature is already in Fahrenheit
                temperature_f = temperature
                temperature_c = (temperature - 32) * 5 / 9
            else:
                # Temperature is in Celsius, convert to Fahrenheit
                temperature_f = (temperature * 9 / 5) + 32
                temperature_c = temperature

            # Format based on user preference
            temperature_str = format_temperature(
                temperature_f,
                unit_pref,
                temperature_c=temperature_c,
                precision=self._get_temperature_precision(unit_pref),
            )
        else:
            temperature_str = "N/A"

        if dewpoint is not None:
            dewpoint_unit_code = properties.get("dewpoint", {}).get("unitCode", "")
            if "degF" in dewpoint_unit_code:
                # Dewpoint is already in Fahrenheit
                dewpoint_f = dewpoint
                dewpoint_c = (dewpoint - 32) * 5 / 9
            else:
                # Dewpoint is in Celsius, convert to Fahrenheit
                dewpoint_f = (dewpoint * 9 / 5) + 32
                dewpoint_c = dewpoint

            # Format based on user preference
            dewpoint_str = format_temperature(
                dewpoint_f,
                unit_pref,
                temperature_c=dewpoint_c,
                precision=self._get_temperature_precision(unit_pref),
            )
        else:
            dewpoint_str = "N/A"

        if wind_speed is not None:
            # Convert from km/h to mph
            wind_speed_mph = wind_speed * 0.621371
            wind_speed_str = format_wind_speed(
                wind_speed_mph, unit_pref, wind_speed_kph=wind_speed, precision=1
            )
        else:
            wind_speed_str = "N/A"

        if barometric_pressure is not None:
            # Convert from Pa to inHg
            pressure_inhg = barometric_pressure / 3386.39
            # Convert from Pa to mb (hPa)
            pressure_mb = barometric_pressure / 100
            pressure_str = format_pressure(
                pressure_inhg, unit_pref, pressure_mb=pressure_mb, precision=2
            )
        else:
            pressure_str = "N/A"

        if relative_humidity is not None:
            humidity_str = f"{relative_humidity:.0f}%"
        else:
            humidity_str = "N/A"

        # Format wind direction
        if wind_direction is not None:
            # Convert degrees to cardinal direction
            directions = [
                "N",
                "NNE",
                "NE",
                "ENE",
                "E",
                "ESE",
                "SE",
                "SSE",
                "S",
                "SSW",
                "SW",
                "WSW",
                "W",
                "WNW",
                "NW",
                "NNW",
            ]
            index = round(wind_direction / 22.5) % 16
            wind_dir_str = directions[index]
        else:
            wind_dir_str = "N/A"

        # Format the text
        text = f"Current Conditions: {description}\n"
        text += f"Temperature: {temperature_str}\n"
        text += f"Humidity: {humidity_str}\n"
        text += f"Wind: {wind_dir_str} at {wind_speed_str}\n"
        text += f"Dewpoint: {dewpoint_str}\n"
        text += f"Pressure: {pressure_str}"

        self.frame.current_conditions_text.SetValue(text)

    def _format_weatherapi_current_conditions(self, conditions_data):
        """Format WeatherAPI.com current conditions data for display.

        Args:
            conditions_data: Dictionary with WeatherAPI.com current conditions data

        Returns:
            str: Formatted current conditions text
        """
        if not conditions_data:
            return "No current conditions data available"

        # Extract key weather data
        temperature = conditions_data.get("temperature")
        temperature_c = conditions_data.get("temperature_c")
        humidity = conditions_data.get("humidity")
        wind_speed = conditions_data.get("wind_speed")
        wind_speed_kph = conditions_data.get("wind_speed_kph")
        wind_direction = conditions_data.get("wind_direction")
        pressure = conditions_data.get("pressure")
        pressure_mb = conditions_data.get("pressure_mb")
        condition = conditions_data.get("condition", "")
        feelslike = conditions_data.get("feelslike")
        feelslike_c = conditions_data.get("feelslike_c")

        # Get user's temperature unit preference
        unit_pref = self._get_temperature_unit_preference()

        # Format temperature
        temperature_str = format_temperature(
            temperature,
            unit_pref,
            temperature_c=temperature_c,
            precision=self._get_temperature_precision(unit_pref),
        )

        # Format humidity
        humidity_str = f"{humidity}%" if humidity is not None else "N/A"

        # Format wind
        wind_speed_str = format_wind_speed(
            wind_speed, unit_pref, wind_speed_kph=wind_speed_kph, precision=1
        )

        # Format pressure
        pressure_str = format_pressure(pressure, unit_pref, pressure_mb=pressure_mb, precision=2)

        # Format feels like
        feelslike_str = format_temperature(
            feelslike,
            unit_pref,
            temperature_c=feelslike_c,
            precision=self._get_temperature_precision(unit_pref),
        )

        # Format the text
        text = f"Current Conditions: {condition}\n"
        text += f"Temperature: {temperature_str}\n"
        text += f"Feels Like: {feelslike_str}\n"
        text += f"Humidity: {humidity_str}\n"
        text += f"Wind: {wind_direction} at {wind_speed_str}\n"
        text += f"Pressure: {pressure_str}"

        return text

    def _extract_weatherapi_data_for_taskbar(self, conditions_data):
        """Extract relevant data from WeatherAPI.com conditions for the taskbar icon.

        Args:
            conditions_data: Dictionary with WeatherAPI.com current conditions data

        Returns:
            dict: Dictionary with extracted data for taskbar icon
        """
        if not conditions_data:
            return {}

        # Extract the current conditions
        current = conditions_data.get("current", {})
        condition = current.get("condition", {})

        # Create a dictionary with the data we want to display in the taskbar
        data = {
            "temp": current.get("temp_f"),
            "temp_f": current.get("temp_f"),
            "temp_c": current.get("temp_c"),
            "condition": condition.get("text", ""),
            "humidity": current.get("humidity"),
            "wind_speed": current.get("wind_mph"),
            "wind_dir": current.get("wind_dir"),
            "pressure": current.get("pressure_in"),
            "feels_like": current.get("feelslike_f"),
            "uv": current.get("uv"),
            "visibility": current.get("vis_miles"),
            "precip": current.get("precip_in"),
            "weather_code": condition.get("code"),  # WeatherAPI condition code
        }

        # Add location information if available
        location = conditions_data.get("location", {})
        if location:
            data["location"] = location.get("name", "")

        return data

    def _extract_nws_data_for_taskbar(self, conditions_data):
        """Extract relevant data from NWS API conditions for the taskbar icon.

        Args:
            conditions_data: Dictionary with NWS API current conditions data

        Returns:
            dict: Dictionary with extracted data for taskbar icon
        """
        try:
            if not conditions_data or "properties" not in conditions_data:
                logger.warning("NWS data extraction: Invalid or missing conditions data")
                return self._create_standardized_taskbar_data()

            properties = conditions_data.get("properties", {})
            logger.debug(
                f"NWS data extraction: Processing properties with keys: {list(properties.keys())}"
            )

            # Extract temperature with error handling
            temperature_f = None
            temperature_c = None
            try:
                temperature_value = properties.get("temperature", {}).get("value")
                temp_unit_code = properties.get("temperature", {}).get("unitCode", "")

                if temperature_value is not None:
                    if "degF" in temp_unit_code:
                        temperature_f = float(temperature_value)
                        temperature_c = (temperature_f - 32) * 5 / 9
                    else:
                        temperature_c = float(temperature_value)
                        temperature_f = (temperature_c * 9 / 5) + 32
                    logger.debug(
                        f"NWS temperature extracted: {temperature_f}°F / {temperature_c}°C"
                    )
                else:
                    logger.warning("NWS data extraction: No temperature value found")
            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"NWS data extraction: Error processing temperature: {e}")

            # Extract humidity with error handling
            humidity = None
            try:
                humidity_value = properties.get("relativeHumidity", {}).get("value")
                if humidity_value is not None:
                    humidity = float(humidity_value)
                    logger.debug(f"NWS humidity extracted: {humidity}%")
            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"NWS data extraction: Error processing humidity: {e}")

            # Extract wind data with error handling
            wind_speed_mph = None
            wind_dir = ""
            try:
                wind_speed_kph = properties.get("windSpeed", {}).get("value")
                if wind_speed_kph is not None:
                    wind_speed_mph = float(wind_speed_kph) * 0.621371
                    logger.debug(f"NWS wind speed extracted: {wind_speed_mph} mph")

                wind_direction_degrees = properties.get("windDirection", {}).get("value")
                if wind_direction_degrees is not None:
                    wind_dir = _convert_wind_direction_to_cardinal(wind_direction_degrees)
                    logger.debug(
                        f"NWS wind direction extracted: {wind_direction_degrees}° -> {wind_dir}"
                    )
            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"NWS data extraction: Error processing wind data: {e}")

            # Extract barometric pressure with error handling
            pressure_inhg = None
            try:
                pressure_pa = properties.get("barometricPressure", {}).get("value")
                if pressure_pa is not None:
                    pressure_inhg = float(pressure_pa) / 3386.39
                    logger.debug(f"NWS pressure extracted: {pressure_inhg} inHg")
            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"NWS data extraction: Error processing pressure: {e}")

            # Extract feels like temperature with error handling
            feels_like_f = None
            feels_like_c = None
            try:
                apparent_temp_value = properties.get("apparentTemperature", {}).get("value")
                apparent_temp_unit_code = properties.get("apparentTemperature", {}).get(
                    "unitCode", ""
                )

                if apparent_temp_value is not None:
                    if "degF" in apparent_temp_unit_code:
                        feels_like_f = float(apparent_temp_value)
                        feels_like_c = (feels_like_f - 32) * 5 / 9
                    else:
                        feels_like_c = float(apparent_temp_value)
                        feels_like_f = (feels_like_c * 9 / 5) + 32
                    logger.debug(f"NWS feels like extracted: {feels_like_f}°F / {feels_like_c}°C")
            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"NWS data extraction: Error processing feels like temperature: {e}")

            # Get location information with thread safety
            location_name = _safe_get_location_name(
                getattr(self.frame, "location_service", None), fallback=""
            )

            # Create combined wind placeholder using utility function
            wind_combined = _format_combined_wind(wind_speed_mph, wind_dir, "mph")

            # Extract weather code for dynamic format management
            weather_code = None
            # Check if this is Open-Meteo data mapped to NWS format
            present_weather = properties.get("presentWeather", [])
            if present_weather and len(present_weather) > 0:
                raw_string = present_weather[0].get("rawString")
                if raw_string and raw_string.isdigit():
                    weather_code = int(raw_string)

            # Get weather condition
            condition = properties.get("textDescription", "")
            logger.debug(f"NWS condition extracted: {condition}")

            # Create standardized data structure
            return self._create_standardized_taskbar_data(
                temp=temperature_f,
                temp_f=temperature_f,
                temp_c=temperature_c,
                condition=condition,
                humidity=humidity,
                wind_speed=wind_speed_mph,
                wind_dir=wind_dir,
                wind=wind_combined,
                pressure=pressure_inhg,
                feels_like=feels_like_f,
                feels_like_f=feels_like_f,
                feels_like_c=feels_like_c,
                location=location_name,
                weather_code=weather_code,
            )

        except Exception as e:
            logger.error(f"NWS data extraction: Unexpected error: {e}")
            return self._create_standardized_taskbar_data()

    def display_hourly_forecast(self, hourly_data):
        """Display hourly forecast data in the UI.

        Args:
            hourly_data: Dictionary with hourly forecast data
        """
        # This method is not currently used directly in the UI
        # The hourly forecast data is incorporated into the main forecast display
        pass

    def display_forecast_error(self, error):
        """Display forecast error in the UI.

        Args:
            error: Error message or exception object
        """
        error_msg = self._format_error_message(error)
        self.frame.forecast_text.SetValue(f"Error fetching forecast: {error_msg}")
        self.frame.current_conditions_text.SetValue("Error fetching current conditions")

    def display_alerts_error(self, error):
        """Display alerts error in the UI.

        Args:
            error: Error message or exception object
        """
        # Clear alerts list
        self.frame.alerts_list.DeleteAllItems()

        # Format the error message
        error_msg = self._format_error_message(error)

        # Add error message to alerts list
        index = self.frame.alerts_list.InsertItem(0, "Error")
        self.frame.alerts_list.SetItem(index, 1, "")  # Empty severity
        self.frame.alerts_list.SetItem(index, 2, f"Error fetching alerts: {error_msg}")

        # Disable the alert button since there are no valid alerts
        if hasattr(self.frame, "alert_btn"):
            self.frame.alert_btn.Disable()

    def _is_weatherapi_data(self, data):
        """Detect if the data is from WeatherAPI.com based on its structure.

        Args:
            data: Weather data dictionary to check

        Returns:
            bool: True if the data is from WeatherAPI.com, False otherwise
        """
        if not data or not isinstance(data, dict):
            return False

        # WeatherAPI data has 'forecast' as a list, not under 'properties'
        if "forecast" in data and isinstance(data["forecast"], list):
            return True

        # WeatherAPI current conditions data has specific fields
        if "temperature" in data and "condition" in data:
            return True

        # WeatherAPI hourly data is in a list under 'hourly' key
        if "hourly" in data and isinstance(data["hourly"], list):
            return True

        # WeatherAPI alerts are in a list
        if "alerts" in data and isinstance(data["alerts"], list):
            return True

        # WeatherAPI location data has specific fields
        if "location" in data and isinstance(data["location"], dict):
            if "name" in data["location"] and "country" in data["location"]:
                return True

        # Not WeatherAPI data
        return False

    def _format_error_message(self, error):
        """Format an error message based on the error type.

        Args:
            error: Error message or exception object

        Returns:
            Formatted error message string
        """
        # If it's already a string, just return it
        if isinstance(error, str):
            return error

        # WeatherAPI.com error handling removed (no longer supported)

        # Handle NOAA API specific errors
        elif isinstance(error, NoaaApiError):
            if error.error_type == NoaaApiError.RATE_LIMIT_ERROR:
                return "NWS API rate limit exceeded. Please try again later."
            elif error.error_type == NoaaApiError.TIMEOUT_ERROR:
                return "NWS API request timed out. Please try again later."
            elif error.error_type == NoaaApiError.CONNECTION_ERROR:
                return "Connection error. Please check your internet connection."
            else:
                return f"NWS API error: {str(error)}"

        # Handle generic API client errors
        elif isinstance(error, ApiClientError):
            return f"API error: {str(error)}"

        # For any other exception, just convert to string
        return str(error)

    def display_ready_state(self):
        """Display ready state in the UI."""
        self.frame.refresh_btn.Enable()
        self.frame.SetStatusText("Ready")

    def OnAlertSelected(self, event):
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
