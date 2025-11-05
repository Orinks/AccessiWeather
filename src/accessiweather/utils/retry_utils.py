"""Retry utilities providing an async retry decorator with exponential backoff."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable, Iterable
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    pass

T = TypeVar("T")

RetryableExceptionTypes = tuple[type[BaseException], ...]
JitterType = float | tuple[float, float] | Callable[[float], float] | None

RETRYABLE_EXCEPTIONS: RetryableExceptionTypes = (
    asyncio.TimeoutError,
    OSError,
)


def calculate_backoff_delay(
    attempt: int,
    base_delay: float,
    *,
    max_delay: float | None = None,
    jitter: JitterType = None,
) -> float:
    """Calculate backoff delay for a given attempt using exponential backoff."""
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    if base_delay < 0:
        raise ValueError("base_delay must be >= 0")
    if max_delay is not None and max_delay < 0:
        raise ValueError("max_delay must be >= 0 when provided")

    delay = base_delay * (2 ** (attempt - 1))
    if max_delay is not None:
        delay = min(delay, max_delay)

    jitter_value = 0.0
    if jitter:
        if callable(jitter):
            jitter_value = float(jitter(delay))
        elif isinstance(jitter, tuple):
            low, high = jitter
            jitter_value = random.uniform(low, high)
        else:
            jitter_value = random.uniform(0.0, float(jitter))

    delay_with_jitter = delay + jitter_value
    if max_delay is not None:
        delay_with_jitter = min(delay_with_jitter, max_delay)

    return max(0.0, delay_with_jitter)


def is_retryable_http_error(exc: BaseException) -> bool:
    """
    Check if exception is a retryable HTTP error from httpx.

    Args:
        exc: Exception to check

    Returns:
        True if this is a retryable httpx error

    """
    try:
        import httpx
    except ImportError:
        return False

    if isinstance(exc, httpx.TimeoutException):
        return True

    if isinstance(exc, httpx.HTTPStatusError):
        # Type checker doesn't know about HTTPStatusError.response attribute
        status = getattr(exc, "response", None)
        if status is not None:
            status_code = getattr(status, "status_code", 0)
            return status_code >= 500 or status_code in (408, 409, 425, 429)

    return bool(isinstance(exc, httpx.RequestError))


def _should_retry(exc: BaseException, retryable: RetryableExceptionTypes) -> bool:
    if isinstance(exc, asyncio.CancelledError):
        return False

    if isinstance(exc, retryable):
        return True

    cause = getattr(exc, "__cause__", None)
    if cause and cause is not exc and _should_retry(cause, retryable):
        return True

    context = getattr(exc, "__context__", None)
    if context and context is not exc and _should_retry(context, retryable):
        return True

    return is_retryable_http_error(exc)


def async_retry_with_backoff(
    *,
    max_attempts: int,
    base_delay: float,
    max_delay: float | None = None,
    jitter: JitterType = None,
    retryable_exceptions: Iterable[type[BaseException]] | None = None,
    timeout: float | None = None,
    logger: logging.Logger | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Retry an async function with exponential backoff."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    if base_delay < 0:
        raise ValueError("base_delay must be >= 0")

    retryable = tuple(retryable_exceptions) if retryable_exceptions else RETRYABLE_EXCEPTIONS

    log = logger or logging.getLogger(__name__)

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exc: BaseException | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    coroutine = func(*args, **kwargs)
                    result = (
                        await asyncio.wait_for(coroutine, timeout=timeout)
                        if timeout
                        else await coroutine
                    )
                    if attempt > 1:
                        log.info(
                            "Retry successful for %s on attempt %s/%s",
                            func.__qualname__,
                            attempt,
                            max_attempts,
                        )
                    return result
                except Exception as exc:  # noqa: BLE001
                    if not _should_retry(exc, retryable):
                        raise

                    last_exc = exc

                    if attempt >= max_attempts:
                        log.error(
                            "Function %s failed after %s attempts: %s",
                            func.__qualname__,
                            max_attempts,
                            exc,
                        )
                        raise

                    delay = calculate_backoff_delay(
                        attempt=attempt,
                        base_delay=base_delay,
                        max_delay=max_delay,
                        jitter=jitter,
                    )

                    log.warning(
                        "Attempt %s/%s for %s failed with %s. Retrying in %.2fs",
                        attempt,
                        max_attempts,
                        func.__qualname__,
                        exc,
                        delay,
                    )

                    await asyncio.sleep(delay)

            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator
