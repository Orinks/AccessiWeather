"""UI Manager for AccessiWeather.

This module provides the UIManager class which handles UI setup and updates.
Refactored to use modular components for better maintainability.
"""

import logging
from typing import Any, Dict, List, Optional

from .ui import (
    AlertsDisplayManager,
    EventHandlers,
    WeatherDataExtractor,
    WeatherDataFormatter,
    WeatherDisplayManager,
    WeatherSourceManager,
    WidgetFactory,
    is_weatherapi_data,
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

        # Initialize modular components
        self.widget_factory = WidgetFactory(frame)
        self.event_handlers = EventHandlers(frame)
        self.weather_display = WeatherDisplayManager(frame)
        self.alerts_display = AlertsDisplayManager(frame)
        self.weather_source = WeatherSourceManager(frame)
        self.data_extractor = WeatherDataExtractor(frame)
        self.data_formatter = WeatherDataFormatter(frame)

        # Set up UI and bind events
        self._setup_ui()
        self._bind_events()

    def _setup_ui(self):
        """Initialize the user interface components using the widget factory."""
        # Create the main panel and layout using the widget factory
        self.widget_factory.create_main_panel()

        # Store references to UI elements that may need to be hidden for Open-Meteo
        self.openmeteo_hidden_elements = self.widget_factory.get_openmeteo_hidden_elements()

    def _bind_events(self):
        """Bind UI events to their handlers using the event handlers manager."""
        self.event_handlers.bind_all_events()

    # Display methods - delegate to appropriate managers
    def display_loading_state(self, location_name=None, is_nationwide=False):
        """Display loading state in the UI."""
        self.weather_display.display_loading_state(location_name, is_nationwide)

    def display_ready_state(self):
        """Display ready state in the UI."""
        self.weather_display.display_ready_state()

    def display_forecast(self, forecast_data, hourly_forecast_data=None):
        """Display forecast data in the UI."""
        self.weather_display.display_forecast(forecast_data, hourly_forecast_data)

    def display_current_conditions(self, conditions_data):
        """Display current weather conditions in the UI."""
        self.weather_display.display_current_conditions(conditions_data)

    def display_alerts(self, alerts_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Display alerts data in the UI and return processed alerts."""
        return self.alerts_display.display_alerts(alerts_data)

    def display_alerts_processed(self, processed_alerts: List[Dict[str, Any]]) -> None:
        """Display already processed alerts data in the UI."""
        self.alerts_display.display_alerts_processed(processed_alerts)

    def display_forecast_error(self, error):
        """Display forecast error in the UI."""
        self.weather_display.display_forecast_error(error)

    def display_alerts_error(self, error):
        """Display alerts error in the UI."""
        self.weather_display.display_alerts_error(error)

    def display_hourly_forecast(self, hourly_data):
        """Display hourly forecast data in the UI."""
        # This method is not currently used directly in the UI
        # The hourly forecast data is incorporated into the main forecast display
        pass

    # Data extraction methods - delegate to data extractor
    def _extract_weatherapi_data_for_taskbar(self, conditions_data):
        """Extract relevant data from WeatherAPI.com conditions for the taskbar icon."""
        return self.data_extractor.extract_weatherapi_data_for_taskbar(conditions_data)

    def _extract_nws_data_for_taskbar(self, conditions_data):
        """Extract relevant data from NWS API conditions for the taskbar icon."""
        return self.data_extractor.extract_nws_data_for_taskbar(conditions_data)

    # Formatting methods - delegate to data formatter
    def _format_national_forecast(self, forecast_data):
        """Format national forecast data for display."""
        return self.data_formatter.format_national_forecast(forecast_data)

    def _format_weatherapi_forecast(self, forecast_data, hourly_forecast_data=None):
        """Format WeatherAPI.com forecast data for display."""
        return self.data_formatter.format_weatherapi_forecast(forecast_data, hourly_forecast_data)

    # Alerts methods - delegate to alerts manager
    def _display_weatherapi_alerts(self, alerts_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Display WeatherAPI.com alerts data in the UI."""
        return self.alerts_display._display_weatherapi_alerts(alerts_data)

    # Weather source methods - delegate to weather source manager
    def _is_using_openmeteo(self) -> bool:
        """Determine if the current location is using Open-Meteo as the weather source."""
        return self.weather_source.is_using_openmeteo()

    def _update_ui_for_weather_source(self):
        """Update UI elements based on the current weather source."""
        self.weather_source.update_ui_for_weather_source(self.openmeteo_hidden_elements)

    def update_ui_for_location_change(self):
        """Update UI elements when the location changes."""
        self.weather_source.update_ui_for_location_change(self.openmeteo_hidden_elements)

    # Utility methods - delegate to ui utilities
    def _is_weatherapi_data(self, data):
        """Detect if the data is from WeatherAPI.com based on its structure."""
        return is_weatherapi_data(data)

    # Temperature unit preference methods - delegate to data formatter
    def _get_temperature_unit_preference(self):
        """Get the user's temperature unit preference from config."""
        return self.data_formatter._get_temperature_unit_preference()

    def _get_temperature_precision(self, unit_pref):
        """Get the appropriate precision for temperature formatting."""
        return self.data_formatter._get_temperature_precision(unit_pref)

    # WeatherAPI formatting methods - delegate to data formatter
    def _format_weatherapi_current_conditions(self, conditions_data):
        """Format WeatherAPI.com current conditions data for display."""
        return self.data_formatter._format_weatherapi_current_conditions(conditions_data)


# Utility functions for backward compatibility with tests
def _convert_wind_direction_to_cardinal(degrees):
    """Convert wind direction from degrees to cardinal direction."""
    from .ui import convert_wind_direction_to_cardinal

    return convert_wind_direction_to_cardinal(degrees)


def _format_combined_wind(wind_speed, wind_direction, speed_unit="mph"):
    """Format combined wind speed and direction for display."""
    from .ui import format_combined_wind

    return format_combined_wind(wind_speed, wind_direction, speed_unit)
