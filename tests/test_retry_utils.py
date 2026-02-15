"""Tests for retry_utils module."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from accessiweather.utils.retry_utils import (
    RETRYABLE_EXCEPTIONS,
    _should_retry,
    async_retry_with_backoff,
    calculate_backoff_delay,
    is_retryable_http_error,
)


class TestCalculateBackoffDelay:
    """Test calculate_backoff_delay."""

    def test_basic_exponential(self):
        assert calculate_backoff_delay(1, 1.0) == 1.0
        assert calculate_backoff_delay(2, 1.0) == 2.0
        assert calculate_backoff_delay(3, 1.0) == 4.0

    def test_max_delay_caps(self):
        assert calculate_backoff_delay(10, 1.0, max_delay=5.0) == 5.0

    def test_zero_base_delay(self):
        assert calculate_backoff_delay(1, 0.0) == 0.0

    def test_invalid_attempt(self):
        with pytest.raises(ValueError, match="attempt must be >= 1"):
            calculate_backoff_delay(0, 1.0)

    def test_negative_base_delay(self):
        with pytest.raises(ValueError, match="base_delay must be >= 0"):
            calculate_backoff_delay(1, -1.0)

    def test_negative_max_delay(self):
        with pytest.raises(ValueError, match="max_delay must be >= 0"):
            calculate_backoff_delay(1, 1.0, max_delay=-1.0)

    def test_jitter_float(self):
        result = calculate_backoff_delay(1, 1.0, jitter=0.5)
        assert 1.0 <= result <= 1.5

    def test_jitter_tuple(self):
        result = calculate_backoff_delay(1, 1.0, jitter=(0.1, 0.2))
        assert 1.1 <= result <= 1.2

    def test_jitter_callable(self):
        result = calculate_backoff_delay(1, 1.0, jitter=lambda d: 0.25)
        assert result == 1.25

    def test_jitter_capped_by_max_delay(self):
        result = calculate_backoff_delay(1, 1.0, max_delay=1.0, jitter=2.0)
        assert result == 1.0


class TestIsRetryableHttpError:
    """Test is_retryable_http_error."""

    def test_non_httpx_exception(self):
        assert is_retryable_http_error(ValueError("nope")) is False

    def test_timeout_exception(self):
        import httpx
        assert is_retryable_http_error(httpx.ConnectTimeout("timeout")) is True

    def test_500_status_error(self):
        import httpx
        response = httpx.Response(500, request=httpx.Request("GET", "http://x"))
        exc = httpx.HTTPStatusError("fail", request=response.request, response=response)
        assert is_retryable_http_error(exc) is True

    def test_429_status_error(self):
        import httpx
        response = httpx.Response(429, request=httpx.Request("GET", "http://x"))
        exc = httpx.HTTPStatusError("fail", request=response.request, response=response)
        assert is_retryable_http_error(exc) is True

    def test_400_not_retryable(self):
        import httpx
        response = httpx.Response(400, request=httpx.Request("GET", "http://x"))
        exc = httpx.HTTPStatusError("fail", request=response.request, response=response)
        assert is_retryable_http_error(exc) is False

    def test_request_error_retryable(self):
        import httpx
        exc = httpx.ConnectError("connection refused")
        assert is_retryable_http_error(exc) is True


class TestShouldRetry:
    """Test _should_retry."""

    def test_cancelled_error_never_retried(self):
        assert _should_retry(asyncio.CancelledError(), RETRYABLE_EXCEPTIONS) is False

    def test_matching_exception(self):
        assert _should_retry(OSError("fail"), RETRYABLE_EXCEPTIONS) is True

    def test_non_matching_exception(self):
        assert _should_retry(ValueError("nope"), RETRYABLE_EXCEPTIONS) is False

    def test_chained_cause(self):
        outer = RuntimeError("outer")
        outer.__cause__ = OSError("inner")
        assert _should_retry(outer, RETRYABLE_EXCEPTIONS) is True

    def test_chained_context(self):
        outer = RuntimeError("outer")
        outer.__context__ = OSError("inner")
        assert _should_retry(outer, RETRYABLE_EXCEPTIONS) is True


class TestAsyncRetryWithBackoff:
    """Test the retry decorator."""

    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        mock_fn = AsyncMock(return_value=42)

        @async_retry_with_backoff(max_attempts=3, base_delay=0.01)
        async def fn():
            return await mock_fn()

        result = await fn()
        assert result == 42
        assert mock_fn.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_retryable_error(self):
        mock_fn = AsyncMock(side_effect=[OSError("fail"), 42])

        @async_retry_with_backoff(max_attempts=3, base_delay=0.001)
        async def fn():
            return await mock_fn()

        result = await fn()
        assert result == 42
        assert mock_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self):
        mock_fn = AsyncMock(side_effect=OSError("fail"))

        @async_retry_with_backoff(max_attempts=2, base_delay=0.001)
        async def fn():
            return await mock_fn()

        with pytest.raises(OSError):
            await fn()
        assert mock_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_non_retryable_raises_immediately(self):
        mock_fn = AsyncMock(side_effect=ValueError("bad"))

        @async_retry_with_backoff(max_attempts=3, base_delay=0.001)
        async def fn():
            return await mock_fn()

        with pytest.raises(ValueError):
            await fn()
        assert mock_fn.call_count == 1

    @pytest.mark.asyncio
    async def test_timeout(self):
        @async_retry_with_backoff(max_attempts=2, base_delay=0.001, timeout=0.001)
        async def fn():
            await asyncio.sleep(10)

        with pytest.raises(asyncio.TimeoutError):
            await fn()

    def test_invalid_max_attempts(self):
        with pytest.raises(ValueError, match="max_attempts must be >= 1"):
            async_retry_with_backoff(max_attempts=0, base_delay=1.0)

    def test_invalid_base_delay(self):
        with pytest.raises(ValueError, match="base_delay must be >= 0"):
            async_retry_with_backoff(max_attempts=1, base_delay=-1.0)

    @pytest.mark.asyncio
    async def test_custom_retryable_exceptions(self):
        mock_fn = AsyncMock(side_effect=[ValueError("retry me"), 99])

        @async_retry_with_backoff(
            max_attempts=3,
            base_delay=0.001,
            retryable_exceptions=[ValueError],
        )
        async def fn():
            return await mock_fn()

        result = await fn()
        assert result == 99
