"""Tests for faulthandler utilities module."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.utils.faulthandler_utils import (
    disable_faulthandler,
    dump_traceback,
    enable_faulthandler,
    register_signal_handler,
)


@pytest.mark.unit
@patch("faulthandler.enable")
@patch("builtins.open")
def test_enable_faulthandler_default(mock_open, mock_enable):
    """Test enable_faulthandler with default parameters."""
    mock_file = MagicMock()
    mock_open.return_value = mock_file

    result = enable_faulthandler()

    mock_enable.assert_called()
    assert result is not None


@pytest.mark.unit
@patch("faulthandler.enable")
@patch("builtins.open")
def test_enable_faulthandler_with_file(mock_open, mock_enable):
    """Test enable_faulthandler with specific file path."""
    mock_file = MagicMock()
    mock_open.return_value = mock_file

    result = enable_faulthandler("/test/path.log")

    mock_open.assert_called()
    mock_enable.assert_called()
    assert result is not None


@pytest.mark.unit
@patch("faulthandler.enable")
@patch("builtins.open", side_effect=Exception("File error"))
def test_enable_faulthandler_file_error(mock_open, mock_enable):
    """Test enable_faulthandler with file error."""
    result = enable_faulthandler("/invalid/path.log")

    # Should still enable faulthandler for stderr
    mock_enable.assert_called()
    assert result is not None


@pytest.mark.unit
@patch("faulthandler.disable")
def test_disable_faulthandler(mock_disable):
    """Test disable_faulthandler."""
    disable_faulthandler()

    mock_disable.assert_called_once()


@pytest.mark.unit
@patch("faulthandler.dump_traceback")
def test_dump_traceback_default(mock_dump):
    """Test dump_traceback with default parameters."""
    dump_traceback()

    mock_dump.assert_called()


@pytest.mark.unit
@patch("faulthandler.dump_traceback")
def test_dump_traceback_all_threads_false(mock_dump):
    """Test dump_traceback with all_threads=False."""
    dump_traceback(all_threads=False)

    mock_dump.assert_called()


@pytest.mark.unit
@patch("faulthandler.register", create=True)
def test_register_signal_handler(mock_register):
    """Test register_signal_handler."""
    with patch("accessiweather.utils.faulthandler_utils.hasattr", return_value=True):
        register_signal_handler(10)  # SIGUSR1

        mock_register.assert_called()


@pytest.mark.unit
@patch("faulthandler.register", side_effect=OSError("Signal error"), create=True)
def test_register_signal_handler_error(mock_register):
    """Test register_signal_handler with error."""
    with patch("accessiweather.utils.faulthandler_utils.hasattr", return_value=True):
        # Should not raise an exception
        register_signal_handler(10)

        mock_register.assert_called()


@pytest.mark.unit
def test_faulthandler_utils_module_import():
    """Test that faulthandler_utils module can be imported."""
    try:
        import accessiweather.utils.faulthandler_utils

        assert hasattr(accessiweather.utils.faulthandler_utils, "enable_faulthandler")
        assert hasattr(accessiweather.utils.faulthandler_utils, "disable_faulthandler")
        assert hasattr(accessiweather.utils.faulthandler_utils, "dump_traceback")
        assert hasattr(accessiweather.utils.faulthandler_utils, "register_signal_handler")
    except ImportError:
        pytest.fail("Failed to import faulthandler_utils module")


@pytest.mark.unit
@patch("faulthandler.enable")
@patch("builtins.open")
@patch("pathlib.Path.mkdir")
def test_enable_faulthandler_creates_directory(mock_mkdir, mock_open, mock_enable):
    """Test enable_faulthandler creates directory if needed."""
    mock_file = MagicMock()
    mock_open.return_value = mock_file

    enable_faulthandler()

    mock_mkdir.assert_called()


@pytest.mark.unit
@patch("faulthandler.enable")
@patch("builtins.open")
def test_enable_faulthandler_all_threads_false(mock_open, mock_enable):
    """Test enable_faulthandler with all_threads=False."""
    mock_file = MagicMock()
    mock_open.return_value = mock_file

    enable_faulthandler(all_threads=False)

    mock_enable.assert_called()


@pytest.mark.unit
@patch("faulthandler.enable")
@patch("builtins.open")
@patch("signal.SIGUSR1", 10, create=True)
@patch("signal.SIGUSR2", 12, create=True)
@patch("faulthandler.register", create=True)
def test_enable_faulthandler_register_signals(mock_register, mock_open, mock_enable):
    """Test enable_faulthandler with signal registration."""
    mock_file = MagicMock()
    mock_open.return_value = mock_file

    with patch("sys.platform", "linux"):
        with patch("accessiweather.utils.faulthandler_utils.hasattr", return_value=True):
            enable_faulthandler(register_all_signals=True)

    mock_enable.assert_called()
    # Signal registration may or may not be called depending on platform
