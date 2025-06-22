"""Service coordination for WeatherApp.

This module handles service integration, data fetching coordination,
async callbacks, and data processing coordination for the WeatherApp.
"""

import logging
import time

import wx

logger = logging.getLogger(__name__)


class WeatherAppServiceCoordination:
    """Service coordination for WeatherApp."""

    def __init__(self, weather_app):
        """Initialize the service coordination module.

        Args:
            weather_app: Reference to the main WeatherApp instance

        """
        self.app = weather_app
        logger.debug("WeatherAppServiceCoordination initialized")

    def _on_national_forecast_fetched(self, forecast_data):
        """Handle the fetched national forecast in the main thread

        Args:
            forecast_data: Dictionary with national forecast data

        """
        logger.debug("National forecast fetch callback received data")
        # Save forecast data
        self.app.current_forecast = forecast_data

        # Extract and store full discussions for WPC and SPC
        try:
            summaries = forecast_data.get("national_discussion_summaries", {})
            wpc_data = summaries.get("wpc", {})
            spc_data = summaries.get("spc", {})

            # Store full discussions from scraper data
            self.app._nationwide_wpc_full = wpc_data.get("full")
            self.app._nationwide_spc_full = spc_data.get("full")

            wpc_len = len(self.app._nationwide_wpc_full) if self.app._nationwide_wpc_full else 0
            spc_len = len(self.app._nationwide_spc_full) if self.app._nationwide_spc_full else 0
            logger.debug(f"Stored WPC discussion (length: {wpc_len})")
            logger.debug(f"Stored SPC discussion (length: {spc_len})")
        except Exception as e:
            logger.error(f"Error extracting national discussions: {e}")
            self.app._nationwide_wpc_full = None
            self.app._nationwide_spc_full = None

        # Update the UI
        self.app.ui_manager.display_forecast(forecast_data)

        # Update timestamp
        self.app.last_update = time.time()

        # Mark both forecast and alerts as complete for nationwide view
        self.app._forecast_complete = True
        self.app._alerts_complete = True  # No alerts for nationwide view

        # Check overall completion
        self.app._check_update_complete()

        # Notify testing framework if hook is set
        if self.app._testing_forecast_callback:
            self.app._testing_forecast_callback(forecast_data)

    def _on_current_conditions_fetched(self, conditions_data):
        """Handle the fetched current conditions in the main thread

        Args:
            conditions_data: Dictionary with current conditions data

        """
        logger.debug("_on_current_conditions_fetched received data")

        # Update the UI
        self.app.ui_manager.display_current_conditions(conditions_data)

    def _on_current_conditions_error(self, error):
        """Handle current conditions fetch error

        Args:
            error: Error message

        """
        logger.error(f"Current conditions fetch error: {error}")

        # Update the UI - use ui_manager to ensure proper error handling
        try:
            self.app.ui_manager.display_forecast_error(error)
        except Exception as e:
            logger.error(f"Error updating UI with current conditions error: {e}")

    def _on_hourly_forecast_fetched(self, hourly_forecast_data):
        """Handle the fetched hourly forecast in the main thread

        Args:
            hourly_forecast_data: Dictionary with hourly forecast data

        """
        logger.debug("_on_hourly_forecast_fetched received data")

        # Store the hourly forecast data to be used when displaying the regular forecast
        self.app.hourly_forecast_data = hourly_forecast_data

        # If we already have the regular forecast data, update the display
        if hasattr(self.app, "current_forecast") and self.app.current_forecast:
            self.app.ui_manager.display_forecast(self.app.current_forecast, hourly_forecast_data)

    def _on_forecast_fetched(self, forecast_data):
        """Handle the fetched forecast in the main thread

        Args:
            forecast_data: Dictionary with forecast data

        """
        logger.debug("_on_forecast_fetched received data")
        # Save forecast data
        self.app.current_forecast = forecast_data

        # Update the UI with both forecast and hourly forecast if available
        hourly_data = getattr(self.app, "hourly_forecast_data", None)
        self.app.ui_manager.display_forecast(forecast_data, hourly_data)

        # Update timestamp
        self.app.last_update = time.time()

        # Mark forecast as complete
        self.app._forecast_complete = True

        # If it's national data (identified by the specific key), mark alerts as complete too
        if "national_discussion_summaries" in forecast_data:
            self.app._alerts_complete = True

        # Check overall completion
        self.app._check_update_complete()

        # Notify testing framework if hook is set
        if self.app._testing_forecast_callback:
            self.app._testing_forecast_callback(forecast_data)

    def _on_forecast_error(self, error):
        """Handle forecast fetch error

        Args:
            error: Error message

        """
        logger.error(f"Forecast fetch error: {error}")

        # Update the UI
        self.app.ui_manager.display_forecast_error(error)

        # Mark forecast as complete and check overall completion
        self.app._forecast_complete = True
        self.app._check_update_complete()

        # Notify testing framework if hook is set
        if self.app._testing_forecast_error_callback:
            self.app._testing_forecast_error_callback(error)

    def _on_alerts_fetched(self, alerts_data):
        """Handle the fetched alerts in the main thread

        Args:
            alerts_data: Dictionary with alerts data

        """
        logger.debug("Alerts fetched successfully, handling in main thread")

        # Process alerts through notification service
        # The notification service will handle notifications for new/updated alerts
        # Unpack all three return values from process_alerts
        processed_alerts, new_count, updated_count = self.app.notification_service.process_alerts(
            alerts_data
        )

        # Log notification status
        logger.info(
            f"Alert processing complete: {len(processed_alerts)} total, {new_count} new, {updated_count} updated"
        )

        # Save processed alerts
        self.app.current_alerts = processed_alerts

        # Update the UI with the processed alerts
        self.app.ui_manager.display_alerts_processed(processed_alerts)

        # Mark alerts as complete
        self.app._alerts_complete = True

        # Check overall completion
        self.app._check_update_complete()

        # Notify testing framework if hook is set
        if self.app._testing_alerts_callback:
            self.app._testing_alerts_callback(alerts_data)

    def _on_alerts_error(self, error):
        """Handle alerts fetch error

        Args:
            error: Error message

        """
        logger.error(f"Alerts fetch error: {error}")

        # Update the UI
        self.app.ui_manager.display_alerts_error(error)

        # Mark alerts as complete and check overall completion
        self.app._alerts_complete = True

        self.app._check_update_complete()

        # Notify testing framework if hook is set
        if self.app._testing_alerts_error_callback:
            self.app._testing_alerts_error_callback(error)

    def _on_discussion_fetched(self, discussion_text, name, loading_dialog):
        """Handle the fetched discussion in the main thread

        Args:
            discussion_text: The discussion text
            name: Location name
            loading_dialog: Progress dialog to close

        """
        logger.debug(f"Discussion fetch callback received for {name}")

        # Clean up loading state using UI management module
        self.app.ui_management.cleanup_discussion_loading(loading_dialog)

        # Re-enable discussion button
        if hasattr(self.app, "discussion_btn") and self.app.discussion_btn:
            self.app.discussion_btn.Enable()

        # Show discussion dialog
        if discussion_text:
            title = f"Forecast Discussion for {name}"
            self.app.ShowWeatherDiscussionDialog(title, discussion_text)
        else:
            self.app.ShowMessageDialog(
                f"No forecast discussion available for {name}",
                "No Discussion Available",
                wx.OK | wx.ICON_INFORMATION,
            )

    def _on_discussion_error(self, error_message, name, loading_dialog):
        """Handle discussion fetch error in the main thread

        Args:
            error_message: Error message
            name: Location name
            loading_dialog: Progress dialog to close

        """
        logger.error(f"Discussion fetch error for {name}: {error_message}")

        # Clean up loading state using UI management module
        self.app.ui_management.cleanup_discussion_loading(loading_dialog)

        # Re-enable discussion button
        if hasattr(self.app, "discussion_btn") and self.app.discussion_btn:
            self.app.discussion_btn.Enable()

        # Show error message
        self.app.ShowMessageDialog(
            f"Error fetching forecast discussion for {name}: {error_message}",
            "Discussion Error",
            wx.OK | wx.ICON_ERROR,
        )
