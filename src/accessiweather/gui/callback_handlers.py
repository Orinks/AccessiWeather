"""Callback handlers module for AccessiWeather.

This module contains all the callback methods for handling async data fetching
results, including forecast, alerts, discussions, and error handling.
"""

import logging
import time

import wx

logger = logging.getLogger(__name__)


class CallbackHandlers:
    """Handles all callback methods for async data fetching operations."""

    def __init__(self, app_instance):
        """Initialize the CallbackHandlers.

        Args:
            app_instance: The WeatherApp instance
        """
        self.app = app_instance
        self.logger = logger

    def on_national_forecast_fetched(self, forecast_data):
        """Handle the fetched national forecast in the main thread.

        Args:
            forecast_data: Dictionary with national forecast data
        """
        self.logger.debug("National forecast fetch callback received data")
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
            self.logger.debug(f"Stored WPC discussion (length: {wpc_len})")
            self.logger.debug(f"Stored SPC discussion (length: {spc_len})")
        except Exception as e:
            self.logger.error(f"Error extracting national discussions: {e}")
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

    def on_current_conditions_fetched(self, conditions_data):
        """Handle the fetched current conditions in the main thread.

        Args:
            conditions_data: Dictionary with current conditions data
        """
        self.logger.debug("on_current_conditions_fetched received data")

        # Update the UI
        self.app.ui_manager.display_current_conditions(conditions_data)

    def on_current_conditions_error(self, error):
        """Handle current conditions fetch error.

        Args:
            error: Error message
        """
        self.logger.error(f"Current conditions fetch error: {error}")

        # Update the UI - use ui_manager to ensure proper error handling
        try:
            self.app.ui_manager.display_forecast_error(error)
        except Exception as e:
            self.logger.error(f"Error updating UI with current conditions error: {e}")

    def on_hourly_forecast_fetched(self, hourly_forecast_data):
        """Handle the fetched hourly forecast in the main thread.

        Args:
            hourly_forecast_data: Dictionary with hourly forecast data
        """
        self.logger.debug("on_hourly_forecast_fetched received data")

        # Store the hourly forecast data to be used when displaying the regular forecast
        self.app.hourly_forecast_data = hourly_forecast_data

        # If we already have the regular forecast data, update the display
        if hasattr(self.app, "current_forecast") and self.app.current_forecast:
            self.app.ui_manager.display_forecast(self.app.current_forecast, hourly_forecast_data)

    def on_forecast_fetched(self, forecast_data):
        """Handle the fetched forecast in the main thread.

        Args:
            forecast_data: Dictionary with forecast data
        """
        self.logger.debug("on_forecast_fetched received data")
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

    def on_forecast_error(self, error):
        """Handle forecast fetch error.

        Args:
            error: Error message
        """
        self.logger.error(f"Forecast fetch error: {error}")

        # Update the UI
        self.app.ui_manager.display_forecast_error(error)

        # Mark forecast as complete and check overall completion
        self.app._forecast_complete = True
        self.app._check_update_complete()

        # Notify testing framework if hook is set
        if self.app._testing_forecast_error_callback:
            self.app._testing_forecast_error_callback(error)

    def on_alerts_fetched(self, alerts_data):
        """Handle the fetched alerts in the main thread.

        Args:
            alerts_data: Dictionary with alerts data
        """
        self.logger.debug("Alerts fetched successfully, handling in main thread")

        # Process alerts through notification service
        # The notification service will handle notifications for new/updated alerts
        # Unpack all three return values from process_alerts
        processed_alerts, new_count, updated_count = self.app.notification_service.process_alerts(
            alerts_data
        )

        # Log notification status
        self.logger.info(
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

    def on_alerts_error(self, error):
        """Handle alerts fetch error.

        Args:
            error: Error message
        """
        self.logger.error(f"Alerts fetch error: {error}")

        # Update the UI
        self.app.ui_manager.display_alerts_error(error)

        # Mark alerts as complete and check overall completion
        self.app._alerts_complete = True

        self.app._check_update_complete()

        # Notify testing framework if hook is set
        if self.app._testing_alerts_error_callback:
            self.app._testing_alerts_error_callback(error)

    def on_discussion_fetched(self, discussion_text, name, loading_dialog):
        """Handle the fetched discussion in the main thread.

        Args:
            discussion_text: The discussion text
            name: Location name
            loading_dialog: Progress dialog to close
        """
        self.logger.debug(f"Discussion fetch callback received for {name}")

        # Clean up loading state
        self._cleanup_discussion_loading(loading_dialog)

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

    def on_discussion_error(self, error_message, name, loading_dialog):
        """Handle discussion fetch error in the main thread.

        Args:
            error_message: Error message
            name: Location name
            loading_dialog: Progress dialog to close
        """
        self.logger.error(f"Discussion fetch error for {name}: {error_message}")

        # Clean up loading state
        self._cleanup_discussion_loading(loading_dialog)

        # Re-enable discussion button
        if hasattr(self.app, "discussion_btn") and self.app.discussion_btn:
            self.app.discussion_btn.Enable()

        # Show error message
        self.app.ShowMessageDialog(
            f"Error fetching forecast discussion for {name}: {error_message}",
            "Discussion Error",
            wx.OK | wx.ICON_ERROR,
        )

    def _cleanup_discussion_loading(self, loading_dialog=None):
        """Clean up resources related to discussion loading.

        Args:
            loading_dialog: Progress dialog instance (optional)
        """
        timer_id = None

        try:
            # --- Stop Timer --- (if applicable)
            if hasattr(self.app, "_discussion_timer") and self.app._discussion_timer:
                self.logger.debug("Stopping discussion timer")
                try:
                    # Store timer ID before stopping for unbinding
                    if hasattr(self.app._discussion_timer, "GetId"):
                        timer_id = self.app._discussion_timer.GetId()

                    # Stop the timer if it's running
                    if self.app._discussion_timer.IsRunning():
                        self.app._discussion_timer.Stop()
                except Exception as timer_e:
                    self.logger.error(f"Error stopping discussion timer: {timer_e}", exc_info=True)

            # --- Close Dialog --- Determine which dialog instance to close
            dialog_to_close = loading_dialog
            if not dialog_to_close and hasattr(self.app, "_discussion_loading_dialog"):
                dialog_to_close = self.app._discussion_loading_dialog

            if dialog_to_close:
                try:
                    # Check if it's a valid wx window instance before proceeding
                    if isinstance(dialog_to_close, wx.Window) and dialog_to_close.IsShown():
                        self.logger.debug("Hiding loading dialog")
                        dialog_to_close.Hide()
                        wx.SafeYield()  # Give UI a chance to process Hide
                        self.logger.debug("Destroying loading dialog")
                        dialog_to_close.Destroy()
                        wx.SafeYield()  # Give UI a chance to process Destroy
                    elif isinstance(dialog_to_close, wx.Window):
                        self.logger.debug(
                            "Loading dialog exists but is not shown, attempting destroy anyway."
                        )
                        # Attempt destroy even if not shown, might already be destroyed
                        try:
                            dialog_to_close.Destroy()
                            wx.SafeYield()
                        except wx.wxAssertionError:
                            self.logger.debug(
                                "Dialog likely already destroyed."
                            )  # Expected if already gone
                        except Exception as destroy_e:
                            self.logger.error(
                                f"Error destroying hidden/non-window dialog: {destroy_e}",
                                exc_info=True,
                            )
                    else:
                        self.logger.warning(
                            f"Item to close is not a valid wx.Window: {type(dialog_to_close)}"
                        )

                except wx.wxAssertionError:
                    # This often happens if the dialog is already destroyed (e.g., by Cancel)
                    self.logger.debug("Loading dialog was likely already destroyed.")
                except Exception as e:
                    self.logger.error(f"Error closing loading dialog: {e}", exc_info=True)
        finally:
            # --- Always unbind the timer event to prevent memory leaks ---
            try:
                if hasattr(self.app, "_discussion_timer") and self.app._discussion_timer:
                    # Try to unbind using the handler and source
                    try:
                        self.app.Unbind(
                            wx.EVT_TIMER,
                            handler=self.app._on_discussion_timer,
                            source=self.app._discussion_timer,
                        )
                        self.logger.debug("Unbound discussion timer event using handler and source")
                    except Exception as unbind_e:
                        self.logger.debug(
                            f"Could not unbind timer with handler and source: {unbind_e}"
                        )

                        # Fall back to unbinding by ID if we have it
                        if timer_id is not None:
                            try:
                                self.app.Unbind(wx.EVT_TIMER, id=timer_id)
                                self.logger.debug(
                                    f"Unbound discussion timer event using ID: {timer_id}"
                                )
                            except Exception as id_unbind_e:
                                self.logger.error(
                                    f"Error unbinding timer event by ID: {id_unbind_e}",
                                    exc_info=True,
                                )
            except Exception as unbind_e:
                self.logger.error(f"Error during timer unbinding: {unbind_e}", exc_info=True)

            # --- Always clear references ---
            try:
                # Clear timer reference
                if hasattr(self.app, "_discussion_timer"):
                    self.app._discussion_timer = None

                # Clear dialog reference
                if hasattr(self.app, "_discussion_loading_dialog"):
                    self.logger.debug("Clearing discussion loading dialog reference")
                    self.app._discussion_loading_dialog = None

                # --- Force UI Update ---
                self.logger.debug("Processing pending events after cleanup")
                wx.GetApp().ProcessPendingEvents()
                wx.SafeYield()
            except Exception as cleanup_e:
                self.logger.error(f"Error during final cleanup: {cleanup_e}", exc_info=True)

            self.logger.debug("Discussion timer cleanup complete")
