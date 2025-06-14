"""Base NOAA API client with core functionality."""

import hashlib
import logging
import threading
import time
from typing import Any, Dict, Optional

import requests
from requests.exceptions import JSONDecodeError

from accessiweather.api.constants import BASE_URL
from accessiweather.api.exceptions import ApiClientError, NoaaApiError
from accessiweather.cache import Cache

logger = logging.getLogger(__name__)


class NoaaApiClient:
    """Base client for interacting with NOAA Weather API."""

    def __init__(
        self,
        user_agent: str = "AccessiWeather",
        contact_info: Optional[str] = None,
        enable_caching: bool = False,
        cache_ttl: int = 300,
    ):
        """Initialize the NOAA API client.

        Args:
            user_agent: User agent string for API requests
            contact_info: Optional contact information (website or email)
                          for API identification. If None, uses the app name.
            enable_caching: Whether to enable caching of API responses
            cache_ttl: Time-to-live for cached responses in seconds (default: 5 minutes)
        """
        self.user_agent = user_agent
        # Use app name as default contact info if none provided
        self.contact_info = contact_info or user_agent

        # Build user agent string according to NOAA API recommendations
        user_agent_string = f"{user_agent} ({self.contact_info})"

        self.headers = {"User-Agent": user_agent_string, "Accept": "application/geo+json"}

        # Add request tracking for rate limiting
        self.last_request_time: float = 0.0  # Ensure float type
        # Half a second between requests to avoid rate limiting
        self.min_request_interval: float = 0.5

        # Add thread lock for thread safety
        self.request_lock = threading.RLock()

        # Initialize cache if enabled
        self.cache = Cache(default_ttl=cache_ttl) if enable_caching else None

        logger.info(f"Initialized NOAA API client with User-Agent: {user_agent_string}")
        if enable_caching:
            logger.info(f"Caching enabled with TTL of {cache_ttl} seconds")

    def _make_request(
        self,
        endpoint_or_url: str,
        params: Optional[Dict[str, Any]] = None,
        use_full_url: bool = False,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Make a request to the NOAA API.

        Args:
            endpoint_or_url: API endpoint path or full URL if use_full_url is True
            params: Query parameters
            use_full_url: Whether the endpoint_or_url is a complete URL
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dict containing response data
        """
        # Initialize to avoid potential UnboundLocalError in finally block
        request_url = ""
        try:
            # Build the full URL
            if use_full_url:
                request_url = endpoint_or_url
            else:
                request_url = f"{BASE_URL}/{endpoint_or_url}"

            # Generate a cache key if caching is enabled
            cache_key = None
            if self.cache and not force_refresh:
                # Create a unique key based on the URL and parameters
                key_parts = [request_url]
                if params:
                    # Sort params to ensure consistent keys
                    sorted_params = sorted(params.items())
                    key_parts.extend([f"{k}={v}" for k, v in sorted_params])

                # Create a hash of the key parts
                key_string = "|".join(key_parts)
                cache_key = hashlib.md5(key_string.encode(), usedforsecurity=False).hexdigest()

                # Check if we have a cached response
                cached_data = self.cache.get(cache_key)
                if cached_data is not None:
                    logger.debug(f"Using cached response for {request_url}")
                    return cached_data  # type: ignore

            # Acquire the thread lock - ensure thread safety for all API requests
            with self.request_lock:
                # Rate limiting
                if self.last_request_time is not None:
                    elapsed = time.time() - self.last_request_time
                    sleep_time = max(0, self.min_request_interval - elapsed)
                    if sleep_time > 0:
                        logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                        time.sleep(sleep_time)

                # Determine the full URL
                if use_full_url:
                    # Use the provided URL directly
                    request_url = endpoint_or_url
                else:
                    # Ensure we don't have a leading slash to avoid double slashes
                    clean_endpoint = endpoint_or_url.lstrip("/")
                    if endpoint_or_url.startswith(BASE_URL):
                        request_url = endpoint_or_url
                    else:
                        request_url = f"{BASE_URL}/{clean_endpoint}"

                logger.debug(f"API request to: {request_url} with params: {params}")
                # Make the request - keeping this inside the lock to avoid
                # concurrent access. Added timeout.
                try:
                    logger.debug(f"Sending GET request to {request_url}")
                    response = requests.get(
                        request_url, headers=self.headers, params=params, timeout=10
                    )
                    logger.debug(
                        f"Received response from {request_url} with status code: "
                        f"{response.status_code}"
                    )
                    self.last_request_time = time.time()
                except Exception as e:
                    logger.error(f"Exception during GET request to {request_url}: {e}")
                    raise

                # Check for HTTP errors first
                try:
                    # Raises HTTPError for bad responses (4xx or 5xx)
                    response.raise_for_status()
                except requests.exceptions.HTTPError as http_err:
                    status_code = http_err.response.status_code
                    error_detail = ""
                    error_type = NoaaApiError.UNKNOWN_ERROR

                    # Try to get more details from the response
                    try:
                        # Try getting detail from JSON response if available
                        error_json = http_err.response.json()
                        detail = error_json.get("detail", "No detail provided")
                        error_detail = f"Detail: {detail}"
                    except JSONDecodeError:
                        # If error response isn't valid JSON, use raw text
                        resp_text = http_err.response.text[:200]
                        error_detail = f"Response body: {resp_text}"
                    except Exception as json_err:  # Catch other JSON errors
                        error_detail = f"Error parsing error response JSON: {json_err}"

                    # Determine error type and message based on status code
                    if status_code == 400:
                        error_type = NoaaApiError.CLIENT_ERROR
                        error_msg = f"Bad request: {error_detail}"
                        logger.error(error_msg)
                    elif status_code == 401:
                        error_type = NoaaApiError.AUTHENTICATION_ERROR
                        error_msg = f"Authentication required: {error_detail}"
                        logger.error(error_msg)
                    elif status_code == 403:
                        error_type = NoaaApiError.AUTHENTICATION_ERROR
                        error_msg = f"Access forbidden: {error_detail}"
                        logger.error(error_msg)
                    elif status_code == 404:
                        error_type = NoaaApiError.CLIENT_ERROR
                        error_msg = f"Resource not found: {error_detail}"
                        logger.warning(error_msg)  # 404 is often expected, so warning level
                    elif status_code == 429:
                        error_type = NoaaApiError.RATE_LIMIT_ERROR
                        error_msg = f"Rate limit exceeded: {error_detail}"
                        logger.warning(error_msg)
                    elif 400 <= status_code < 500:
                        error_type = NoaaApiError.CLIENT_ERROR
                        error_msg = f"Client error ({status_code}): {error_detail}"
                        logger.error(error_msg)
                    elif 500 <= status_code < 600:
                        error_type = NoaaApiError.SERVER_ERROR
                        error_msg = f"Server error ({status_code}): {error_detail}"
                        logger.error(error_msg)
                    else:
                        error_type = NoaaApiError.UNKNOWN_ERROR
                        error_msg = f"Unexpected status code ({status_code}): {error_detail}"
                        logger.error(error_msg)

                    raise NoaaApiError(
                        message=error_msg,
                        status_code=status_code,
                        error_type=error_type,
                        url=request_url,
                    ) from http_err

                # If status is OK, try to parse JSON
                try:
                    json_data = response.json()  # type: ignore
                    logger.debug(f"Successfully parsed JSON response from {request_url}")
                    # Log the keys in the response for debugging
                    if isinstance(json_data, dict):
                        logger.debug(f"Response keys: {list(json_data.keys())}")

                    # Store the response in the cache if caching is enabled
                    if self.cache and cache_key:
                        logger.debug(f"Caching response for {request_url} with key {cache_key}")
                        self.cache.set(cache_key, json_data)

                    return json_data  # type: ignore
                except JSONDecodeError as json_err:
                    resp_text = response.text[:200]  # Limit length
                    error_msg = (
                        f"Failed to decode JSON response from {request_url}. "
                        f"Error: {json_err}. Response text: {resp_text}"
                    )
                    logger.error(error_msg, exc_info=True)
                    raise NoaaApiError(
                        message=error_msg,
                        status_code=response.status_code,
                        error_type=NoaaApiError.PARSE_ERROR,
                        url=request_url,
                    ) from json_err

        except requests.exceptions.Timeout as timeout_err:
            # Handle timeout errors specifically
            error_msg = f"Request timed out during API request to {request_url}: {timeout_err}"
            logger.error(error_msg)
            raise NoaaApiError(
                message=error_msg, error_type=NoaaApiError.TIMEOUT_ERROR, url=request_url
            ) from timeout_err
        except requests.exceptions.ConnectionError as conn_err:
            # Handle connection errors specifically
            error_msg = f"Connection error during API request to {request_url}: {conn_err}"
            logger.error(error_msg)
            raise NoaaApiError(
                message=error_msg, error_type=NoaaApiError.CONNECTION_ERROR, url=request_url
            ) from conn_err
        except requests.exceptions.RequestException as req_err:
            # Catch other request exceptions
            error_msg = f"Network error during API request to {request_url}: {req_err}"
            # Log without traceback to avoid cluttering logs with expected errors
            logger.error(error_msg)  # Don't include exc_info=True
            raise NoaaApiError(
                message=error_msg, error_type=NoaaApiError.NETWORK_ERROR, url=request_url
            ) from req_err
        except NoaaApiError:  # Re-raise NoaaApiErrors directly
            raise
        except ApiClientError:  # Re-raise ApiClientErrors directly
            raise
        except Exception as e:
            # Catch any other unexpected errors
            error_msg = f"Unexpected error during API request to {request_url}: {e}"
            logger.error(error_msg, exc_info=True)  # Log with traceback
            raise NoaaApiError(
                message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=request_url
            ) from e
