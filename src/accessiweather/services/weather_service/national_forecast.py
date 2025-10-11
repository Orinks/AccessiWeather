"""
National forecast functionality for WeatherService.

This module handles national forecast data operations including
caching and retrieval of nationwide forecast discussions.
"""

import logging
import time

from accessiweather.api_client import ApiClientError
from accessiweather.services.national_discussion_scraper import NationalDiscussionScraper

logger = logging.getLogger(__name__)


class NationalForecastHandler:
    """Handles national forecast data operations."""

    def __init__(self):
        """Initialize the national forecast handler."""
        self.national_scraper = NationalDiscussionScraper(request_delay=1.0)
        self.national_data_cache: dict[str, dict[str, str]] | None = None
        self.national_data_timestamp: float = 0.0
        self.cache_expiry = 3600  # 1 hour in seconds

    def get_national_forecast_data(self, force_refresh: bool = False) -> dict:
        """
        Get nationwide forecast data, including national discussion summaries.

        Args:
        ----
            force_refresh: Whether to force a refresh of the data

        Returns:
        -------
            Dictionary containing national forecast data with structure:
            {
                "national_discussion_summaries": {
                    "wpc": {
                        "short_range_summary": str,
                        "short_range_full": str
                    },
                    "spc": {
                        "day1_summary": str,
                        "day1_full": str
                    },
                    "attribution": str
                }
            }

        Raises:
        ------
            ApiClientError: If there was an error retrieving the data

        """
        current_time = time.time()

        # Check if we have cached data that's still valid and not forcing refresh
        if (
            not force_refresh
            and self.national_data_cache
            and current_time - self.national_data_timestamp < self.cache_expiry
        ):
            logger.info("Using cached nationwide forecast data")
            return {"national_discussion_summaries": self.national_data_cache}

        try:
            logger.info("Getting nationwide forecast data from scraper")
            # Fetch fresh data from the scraper
            national_data = self.national_scraper.fetch_all_discussions()

            # Update cache
            self.national_data_cache = national_data
            self.national_data_timestamp = current_time

            return {"national_discussion_summaries": national_data}
        except Exception as e:
            logger.error(f"Error getting nationwide forecast data: {str(e)}")

            # If we have cached data, return it even if expired
            if self.national_data_cache:
                logger.info("Returning cached national data due to fetch error")
                return {"national_discussion_summaries": self.national_data_cache}

            # Otherwise, raise an error
            raise ApiClientError(f"Unable to retrieve nationwide forecast data: {str(e)}") from e
