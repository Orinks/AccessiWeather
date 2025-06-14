"""Unified NOAA API client that combines all functionality."""

from typing import Any, Dict, Optional, Tuple

from accessiweather.api.alerts_client import AlertsClient
from accessiweather.api.forecast_client import ForecastClient
from accessiweather.api.national_products_client import NationalProductsClient


class NoaaApiClient(ForecastClient, AlertsClient, NationalProductsClient):
    """Unified NOAA API client with all functionality.

    This class combines forecast, alerts, and national products functionality
    into a single client interface for backward compatibility.
    """

    def __init__(
        self,
        user_agent: str = "AccessiWeather",
        contact_info: Optional[str] = None,
        enable_caching: bool = False,
        cache_ttl: int = 300,
    ):
        """Initialize the unified NOAA API client.

        Args:
            user_agent: User agent string for API requests
            contact_info: Optional contact information (website or email)
                          for API identification. If None, uses the app name.
            enable_caching: Whether to enable caching of API responses
            cache_ttl: Time-to-live for cached responses in seconds (default: 5 minutes)
        """
        # Initialize the base client (only need to call one parent's __init__)
        ForecastClient.__init__(self, user_agent, contact_info, enable_caching, cache_ttl)
