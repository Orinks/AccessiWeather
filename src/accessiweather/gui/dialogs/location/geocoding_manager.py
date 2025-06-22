"""Geocoding service integration and search management for location dialogs.

This module handles geocoding service integration, search threading,
result processing, and search history management for location dialogs.
"""

import logging
import threading
from collections.abc import Callable

import wx

from accessiweather.geocoding import GeocodingService

from .constants import (
    CUSTOM_COORDINATES_FORMAT,
    FOUND_RESULT_FORMAT,
    GEOCODING_TIMEOUT,
    MAX_HISTORY_ITEMS,
    SEARCH_THREAD_JOIN_TIMEOUT,
)

logger = logging.getLogger(__name__)


class SearchResultHandler:
    """Handles processing and formatting of geocoding search results."""

    @staticmethod
    def create_detailed_location_name(address: str, query: str) -> str:
        """Create a more detailed location name from the full address.

        Args:
            address: Full address from geocoding service
            query: Original search query

        Returns:
            A more detailed but concise location name

        """
        try:
            # If we have a full address, use it directly
            # This preserves all the useful context like county, state, country
            if address and ", " in address:
                return address
            # Fall back to the original query if no address is available
            return query
        except Exception as e:
            logger.error(f"Error creating detailed location name: {str(e)}")
            # Fall back to the original query
            return query

    @staticmethod
    def format_found_result(lat: float, lon: float, address: str) -> str:
        """Format a successful search result for display.

        Args:
            lat: Latitude
            lon: Longitude
            address: Address string

        Returns:
            Formatted result string

        """
        return FOUND_RESULT_FORMAT.format(address=address, lat=lat, lon=lon)

    @staticmethod
    def format_custom_coordinates(lat: float, lon: float) -> str:
        """Format custom coordinates for display.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Formatted coordinates string

        """
        return CUSTOM_COORDINATES_FORMAT.format(lat=lat, lon=lon)

    @staticmethod
    def format_no_results_message(query: str, geocoding_service: GeocodingService) -> str:
        """Format a no results message based on query type and data source.

        Args:
            query: Original search query
            geocoding_service: Geocoding service instance

        Returns:
            Formatted no results message

        """
        # Check if the query might be a ZIP code
        if geocoding_service.is_zip_code(query):
            return (
                f"No results found for ZIP code: {query}\n\n"
                f"Try adding city or state (e.g., '{query}, NY' or '{query}, Chicago')"
            )
        if geocoding_service.data_source == "nws":
            return (
                f"No results found for '{query}' or location is outside the US NWS coverage area."
            )
        return f"No results found for '{query}'. Please try a different search term."

    @staticmethod
    def format_timeout_error() -> str:
        """Format a timeout error message.

        Returns:
            Formatted timeout error message

        """
        return (
            "Search timed out. The geocoding service may be busy.\n"
            "Please try again in a moment or try a more specific search term."
        )

    @staticmethod
    def format_general_error(error_msg: str) -> str:
        """Format a general error message.

        Args:
            error_msg: Error message

        Returns:
            Formatted error message

        """
        return f"Error during search: {error_msg}"


class SearchHistoryManager:
    """Manages search history for location dialogs."""

    def __init__(self, max_items: int = MAX_HISTORY_ITEMS):
        """Initialize the search history manager.

        Args:
            max_items: Maximum number of history items to keep

        """
        self.search_history: list[str] = []
        self.max_items = max_items

    def add_to_history(self, query: str) -> None:
        """Add a query to search history.

        Args:
            query: Search query to add

        """
        # Remove the query if it already exists in history
        if query in self.search_history:
            self.search_history.remove(query)

        # Add query to beginning of history list
        self.search_history.insert(0, query)

        # Limit the size of history
        if len(self.search_history) > self.max_items:
            self.search_history = self.search_history[: self.max_items]

    def get_history(self) -> list[str]:
        """Get the current search history.

        Returns:
            List of search history items

        """
        return self.search_history.copy()

    def clear_history(self) -> None:
        """Clear the search history."""
        self.search_history.clear()


