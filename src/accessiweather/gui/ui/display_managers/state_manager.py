"""State management for AccessiWeather UI display.

This module handles loading and ready states for the weather display.
"""

import logging

logger = logging.getLogger(__name__)


class StateManager:
    """Manages UI state transitions for weather data display."""

    def __init__(self, frame):
        """Initialize the state manager.

        Args:
            frame: The main WeatherApp frame instance.
        """
        self.frame = frame

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

    def display_ready_state(self):
        """Display ready state in the UI."""
        self.frame.refresh_btn.Enable()
        self.frame.SetStatusText("Ready")
