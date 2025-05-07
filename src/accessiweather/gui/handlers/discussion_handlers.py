"""Discussion handlers for the WeatherApp class

This module contains the discussion-related handlers for the WeatherApp class.
"""

import functools
import logging

import wx

from .common import WeatherAppHandlerBase

logger = logging.getLogger(__name__)


class WeatherAppDiscussionHandlers(WeatherAppHandlerBase):
    """Discussion handlers for the WeatherApp class

    This class is meant to be inherited by WeatherApp, not used directly.
    It provides discussion-related event handlers for the WeatherApp class.
    """

    def OnViewDiscussion(self, event):  # event is required by wx
        """Handle view discussion button click

        Args:
            event: Button event
        """
        # Check if we're in nationwide view mode
        if hasattr(self, "_in_nationwide_mode") and self._in_nationwide_mode:
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
            if hasattr(self, "_discussion_timer") and self._discussion_timer is not None:
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
            if self._discussion_loading_dialog is not None:
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
                        if self._discussion_loading_dialog is not None:
                            self._discussion_loading_dialog.Destroy()
                    except Exception as destroy_e:
                        logger.error(f"Error destroying dialog: {destroy_e}")
                        # Try to hide it if we can't destroy it
                        try:
                            if self._discussion_loading_dialog is not None:
                                self._discussion_loading_dialog.Hide()
                        except Exception:
                            pass

                    # Clear references
                    self._discussion_loading_dialog = None

                    # Stop the timer
                    logger.debug("Stopping discussion timer")
                    if self._discussion_timer is not None:
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
            if hasattr(self, "_discussion_timer") and self._discussion_timer is not None:
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

    def _handle_nationwide_discussion(self):
        """Handle nationwide discussion view

        This method shows a dialog with tabbed interface for nationwide discussions.
        """
        logger.debug("Handling nationwide discussion view")

        # Check if we have the full discussion data
        if not hasattr(self, "_nationwide_wpc_full") and not hasattr(self, "_nationwide_spc_full"):
            wx.MessageBox(
                "No nationwide discussions available", "No Data", wx.OK | wx.ICON_INFORMATION
            )
            return

        # Create the national discussion data structure
        national_data = {
            "national_discussion_summaries": {
                "wpc": {
                    "short_range_full": (
                        self._nationwide_wpc_full if hasattr(self, "_nationwide_wpc_full") else None
                    )
                },
                "spc": {
                    "day1_full": (
                        self._nationwide_spc_full if hasattr(self, "_nationwide_spc_full") else None
                    )
                },
            }
        }

        # Show the national discussion dialog
        from ..dialogs import NationalDiscussionDialog

        logger.debug("Creating and showing NationalDiscussionDialog")
        dialog = NationalDiscussionDialog(self, national_data)
        dialog.ShowModal()
        dialog.Destroy()
        logger.debug("NationalDiscussionDialog closed")