class GeocodingSearchManager:
    """Manages geocoding searches with threading and result callbacks."""

    def __init__(
        self,
        data_source: str = "nws",
        timeout: int = GEOCODING_TIMEOUT,
        result_callback: Callable | None = None,
        error_callback: Callable | None = None,
    ):
        """Initialize the geocoding search manager.

        Args:
            data_source: Data source for geocoding service
            timeout: Timeout for geocoding requests
            result_callback: Callback for successful results
            error_callback: Callback for errors

        """
        self.geocoding_service = GeocodingService(timeout=timeout, data_source=data_source)
        self.result_callback = result_callback
        self.error_callback = error_callback
        self.search_history = SearchHistoryManager()

        # Thread control
        self.search_thread: threading.Thread | None = None
        self.search_stop_event = threading.Event()

    def perform_search(self, query: str) -> None:
        """Perform a geocoding search in a background thread.

        Args:
            query: Search query string

        """
        # Add to search history immediately
        self.search_history.add_to_history(query)

        # Cancel any existing search
        if self.search_thread is not None and self.search_thread.is_alive():
            logger.debug("Cancelling in-progress location search")
            self.search_stop_event.set()

        # Reset stop event for new search
        self.search_stop_event.clear()

        # Start a new thread to perform the search
        self.search_thread = threading.Thread(target=self._search_thread_func, args=(query,))
        self.search_thread.daemon = True
        self.search_thread.start()

    def _search_thread_func(self, query: str) -> None:
        """Thread function to perform location search.

        Args:
            query: Search query string

        """
        try:
            # Check if we've been asked to stop
            if self.search_stop_event.is_set():
                logger.debug("Location search cancelled")
                return

            # Perform the geocoding
            logger.debug(f"Performing geocoding for query: {query}")
            result = self.geocoding_service.geocode_address(query)

            # Check again if we've been asked to stop before delivering results
            if self.search_stop_event.is_set():
                logger.debug("Location search completed but results discarded")
                return

            # Deliver results on the main thread
            if self.result_callback:
                wx.CallAfter(self.result_callback, result, query)

        except Exception as e:
            if not self.search_stop_event.is_set():
                logger.error(f"Error during geocoding thread: {str(e)}")
                if self.error_callback:
                    wx.CallAfter(self.error_callback, str(e))

    def get_suggestions(self, query: str, limit: int = 5) -> list[str]:
        """Get location suggestions for a query.

        Args:
            query: Search query
            limit: Maximum number of suggestions

        Returns:
            List of location suggestions

        """
        try:
            return self.geocoding_service.suggest_locations(query, limit)
        except Exception as e:
            logger.error(f"Error fetching search suggestions: {e}")
            return []

    def stop_search(self) -> None:
        """Stop any running search thread."""
        if self.search_thread is not None and self.search_thread.is_alive():
            logger.debug("Stopping search thread")
            self.search_stop_event.set()
            # Join with a short timeout to avoid blocking UI indefinitely
            self.search_thread.join(SEARCH_THREAD_JOIN_TIMEOUT)

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_search()

    def get_search_history(self) -> list[str]:
        """Get the current search history.

        Returns:
            List of search history items

        """
        return self.search_history.get_history()


class LocationSearchResultProcessor:
    """Processes and formats location search results for UI display."""

    def __init__(self, geocoding_manager: GeocodingSearchManager):
        """Initialize the result processor.

        Args:
            geocoding_manager: Geocoding search manager instance

        """
        self.geocoding_manager = geocoding_manager

    def process_search_result(
        self, result: tuple[float, float, str] | None, query: str
    ) -> tuple[float | None, float | None, str, str | None]:
        """Process a search result and return formatted data.

        Args:
            result: Geocoding result tuple or None
            query: Original search query

        Returns:
            Tuple of (latitude, longitude, result_text, detailed_name)

        """
        if result:
            lat, lon, address = result
            result_text = SearchResultHandler.format_found_result(lat, lon, address)
            detailed_name = SearchResultHandler.create_detailed_location_name(address, query)
            return lat, lon, result_text, detailed_name
        result_text = SearchResultHandler.format_no_results_message(
            query, self.geocoding_manager.geocoding_service
        )
        return None, None, result_text, None

    def process_search_error(self, error_msg: str) -> str:
        """Process a search error and return formatted message.

        Args:
            error_msg: Error message

        Returns:
            Formatted error message

        """
        if "timeout" in str(error_msg).lower():
            return SearchResultHandler.format_timeout_error()
        return SearchResultHandler.format_general_error(error_msg)
