"""Tests for logging configuration."""

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, mock_open, patch

import pytest

from accessiweather.logging_config import setup_logging

# --- Test Data ---

MOCK_HOME = Path("/home/user")
MOCK_LOG_DIR = MOCK_HOME / "AccessiWeather_logs"
MOCK_LOG_FILE = MOCK_LOG_DIR / "accessiweather.log"

# --- Tests ---

def test_setup_logging_directory_creation():
    """Test that the log directory is created."""
    mock_console = MagicMock(level=logging.NOTSET)  # Mock handler with level
    mock_file = MagicMock(level=logging.NOTSET)  # Mock handler with level
    
    with patch("pathlib.Path.home", return_value=MOCK_HOME):
        with patch("pathlib.Path.__truediv__") as mock_truediv:
            with patch("pathlib.Path.mkdir") as mock_mkdir:  # Mock mkdir directly
                with patch("logging.StreamHandler", return_value=mock_console):
                    with patch("logging.handlers.RotatingFileHandler", return_value=mock_file):
                        with patch("logging.FileHandler._open"):  # Prevent file opening
                            mock_truediv.side_effect = [MOCK_LOG_DIR, MOCK_LOG_FILE]
                            
                            setup_logging()
                            
                            mock_mkdir.assert_called_once_with(exist_ok=True)

def test_setup_logging_root_logger_config():
    """Test that the root logger is configured correctly."""
    mock_logger = MagicMock()
    mock_handler = MagicMock()
    mock_logger.handlers = [mock_handler]
    mock_console = MagicMock(level=logging.NOTSET)  # Mock handler with level
    mock_file = MagicMock(level=logging.NOTSET)  # Mock handler with level
    
    with patch("logging.getLogger", return_value=mock_logger):
        with patch("pathlib.Path.home", return_value=MOCK_HOME):
            with patch("pathlib.Path.__truediv__") as mock_truediv:
                with patch("pathlib.Path.mkdir"):  # Mock mkdir directly
                    with patch("logging.StreamHandler", return_value=mock_console):
                        with patch("logging.handlers.RotatingFileHandler", return_value=mock_file):
                            with patch("logging.FileHandler._open"):  # Prevent file opening
                                mock_truediv.side_effect = [MOCK_LOG_DIR, MOCK_LOG_FILE]
                                
                                setup_logging(log_level=logging.INFO)
                                
                                mock_logger.setLevel.assert_called_once_with(logging.INFO)
                                mock_logger.removeHandler.assert_called_once_with(mock_handler)

def test_setup_logging_formatters():
    """Test that formatters are created correctly."""
    mock_console = MagicMock(level=logging.NOTSET)  # Mock handler with level
    mock_file = MagicMock(level=logging.NOTSET)  # Mock handler with level
    
    with patch("logging.Formatter") as mock_formatter:
        with patch("pathlib.Path.home", return_value=MOCK_HOME):
            with patch("pathlib.Path.__truediv__") as mock_truediv:
                with patch("pathlib.Path.mkdir"):  # Mock mkdir directly
                    with patch("logging.StreamHandler", return_value=mock_console):
                        with patch("logging.handlers.RotatingFileHandler", return_value=mock_file):
                            with patch("logging.FileHandler._open"):  # Prevent file opening
                                mock_truediv.side_effect = [MOCK_LOG_DIR, MOCK_LOG_FILE]
                                
                                setup_logging()
                                
                                # Check console formatter
                                mock_formatter.assert_any_call(
                                    "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
                                    datefmt="%H:%M:%S"
                                )
                                # Check file formatter
                                mock_formatter.assert_any_call(
                                    "%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s"
                                )

def test_setup_logging_console_handler():
    """Test that console handler is configured correctly."""
    mock_logger = MagicMock()
    mock_formatter = MagicMock()
    mock_console = MagicMock(level=logging.NOTSET)  # Mock handler with level
    mock_file = MagicMock(level=logging.NOTSET)  # Mock handler with level
    
    with patch("logging.getLogger", return_value=mock_logger):
        with patch("logging.Formatter", return_value=mock_formatter):
            with patch("logging.StreamHandler", return_value=mock_console) as mock_stream:
                with patch("pathlib.Path.home", return_value=MOCK_HOME):
                    with patch("pathlib.Path.__truediv__") as mock_truediv:
                        with patch("pathlib.Path.mkdir"):  # Mock mkdir directly
                            with patch("logging.handlers.RotatingFileHandler", return_value=mock_file):
                                with patch("logging.FileHandler._open"):  # Prevent file opening
                                    mock_truediv.side_effect = [MOCK_LOG_DIR, MOCK_LOG_FILE]
                                    
                                    setup_logging(log_level=logging.INFO)
                                    
                                    mock_stream.assert_called_once_with(stream=sys.stdout)
                                    mock_console.setLevel.assert_called_once_with(logging.INFO)
                                    mock_console.setFormatter.assert_called_once_with(mock_formatter)
                                    mock_logger.addHandler.assert_any_call(mock_console)

