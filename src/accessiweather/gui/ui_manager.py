"""UI Manager for AccessiWeather.

This module provides the UIManager class which handles UI setup and updates.
"""

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

logger = logging.getLogger(__name__)


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
        self.frame.settings_btn = AccessibleButton(panel, wx.ID_ANY, "Settings")
        self.frame.minimize_to_tray_btn = AccessibleButton(panel, wx.ID_ANY, "Minimize to Tray")

        location_sizer.Add(self.frame.add_btn, 0, wx.ALL, 5)
        location_sizer.Add(self.frame.remove_btn, 0, wx.ALL, 5)
        location_sizer.Add(self.frame.refresh_btn, 0, wx.ALL, 5)
        location_sizer.Add(self.frame.settings_btn, 0, wx.ALL, 5)
        location_sizer.Add(self.frame.minimize_to_tray_btn, 0, wx.ALL, 5)
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

        # Handle regular location forecast data
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

                    text += f"{formatted_time}: {temp}°{unit}, {short_forecast}\n"

                text += "\n"

        # Add daily forecast
        text += "Extended Forecast:\n"
        for period in periods[:14]:  # Show up to 14 periods (7 days, day and night)
            name = period.get("name", "Unknown")
            temp = period.get("temperature", "?")
            unit = period.get("temperatureUnit", "F")
            details = period.get("detailedForecast", "No details available")

            text += f"{name}: {temp}°{unit}\n"
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

        if not alerts_data or "features" not in alerts_data:
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

        # Convert units if needed
        if temperature is not None:
            # Convert from Celsius to Fahrenheit
            temperature_f = (temperature * 9 / 5) + 32
            temperature_str = f"{temperature_f:.1f}°F ({temperature:.1f}°C)"
        else:
            temperature_str = "N/A"

        if dewpoint is not None:
            # Convert from Celsius to Fahrenheit
            dewpoint_f = (dewpoint * 9 / 5) + 32
            dewpoint_str = f"{dewpoint_f:.1f}°F ({dewpoint:.1f}°C)"
        else:
            dewpoint_str = "N/A"

        if wind_speed is not None:
            # Convert from km/h to mph
            wind_speed_mph = wind_speed * 0.621371
            wind_speed_str = f"{wind_speed_mph:.1f} mph ({wind_speed:.1f} km/h)"
        else:
            wind_speed_str = "N/A"

        if barometric_pressure is not None:
            # Convert from Pa to inHg
            pressure_inhg = barometric_pressure / 3386.39
            pressure_str = f"{pressure_inhg:.2f} inHg"
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

    def display_hourly_forecast(self, hourly_data):
        """Display hourly forecast data in the UI.

        Args:
            hourly_data: Dictionary with hourly forecast data
        """
        # This method is not currently used directly in the UI
        # The hourly forecast data is incorporated into the main forecast display
        pass

    def display_forecast_error(self, error_msg):
        """Display forecast error in the UI.

        Args:
            error_msg: Error message to display
        """
        self.frame.forecast_text.SetValue(f"Error fetching forecast: {error_msg}")
        self.frame.current_conditions_text.SetValue("Error fetching current conditions")

    def display_alerts_error(self, error_msg):
        """Display alerts error in the UI.

        Args:
            error_msg: Error message to display
        """
        # Clear alerts list
        self.frame.alerts_list.DeleteAllItems()

        # Add error message to alerts list
        index = self.frame.alerts_list.InsertItem(0, "Error")
        self.frame.alerts_list.SetItem(index, 1, "")  # Empty severity
        self.frame.alerts_list.SetItem(index, 2, f"Error fetching alerts: {error_msg}")

        # Disable the alert button since there are no valid alerts
        if hasattr(self.frame, "alert_btn"):
            self.frame.alert_btn.Disable()

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
