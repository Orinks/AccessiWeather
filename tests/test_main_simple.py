"""Tests for main module."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.main import main as app_main


@pytest.mark.unit
def test_main_module_import():
    """Test that main module can be imported."""
    try:
        import accessiweather.main

        assert hasattr(accessiweather.main, "main")
    except ImportError:
        pytest.fail("Failed to import main module")


@pytest.mark.unit
@patch("accessiweather.simple.main")
def test_app_main_another_instance_running(mock_toga_main):
    """Test app_main delegates to toga main."""
    mock_app = MagicMock()
    mock_toga_main.return_value = mock_app

    result = app_main()

    assert result == mock_app
    mock_toga_main.assert_called_once()


@pytest.mark.unit
@patch("accessiweather.simple.main")
def test_app_main_exception_handling(mock_toga_main):
    """Test app_main exception handling."""
    mock_toga_main.side_effect = Exception("Test error")

    # Since the current main function doesn't handle exceptions,
    # this should raise the exception
    with pytest.raises(Exception, match="Test error"):
        app_main()
