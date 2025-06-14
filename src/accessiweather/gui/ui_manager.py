"""UI Manager for AccessiWeather.

This module provides the UIManager class which handles UI setup and updates.
"""

import logging

from .alerts_display import display_alerts, display_alerts_error, display_alerts_processed
from .forecast_display import display_forecast, display_hourly_forecast
from .ui_setup import bind_ui_events, setup_ui_components, update_ui_for_weather_source
from .weather_display import (
    display_current_conditions,
    display_forecast_error,
    display_loading_state,
    display_ready_state,
)
from .weather_source_detection import is_using_openmeteo

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

        # Set up UI components and get references to elements that need to be hidden for Open-Meteo
        panel, self.openmeteo_hidden_elements = setup_ui_components(frame)

        # Bind events
        bind_ui_events(frame, self)

    # Delegate all display methods to the appropriate modules
    def display_loading_state(self, location_name=None, is_nationwide=False):
        """Display loading state in the UI."""
        display_loading_state(self.frame, location_name, is_nationwide)

    def display_forecast(self, forecast_data, hourly_forecast_data=None):
        """Display forecast data in the UI."""
        display_forecast(self.frame, forecast_data, hourly_forecast_data)

    def display_alerts(self, alerts_data):
        """Display alerts data in the UI and return processed alerts."""
        return display_alerts(self.frame, alerts_data)

    def display_alerts_processed(self, processed_alerts):
        """Display already processed alerts data in the UI."""
        display_alerts_processed(self.frame, processed_alerts)

    def display_current_conditions(self, conditions_data):
        """Display current weather conditions in the UI."""
        display_current_conditions(self.frame, conditions_data)

    def display_hourly_forecast(self, hourly_data):
        """Display hourly forecast data in the UI."""
        display_hourly_forecast(self.frame, hourly_data)

    def display_forecast_error(self, error):
        """Display forecast error in the UI."""
        display_forecast_error(self.frame, error)

    def display_alerts_error(self, error):
        """Display alerts error in the UI."""
        display_alerts_error(self.frame, error)

    def display_ready_state(self):
        """Display ready state in the UI."""
        display_ready_state(self.frame)

    def update_ui_for_location_change(self):
        """Update UI elements when the location changes."""
        is_openmeteo = is_using_openmeteo(self.frame)
        update_ui_for_weather_source(self.frame, self.openmeteo_hidden_elements, is_openmeteo)

    def OnAlertSelected(self, event):
        """Handle alert list item selection event."""
        # Enable the alert button when an alert is selected
        if hasattr(self.frame, "alert_btn"):
            self.frame.alert_btn.Enable()
            # Set accessibility properties to ensure it's in the tab order
            self.frame.alert_btn.SetHelpText("View details for the selected alert")
            self.frame.alert_btn.SetToolTip("View details for the selected alert")

        # Allow the event to propagate
        event.Skip()
