"""Error handling for AccessiWeather UI display.

This module handles the display of various error states in the UI.
"""

import logging

from accessiweather.api_client import ApiClientError, NoaaApiError

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Handles error display in the UI."""

    def __init__(self, frame):
        """Initialize the error handler.

        Args:
            frame: The main WeatherApp frame instance.
        """
        self.frame = frame

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
