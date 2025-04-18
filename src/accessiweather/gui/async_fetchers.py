"""Asynchronous data fetching components for AccessiWeather

This module provides thread-based asynchronous fetching of weather data.
"""

import logging
import threading

import wx

logger = logging.getLogger(__name__)


# Helper function to safely use CallAfter
def safe_call_after(callback, *args, **kwargs):
    """Safely use wx.CallAfter to schedule callback on the main thread.

    Args:
        callback: Function to call on the main thread
        *args: Arguments to pass to the callback
        **kwargs: Keyword arguments to pass to the callback
    """
    try:
        # Check if the wx.App is still valid
        app = wx.GetApp()
        if app is None or not app.IsMainLoopRunning():
            logger.warning("Cannot schedule callback: Application context not available")
            return False
            
        # Log callback details
        callback_name = getattr(callback, "__name__", str(callback))
        logger.debug(f"Scheduling callback {callback_name} with args: {args}, kwargs: {kwargs}")

        # Always use wx.CallAfter to ensure main thread execution
        wx.CallAfter(callback, *args, **kwargs)
        logger.debug(f"Successfully scheduled callback {callback_name} using wx.CallAfter")
        return True
    except (AssertionError, RuntimeError) as e:
        # This might happen if wx.App isn't fully initialized or is destroyed
        logger.error(f"Could not schedule callback via wx.CallAfter: {e}")
        
        # Try to display an error to the user if this is a UI callback
        try:
            # Only attempt to show error dialog if we have a valid app
            if wx.GetApp() and wx.GetApp().IsMainLoopRunning():
                wx.CallAfter(lambda: wx.MessageBox("Error: Application context lost. Try restarting the application.", 
                                                "Error", wx.OK | wx.ICON_ERROR))
        except Exception as dialog_err:
            logger.error(f"Failed to show error dialog: {dialog_err}")
        
        return False


class ForecastFetcher:
    """Handles asynchronous fetching of forecast data"""

    def __init__(self, api_client):
        """Initialize forecast fetcher

        Args:
            api_client: NoaaApiClient instance
        """
        self.api_client = api_client
        self.thread = None
        self._stop_event = threading.Event()

    def fetch(self, lat, lon, on_success=None, on_error=None):
        """Fetch forecast data asynchronously

        Args:
            lat: Latitude
            lon: Longitude
            on_success: Callback for successful fetch
            on_error: Callback for error handling
        """
        # Cancel any existing fetch
        if self.thread is not None and self.thread.is_alive():
            logger.debug("Cancelling in-progress forecast fetch")
            self._stop_event.set()
            # Join with a short timeout to avoid blocking UI indefinitely
            self.thread.join(0.5)

        # Reset stop event for new fetch
        self._stop_event.clear()

        # Create and start new thread
        self.thread = threading.Thread(
            target=self._fetch_thread, args=(lat, lon, on_success, on_error)
        )
        self.thread.daemon = True
        self.thread.start()

    def _fetch_thread(self, lat, lon, on_success, on_error):
        """Thread function to fetch the forecast

        Args:
            lat: Latitude
            lon: Longitude
            on_success: Success callback
            on_error: Error callback
        """
        try:
            # Check if we've been asked to stop
            if self._stop_event.is_set():
                logger.debug("Forecast fetch cancelled before API call")
                return

            # Get forecast data from API
            forecast_data = self.api_client.get_forecast(lat, lon)

            # Check again if we've been asked to stop before delivering results
            if self._stop_event.is_set():
                logger.debug("Forecast fetch completed but cancelled")
                return

            # Call success callback if provided
            if on_success and not self._stop_event.is_set():
                # Call callback on main thread
                if not safe_call_after(on_success, forecast_data):
                    logger.error("Failed to deliver forecast data due to application context issues")
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"Failed to retrieve forecast: {str(e)}")
                if on_error:
                    # Call error callback on main thread
                    error_msg = f"Unable to retrieve forecast data: {str(e)}"
                    if not safe_call_after(on_error, error_msg):
                        logger.error("Failed to deliver forecast error due to application context issues")


