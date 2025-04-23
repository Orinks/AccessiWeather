"""Event handlers for the WeatherApp class

This module contains event handlers for the WeatherApp class.
"""

import functools
import json
import logging
import os
import time
from typing import Any, Optional
import wx
from .alert_dialog import AlertDetailsDialog
from .dialogs import LocationDialog
from .settings_dialog import (
    API_CONTACT_KEY,
    CACHE_ENABLED_KEY,
    CACHE_TTL_KEY,
    MINIMIZE_ON_STARTUP_KEY,
    PRECISE_LOCATION_ALERTS_KEY,
    SettingsDialog,
)

logger = logging.getLogger(__name__)


class WeatherAppHandlers:
    """Event handlers for the WeatherApp class

    This class is meant to be inherited by WeatherApp, not used directly.
    It provides event handlers for the WeatherApp class.
    """

    # Type annotations for attributes that will be provided by WeatherApp
    timer: wx.Timer
    location_choice: wx.Choice
    location_service: Any
    forecast_text: wx.TextCtrl
    alerts_list: wx.ListCtrl
    current_alerts: list
    updating: bool
    last_update: float
    config: dict
    _config_path: str
    api_client: Any
    weather_service: Any
    notification_service: Any
    discussion_fetcher: Any
    _on_discussion_fetched: Any
    _on_discussion_error: Any

    # Methods that will be provided by WeatherApp
    def Destroy(self) -> None:
        """Placeholder for wx.Frame.Destroy method"""
        pass

    def UpdateWeatherData(self) -> None:
        """Placeholder for WeatherApp.UpdateWeatherData method"""
        pass

    def UpdateLocationDropdown(self) -> None:
        """Placeholder for WeatherApp.UpdateLocationDropdown method"""
        pass

    def SetStatusText(self, text: str) -> None:
        """Placeholder for wx.Frame.SetStatusText method"""
        pass

    def Bind(self, *args, **kwargs) -> None:
        """Placeholder for wx.Frame.Bind method"""
        pass

    def Unbind(self, *args, **kwargs) -> None:
        """Placeholder for wx.Frame.Unbind method"""
        pass

    def OnKeyDown(self, event):
        """Handle key down events for accessibility

        Args:
            event: Key event
        """
        # Handle key events for accessibility
        # For example, F5 to refresh
        if event.GetKeyCode() == wx.WXK_F5:
            self.OnRefresh(event)
        else:
            event.Skip()

    def OnClose(self, event, force_close=False):  # event is required by wx
        """Handle window close event.
        
        Args:
            event: The close event
            force_close: Whether to force the window to close
        """
        logger.info("OnClose called with force_close=%s", force_close)
        
        # Check for force close flag on the instance or parameter
        force_close = force_close or getattr(self, '_force_close', False)
        logger.debug("Final force_close value: %s", force_close)
        
        # Stop all fetcher threads first
        logger.info("Stopping fetcher threads...")
        self._stop_fetcher_threads()
        
        # If we're not force closing and have a taskbar icon, just hide
        if not force_close and hasattr(self, "taskbar_icon") and self.taskbar_icon:
            logger.debug("Hiding window instead of closing")
            # Stop the timer when hiding
            if hasattr(self, "timer") and self.timer.IsRunning():
                logger.debug("Stopping timer before hiding")
                self.timer.Stop()
            self.Hide()
            event.Veto()
            # Restart timer after hiding
            if hasattr(self, "timer"):
                logger.debug("Restarting timer after hiding")
                self.timer.Start()
            return
        
        # Force closing - clean up resources
        logger.info("Proceeding with force close cleanup")
        
        # Stop timer
        if hasattr(self, "timer") and self.timer.IsRunning():
            logger.debug("Stopping timer")
            self.timer.Stop()

        # Remove taskbar icon
        if hasattr(self, "taskbar_icon") and self.taskbar_icon:
            logger.debug("Removing taskbar icon")
            try:
                if hasattr(self.taskbar_icon, "RemoveIcon"):
                    self.taskbar_icon.RemoveIcon()
                self.taskbar_icon.Destroy()
                self.taskbar_icon = None
            except Exception as e:
                logger.error("Error removing taskbar icon: %s", e)

        # Save config
        if hasattr(self, "_save_config"):
            logger.debug("Saving configuration")
            try:
                self._save_config()
            except Exception as e:
                logger.error("Error saving config: %s", e)

        # Destroy the window
        logger.info("Destroying window")
        self.Destroy()

    def _stop_fetcher_threads(self):
        """Stop all fetcher threads directly."""
        logger.debug("Stopping all fetcher threads")
        try:
            # Stop forecast fetcher
            if hasattr(self, "forecast_fetcher"):
                logger.debug("Stopping forecast fetcher")
                if hasattr(self.forecast_fetcher, "cancel"):
                    self.forecast_fetcher.cancel()
                if hasattr(self.forecast_fetcher, "_stop_event"):
                    self.forecast_fetcher._stop_event.set()

            # Stop alerts fetcher
            if hasattr(self, "alerts_fetcher"):
                logger.debug("Stopping alerts fetcher")
                if hasattr(self.alerts_fetcher, "cancel"):
                    self.alerts_fetcher.cancel()
                if hasattr(self.alerts_fetcher, "_stop_event"):
                    self.alerts_fetcher._stop_event.set()

            # Stop discussion fetcher
            if hasattr(self, "discussion_fetcher"):
                logger.debug("Stopping discussion fetcher")
                if hasattr(self.discussion_fetcher, "cancel"):
                    self.discussion_fetcher.cancel()
                if hasattr(self.discussion_fetcher, "_stop_event"):
                    self.discussion_fetcher._stop_event.set()

            # Stop national forecast fetcher
            if hasattr(self, "national_forecast_fetcher"):
                logger.debug("Stopping national forecast fetcher")
                if hasattr(self.national_forecast_fetcher, "cancel"):
                    self.national_forecast_fetcher.cancel()
                if hasattr(self.national_forecast_fetcher, "_stop_event"):
                    self.national_forecast_fetcher._stop_event.set()

        except Exception as e:
            logger.error("Error stopping fetcher threads: %s", e, exc_info=True)

    def OnLocationChange(self, event):  # event is required by wx
        """Handle location change event

        Args:
            event: Choice event
        """
        # Get selected location
        selected = self.location_choice.GetStringSelection()
        if not selected:
            return

        # Check if this is the Nationwide location and disable remove button if it is
        if hasattr(self, "remove_btn") and self.location_service.is_nationwide_location(selected):
            self.remove_btn.Disable()
            # Accessibility: update accessible description
            self.remove_btn.SetHelpText("Remove button is disabled for nationwide location")
            self.remove_btn.SetToolTip("Cannot remove nationwide location")
            # Set nationwide mode flag if not already set
            if hasattr(self, '_in_nationwide_mode'):
                self._in_nationwide_mode = True
        elif hasattr(self, "remove_btn"):
            self.remove_btn.Enable()
            # Reset accessible description
            self.remove_btn.SetHelpText("Remove the selected location")
            self.remove_btn.SetToolTip("Remove the selected location")
            # Reset nationwide mode flag if set
            if hasattr(self, '_in_nationwide_mode'):
                self._in_nationwide_mode = False
                self._nationwide_wpc_full = None
                self._nationwide_spc_full = None

        # Set current location using the location service
        self.location_service.set_current_location(selected)

        # Set status and update weather
        self.SetStatusText(f"Loading weather data for {selected}...")
        self.UpdateWeatherData()

        # Explicitly clear the selection in the alerts list and disable the alert button
        # to prevent accessing a cached alert for a previous location
        if hasattr(self, "alerts_list") and hasattr(self, "alert_btn"):
            self.alerts_list.DeleteAllItems()
            self.alert_btn.Disable()

    def OnAddLocation(self, event):  # event is required by wx
        """Handle add location button click

        Args:
            event: Button event
        """
        # Show location dialog
        dialog = LocationDialog(self)
        result = dialog.ShowModal()

        if result == wx.ID_OK:
            # Get location data using the GetValues method
            name, lat, lon = dialog.GetValues()

            if name and lat is not None and lon is not None:
                # Add location using the location service
                self.location_service.add_location(name, lat, lon)

                # Update dropdown
                self.UpdateLocationDropdown()

                # Select the newly added location
                self.location_choice.SetStringSelection(name)

                # Set as current location
                self.location_service.set_current_location(name)

                # Update weather data
                self.UpdateWeatherData()

        dialog.Destroy()

    def OnRemoveLocation(self, event):  # event is required by wx
        """Handle remove location button click

        Args:
            event: Button event
        """
        # Get selected location
        selected = self.location_choice.GetStringSelection()
        if not selected:
            wx.MessageBox(
                "Please select a location to remove", "No Location Selected", wx.OK | wx.ICON_ERROR
            )
            return

        # Check if this is the Nationwide location
        if self.location_service.is_nationwide_location(selected):
            wx.MessageBox(
                "The Nationwide location cannot be removed.",
                "Cannot Remove",
                wx.OK | wx.ICON_INFORMATION
            )
            # Accessibility: announce for screen readers
            if hasattr(self, 'AnnounceForScreenReader'):
                self.AnnounceForScreenReader("The Nationwide location cannot be removed.")
            return

        # Confirm removal
        confirm = wx.MessageBox(
            f"Are you sure you want to remove {selected}?",
            "Confirm Removal",
            wx.YES_NO | wx.ICON_QUESTION,
        )

        if confirm == wx.YES:
            # Remove location using the location service
            removed = self.location_service.remove_location(selected)

            if not removed:
                wx.MessageBox(
                    f"Could not remove {selected}.",
                    "Error",
                    wx.OK | wx.ICON_ERROR
                )
                return

            # Update dropdown
            self.UpdateLocationDropdown()

            # Clear forecast and alerts if current location was removed
            if self.location_service.get_current_location_name() is None:
                self.forecast_text.SetValue("Select a location to view the forecast")
                self.alerts_list.DeleteAllItems()  # Clear display
                self.current_alerts = []
                self.SetStatusText("Location removed. Select a new location.")
            else:
                # If another location is now current, update data
                self.UpdateWeatherData()

    def OnRefresh(self, event):  # event is required by wx
        """Handle refresh button click

        Args:
            event: Button event
        """
        # Trigger weather data update
        self.UpdateWeatherData()

    def OnViewDiscussion(self, event):  # event is required by wx
        """Handle view discussion button click

        Args:
            event: Button event
        """
        # Check if we're in nationwide view mode
        if hasattr(self, '_in_nationwide_mode') and self._in_nationwide_mode:
            self._handle_nationwide_discussion()
            return
            
        # Get current location from the location service
        location = self.location_service.get_current_location()
        if location is None:
            wx.MessageBox(
                "Please select a location first", "No Location Selected", wx.OK | wx.ICON_ERROR
            )
            return

        # Show loading dialog
        name, lat, lon = location
        self.SetStatusText(f"Loading forecast discussion for {name}...")

        # Create a progress dialog
        loading_dialog = wx.ProgressDialog(
            "Fetching Discussion",
            f"Fetching forecast discussion for {name}...",
            maximum=100,
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT,
        )

        # Store the loading dialog as an instance variable so we can access it later
        self._discussion_loading_dialog = loading_dialog

        # Start a timer to pulse the dialog and check for cancel
        self._discussion_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_discussion_timer, self._discussion_timer)
        self._discussion_timer.Start(100)  # Check every 100ms

        # Fetch discussion data
        self.discussion_fetcher.fetch(
            lat,
            lon,
            on_success=functools.partial(
                self._on_discussion_fetched, name=name, loading_dialog=loading_dialog
            ),
            on_error=functools.partial(
                self._on_discussion_error, name=name, loading_dialog=loading_dialog
            ),
        )

    def _on_discussion_timer(self, event):  # event is required by wx
        """Handle timer events for the discussion loading dialog

        Args:
            event: Timer event
        """
        has_dialog = hasattr(self, "_discussion_loading_dialog")
        dialog_exists = has_dialog and self._discussion_loading_dialog is not None

        if not dialog_exists:
            # Dialog no longer exists, stop the timer
            if hasattr(self, "_discussion_timer"):
                logger.debug("Dialog no longer exists, stopping timer")
                self._discussion_timer.Stop()
                # Try to unbind the timer event to prevent memory leaks
                try:
                    self.Unbind(
                        wx.EVT_TIMER,
                        handler=self._on_discussion_timer,
                        source=self._discussion_timer,
                    )
                except Exception as e:
                    logger.error(f"Error unbinding timer event: {e}")
            return

        try:
            # Pulse the dialog and check for cancel
            # The first return value indicates if the user wants to continue (hasn't clicked cancel)
            # The second return value (skip) is not used in this implementation
            cont, _ = self._discussion_loading_dialog.Pulse()
            if not cont:  # User clicked cancel
                logger.debug("Cancel button clicked on discussion loading dialog")

                # Stop the fetching
                if hasattr(self, "discussion_fetcher"):
                    # Set the stop event to cancel the fetch
                    if hasattr(self.discussion_fetcher, "_stop_event"):
                        logger.debug("Setting stop event for discussion fetcher")
                        self.discussion_fetcher._stop_event.set()

                # Force immediate cleanup
                try:
                    logger.debug("Destroying discussion loading dialog")
                    self._discussion_loading_dialog.Destroy()
                except Exception as destroy_e:
                    logger.error(f"Error destroying dialog: {destroy_e}")
                    # Try to hide it if we can't destroy it
                    try:
                        self._discussion_loading_dialog.Hide()
                    except Exception:
                        pass

                # Clear references
                self._discussion_loading_dialog = None

                # Stop the timer
                logger.debug("Stopping discussion timer")
                self._discussion_timer.Stop()
                # Try to unbind the timer event to prevent memory leaks
                try:
                    self.Unbind(
                        wx.EVT_TIMER,
                        handler=self._on_discussion_timer,
                        source=self._discussion_timer,
                    )
                except Exception as e:
                    logger.error(f"Error unbinding timer event: {e}")

                # Re-enable the discussion button
                if hasattr(self, "discussion_btn") and self.discussion_btn:
                    logger.debug("Re-enabling discussion button")
                    self.discussion_btn.Enable()

                # Update status
                self.SetStatusText("Discussion fetch cancelled")

                # Force a UI update
                wx.SafeYield()
                # Process pending events to ensure UI is updated
                wx.GetApp().ProcessPendingEvents()
        except Exception as e:
            # Dialog might have been destroyed already
            logger.error(f"Error in discussion timer: {e}")
            if hasattr(self, "_discussion_timer"):
                self._discussion_timer.Stop()
                # Try to unbind the timer event to prevent memory leaks
                try:
                    self.Unbind(
                        wx.EVT_TIMER,
                        handler=self._on_discussion_timer,
                        source=self._discussion_timer,
                    )
                except Exception as unbind_e:
                    logger.error(f"Error unbinding timer event: {unbind_e}")

    def OnViewAlert(self, event):  # event is required by wx
        """Handle view alert button click

        Args:
            event: Button event
        """
        # Get selected alert
        selected = self.alerts_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox(
                "Please select an alert to view", "No Alert Selected", wx.OK | wx.ICON_ERROR
            )
            return

        # Get alert data
        if selected < len(self.current_alerts):
            alert = self.current_alerts[selected]
            title = alert.get("headline", "Weather Alert")

            # Create and show the alert details dialog
            dialog = AlertDetailsDialog(self, title, alert)
            dialog.ShowModal()
            dialog.Destroy()
        else:
            logger.error(
                f"Selected index {selected} out of range for "
                f"current_alerts (len={len(self.current_alerts)})"
            )
            wx.MessageBox("Error retrieving alert details.", "Error", wx.OK | wx.ICON_ERROR)

    def OnAlertActivated(self, event):
        """Handle alert list item activation (double-click)

        Args:
            event: List item activated event
        """
        # Just call the view alert handler
        self.OnViewAlert(event)

    def OnMinimizeToTray(self, event):  # event is required by wx
        """Handle minimize to tray button click

        Args:
            event: Button event
        """
        logger.debug("Minimizing to tray")
        self.Hide()

    def OnSettings(self, event):  # event is required by wx
        """Handle settings button click

        Args:
            event: Button event
        """
        # Get current settings
        settings = self.config.get("settings", {})
        api_settings = self.config.get("api_settings", {})

        # Combine settings and api_settings for the dialog
        combined_settings = settings.copy()
        combined_settings.update(api_settings)

        # Create settings dialog
        dialog = SettingsDialog(self, combined_settings)
        result = dialog.ShowModal()

        if result == wx.ID_OK:
            # Get updated settings
            updated_settings = dialog.get_settings()
            updated_api_settings = dialog.get_api_settings()

            # Update config
            self.config["settings"] = updated_settings
            self.config["api_settings"] = updated_api_settings

            # Save config
            self._save_config()

            # Note: We can't update the contact info directly in the API client
            # as it doesn't have a setter method. The contact info will be used
            # the next time the app is started.

            # Update notifier settings
            # Note: Alert radius is stored in config and will be used
            # the next time alerts are fetched

            # If precise location setting changed, refresh alerts
            old_precise_setting = settings.get(PRECISE_LOCATION_ALERTS_KEY, True)
            new_precise_setting = updated_settings.get(PRECISE_LOCATION_ALERTS_KEY, True)
            if old_precise_setting != new_precise_setting:
                logger.info(
                    f"Precise location setting changed from {old_precise_setting} "
                    f"to {new_precise_setting}, refreshing alerts"
                )
                # Refresh weather data to apply new setting
                self.UpdateWeatherData()

            # If minimize on startup setting changed, log it
            old_minimize_setting = settings.get(MINIMIZE_ON_STARTUP_KEY, False)
            new_minimize_setting = updated_settings.get(MINIMIZE_ON_STARTUP_KEY, False)
            if old_minimize_setting != new_minimize_setting:
                logger.info(
                    f"Minimize on startup setting changed from {old_minimize_setting} "
                    f"to {new_minimize_setting}"
                )

            # If cache settings changed, update API client if possible
            old_cache_enabled = settings.get(CACHE_ENABLED_KEY, True)
            new_cache_enabled = updated_settings.get(CACHE_ENABLED_KEY, True)
            old_cache_ttl = settings.get(CACHE_TTL_KEY, 300)
            new_cache_ttl = updated_settings.get(CACHE_TTL_KEY, 300)

            if old_cache_enabled != new_cache_enabled or old_cache_ttl != new_cache_ttl:
                logger.info(
                    f"Cache settings changed: enabled {old_cache_enabled} -> {new_cache_enabled}, "
                    f"TTL {old_cache_ttl} -> {new_cache_ttl}"
                )
                # Note: We can't update the cache settings directly in the API client
                # as it doesn't have setter methods. The cache settings will be used
                # the next time the app is started.

        dialog.Destroy()

    def OnTimer(self, event):  # event is required by wx
        """Handle timer event for periodic updates

        Args:
            event: Timer event
        """
        # Get update interval from config (default to 30 minutes)
        update_interval_minutes = self.config.get("settings", {}).get("update_interval_minutes", 30)
        update_interval_seconds = update_interval_minutes * 60

        # Check if it's time to update
        now = time.time()
        if (now - self.last_update) >= update_interval_seconds:
            if not self.updating:
                logger.info("Timer triggered weather update.")
                self.UpdateWeatherData()
            else:
                logger.debug("Timer skipped update: already updating.")

    def _save_config(self, show_errors=True):
        """Save configuration to file
        
        Args:
            show_errors: Whether to show error message boxes (default: True)
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        start_time = time.time()
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)

            # Save config
            with open(self._config_path, "w") as f:
                json.dump(self.config, f, indent=2)
                
            elapsed = time.time() - start_time
            logger.debug(f"[EXIT OPTIMIZATION] Configuration saved in {elapsed:.3f}s")
            return True
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[EXIT OPTIMIZATION] Failed to save config after {elapsed:.3f}s: {str(e)}")
            if show_errors:
                wx.MessageBox(
                    f"Failed to save configuration: {str(e)}",
                    "Configuration Error",
                    wx.OK | wx.ICON_ERROR,
                )
            return False

    def _save_config_async(self):
        """Save configuration in a separate thread to avoid blocking the UI
        
        Returns:
            thread: The started thread object, which can be joined if needed
        """
        import threading
        logger.debug(f"[EXIT OPTIMIZATION] Starting async config save thread")
        # Create a unique thread name with timestamp for easier tracking
        thread_name = f"ConfigSaveThread-{int(time.time())}"
        thread = threading.Thread(target=self._save_config_thread, daemon=True, name=thread_name)
        thread.start()
        
        # Register with thread manager for proper cleanup
        from accessiweather.utils.thread_manager import register_thread
        stop_event = threading.Event()
        register_thread(thread, stop_event, name=thread_name)
        return thread

    def _save_config_thread(self):
        """Thread function to save configuration without blocking the UI
        This is called by _save_config_async.
        """
        import threading
        thread_id = threading.get_ident()
        thread_name = threading.current_thread().name
        
        try:
            start_time = time.time()
            logger.debug(f"[EXIT OPTIMIZATION] Config save thread {thread_name} started")
            
            # Quick check if we should abort (app might be closing)
            from accessiweather.utils.thread_manager import get_thread_manager
            manager = get_thread_manager()
            thread_info = next((t for t in manager._threads.values() if t.get('thread') == threading.current_thread()), None)
            
            if thread_info and hasattr(thread_info.get('stop_event', None), 'is_set') and thread_info.get('stop_event').is_set():
                logger.debug(f"[EXIT OPTIMIZATION] Config save thread {thread_name} aborting due to stop event")
                return
            
            # Do the actual config save
            success = self._save_config(show_errors=False)
            elapsed = time.time() - start_time
            
            if success:
                logger.debug(f"[EXIT OPTIMIZATION] Async config save completed in {elapsed:.3f}s")
            else:
                logger.error(f"[EXIT OPTIMIZATION] Async config save failed after {elapsed:.3f}s")
        except Exception as e:
            logger.error(f"[EXIT OPTIMIZATION] Unexpected error in config save thread: {e}", exc_info=True)
        finally:
            # Always unregister thread when done for proper cleanup
            try:
                from accessiweather.utils.thread_manager import unregister_thread
                logger.debug(f"[EXIT OPTIMIZATION] Unregistering config save thread {thread_name}")
                unregister_thread(thread_id)
            except Exception as e:
                logger.warning(f"[EXIT OPTIMIZATION] Error unregistering config thread: {e}")

    def _handle_nationwide_discussion(self):
        """Handle nationwide discussion view
        
        This method shows a dialog allowing the user to select which nationwide discussion to view,
        """
        logger.debug("Handling nationwide discussion view")
        
        # Check if we have the full discussion data
        if not hasattr(self, '_nationwide_wpc_full') and not hasattr(self, '_nationwide_spc_full'):
            wx.MessageBox(
                "No nationwide discussions available", "No Data", wx.OK | wx.ICON_INFORMATION
            )
            return
        
        # Create a dialog to select which discussion to view
        choices = []
        if hasattr(self, '_nationwide_wpc_full') and self._nationwide_wpc_full:
            choices.append("Weather Prediction Center (WPC) Discussion")
        if hasattr(self, '_nationwide_spc_full') and self._nationwide_spc_full:
            choices.append("Storm Prediction Center (SPC) Discussion")
            
        # If only one choice, just show that one
        if len(choices) == 1:
            self._show_nationwide_discussion(0)
            return
            
        dialog = wx.SingleChoiceDialog(
            self, "Select a discussion to view:", "Nationwide Discussions", choices
        )
        result = dialog.ShowModal()
        selection = dialog.GetSelection()
        dialog.Destroy()
        
        if result == wx.ID_OK:
            self._show_nationwide_discussion(selection)
            
    def _show_nationwide_discussion(self, selection):
        """Show the selected nationwide discussion
        
        Args:
            selection: Index of the selected discussion (0 for WPC, 1 for SPC)
        """
        from .dialogs import WeatherDiscussionDialog
        
        if selection == 0 and hasattr(self, '_nationwide_wpc_full') and self._nationwide_wpc_full:
            # Show WPC discussion
            title = "Weather Prediction Center (WPC) Discussion"
            text = self._nationwide_wpc_full
        elif selection == 1 and hasattr(self, '_nationwide_spc_full') and self._nationwide_spc_full:
            # Show SPC discussion
            title = "Storm Prediction Center (SPC) Discussion"
            text = self._nationwide_spc_full
        else:
            logger.error(f"Invalid nationwide discussion selection: {selection}")
            return
            
        discussion_dialog = WeatherDiscussionDialog(self, title, text)
        discussion_dialog.ShowModal()
        discussion_dialog.Destroy()
        
    def _check_api_contact_configured(self):
        """Check if API contact information is configured and prompt if not"""
        # Check if api_settings section exists
        if "api_settings" not in self.config:
            logger.warning("API settings section missing from config")
            self.config["api_settings"] = {}

        # Check if api_contact is set
        api_contact = self.config.get("api_settings", {}).get(API_CONTACT_KEY, "")
        if not api_contact:
            logger.warning("API contact information not configured")
            dialog = wx.MessageDialog(
                self,
                "API contact information is required for NOAA API access. "
                "Would you like to configure it now?",
                "API Configuration Required",
                wx.YES_NO | wx.ICON_QUESTION,
            )
            result = dialog.ShowModal()
            dialog.Destroy()

            if result == wx.ID_YES:
                # Open settings dialog
                self.OnSettings(None)
