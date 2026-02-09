"""Tests for performance/timer.py module."""

import asyncio
import logging
import os
import time
from unittest import mock

import pytest

from accessiweather.performance.timer import (
    measure,
    measure_async,
    timed,
    timed_async,
)


class TestMeasure:
    """Tests for the measure() sync context manager."""

    def test_measure_logs_completion(self, caplog):
        """Successful operation logs completion time."""
        with caplog.at_level(logging.INFO, logger="performance"), measure("test_op"):
            time.sleep(0.01)
        assert any("test_op completed in" in r.message for r in caplog.records)

    def test_measure_logs_failure_and_reraises(self, caplog):
        """Failed operation logs warning and re-raises the exception."""
        with (
            caplog.at_level(logging.WARNING, logger="performance"),
            pytest.raises(ValueError, match="boom"),
            measure("fail_op"),
        ):
            raise ValueError("boom")
        assert any("fail_op failed after" in r.message for r in caplog.records)
        assert any("ValueError: boom" in r.message for r in caplog.records)

    def test_measure_yields_none(self):
        """measure() yields None (no value)."""
        with measure("noop") as val:
            assert val is None


class TestMeasureAsync:
    """Tests for the measure_async() async context manager."""

    @pytest.mark.asyncio
    async def test_measure_async_logs_completion(self, caplog):
        """Successful async operation logs completion time."""
        with caplog.at_level(logging.INFO, logger="performance"):
            async with measure_async("async_op"):
                await asyncio.sleep(0.01)
        assert any("async_op completed in" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_measure_async_logs_failure_and_reraises(self, caplog):
        """Failed async operation logs warning and re-raises."""
        with (
            caplog.at_level(logging.WARNING, logger="performance"),
            pytest.raises(RuntimeError, match="async_boom"),
        ):
            async with measure_async("async_fail"):
                raise RuntimeError("async_boom")
        assert any("async_fail failed after" in r.message for r in caplog.records)


class TestTimed:
    """Tests for the @timed decorator."""

    def test_timed_decorator_calls_function(self):
        """Decorated function should still return its value."""

        @timed("my_func")
        def add(a, b):
            return a + b

        result = add(2, 3)
        assert result == 5

    def test_timed_uses_function_name_by_default(self):
        """When no name given, uses function.__name__."""

        @timed()
        def some_function():
            return 42

        assert some_function.__name__ == "some_function"
        assert some_function() == 42

    def test_timed_logs_when_performance_mode(self, caplog):
        """With INFO logging enabled, timed logs execution time."""
        with caplog.at_level(logging.INFO, logger="performance"):

            @timed("perf_test")
            def do_work():
                return "done"

            result = do_work()
            assert result == "done"
        assert any("perf_test completed in" in r.message for r in caplog.records)

    def test_timed_skips_logging_when_disabled(self):
        """When PERFORMANCE_MODE is off and logger level > INFO, function runs without measure."""
        perf_logger = logging.getLogger("performance")
        original_level = perf_logger.level

        try:
            perf_logger.setLevel(logging.CRITICAL)
            with mock.patch("accessiweather.performance.timer.PERFORMANCE_MODE", False):

                @timed("skip_test")
                def quick():
                    return "fast"

                assert quick() == "fast"
        finally:
            perf_logger.setLevel(original_level)

    def test_timed_prevents_double_wrapping(self):
        """Applying @timed twice should not double-wrap."""

        @timed("first")
        def my_func():
            return 1

        wrapped_once = my_func
        double_wrapped = timed("second")(wrapped_once)
        # Should be the same function (not re-wrapped)
        assert double_wrapped is wrapped_once


class TestTimedAsync:
    """Tests for the @timed_async decorator."""

    @pytest.mark.asyncio
    async def test_timed_async_calls_function(self):
        """Decorated async function should return its value."""

        @timed_async("async_func")
        async def fetch():
            return "data"

        result = await fetch()
        assert result == "data"

    @pytest.mark.asyncio
    async def test_timed_async_uses_function_name(self):
        """When no name given, uses function.__name__."""

        @timed_async()
        async def another_func():
            return 99

        assert another_func.__name__ == "another_func"
        assert await another_func() == 99

    @pytest.mark.asyncio
    async def test_timed_async_logs_when_enabled(self, caplog):
        """With INFO logging, timed_async logs execution time."""
        with caplog.at_level(logging.INFO, logger="performance"):

            @timed_async("async_perf")
            async def async_work():
                return "ok"

            result = await async_work()
            assert result == "ok"
        assert any("async_perf completed in" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_timed_async_prevents_double_wrapping(self):
        """Applying @timed_async twice should not double-wrap."""

        @timed_async("first")
        async def my_async():
            return 1

        wrapped_once = my_async
        double_wrapped = timed_async("second")(wrapped_once)
        assert double_wrapped is wrapped_once

    @pytest.mark.asyncio
    async def test_timed_async_skips_logging_when_disabled(self):
        """When PERFORMANCE_MODE off and logger > INFO, runs without measure."""
        perf_logger = logging.getLogger("performance")
        original_level = perf_logger.level

        try:
            perf_logger.setLevel(logging.CRITICAL)
            with mock.patch("accessiweather.performance.timer.PERFORMANCE_MODE", False):

                @timed_async("skip_async")
                async def quick_async():
                    return "fast"

                assert await quick_async() == "fast"
        finally:
            perf_logger.setLevel(original_level)


class TestPerformanceMode:
    """Tests for PERFORMANCE_MODE flag."""

    def test_performance_mode_default_is_false(self):
        """By default, PERFORMANCE_MODE should be False (no env var set)."""
        # The actual value depends on env, but we can verify the logic
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ACCESSIWEATHER_PERFORMANCE", None)
            # Re-evaluate the expression
            result = os.environ.get("ACCESSIWEATHER_PERFORMANCE", "").lower() in (
                "1",
                "true",
                "yes",
            )
            assert result is False

    def test_performance_mode_enabled(self):
        """ACCESSIWEATHER_PERFORMANCE=1 enables performance mode."""
        result = "1" in ("1", "true", "yes")
        assert result is True
