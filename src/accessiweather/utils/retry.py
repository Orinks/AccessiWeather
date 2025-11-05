"""HTTP retry utilities for weather API calls."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")


class APITimeoutError(Exception):
    """Raised when an API request times out after retries."""

    def __init__(self, message: str, original_error: Exception | None = None):
        """
        Initialize the timeout error.

        Args:
        ----
            message: Error message describing the timeout
            original_error: The original exception that caused the timeout

        """
        super().__init__(message)
        self.original_error = original_error


async def retry_with_backoff(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = 1,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (httpx.TimeoutException, httpx.ConnectError),
    **kwargs: Any,
) -> Any:
    """
    Retry an async function with exponential backoff.

    Args:
    ----
        func: The async function to retry
        *args: Positional arguments to pass to func
        max_retries: Maximum number of retry attempts (default: 1)
        initial_delay: Initial delay in seconds before first retry (default: 1.0)
        backoff_factor: Multiplier for delay on each retry (default: 2.0)
        exceptions: Tuple of exception types to catch and retry (default: timeout/connect errors)
        **kwargs: Keyword arguments to pass to func

    Returns:
    -------
        The result of the function call

    Raises:
    ------
        APITimeoutError: If all retries are exhausted
        Exception: Any non-retryable exception from the function

    """
    last_exception = None
    delay = initial_delay

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as exc:
            last_exception = exc

            if attempt < max_retries:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {exc}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error(f"All {max_retries + 1} attempts failed. Last error: {exc}")

    # If we get here, all retries were exhausted
    error_msg = f"Request failed after {max_retries + 1} attempts"
    raise APITimeoutError(error_msg, last_exception)
