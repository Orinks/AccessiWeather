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

    def fetch(self, on_success=None, on_error=None, additional_data=None, force_refresh=False):
        """Fetch national forecast data asynchronously.

        Args:
            on_success: Callback function to call on successful fetch.
            on_error: Callback function to call on error.
            additional_data: Additional data to pass to the callbacks.
            force_refresh: Whether to force a refresh of the data.
        """
        logger.info("Starting national forecast fetch")

        def _fetch_thread():
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
                    on_success(data)

            except Exception as e:
                logger.error(f"Error fetching national forecast data: {e}")

                # Call the error callback if provided
                if on_error:
                    error_message = f"Error fetching national forecast data: {e}"
                    logger.info("Calling error callback")
                    on_error(error_message)

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
