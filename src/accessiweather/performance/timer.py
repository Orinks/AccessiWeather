"""Performance timing utilities for profiling async operations."""

from __future__ import annotations

import functools
import logging
import os
import time
from collections.abc import Callable
from contextlib import asynccontextmanager, contextmanager
from typing import Any, TypeVar

logger = logging.getLogger("performance")

# Enable performance logging via environment variable
PERFORMANCE_MODE = os.environ.get("ACCESSIWEATHER_PERFORMANCE", "").lower() in ("1", "true", "yes")

F = TypeVar("F", bound=Callable[..., Any])


@contextmanager
def measure(operation_name: str):
    """
    Context manager to measure and log the execution time of a synchronous operation.

    Args:
    ----
        operation_name: Name of the operation being measured

    Example:
    -------
        with measure("fetch_data"):
            data = fetch_from_api()

    """
    start_time = time.perf_counter()
    exception_info = None

    try:
        yield
    except Exception as exc:
        exception_info = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        if exception_info:
            logger.warning(
                f"⏱️  {operation_name} failed after {elapsed_ms:.2f}ms - {exception_info}"
            )
        else:
            logger.info(f"⏱️  {operation_name} completed in {elapsed_ms:.2f}ms")


@asynccontextmanager
async def measure_async(operation_name: str):
    """
    Async context manager to measure and log the execution time of an async operation.

    Args:
    ----
        operation_name: Name of the operation being measured

    Example:
    -------
        async with measure_async("fetch_weather"):
            weather = await fetch_from_api()

    """
    start_time = time.perf_counter()
    exception_info = None

    try:
        yield
    except Exception as exc:
        exception_info = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        if exception_info:
            logger.warning(
                f"⏱️  {operation_name} failed after {elapsed_ms:.2f}ms - {exception_info}"
            )
        else:
            logger.info(f"⏱️  {operation_name} completed in {elapsed_ms:.2f}ms")


def timed(operation_name: str | None = None) -> Callable[[F], F]:
    """
    Measure execution time of a synchronous function.

    Args:
    ----
        operation_name: Optional name for the operation (defaults to function name)

    Example:
    -------
        @timed("cache_lookup")
        def get_cached_data():
            return cache.get()

    """

    def decorator(func: F) -> F:
        # Check if already wrapped to prevent double-wrapping
        if hasattr(func, "_timed_wrapper"):
            return func

        name = operation_name or func.__name__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not PERFORMANCE_MODE and not logger.isEnabledFor(logging.INFO):
                return func(*args, **kwargs)

            with measure(name):
                return func(*args, **kwargs)

        wrapper._timed_wrapper = True  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


def timed_async(operation_name: str | None = None) -> Callable[[F], F]:
    """
    Measure execution time of an async function.

    Args:
    ----
        operation_name: Optional name for the operation (defaults to function name)

    Example:
    -------
        @timed_async("fetch_weather")
        async def get_weather_data():
            return await api.fetch()

    """

    def decorator(func: F) -> F:
        # Check if already wrapped to prevent double-wrapping
        if hasattr(func, "_timed_wrapper"):
            return func

        name = operation_name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not PERFORMANCE_MODE and not logger.isEnabledFor(logging.INFO):
                return await func(*args, **kwargs)

            async with measure_async(name):
                return await func(*args, **kwargs)

        wrapper._timed_wrapper = True  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator
