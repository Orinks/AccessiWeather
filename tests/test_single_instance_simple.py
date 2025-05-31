"""Tests for single instance utility module."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.utils.single_instance import SingleInstanceChecker


@pytest.mark.unit
def test_single_instance_checker_init():
    """Test SingleInstanceChecker initialization."""
    checker = SingleInstanceChecker("test_app")
    assert checker.app_name == "test_app"
    assert checker.checker is None


@pytest.mark.unit
def test_single_instance_checker_init_default():
    """Test SingleInstanceChecker initialization with default app name."""
    checker = SingleInstanceChecker()
    assert checker.app_name == "accessiweather"
    assert checker.checker is None


@pytest.mark.unit
@patch("wx.SingleInstanceChecker")
@patch("wx.GetUserId", return_value=1000)
def test_try_acquire_lock_success(mock_get_user_id, mock_wx_checker):
    """Test successful lock acquisition."""
    mock_checker_instance = MagicMock()
    mock_checker_instance.IsAnotherRunning.return_value = False
    mock_wx_checker.return_value = mock_checker_instance

    checker = SingleInstanceChecker("test_app")
    result = checker.try_acquire_lock()

    assert result is True
    assert checker.checker == mock_checker_instance
    mock_wx_checker.assert_called_once_with("test_app-1000")


@pytest.mark.unit
@patch("wx.SingleInstanceChecker")
def test_try_acquire_lock_another_running(mock_wx_checker):
    """Test lock acquisition when another instance is running."""
    mock_checker_instance = MagicMock()
    mock_checker_instance.IsAnotherRunning.return_value = True
    mock_wx_checker.return_value = mock_checker_instance

    checker = SingleInstanceChecker("test_app")
    result = checker.try_acquire_lock()

    assert result is False
    assert checker.checker == mock_checker_instance


@pytest.mark.unit
@patch("wx.SingleInstanceChecker")
def test_try_acquire_lock_exception(mock_wx_checker):
    """Test lock acquisition with exception."""
    mock_wx_checker.side_effect = Exception("Test error")

    checker = SingleInstanceChecker("test_app")
    result = checker.try_acquire_lock()

    assert result is True  # Should return True on exception to avoid blocking
    assert checker.checker is None


@pytest.mark.unit
def test_release_lock_no_checker():
    """Test release lock when no checker exists."""
    checker = SingleInstanceChecker("test_app")
    # Should not raise an exception
    checker.release_lock()


@pytest.mark.unit
def test_release_lock_with_checker():
    """Test release lock with checker."""
    checker = SingleInstanceChecker("test_app")
    mock_checker = MagicMock()
    checker.checker = mock_checker

    checker.release_lock()

    assert checker.checker is None


@pytest.mark.unit
def test_single_instance_module_import():
    """Test that single_instance module can be imported."""
    try:
        import accessiweather.utils.single_instance

        assert hasattr(accessiweather.utils.single_instance, "SingleInstanceChecker")
    except ImportError:
        pytest.fail("Failed to import single_instance module")


@pytest.mark.unit
@patch("wx.SingleInstanceChecker")
@patch("wx.GetUserId", return_value=1000)
def test_try_acquire_lock_already_acquired(mock_get_user_id, mock_wx_checker):
    """Test trying to acquire lock when already acquired."""
    mock_checker_instance = MagicMock()
    mock_checker_instance.IsAnotherRunning.return_value = False
    mock_wx_checker.return_value = mock_checker_instance

    checker = SingleInstanceChecker("test_app")

    # First acquisition
    result1 = checker.try_acquire_lock()
    assert result1 is True

    # Second acquisition should return True (already acquired)
    result2 = checker.try_acquire_lock()
    assert result2 is True

    # Should create two checkers since the method doesn't check if already acquired
    assert mock_wx_checker.call_count == 2


@pytest.mark.unit
def test_single_instance_checker_str():
    """Test string representation of SingleInstanceChecker."""
    checker = SingleInstanceChecker("test_app")
    str_repr = str(checker)
    assert "test_app" in str_repr or "SingleInstanceChecker" in str_repr
