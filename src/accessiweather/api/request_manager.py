"""Request management for NOAA API wrapper.

This module handles rate limiting, caching, error handling, and HTTP request logic
for the NOAA API wrapper.
"""

import hashlib
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional, cast

import httpx

from accessiweather.api.exceptions import ApiClientError, NoaaApiError
from accessiweather.cache import Cache
from accessiweather.weather_gov_api_client.errors import UnexpectedStatus

logger = logging.getLogger(__name__)


class ApiRequestManager:
    """Manages API requests, rate limiting, caching, and error handling."""

    def __init__(
        self,
        client: Any,
        base_url: str,
        user_agent: str,
        cache: Optional[Cache] = None,
        min_request_interval: float = 0.5,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
        retry_initial_wait: float = 5.0,
    ):
        """Initialize the request manager.

        Args:
            client: The HTTP client instance
            base_url: Base URL for API requests
            user_agent: User agent string for requests
            cache: Optional cache instance
            min_request_interval: Minimum interval between requests in seconds
            max_retries: Maximum number of retries for rate-limited requests
            retry_backoff: Multiplier for exponential backoff between retries
            retry_initial_wait: Initial wait time in seconds after a rate limit error
        """
        self.client = client
        self.base_url = base_url
        self.user_agent = user_agent
        self.cache = cache
        self.min_request_interval = min_request_interval
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.retry_initial_wait = retry_initial_wait

        # Add request tracking for rate limiting
        self.last_request_time: float = 0.0

        # Add thread lock for thread safety
        self.request_lock = threading.RLock()

    def generate_cache_key(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Generate a cache key for the given endpoint and parameters.

        Args:
            endpoint: The API endpoint
            params: Optional parameters for the request

        Returns:
            A cache key string
        """
        # Create a unique key based on the endpoint and parameters
        key_parts = [endpoint]
        if params:
            # Sort params to ensure consistent keys
            sorted_params = sorted(params.items())
            key_parts.extend([f"{k}={v}" for k, v in sorted_params])

        # Create a hash of the key parts
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode(), usedforsecurity=False).hexdigest()

    def rate_limit(self) -> None:
        """Apply rate limiting to avoid overwhelming the API.

        This method ensures that requests are spaced at least min_request_interval
        seconds apart to comply with the NWS API rate limits.
        """
        with self.request_lock:
            if self.last_request_time is not None:
                elapsed = time.time() - self.last_request_time
                sleep_time = max(0, self.min_request_interval - elapsed)
                if sleep_time > 0:
                    logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                    time.sleep(sleep_time)
            self.last_request_time = time.time()

    def fetch_url(self, url: str) -> Dict[str, Any]:
        """Fetch data from a URL.

        Args:
            url: The URL to fetch

        Returns:
            Dict containing the response data
        """
        self.rate_limit()
        try:
            # Create a request with the appropriate headers
            headers = {"User-Agent": self.user_agent, "Accept": "application/geo+json"}
            response = httpx.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return cast(Dict[str, Any], response.json())
        except Exception as e:
            logger.error(f"Error fetching URL {url}: {str(e)}")
            raise ApiClientError(f"Error fetching URL {url}: {str(e)}")

    def handle_rate_limit(self, url: str, retry_count: int = 0) -> None:
        """Handle rate limit errors with exponential backoff.

        Args:
            url: The URL that triggered the rate limit
            retry_count: Current retry attempt (0-based)

        Raises:
            NoaaApiError: If max retries are exceeded
        """
        if retry_count >= self.max_retries:
            error_msg = (
                f"Rate limit exceeded for {url} after {self.max_retries} retries. "
                f"Please try again later."
            )
            logger.error(error_msg)
            raise NoaaApiError(message=error_msg, error_type=NoaaApiError.RATE_LIMIT_ERROR, url=url)

        # Calculate backoff delay with exponential increase
        wait_time = self.retry_initial_wait * (self.retry_backoff**retry_count)

        logger.warning(
            f"Rate limit exceeded for {url}. "
            f"Retrying in {wait_time:.1f}s (attempt {retry_count + 1}/{self.max_retries})"
        )

        # Sleep with the lock released to allow other threads to proceed
        with self.request_lock:
            self.last_request_time = time.time() + wait_time

        time.sleep(wait_time)

    def get_cached_or_fetch(
        self,
        cache_key: str,
        fetch_func: Callable[[], Any],
        force_refresh: bool = False,
    ) -> Any:
        """Get data from cache or fetch it if not available.

        Args:
            cache_key: Cache key for the data
            fetch_func: Function to call to fetch the data if not in cache
            force_refresh: Whether to force a refresh of the data

        Returns:
            The data from cache or freshly fetched
        """
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

    def make_api_request(self, module_func: Callable, **kwargs) -> Any:
        """Call a function from the generated client modules and handle exceptions.

        Args:
            module_func: Function from the generated client modules (e.g., point.sync)
            **kwargs: Keyword arguments to pass to the function

        Returns:
            The result of the function call

        Raises:
            NoaaApiError: If an error occurs during the API request
        """
        # Always add the client to kwargs
        kwargs["client"] = self.client

        try:
            # Call the function
            return module_func(**kwargs)
        except UnexpectedStatus as e:
            # Map UnexpectedStatus to NoaaApiError
            status_code = e.status_code
            url = kwargs.get("url", self.base_url)

            if status_code == 404:
                error_msg = f"Resource not found: {e}"
                logger.warning(error_msg)
                raise NoaaApiError(
                    message=error_msg,
                    status_code=status_code,
                    error_type=NoaaApiError.CLIENT_ERROR,
                    url=url,
                )
            elif status_code == 429:
                error_msg = f"Rate limit exceeded: {e}"
                logger.warning(error_msg)
                # For tests, we need to include the exact phrase "Rate limit exceeded" in the message
                raise NoaaApiError(
                    message=f"Rate limit exceeded: {e}",
                    status_code=status_code,
                    error_type=NoaaApiError.RATE_LIMIT_ERROR,
                    url=url,
                )
            elif 400 <= status_code < 500:
                error_msg = f"Client error ({status_code}): {e}"
                logger.error(error_msg)
                raise NoaaApiError(
                    message=error_msg,
                    status_code=status_code,
                    error_type=NoaaApiError.CLIENT_ERROR,
                    url=url,
                )
            elif 500 <= status_code < 600:
                error_msg = f"Server error ({status_code}): {e}"
                logger.error(error_msg)
                # For tests, we need to include the exact phrase "Server error" in the message
                raise NoaaApiError(
                    message=f"Server error ({status_code}): {e}",
                    status_code=status_code,
                    error_type=NoaaApiError.SERVER_ERROR,
                    url=url,
                )
            else:
                error_msg = f"Unexpected status code ({status_code}): {e}"
                logger.error(error_msg)
                raise NoaaApiError(
                    message=error_msg,
                    status_code=status_code,
                    error_type=NoaaApiError.UNKNOWN_ERROR,
                    url=url,
                )
        except httpx.TimeoutException as e:
            url = kwargs.get("url", self.base_url)
            error_msg = f"Request timed out: {e}"
            logger.error(error_msg)
            raise NoaaApiError(message=error_msg, error_type=NoaaApiError.TIMEOUT_ERROR, url=url)
        except httpx.ConnectError as e:
            url = kwargs.get("url", self.base_url)
            error_msg = f"Connection error: {e}"
            logger.error(error_msg)
            raise NoaaApiError(message=error_msg, error_type=NoaaApiError.CONNECTION_ERROR, url=url)
        except httpx.RequestError as e:
            url = kwargs.get("url", self.base_url)
            error_msg = f"Network error: {e}"
            logger.error(error_msg)
            raise NoaaApiError(message=error_msg, error_type=NoaaApiError.NETWORK_ERROR, url=url)
        except Exception as e:
            url = kwargs.get("url", self.base_url)
            error_msg = f"Unexpected error: {e}"
            logger.error(error_msg, exc_info=True)
            raise NoaaApiError(message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url)

    def handle_client_error(self, error: Exception, url: str, retry_count: int = 0) -> NoaaApiError:
        """Map client errors to NoaaApiError types.

        Args:
            error: The original error
            url: The URL that caused the error
            retry_count: Current retry attempt (0-based)

        Returns:
            A NoaaApiError instance

        Note:
            This method will handle rate limiting (HTTP 429) errors by implementing
            exponential backoff and retrying the request if retry_count is less than
            max_retries.
        """
        if isinstance(error, UnexpectedStatus):
            status_code = error.status_code

            if status_code == 429:
                # Handle rate limiting with exponential backoff
                try:
                    self.handle_rate_limit(url, retry_count)
                    # If handle_rate_limit doesn't raise an exception, it means
                    # we should retry the request, so we return a special error type
                    return NoaaApiError(
                        message="Rate limit retry",
                        status_code=status_code,
                        error_type="retry",  # Special error type to indicate retry
                        url=url,
                    )
                except NoaaApiError as rate_error:
                    # If handle_rate_limit raises an exception, it means we've
                    # exceeded max retries, so we return that error
                    return rate_error
            elif 400 <= status_code < 500:
                error_type = NoaaApiError.CLIENT_ERROR
                error_msg = f"Client error ({status_code}): {error}"
            elif 500 <= status_code < 600:
                error_type = NoaaApiError.SERVER_ERROR
                error_msg = f"Server error ({status_code}): {error}"
            else:
                error_type = NoaaApiError.UNKNOWN_ERROR
                error_msg = f"Unexpected status code ({status_code}): {error}"

            return NoaaApiError(
                message=error_msg, status_code=status_code, error_type=error_type, url=url
            )
        elif isinstance(error, httpx.TimeoutException):
            error_msg = f"Request timed out during API request to {url}: {error}"
            return NoaaApiError(message=error_msg, error_type=NoaaApiError.TIMEOUT_ERROR, url=url)
        elif isinstance(error, httpx.ConnectError):
            error_msg = f"Connection error during API request to {url}: {error}"
            return NoaaApiError(
                message=error_msg, error_type=NoaaApiError.CONNECTION_ERROR, url=url
            )
        elif isinstance(error, httpx.RequestError):
            error_msg = f"Network error during API request to {url}: {error}"
            return NoaaApiError(message=error_msg, error_type=NoaaApiError.NETWORK_ERROR, url=url)
        else:
            error_msg = f"Unexpected error during API request to {url}: {error}"
            return NoaaApiError(message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url)
