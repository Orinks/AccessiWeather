"""
National forecast functionality for WeatherService.

This module handles national forecast data operations including
caching and retrieval of nationwide forecast discussions.
"""

import logging
import time

from accessiweather.api_client import ApiClientError
from accessiweather.services.national_discussion_service import NationalDiscussionService

logger = logging.getLogger(__name__)


class NationalForecastHandler:
    """Handles national forecast data operations."""

    def __init__(self):
        """Initialize the national forecast handler."""
        self.national_service = NationalDiscussionService(request_delay=1.0)
        # Keep backward-compatible attribute names
        self.national_data_cache: dict | None = None
        self.national_data_timestamp: float = 0.0
        self.cache_expiry = 3600  # 1 hour in seconds

    def get_national_forecast_data(self, force_refresh: bool = False) -> dict:
        """
        Get nationwide forecast data using NationalDiscussionService.

        The service handles its own caching internally. This method delegates
        to the service and wraps the result for backward compatibility.

        Args:
        ----
            force_refresh: Whether to force a refresh of the data

        Returns:
        -------
            Dictionary containing national forecast data with structure:
            {
                "national_discussion_summaries": {
                    "wpc": {...},
                    "spc": {...},
                    "qpf": {...},
                    "nhc": {...},
                    "cpc": {...}
                }
            }

        Raises:
        ------
            ApiClientError: If there was an error retrieving the data

        """
        try:
            logger.info("Getting nationwide forecast data from NationalDiscussionService")
            national_data = self.national_service.fetch_all_discussions(force_refresh=force_refresh)

            # Update local cache reference for backward compat
            self.national_data_cache = national_data
            self.national_data_timestamp = time.time()

            return {"national_discussion_summaries": national_data}
        except Exception as e:
            logger.error(f"Error getting nationwide forecast data: {str(e)}")

            # If we have cached data, return it even if expired
            if self.national_data_cache:
                logger.info("Returning cached national data due to fetch error")
                return {"national_discussion_summaries": self.national_data_cache}

            raise ApiClientError(f"Unable to retrieve nationwide forecast data: {str(e)}") from e
