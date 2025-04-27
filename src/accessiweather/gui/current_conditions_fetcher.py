"""Current conditions fetcher for AccessiWeather

This module provides asynchronous fetching of current weather conditions data.
"""

import logging
import threading

from accessiweather.gui.async_fetchers import safe_call_after
from accessiweather.utils.thread_manager import get_thread_manager, register_thread

logger = logging.getLogger(__name__)


class CurrentConditionsFetcher:
    """Handles asynchronous fetching of current weather conditions data"""

    def __init__(self, api_client):
        """Initialize current conditions fetcher

        Args:
            api_client: NoaaApiClient instance
        """
        self.api_client = api_client
        self.thread = None
        self._stop_event = threading.Event()

    def cancel(self):
        """Cancel any in-progress fetch operations immediately.

        Returns:
            bool: True if a thread was cancelled, False otherwise
        """
        if self.thread is not None and self.thread.is_alive():
            logger.debug("[EXIT OPTIMIZATION] Fast-cancelling current conditions fetch thread")
            self._stop_event.set()
            # Use minimal timeout for immediate response
            self.thread.join(0.01)
            return True
        return False

    def fetch(self, lat, lon, on_success=None, on_error=None):
        """Fetch current conditions data asynchronously

        Args:
            lat: Latitude
            lon: Longitude
            on_success: Callback for successful fetch
            on_error: Callback for error handling
        """
        # Cancel any existing fetch
        if self.thread is not None and self.thread.is_alive():
            logger.debug("Cancelling in-progress current conditions fetch")
            self._stop_event.set()
            # Reduced timeout for faster UI response
            self.thread.join(0.1)

        # Reset stop event for new fetch
        self._stop_event.clear()

        # Create and start new thread
        args = (lat, lon, on_success, on_error)
        self.thread = threading.Thread(target=self._fetch_thread, args=args, daemon=True)
        self.thread.start()
        # Register the thread with the manager
        register_thread(self.thread, self._stop_event, name=f"CurrentConditionsFetcher-{lat}-{lon}")

    def _fetch_thread(self, lat, lon, on_success, on_error):
        """Thread function to fetch the current conditions

        Args:
            lat: Latitude
            lon: Longitude
            on_success: Success callback
            on_error: Error callback
        """
        thread_id = threading.get_ident()
        thread_manager = get_thread_manager()
        try:
            # Check if we've been asked to stop
            if self._stop_event.is_set():
                logger.debug("Current conditions fetch cancelled before API call")
                return

            # Get current conditions data from API
            current_conditions = self.api_client.get_current_conditions(lat, lon)

            # Check again if we've been asked to stop before delivering results
            if self._stop_event.is_set():
                logger.debug("Current conditions fetch completed but cancelled")
                return

            # Call success callback if provided
            if on_success and not self._stop_event.is_set():
                # Call callback on main thread
                if not safe_call_after(on_success, current_conditions):
                    logger.error(
                        "Failed to deliver current conditions data due to application context issues"
                    )
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"Failed to retrieve current conditions: {str(e)}")
                if on_error:
                    # Call error callback on main thread
                    error_msg = f"Unable to retrieve current conditions data: {str(e)}"
                    if not safe_call_after(on_error, error_msg):
                        logger.error(
                            "Failed to deliver current conditions error due to application context issues"
                        )
        finally:
            # Ensure the thread is unregistered
            logger.debug(f"CurrentConditionsFetcher ({thread_id}): Thread finished, unregistering.")
            thread_manager.unregister_thread(thread_id)  # Use thread_id
