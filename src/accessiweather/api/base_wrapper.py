"""
Base API wrapper for AccessiWeather.

This module provides the BaseApiWrapper abstract class that contains shared
functionality for all weather API providers, including caching, rate limiting,
error handling, and HTTP request management.
"""

import hashlib
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

import httpx

from accessiweather.api_client import NoaaApiError
from accessiweather.cache import Cache

logger = logging.getLogger(__name__)


class BaseApiWrapper(ABC):
    """
    Abstract base class for weather API wrappers.

    Provides common functionality including:
    - Rate limiting
    - Caching
    - Error handling
    - HTTP request management
    - Thread safety
    """

    def __init__(
        self,
        user_agent: str = "AccessiWeather",
        contact_info: str | None = None,
        enable_caching: bool = False,
        cache_ttl: int = 300,
        min_request_interval: float = 0.5,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
        retry_initial_wait: float = 5.0,
    ):
        """
        Initialize the base API wrapper.

        Args:
        ----
            user_agent: User agent string for API requests
            contact_info: Optional contact information for API identification
            enable_caching: Whether to enable caching of API responses
            cache_ttl: Time-to-live for cached responses in seconds
            min_request_interval: Minimum interval between requests in seconds
            max_retries: Maximum number of retries for rate-limited requests
            retry_backoff: Multiplier for exponential backoff between retries
            retry_initial_wait: Initial wait time after a rate limit error

        """
        self.user_agent = user_agent
        self.contact_info = contact_info or user_agent

        # Rate limiting configuration
        self.last_request_time: float = 0.0
        self.min_request_interval: float = min_request_interval
        self.max_retries: int = max_retries
        self.retry_backoff: float = retry_backoff
        self.retry_initial_wait: float = retry_initial_wait

        # Thread safety
        self.request_lock = threading.RLock()

        # Initialize cache if enabled
        self.cache = Cache(default_ttl=cache_ttl) if enable_caching else None

        logger.info(f"Initialized {self.__class__.__name__} with User-Agent: {self.user_agent}")
        if enable_caching:
            logger.info(f"Caching enabled with TTL of {cache_ttl} seconds")

    # Abstract methods that must be implemented by subclasses
    @abstractmethod
    def get_current_conditions(self, lat: float, lon: float, **kwargs) -> dict[str, Any]:
        """Get current weather conditions for a location."""

    @abstractmethod
    def get_forecast(self, lat: float, lon: float, **kwargs) -> dict[str, Any]:
        """Get forecast data for a location."""

    @abstractmethod
    def get_hourly_forecast(self, lat: float, lon: float, **kwargs) -> dict[str, Any]:
        """Get hourly forecast data for a location."""

    # Shared utility methods
    def _rate_limit(self) -> None:
        """Apply rate limiting to avoid overwhelming the API."""
        with self.request_lock:
            if self.last_request_time is not None:
                elapsed = time.time() - self.last_request_time
                sleep_time = max(0, self.min_request_interval - elapsed)
                if sleep_time > 0:
                    logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                    time.sleep(sleep_time)
            self.last_request_time = time.time()

    def _handle_rate_limit(self, url: str, retry_count: int = 0) -> None:
        """Handle rate limit errors with exponential backoff."""
        if retry_count >= self.max_retries:
            error_msg = (
                f"Rate limit exceeded for {url} after {self.max_retries} retries. "
                f"Please try again later."
            )
            logger.error(error_msg)
            raise NoaaApiError(message=error_msg, error_type=NoaaApiError.RATE_LIMIT_ERROR, url=url)

        # Calculate wait time with exponential backoff
        wait_time = self.retry_initial_wait * (self.retry_backoff**retry_count)
        logger.warning(
            f"Rate limited on {url}. Waiting {wait_time:.1f}s before retry "
            f"{retry_count + 1}/{self.max_retries}"
        )
        time.sleep(wait_time)

    def _get_cached_or_fetch(
        self,
        cache_key: str,
        fetch_func: Callable[[], Any],
        force_refresh: bool = False,
    ) -> Any:
        """Get data from cache or fetch it if not available."""
        # If caching is disabled or force refresh is requested, fetch directly
        if self.cache is None or force_refresh:
            return fetch_func()

        # Try to get from cache
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"Using cached data for {cache_key}")
            return cached_data

        # Fetch and cache
        data = fetch_func()
        self.cache.set(cache_key, data)
        return data

    def _generate_cache_key(self, endpoint: str, params: dict[str, Any]) -> str:
        """Generate a cache key for the given endpoint and parameters."""
        # Create a string representation of the parameters
        param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        cache_string = f"{endpoint}?{param_str}"

        # Generate a hash for the cache key (using SHA256 for security)
        return hashlib.sha256(cache_string.encode()).hexdigest()

    def _fetch_url(self, url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        """Fetch data from a URL with error handling and retries."""
        retry_count = 0

        while retry_count <= self.max_retries:
            try:
                self._rate_limit()

                # Prepare headers
                request_headers = {"User-Agent": f"{self.user_agent} ({self.contact_info})"}
                if headers:
                    request_headers.update(headers)

                # Make the request
                with httpx.Client(timeout=httpx.Timeout(10.0), follow_redirects=True) as client:
                    response = client.get(url, headers=request_headers)
                    response.raise_for_status()
                    return response.json()  # type: ignore[no-any-return]

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limited
                    self._handle_rate_limit(url, retry_count)
                    retry_count += 1
                    continue
                # For other HTTP errors, raise immediately
                error_msg = f"HTTP {e.response.status_code} error for {url}: {e.response.text}"
                logger.error(error_msg)
                raise NoaaApiError(
                    message=error_msg,
                    error_type=NoaaApiError.HTTP_ERROR,
                    url=url,
                    status_code=e.response.status_code,
                ) from e
            except httpx.RequestError as e:
                error_msg = f"Network error during API request to {url}: {e}"
                logger.error(error_msg)
                raise NoaaApiError(
                    message=error_msg, error_type=NoaaApiError.NETWORK_ERROR, url=url
                ) from e
            except Exception as e:
                error_msg = f"Unexpected error during API request to {url}: {e}"
                logger.error(error_msg)
                raise NoaaApiError(
                    message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                ) from e

        # This should never be reached due to the exception handling above
        raise NoaaApiError(
            message=f"Request failed after {self.max_retries} retries",
            error_type=NoaaApiError.RATE_LIMIT_ERROR,
            url=url,
        )
