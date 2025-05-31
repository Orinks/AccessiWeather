"""Tests for __main__ module."""

import sys
from unittest.mock import patch

import pytest


@pytest.mark.unit
def test_main_module_import():
    """Test that __main__ module can be imported."""
    try:
        import accessiweather.__main__  # noqa: F401

        # If we get here, the import was successful
        assert True
    except ImportError:
        pytest.fail("Failed to import accessiweather.__main__")


@pytest.mark.unit
@patch("accessiweather.__main__.main")
def test_main_module_execution(mock_main):
    """Test __main__ module execution."""
    mock_main.return_value = 0

    # Simulate running python -m accessiweather
    with patch.object(sys, "argv", ["__main__.py"]):
        # Import and execute the main module
        import accessiweather.__main__  # noqa: F401

        # The main function should be called when the module is executed
        # Note: This test verifies the structure exists, actual execution
        # happens when run as a module