class AlertsFetcher:
    """Handles asynchronous fetching of alerts data"""

    def __init__(self, api_client):
        """Initialize alerts fetcher

        Args:
            api_client: NoaaApiClient instance
        """
        self.api_client = api_client
        self.thread = None
        self._stop_event = threading.Event()

    def fetch(self, lat, lon, on_success=None, on_error=None, precise_location=True, radius=25):
        """Fetch alerts data asynchronously

        Args:
            lat: Latitude
            lon: Longitude
            on_success: Callback for successful fetch
            on_error: Callback for error handling
            precise_location: Whether to get alerts for the precise location or statewide
            radius: Radius in miles to search for alerts if location type cannot be determined
        """
        # Cancel any existing fetch
        if self.thread is not None and self.thread.is_alive():
            logger.debug("Cancelling in-progress alerts fetch")
            self._stop_event.set()
            # Join with a short timeout to avoid blocking UI indefinitely
            self.thread.join(0.5)

        # Reset stop event for new fetch
        self._stop_event.clear()

        # Create and start new thread
        self.thread = threading.Thread(
            target=self._fetch_thread,
            args=(lat, lon, on_success, on_error, precise_location, radius),
        )
        self.thread.daemon = True
        self.thread.start()

    def _fetch_thread(self, lat, lon, on_success, on_error, precise_location, radius):
        """Thread function to fetch the alerts

        Args:
            lat: Latitude
            lon: Longitude
            on_success: Success callback
            on_error: Error callback
            precise_location: Whether to get alerts for the precise location or statewide
            radius: Radius in miles to search for alerts if location type cannot be determined
        """
        try:
            # Check if we've been asked to stop
            if self._stop_event.is_set():
                logger.debug("Alerts fetch cancelled before API call")
                return

            # Get alerts data from API with precise location setting
            logger.debug(
                f"Fetching alerts with precise_location={precise_location}, radius={radius}"
            )
            alerts_data = self.api_client.get_alerts(
                lat, lon, radius=radius, precise_location=precise_location
            )

            # Check again if we've been asked to stop before delivering results
            if self._stop_event.is_set():
                logger.debug("Alerts fetch completed but cancelled")
                return

            # Call success callback if provided
            if on_success and not self._stop_event.is_set():
                # Call callback on main thread
                if not safe_call_after(on_success, alerts_data):
                    logger.error("Failed to deliver alerts data due to application context issues")
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"Failed to retrieve alerts: {str(e)}")
                if on_error:
                    # Call error callback on main thread
                    error_msg = f"Unable to retrieve alerts data: {str(e)}"
                    if not safe_call_after(on_error, error_msg):
                        logger.error("Failed to deliver alerts error due to application context issues")


