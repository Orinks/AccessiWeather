"""Completely isolated Toga tests without any fixture dependencies."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set up Toga dummy backend before any imports
os.environ["TOGA_BACKEND"] = "toga_dummy"

import pytest


class TestTogaBasics:
    """Basic Toga infrastructure tests."""

    def test_toga_backend_environment(self):
        """Test that Toga dummy backend environment is set."""
        assert os.environ.get("TOGA_BACKEND") == "toga_dummy"

    def test_python_path_setup(self):
        """Test that Python path includes src directory."""
        src_path = str(Path(__file__).parent.parent / "src")
        assert src_path in sys.path

    @pytest.mark.asyncio
    async def test_basic_async_functionality(self):
        """Test basic async functionality works."""

        async def simple_task():
            await asyncio.sleep(0.01)
            return "async_works"

        result = await simple_task()
        assert result == "async_works"

    def test_toga_dummy_import(self):
        """Test that toga-dummy can be imported."""
        try:
            import toga_dummy

            assert toga_dummy is not None
        except ImportError:
            pytest.skip("toga-dummy not available")

    @pytest.mark.asyncio
    async def test_asyncio_timeout(self):
        """Test asyncio timeout functionality."""

        async def quick_task():
            await asyncio.sleep(0.001)
            return "completed"

        try:
            result = await asyncio.wait_for(quick_task(), timeout=1.0)
            assert result == "completed"
        except TimeoutError:
            pytest.fail("Task should not have timed out")

    def test_mock_creation(self):
        """Test basic mock creation."""
        from unittest.mock import AsyncMock, Mock

        # Test sync mock
        sync_mock = Mock(return_value="sync_result")
        assert sync_mock() == "sync_result"

        # Test async mock
        async_mock = AsyncMock(return_value="async_result")
        assert asyncio.iscoroutine(async_mock())

    @pytest.mark.asyncio
    async def test_async_mock_execution(self):
        """Test async mock execution."""
        from unittest.mock import AsyncMock

        async_mock = AsyncMock(return_value="async_result")
        result = await async_mock()
        assert result == "async_result"

    def test_simple_data_structures(self):
        """Test simple data structure creation."""
        test_data = {
            "name": "Test Location",
            "temperature": 75.0,
            "condition": "Sunny",
            "timestamp": "2025-06-29T12:00:00Z",
        }

        assert test_data["name"] == "Test Location"
        assert test_data["temperature"] == 75.0
        assert test_data["condition"] == "Sunny"

    @pytest.mark.asyncio
    async def test_concurrent_tasks(self):
        """Test concurrent async task execution."""

        async def task(delay, result):
            await asyncio.sleep(delay)
            return result

        # Run multiple tasks concurrently
        tasks = [task(0.01, "task1"), task(0.02, "task2"), task(0.01, "task3")]

        results = await asyncio.gather(*tasks)
        assert results == ["task1", "task2", "task3"]

    def test_environment_isolation(self):
        """Test that test environment is properly isolated."""
        # Test that we can set and read environment variables
        test_var = "TOGA_TEST_VAR"
        test_value = "test_value_123"

        os.environ[test_var] = test_value
        assert os.environ.get(test_var) == test_value

        # Clean up
        del os.environ[test_var]
        assert os.environ.get(test_var) is None
