"""Display Managers for AccessiWeather UI.

This module provides classes for managing the display of weather data
in various UI components.

This module has been refactored for better maintainability. The functionality
is now split across multiple focused modules.
"""

import logging

from ..alerts_manager import AlertsDisplayManager
from ..data_extractors import WeatherDataExtractor
from ..data_formatters import WeatherDataFormatter
from .conditions_display import ConditionsDisplay
from .error_handler import ErrorHandler
from .forecast_display import ForecastDisplay
from .state_manager import StateManager

logger = logging.getLogger(__name__)


class WeatherDisplayManager:
    """Manages the display of weather data in UI components."""

    def __init__(self, frame):
        """Initialize the display manager.

        Args:
            frame: The main WeatherApp frame instance.
        """
        self.frame = frame
        self.formatter = WeatherDataFormatter(frame)
        self.extractor = WeatherDataExtractor(frame)
        self.alerts_manager = AlertsDisplayManager(frame)

        # Initialize specialized display managers
        self.state_manager = StateManager(frame)
        self.forecast_display = ForecastDisplay(frame, self.formatter)
        self.conditions_display = ConditionsDisplay(frame, self.formatter, self.extractor)
        self.error_handler = ErrorHandler(frame)

    def display_loading_state(self, location_name=None, is_nationwide=False):
        """Display loading state in the UI.

        Args:
            location_name: Optional location name for status text
            is_nationwide: Whether this is a nationwide forecast
        """
        self.state_manager.display_loading_state(location_name, is_nationwide)

    def display_ready_state(self):
        """Display ready state in the UI."""
        self.state_manager.display_ready_state()

    def display_forecast(self, forecast_data, hourly_forecast_data=None):
        """Display forecast data in the UI.

        Args:
            forecast_data: Dictionary with forecast data
            hourly_forecast_data: Optional dictionary with hourly forecast data
        """
        self.forecast_display.display_forecast(forecast_data, hourly_forecast_data)

    def display_current_conditions(self, conditions_data):
        """Display current weather conditions in the UI.

        Args:
            conditions_data: Dictionary with current conditions data
        """
        self.conditions_display.display_current_conditions(conditions_data)

    def display_forecast_error(self, error):
        """Display forecast error in the UI.

        Args:
            error: Error message or exception object
        """
        self.error_handler.display_forecast_error(error)

    def display_alerts_error(self, error):
        """Display alerts error in the UI.

        Args:
            error: Error message or exception object
        """
        self.error_handler.display_alerts_error(error)


__all__ = ["WeatherDisplayManager"]
