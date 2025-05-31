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
@patch("accessiweather.main.SingleInstanceChecker")
@patch("accessiweather.main.setup_root_logging")
@patch("wx.App")
@patch("wx.MessageBox")
def test_app_main_another_instance_running(
    mock_message_box, mock_wx_app, mock_setup_logging, mock_instance_checker
):
    """Test app_main when another instance is running."""
    mock_instance_checker_obj = MagicMock()
    mock_instance_checker_obj.try_acquire_lock.return_value = False
    mock_instance_checker.return_value = mock_instance_checker_obj

    result = app_main()

    assert result == 1
    mock_message_box.assert_called_once()


@pytest.mark.unit
@patch("accessiweather.main.SingleInstanceChecker")
@patch("accessiweather.main.setup_root_logging")
@patch("accessiweather.main.get_config_dir")
@patch("wx.App")
def test_app_main_exception_handling(
    mock_wx_app, mock_get_config_dir, mock_setup_logging, mock_instance_checker
):
    """Test app_main exception handling."""
    mock_instance_checker_obj = MagicMock()
    mock_instance_checker_obj.try_acquire_lock.return_value = True
    mock_instance_checker.return_value = mock_instance_checker_obj

    mock_get_config_dir.side_effect = Exception("Test error")

    result = app_main()

    assert result == 1
    mock_instance_checker_obj.release_lock.assert_called_once()