def test_setup_logging_file_handler():
    """Test that file handler is configured correctly."""
    mock_logger = MagicMock()
    mock_formatter = MagicMock()
    mock_console = MagicMock(level=logging.NOTSET)  # Mock handler with level
    mock_file = MagicMock(level=logging.NOTSET)  # Mock handler with level
    mock_stream = MagicMock()  # Mock for the file handler's stream
    
    with patch("logging.getLogger", return_value=mock_logger):
        with patch("logging.Formatter", return_value=mock_formatter):
            with patch("logging.StreamHandler", return_value=mock_console):
                with patch("logging.handlers.RotatingFileHandler", return_value=mock_file) as mock_file_handler:
                    with patch("pathlib.Path.home", return_value=MOCK_HOME):
                        with patch("pathlib.Path.__truediv__") as mock_truediv:
                            with patch("pathlib.Path.mkdir"):  # Mock mkdir directly
                                with patch("logging.FileHandler._open", return_value=mock_stream):  # Mock the file stream
                                    mock_truediv.side_effect = [MOCK_LOG_DIR, MOCK_LOG_FILE]
                                    
                                    setup_logging(log_level=logging.INFO)
                                    
                                    mock_file_handler.assert_called_once_with(
                                        MOCK_LOG_FILE,
                                        maxBytes=5 * 1024 * 1024,  # 5 MB
                                        backupCount=3
                                    )
                                    mock_file.setLevel.assert_called_once_with(logging.DEBUG)  # Always DEBUG for file
                                    mock_file.setFormatter.assert_called_once_with(mock_formatter)
                                    mock_logger.addHandler.assert_any_call(mock_file)

def test_setup_logging_debug_level():
    """Test that DEBUG level is handled correctly."""
    mock_logger = MagicMock()
    mock_console = MagicMock(level=logging.NOTSET)  # Mock handler with level
    mock_file = MagicMock(level=logging.NOTSET)  # Mock handler with level
    mock_stream = MagicMock()  # Mock for the file handler's stream
    
    with patch("logging.getLogger", return_value=mock_logger):
        with patch("logging.StreamHandler", return_value=mock_console):
            with patch("logging.handlers.RotatingFileHandler", return_value=mock_file):
                with patch("pathlib.Path.home", return_value=MOCK_HOME):
                    with patch("pathlib.Path.__truediv__") as mock_truediv:
                        with patch("pathlib.Path.mkdir"):  # Mock mkdir directly
                            with patch("logging.FileHandler._open", return_value=mock_stream):  # Mock the file stream
                                mock_truediv.side_effect = [MOCK_LOG_DIR, MOCK_LOG_FILE]
                                
                                setup_logging(log_level=logging.DEBUG)
                                
                                mock_logger.setLevel.assert_called_once_with(logging.DEBUG)
                                mock_console.setLevel.assert_called_once_with(logging.DEBUG)
                                mock_file.setLevel.assert_called_once_with(logging.DEBUG)

def test_setup_logging_return_value():
    """Test that the correct log directory path is returned."""
    mock_console = MagicMock(level=logging.NOTSET)  # Mock handler with level
    mock_file = MagicMock(level=logging.NOTSET)  # Mock handler with level
    
    with patch("pathlib.Path.home", return_value=MOCK_HOME):
        with patch("pathlib.Path.__truediv__") as mock_truediv:
            with patch("pathlib.Path.mkdir"):  # Mock mkdir directly
                with patch("logging.StreamHandler", return_value=mock_console):
                    with patch("logging.handlers.RotatingFileHandler", return_value=mock_file):
                        with patch("logging.FileHandler._open"):  # Prevent file opening
                            mock_truediv.side_effect = [MOCK_LOG_DIR, MOCK_LOG_FILE]
                            
                            result = setup_logging()
                            
                            assert result == MOCK_LOG_DIR