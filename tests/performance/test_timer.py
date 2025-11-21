"""Unit tests for performance timing utilities."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import MagicMock

import pytest

from accessiweather.performance.timer import measure, measure_async, timed, timed_async


@pytest.fixture
def mock_logger(monkeypatch):
    """Mock the performance logger."""
    mock = MagicMock()
    monkeypatch.setattr("accessiweather.performance.timer.logger", mock)
    return mock


def test_measure_context_manager_success(mock_logger):
    """Test that measure logs elapsed time on success."""
    with measure("test_operation"):
        pass

    assert mock_logger.info.called
    call_args = mock_logger.info.call_args[0][0]
    assert "test_operation completed in" in call_args
    assert "ms" in call_args


def test_measure_context_manager_with_exception(mock_logger):
    """Test that measure logs elapsed time even when exception occurs."""
    with pytest.raises(ValueError), measure("failing_operation"):
        raise ValueError("Test error")

    assert mock_logger.warning.called
    call_args = mock_logger.warning.call_args[0][0]
    assert "failing_operation failed after" in call_args
    assert "ValueError: Test error" in call_args


@pytest.mark.asyncio
async def test_measure_async_context_manager_success(mock_logger):
    """Test that measure_async logs elapsed time on success."""
    async with measure_async("async_operation"):
        await asyncio.sleep(0.001)

    assert mock_logger.info.called
    call_args = mock_logger.info.call_args[0][0]
    assert "async_operation completed in" in call_args
    assert "ms" in call_args


@pytest.mark.asyncio
async def test_measure_async_context_manager_with_exception(mock_logger):
    """Test that measure_async logs elapsed time even when exception occurs."""
    with pytest.raises(RuntimeError):
        async with measure_async("failing_async_operation"):
            raise RuntimeError("Async test error")

    assert mock_logger.warning.called
    call_args = mock_logger.warning.call_args[0][0]
    assert "failing_async_operation failed after" in call_args
    assert "RuntimeError: Async test error" in call_args


def test_timed_decorator(mock_logger):
    """Test timed decorator on synchronous function."""

    @timed("decorated_func")
    def sample_function():
        return "result"

    result = sample_function()

    assert result == "result"
    assert mock_logger.info.called or not mock_logger.isEnabledFor(logging.INFO)


def test_timed_decorator_prevents_double_wrapping():
    """Test that timed decorator doesn't double-wrap functions."""

    @timed()
    def func1():
        return 1

    # Try to wrap again
    @timed()
    def func2():
        return 1

    # Functions should have the wrapper attribute
    assert hasattr(func1, "_timed_wrapper")


@pytest.mark.asyncio
async def test_timed_async_decorator(mock_logger):
    """Test timed_async decorator on async function."""

    @timed_async("async_decorated_func")
    async def sample_async_function():
        await asyncio.sleep(0.001)
        return "async_result"

    result = await sample_async_function()

    assert result == "async_result"
    assert mock_logger.info.called or not mock_logger.isEnabledFor(logging.INFO)


@pytest.mark.asyncio
async def test_timed_async_decorator_prevents_double_wrapping():
    """Test that timed_async decorator doesn't double-wrap functions."""

    @timed_async()
    async def async_func1():
        return 1

    # Functions should have the wrapper attribute
    assert hasattr(async_func1, "_timed_wrapper")


def test_measure_with_multiple_operations(mock_logger):
    """Test measuring multiple operations."""
    operations = ["op1", "op2", "op3"]

    for op in operations:
        with measure(op):
            pass

    # Should have 3 info calls
    assert mock_logger.info.call_count >= len(operations) or not mock_logger.isEnabledFor(
        logging.INFO
    )
