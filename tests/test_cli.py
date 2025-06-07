"""Tests for CLI module."""

import sys
from unittest.mock import patch

import pytest

from accessiweather.cli import main, parse_args


@pytest.mark.unit
def test_parse_args_default():
    """Test parse_args with default arguments."""
    with patch.object(sys, "argv", ["accessiweather"]):
        args = parse_args()
        assert args.config is None
        assert args.debug is False
        assert args.no_cache is False
        assert args.portable is False


@pytest.mark.unit
def test_parse_args_with_config():
    """Test parse_args with config directory."""
    with patch.object(sys, "argv", ["accessiweather", "--config", "/path/to/config"]):
        args = parse_args()
        assert args.config == "/path/to/config"
        assert args.debug is False
        assert args.no_cache is False
        assert args.portable is False


@pytest.mark.unit
def test_parse_args_with_debug():
    """Test parse_args with debug flag."""
    with patch.object(sys, "argv", ["accessiweather", "--debug"]):
        args = parse_args()
        assert args.config is None
        assert args.debug is True
        assert args.no_cache is False
        assert args.portable is False


@pytest.mark.unit
def test_parse_args_with_no_cache():
    """Test parse_args with no-cache flag."""
    with patch.object(sys, "argv", ["accessiweather", "--no-cache"]):
        args = parse_args()
        assert args.config is None
        assert args.debug is False
        assert args.no_cache is True
        assert args.portable is False


@pytest.mark.unit
def test_parse_args_with_portable():
    """Test parse_args with portable flag."""
    with patch.object(sys, "argv", ["accessiweather", "--portable"]):
        args = parse_args()
        assert args.config is None
        assert args.debug is False
        assert args.no_cache is False
        assert args.portable is True


@pytest.mark.unit
def test_parse_args_all_flags():
    """Test parse_args with all flags."""
    with patch.object(
        sys, "argv", ["accessiweather", "--config", "/test", "--debug", "--no-cache", "--portable"]
    ):
        args = parse_args()
        assert args.config == "/test"
        assert args.debug is True
        assert args.no_cache is True
        assert args.portable is True


@pytest.mark.unit
@patch("accessiweather.cli.app_main")
def test_main_success(mock_app_main):
    """Test main function success case."""
    mock_app_main.return_value = None

    with patch.object(sys, "argv", ["accessiweather"]):
        result = main()

    assert result == 0
    mock_app_main.assert_called_once_with(
        config_dir=None, debug_mode=False, enable_caching=True, portable_mode=False
    )


@pytest.mark.unit
@patch("accessiweather.cli.app_main")
def test_main_with_arguments(mock_app_main):
    """Test main function with arguments."""
    mock_app_main.return_value = None

    with patch.object(
        sys, "argv", ["accessiweather", "--config", "/test", "--debug", "--no-cache", "--portable"]
    ):
        result = main()

    assert result == 0
    mock_app_main.assert_called_once_with(
        config_dir="/test", debug_mode=True, enable_caching=False, portable_mode=True
    )


@pytest.mark.unit
@patch("accessiweather.cli.app_main")
@patch("accessiweather.cli.logging")
def test_main_exception(mock_logging, mock_app_main):
    """Test main function exception handling."""
    mock_app_main.side_effect = Exception("Test error")

    with patch.object(sys, "argv", ["accessiweather"]):
        result = main()

    assert result == 1
    mock_logging.error.assert_called_once_with("Error running application: Test error")


@pytest.mark.unit
def test_main_entry_point():
    """Test that main can be called as entry point."""
    # This test ensures the if __name__ == "__main__" block works
    with patch("accessiweather.cli.main") as mock_main:
        mock_main.return_value = 0
        with patch.object(sys, "argv", ["test"]):
            # Import the module to trigger the main block
            import accessiweather.cli  # noqa: F401

            # The main block should not execute during import
            mock_main.assert_not_called()
