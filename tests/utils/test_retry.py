"""Tests for HTTP retry utilities."""

import asyncio

import httpx
import pytest

from accessiweather.utils.retry import APITimeoutError, retry_with_backoff


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_success_on_first_attempt():
    """Test successful function call on first attempt."""
    call_count = 0

    async def success_func():
        nonlocal call_count
        call_count += 1
        return "success"

    result = await retry_with_backoff(success_func, max_retries=2)
    assert result == "success"
    assert call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_success_on_second_attempt():
    """Test successful function call after one retry."""
    call_count = 0

    async def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.TimeoutException("Timeout on first attempt")
        return "success"

    result = await retry_with_backoff(flaky_func, max_retries=2, initial_delay=0.01)
    assert result == "success"
    assert call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_exhausted():
    """Test that all retries are exhausted and APITimeoutError is raised."""

    async def always_fails():
        raise httpx.TimeoutException("Always fails")

    with pytest.raises(APITimeoutError) as exc_info:
        await retry_with_backoff(always_fails, max_retries=2, initial_delay=0.01)

    assert "Request failed after 3 attempts" in str(exc_info.value)
    assert isinstance(exc_info.value.original_error, httpx.TimeoutException)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_with_connect_error():
    """Test retry with httpx.ConnectError exception."""
    call_count = 0

    async def connect_fails_once():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.ConnectError("Connection refused")
        return "connected"

    result = await retry_with_backoff(connect_fails_once, max_retries=1, initial_delay=0.01)
    assert result == "connected"
    assert call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_non_retryable_exception():
    """Test that non-retryable exceptions are raised immediately."""

    async def raises_value_error():
        raise ValueError("Not a retryable error")

    with pytest.raises(ValueError, match="Not a retryable error"):
        await retry_with_backoff(raises_value_error, max_retries=2, initial_delay=0.01)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_with_args_and_kwargs():
    """Test retry function with positional and keyword arguments."""

    async def func_with_args(x, y, z=0):
        return x + y + z

    result = await retry_with_backoff(func_with_args, 1, 2, z=3, max_retries=1)
    assert result == 6


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_backoff_delay():
    """Test that backoff delay increases with each retry."""
    call_times = []

    async def track_timing():
        call_times.append(asyncio.get_event_loop().time())
        if len(call_times) < 3:
            raise httpx.TimeoutException("Timeout")
        return "success"

    result = await retry_with_backoff(
        track_timing, max_retries=2, initial_delay=0.1, backoff_factor=2.0
    )

    assert result == "success"
    assert len(call_times) == 3

    # Check that delays increase: ~0.1s then ~0.2s
    delay1 = call_times[1] - call_times[0]
    delay2 = call_times[2] - call_times[1]

    assert 0.08 < delay1 < 0.15  # ~0.1s with some tolerance
    assert 0.18 < delay2 < 0.25  # ~0.2s with some tolerance


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_custom_exceptions():
    """Test retry with custom exception types."""
    call_count = 0

    async def custom_failure():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OSError("Custom retryable error")
        return "recovered"

    result = await retry_with_backoff(
        custom_failure, max_retries=1, initial_delay=0.01, exceptions=(OSError,)
    )

    assert result == "recovered"
    assert call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_zero_retries():
    """Test that max_retries=0 means only one attempt (no retries)."""
    call_count = 0

    async def fails_once():
        nonlocal call_count
        call_count += 1
        raise httpx.TimeoutException("Timeout")

    with pytest.raises(APITimeoutError):
        await retry_with_backoff(fails_once, max_retries=0, initial_delay=0.01)

    assert call_count == 1  # Only one attempt, no retries
