"""National forecast fetcher for AccessiWeather.

This module provides a class for fetching national forecast data asynchronously.
"""

import logging
import threading

logger = logging.getLogger(__name__)


class NationalForecastFetcher:
    """Fetches national forecast data asynchronously."""

    def __init__(self, service):
        """Initialize the fetcher.

        Args:
            service: The weather service to use for fetching data.
        """
        self.service = service
        self.thread = None
        self._stop_event = threading.Event()

    def fetch(self, on_success=None, on_error=None, additional_data=None, force_refresh=False, callback_timeout=5.0):
        """Fetch national forecast data asynchronously.

        Args:
            on_success: Callback function to call on successful fetch.
            on_error: Callback function to call on error.
            additional_data: Additional data to pass to the callbacks.
            force_refresh: Whether to force a refresh of the data.
            callback_timeout: Maximum time in seconds to wait for callbacks to complete.
        """
        logger.info("Starting national forecast fetch")

        # Reset the stop event in case it was set previously
        self._stop_event.clear()

        def _fetch_thread():
            # Flag to track thread completion for logging
            completed = False
            try:
                # Check if we should stop
                if self._stop_event.is_set():
                    logger.info("National forecast fetch cancelled")
                    return

                # Fetch the data
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
                        if hasattr(threading, 'Timer'):
                            timer = threading.Timer(callback_timeout, lambda: self._stop_event.set())
                            timer.daemon = True
                            timer.start()
                        
                        # Wrap callback in try-except to prevent thread from hanging on callback errors
                        on_success(data)
                        
                        # Cancel the timer if it's still active
                        if hasattr(threading, 'Timer'):
                            timer.cancel()
                            
                        logger.debug("National forecast fetch success callback completed")
                    except Exception as callback_error:
                        logger.error(f"Error in national forecast success callback: {callback_error}")

            except Exception as e:
                logger.error(f"Error fetching national forecast data: {e}")

                # Call the error callback if provided
                if on_error:
                    error_message = f"Error fetching national forecast data: {e}"
                    logger.info("Calling error callback")
                    try:
                        # Create a safety timeout for the callback
                        if hasattr(threading, 'Timer'):
                            timer = threading.Timer(callback_timeout, lambda: self._stop_event.set())
                            timer.daemon = True
                            timer.start()
                            
                        on_error(error_message)
                        
                        # Cancel the timer if it's still active
                        if hasattr(threading, 'Timer'):
                            timer.cancel()
                    except Exception as callback_error:
                        logger.error(f"Error in national forecast error callback: {callback_error}")
            finally:
                completed = True
                logger.debug("National forecast fetch thread completed")

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
        except Exception as e:
            # During interpreter shutdown, logger might not be available
            pass
