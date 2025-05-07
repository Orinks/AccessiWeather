"""National forecast fetcher for AccessiWeather.

This module provides a class for fetching national forecast data asynchronously.
"""

import logging
import threading

import wx

from accessiweather.utils.thread_manager import ThreadManager

logger = logging.getLogger(__name__)


class NationalForecastFetcher:
    """Fetches national forecast data asynchronously.

    This class is responsible for fetching national forecast data from the
    WeatherService in a background thread and calling the appropriate callbacks
    when the data is available or when an error occurs.
    """

    def __init__(self, service):
        """Initialize the fetcher.

        Args:
            service: The weather service to use for fetching data.
        """
        self.service = service
        self.thread = None
        self._stop_event = threading.Event()

    def fetch(
        self,
        on_success=None,
        on_error=None,
        force_refresh=False,
        callback_timeout=5.0,
    ):
        """Fetch national forecast data asynchronously.

        Args:
            on_success: Callback function to call on successful fetch.
            on_error: Callback function to call on error.
            force_refresh: Whether to force a refresh of the data.
            callback_timeout: Maximum time in seconds to wait for callbacks to complete.
        """
        logger.info("Starting national forecast fetch")

        # Cancel any existing fetch operation
        if self.thread and self.thread.is_alive():
            logger.debug("Cancelling in-progress national forecast fetch")
            self.cancel()
            # Wait briefly for the thread to terminate
            self.thread.join(0.5)

        # Reset the stop event in case it was set previously
        self._stop_event.clear()

        def _fetch_thread():
            thread = threading.current_thread()
            # Register this thread with the ThreadManager
            ThreadManager.instance().register_thread(thread, self._stop_event)
            try:
                # Check if we should stop
                if self._stop_event.is_set():
                    logger.info("National forecast fetch cancelled")
                    return

                # Fetch the data from the weather service
                # This returns a dictionary with the structure:
                # {
                #     "national_discussion_summaries": {
                #         "wpc": {
                #             "short_range_summary": str,
                #             "short_range_full": str
                #         },
                #         "spc": {
                #             "day1_summary": str,
                #             "day1_full": str
                #         },
                #         "attribution": str
                #     }
                # }
                data = self.service.get_national_forecast_data(force_refresh=force_refresh)

                # Check if we should stop before calling the callback
                if self._stop_event.is_set():
                    logger.info("National forecast fetch cancelled after data retrieval")
                    return

                # Call the success callback if provided
                if on_success:
                    logger.info("National forecast fetch successful, calling success callback")
                    try:
                        # Create a safety timeout for the callback
                        if hasattr(threading, "Timer"):
                            timer = threading.Timer(
                                callback_timeout, lambda: self._stop_event.set()
                            )
                            timer.daemon = True
                            timer.start()

                        # Use wx.CallAfter to ensure the callback runs in the main thread
                        # This is important for UI updates
                        wx.CallAfter(on_success, data)

                        # Cancel the timer if it's still active
                        if hasattr(threading, "Timer"):
                            timer.cancel()

                        logger.debug("National forecast fetch success callback completed")
                    except Exception as callback_error:
                        logger.error(
                            f"Error in national forecast success callback: {callback_error}"
                        )

            except Exception as e:
                logger.error(f"Error fetching national forecast data: {e}")

                # Call the error callback if provided
                if on_error:
                    error_message = f"Error fetching national forecast data: {e}"
                    logger.info("Calling error callback")
                    try:
                        # Create a safety timeout for the callback
                        if hasattr(threading, "Timer"):
                            timer = threading.Timer(
                                callback_timeout, lambda: self._stop_event.set()
                            )
                            timer.daemon = True
                            timer.start()

                        # Use wx.CallAfter to ensure the callback runs in the main thread
                        wx.CallAfter(on_error, error_message)

                        # Cancel the timer if it's still active
                        if hasattr(threading, "Timer"):
                            timer.cancel()
                    except Exception as callback_error:
                        logger.error(f"Error in national forecast error callback: {callback_error}")
            finally:
                logger.debug("National forecast fetch thread completed")
                # Unregister this thread from the ThreadManager
                ThreadManager.instance().unregister_thread(thread.ident)

        # Create and start the thread
        self.thread = threading.Thread(target=_fetch_thread, daemon=True)
        self.thread.start()

    def cancel(self):
        """Cancel the current fetch operation."""
        logger.info("Cancelling national forecast fetch")
        self._stop_event.set()

        # Wait for the thread to finish if it's running
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
            logger.info("National forecast fetch thread joined")

    def cleanup(self):
        """Clean up resources used by the fetcher.

        This method should be called when the fetcher is no longer needed.
        It cancels any ongoing operations and releases thread resources.
        """
        logger.debug("Cleaning up NationalForecastFetcher resources")
        self._stop_event.set()

        # Wait for the thread to finish if it's running
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.5)
            logger.debug("National forecast fetch thread joined during cleanup")

        # Reset the thread
        self.thread = None

    def __del__(self):
        """Destructor to ensure threads are cleaned up.

        This method is called when the object is garbage collected.
        It ensures that any running threads are properly terminated.
        """
        try:
            logger.debug("NationalForecastFetcher being garbage collected, cleaning up resources")
            self._stop_event.set()
            self.thread = None
        except Exception:
            # During interpreter shutdown, logger might not be available
            pass
