"""UI management for WeatherApp.

This module handles UI lifecycle, cleanup operations, debug methods,
and UI state management for the WeatherApp.
"""

import logging
import time

import wx

from ..settings.constants import ALERT_RADIUS_KEY, PRECISE_LOCATION_ALERTS_KEY, UPDATE_INTERVAL_KEY

logger = logging.getLogger(__name__)


class WeatherAppUIManagement:
    """UI management for WeatherApp."""

    def __init__(self, weather_app):
        """Initialize the UI management module.

        Args:
            weather_app: Reference to the main WeatherApp instance
        """
        self.app = weather_app
        logger.debug("WeatherAppUIManagement initialized")

    def setup_status_bar(self):
        """Set up the status bar based on debug mode."""
        if self.app.debug_mode:
            # Use the debug status bar in debug mode
            from ..debug_status_bar import DebugStatusBar

            self.app.status_bar = DebugStatusBar(self.app, UPDATE_INTERVAL_KEY)
            self.app.SetStatusBar(self.app.status_bar)
        else:
            # Use the standard status bar
            self.app.CreateStatusBar()

        self.app.SetStatusText("Ready")

    def setup_accessibility(self):
        """Register with accessibility system."""
        self.app.SetName("AccessiWeather")
        accessible = self.app.GetAccessible()
        if accessible:
            accessible.SetName("AccessiWeather")
            accessible.SetRole(wx.ACC_ROLE_WINDOW)

    def cleanup_discussion_loading(self, loading_dialog=None):
        """Clean up resources related to discussion loading

        Args:
            loading_dialog: Progress dialog instance (optional)
        """
        timer_id = None

        try:
            # --- Stop Timer --- (if applicable)
            if hasattr(self.app, "_discussion_timer") and self.app._discussion_timer:
                logger.debug("Stopping discussion timer")
                try:
                    # Store timer ID before stopping for unbinding
                    if hasattr(self.app._discussion_timer, "GetId"):
                        timer_id = self.app._discussion_timer.GetId()

                    # Stop the timer if it's running
                    if self.app._discussion_timer.IsRunning():
                        self.app._discussion_timer.Stop()
                except Exception as timer_e:
                    logger.error(f"Error stopping discussion timer: {timer_e}", exc_info=True)

            # --- Close Dialog --- Determine which dialog instance to close
            dialog_to_close = loading_dialog
            if not dialog_to_close and hasattr(self.app, "_discussion_loading_dialog"):
                dialog_to_close = self.app._discussion_loading_dialog

            if dialog_to_close:
                try:
                    # Check if it's a valid wx window instance before proceeding
                    if isinstance(dialog_to_close, wx.Window) and dialog_to_close.IsShown():
                        logger.debug("Hiding loading dialog")
                        dialog_to_close.Hide()
                        wx.SafeYield()  # Give UI a chance to process Hide
                        logger.debug("Destroying loading dialog")
                        dialog_to_close.Destroy()
                        wx.SafeYield()  # Give UI a chance to process Destroy
                    elif isinstance(dialog_to_close, wx.Window):
                        logger.debug(
                            "Loading dialog exists but is not shown, attempting destroy anyway."
                        )
                        # Attempt destroy even if not shown, might already be destroyed
                        try:
                            dialog_to_close.Destroy()
                            wx.SafeYield()
                        except wx.wxAssertionError:
                            logger.debug(
                                "Dialog likely already destroyed."
                            )  # Expected if already gone
                        except Exception as destroy_e:
                            logger.error(
                                f"Error destroying hidden/non-window dialog: {destroy_e}",
                                exc_info=True,
                            )
                    else:
                        logger.warning(
                            f"Item to close is not a valid wx.Window: {type(dialog_to_close)}"
                        )

                except wx.wxAssertionError:
                    # This often happens if the dialog is already destroyed (e.g., by Cancel)
                    logger.debug("Loading dialog was likely already destroyed.")
                except Exception as e:
                    logger.error(f"Error closing loading dialog: {e}", exc_info=True)
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
                        logger.debug("Unbound discussion timer event using handler and source")
                    except Exception as unbind_e:
                        logger.debug(f"Could not unbind timer with handler and source: {unbind_e}")

                        # Fall back to unbinding by ID if we have it
                        if timer_id is not None:
                            try:
                                self.app.Unbind(wx.EVT_TIMER, id=timer_id)
                                logger.debug(f"Unbound discussion timer event using ID: {timer_id}")
                            except Exception as id_unbind_e:
                                logger.error(
                                    f"Error unbinding timer event by ID: {id_unbind_e}",
                                    exc_info=True,
                                )
            except Exception as unbind_e:
                logger.error(f"Error during timer unbinding: {unbind_e}", exc_info=True)

            # --- Always clear references ---
            try:
                # Clear timer reference
                if hasattr(self.app, "_discussion_timer"):
                    self.app._discussion_timer = None

                # Clear dialog reference
                if hasattr(self.app, "_discussion_loading_dialog"):
                    logger.debug("Clearing discussion loading dialog reference")
                    self.app._discussion_loading_dialog = None

                # --- Force UI Update ---
                logger.debug("Processing pending events after cleanup")
                wx.GetApp().ProcessPendingEvents()
                wx.SafeYield()
            except Exception as cleanup_e:
                logger.error(f"Error during final cleanup: {cleanup_e}", exc_info=True)

            logger.debug("Discussion timer cleanup complete")

    def test_alert_update(self):
        """Manually trigger an alert update for testing purposes.

        This method is only available in debug mode.
        """
        if not self.app.debug_mode:
            logger.warning("test_alert_update called but debug mode is not enabled")
            return

        logger.info("[DEBUG] Manually triggering alert update")

        # Get current location
        location = self.app.location_service.get_current_location()
        if not location:
            logger.error("[DEBUG ALERTS] No location selected for alert testing")
            return

        # Extract coordinates
        _, lat, lon = location

        # Get alert settings from config
        settings = self.app.config.get("settings", {})
        precise_location = settings.get(PRECISE_LOCATION_ALERTS_KEY, True)
        alert_radius = settings.get(ALERT_RADIUS_KEY, 25)

        # Log the alert fetch parameters
        logger.info(
            f"[DEBUG ALERTS] Fetching alerts for coordinates ({lat}, {lon}), "
            f"precise_location={precise_location}, radius={alert_radius}"
        )

        # Start alerts fetching thread
        self.app.alerts_fetcher.fetch(
            lat,
            lon,
            on_success=self.app._on_alerts_fetched,
            on_error=self.app._on_alerts_error,
            precise_location=precise_location,
            radius=alert_radius,
        )

    def verify_update_interval(self):
        """Verify the unified update interval by logging detailed information.

        This method is only available in debug mode.
        """
        if not self.app.debug_mode:
            logger.warning("verify_update_interval called but debug mode is not enabled")
            return

        # Get update interval from config
        settings = self.app.config.get("settings", {})
        update_interval_minutes = settings.get(UPDATE_INTERVAL_KEY, 10)
        update_interval_seconds = update_interval_minutes * 60

        # Calculate time since last update
        now = time.time()
        time_since_last_update = now - self.app.last_update
        next_update_in = update_interval_seconds - time_since_last_update

        # Log detailed information
        logger.info(
            f"[DEBUG] Update interval verification:\n"
            f"  - Configured interval: {update_interval_minutes} minutes ({update_interval_seconds} seconds)\n"
            f"  - Last update timestamp: {self.app.last_update} ({time.ctime(self.app.last_update)})\n"
            f"  - Current timestamp: {now} ({time.ctime(now)})\n"
            f"  - Time since last update: {time_since_last_update:.1f} seconds\n"
            f"  - Next update in: {next_update_in:.1f} seconds\n"
            f"  - Update due: {'Yes' if time_since_last_update >= update_interval_seconds else 'No'}"
        )
