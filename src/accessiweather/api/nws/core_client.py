"""Core client operations for NWS API wrapper.

This module handles the foundational API client operations including
initialization, client setup, and core request handling.
"""

import logging
from typing import Any

from accessiweather.api_client import NoaaApiError
from accessiweather.weather_gov_api_client.client import Client
from accessiweather.weather_gov_api_client.errors import UnexpectedStatus

logger = logging.getLogger(__name__)


class NwsCoreClient:
    """Handles core NWS API client operations and request management."""

    BASE_URL = "https://api.weather.gov"

    def __init__(self, wrapper_instance):
        """Initialize the core client with reference to the main wrapper.
        
        Args:
            wrapper_instance: The main NwsApiWrapper instance
        """
        self.wrapper = wrapper_instance
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the generated NWS client."""
        # Build user agent string according to NOAA API recommendations
        user_agent_string = f"{self.wrapper.user_agent} ({self.wrapper.contact_info})"

        # Initialize the generated NWS client
        self.client = Client(
            base_url=self.BASE_URL,
            headers={"User-Agent": user_agent_string, "Accept": "application/geo+json"},
            timeout=10.0,
            follow_redirects=True,
        )

        logger.info(f"Initialized NWS API wrapper with User-Agent: {user_agent_string}")

    def make_api_request(self, module_func, **kwargs) -> Any:
        """Call a function from the generated NWS client modules and handle exceptions.
        
        Args:
            module_func: The API function to call
            **kwargs: Arguments to pass to the function
            
        Returns:
            The response from the API call
            
        Raises:
            NoaaApiError: For various API error conditions
        """
        # Always add the client to kwargs
        kwargs["client"] = self.client

        try:
            # Call the function
            return module_func(**kwargs)
        except UnexpectedStatus as e:
            # Map UnexpectedStatus to NoaaApiError
            status_code = e.status_code
            url = kwargs.get("url", self.BASE_URL)

            if status_code == 404:
                error_msg = f"Resource not found (404) at {url}"
                raise NoaaApiError(
                    message=error_msg,
                    error_type=NoaaApiError.NOT_FOUND_ERROR,
                    url=url,
                    status_code=status_code,
                )
            elif status_code == 429:
                error_msg = f"Rate limit exceeded (429) for {url}"
                raise NoaaApiError(
                    message=error_msg,
                    error_type=NoaaApiError.RATE_LIMIT_ERROR,
                    url=url,
                    status_code=status_code,
                )
            elif status_code >= 500:
                error_msg = f"Server error ({status_code}) at {url}"
                raise NoaaApiError(
                    message=error_msg,
                    error_type=NoaaApiError.SERVER_ERROR,
                    url=url,
                    status_code=status_code,
                )
            else:
                error_msg = f"HTTP {status_code} error at {url}: {e.content}"
                raise NoaaApiError(
                    message=error_msg,
                    error_type=NoaaApiError.HTTP_ERROR,
                    url=url,
                    status_code=status_code,
                )
        except Exception as e:
            # Handle other exceptions
            url = kwargs.get("url", self.BASE_URL)
            error_msg = f"Unexpected error during NWS API request to {url}: {e}"
            logger.error(error_msg)
            raise NoaaApiError(message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url)