class DiscussionFetcher:
    """Handles asynchronous fetching of weather discussion data"""

    def __init__(self, api_client):
        """Initialize discussion fetcher

        Args:
            api_client: NoaaApiClient instance
        """
        self.api_client = api_client
        self.thread = None
        self._stop_event = threading.Event()

    def fetch(self, lat, lon, on_success=None, on_error=None, additional_data=None):
        """Fetch discussion data asynchronously

        Args:
            lat: Latitude
            lon: Longitude
            on_success: Callback for successful fetch
            on_error: Callback for error handling
            additional_data: Additional data to pass to callbacks
        """
        # Cancel any existing fetch
        if self.thread is not None and self.thread.is_alive():
            logger.debug("Cancelling in-progress discussion fetch")
            self._stop_event.set()
            # Join with a short timeout to avoid blocking UI indefinitely
            self.thread.join(0.5)

        # Reset stop event for new fetch
        self._stop_event.clear()

        # Create and start new thread
        self.thread = threading.Thread(
            target=self._fetch_thread, args=(lat, lon, on_success, on_error, additional_data)
        )
        self.thread.daemon = True
        self.thread.start()

    def _fetch_thread(self, lat, lon, on_success, on_error, additional_data):
        """Thread function to fetch the discussion

        Args:
            lat: Latitude
            lon: Longitude
            on_success: Success callback
            on_error: Error callback
            additional_data: Additional data to pass to callbacks
        """
        try:
            # Check if we've been asked to stop
            if self._stop_event.is_set():
                logger.debug("Discussion fetch cancelled before API call")
                return

            # Get discussion text from API
            logger.debug(f"Calling get_discussion with coordinates: ({lat}, {lon})")
            try:
                logger.debug("About to call api_client.get_discussion")
                discussion_text = self.api_client.get_discussion(lat, lon)
                logger.debug("Returned from api_client.get_discussion call")

                # Log the discussion text
                if discussion_text is None:
                    logger.warning("API returned None for discussion text")
                    # Use a default message instead of None
                    discussion_text = "No discussion available"
                else:
                    logger.debug(
                        f"API returned discussion text with length: {len(discussion_text)}"
                    )
                    # Log the first 100 characters of the discussion text
                    preview = (
                        discussion_text[:100].replace("\n", "\\n") if discussion_text else "None"
                    )
                    logger.debug(f"Discussion text preview: {preview}...")

                # Check again if we've been asked to stop before delivering results
                if self._stop_event.is_set():
                    logger.debug("Discussion fetch completed but cancelled")
                    return

                # Call success callback if provided
                if on_success and not self._stop_event.is_set():
                    logger.debug(
                        f"Calling success callback with discussion_text and "
                        f"additional_data: {additional_data}"
                    )
                    # Call callback on main thread
                    try:
                        if additional_data is not None:
                            logger.debug(
                                f"Calling success callback with additional data: {additional_data}"
                            )
                            if not safe_call_after(on_success, discussion_text, *additional_data):
                                logger.error("Failed to deliver discussion with additional data due to application context issues")
                        else:
                            logger.debug("Calling success callback without additional data")
                            if not safe_call_after(on_success, discussion_text):
                                logger.error("Failed to deliver discussion data due to application context issues")
                        logger.debug("Success callback scheduled successfully")
                    except Exception as e:
                        logger.error(f"Error scheduling success callback: {e}")
                        # Try to close the loading dialog if it exists
                        if (
                            additional_data
                            and len(additional_data) > 1
                            and hasattr(additional_data[1], "Destroy")
                        ):
                            try:
                                logger.debug(
                                    "Attempting to close loading dialog after callback error"
                                )
                                if not safe_call_after(additional_data[1].Destroy):
                                    logger.error("Failed to close loading dialog due to application context issues")
                            except Exception as dialog_e:
                                logger.error(f"Error closing loading dialog: {dialog_e}")
            except Exception as e:
                logger.error(f"Error in get_discussion: {e}")
                # If there's an error, still try to call the error callback
                if on_error and not self._stop_event.is_set():
                    error_msg = f"Failed to retrieve discussion: {str(e)}"
                    if additional_data is not None:
                        if not safe_call_after(on_error, error_msg, *additional_data):
                            logger.error("Failed to deliver discussion error with additional data due to application context issues")
                    else:
                        if not safe_call_after(on_error, error_msg):
                            logger.error("Failed to deliver discussion error due to application context issues")
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"Failed to retrieve discussion: {str(e)}")
                if on_error:
                    # Call error callback on main thread
                    error_msg = f"Unable to retrieve forecast discussion: {str(e)}"
                    if additional_data is not None:
                        if not safe_call_after(on_error, error_msg, *additional_data):
                            logger.error("Failed to deliver discussion error with additional data due to application context issues")
                    else:
                        if not safe_call_after(on_error, error_msg):
                            logger.error("Failed to deliver discussion error due to application context issues")
