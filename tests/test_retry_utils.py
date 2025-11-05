import asyncio
import logging

import httpx
import pytest

from accessiweather.utils.retry_utils import (
    async_retry_with_backoff,
    calculate_backoff_delay,
    is_retryable_http_error,
)


def test_calculate_backoff_delay_basic() -> None:
    assert calculate_backoff_delay(1, 0.5) == pytest.approx(0.5)
    assert calculate_backoff_delay(2, 0.5) == pytest.approx(1.0)


def test_calculate_backoff_delay_with_max_and_callable_jitter() -> None:
    delay = calculate_backoff_delay(
        3,
        1.0,
        max_delay=5.0,
        jitter=lambda current: current * 0.1,
    )
    # 1 * 2^(3-1) = 4, jitter adds 0.4 but max_delay keeps it <= 5
    assert delay == pytest.approx(4.4, rel=1e-3)


def test_is_retryable_http_error_variants() -> None:
    timeout_exc = httpx.TimeoutException("timed out")
    assert is_retryable_http_error(timeout_exc)

    request = httpx.Request("GET", "https://example.com")
    retryable_response = httpx.Response(500, request=request)
    http_error = httpx.HTTPStatusError("Server error", request=request, response=retryable_response)
    assert is_retryable_http_error(http_error)

    non_retryable_response = httpx.Response(404, request=request)
    not_retryable = httpx.HTTPStatusError(
        "Not found", request=request, response=non_retryable_response
    )
    assert not is_retryable_http_error(not_retryable)


@pytest.mark.asyncio
async def test_async_retry_retries_and_succeeds(monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    attempts = {"count": 0}

    async def fake_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("accessiweather.utils.retry_utils.asyncio.sleep", fake_sleep)

    async def flaky() -> int:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise httpx.RequestError("temporary failure")
        return 42

    logger = logging.getLogger("test.retry.success")
    caplog.set_level(logging.INFO, logger.name)  # Changed to INFO to capture success message

    decorated = async_retry_with_backoff(
        max_attempts=3,
        base_delay=0.01,
        logger=logger,
    )(flaky)

    assert await decorated() == 42
    assert attempts["count"] == 3
    assert any("Retry successful" in message for message in caplog.messages)


@pytest.mark.asyncio
async def test_async_retry_exhausts_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0}

    async def fake_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("accessiweather.utils.retry_utils.asyncio.sleep", fake_sleep)

    async def always_fail() -> None:
        attempts["count"] += 1
        raise httpx.ConnectError("down", request=httpx.Request("GET", "https://example.com"))

    decorated = async_retry_with_backoff(max_attempts=3, base_delay=0.01)(always_fail)

    with pytest.raises(httpx.ConnectError):
        await decorated()

    assert attempts["count"] == 3


@pytest.mark.asyncio
async def test_async_retry_timeout_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0}

    # Don't patch asyncio.sleep - we want the timeout to actually trigger
    async def slow() -> None:
        attempts["count"] += 1
        await asyncio.sleep(0.1)  # Sleep longer than timeout

    decorated = async_retry_with_backoff(max_attempts=2, base_delay=0.001, timeout=0.01)(slow)

    with pytest.raises(asyncio.TimeoutError):
        await decorated()

    assert attempts["count"] == 2
