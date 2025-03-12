"""Tests for the CLI module"""

import pytest
from unittest.mock import patch, MagicMock

from noaa_weather_app.cli import parse_args, main


class TestCli:
    """Test suite for CLI functionality"""
    
    def test_parse_args_defaults(self):
        """Test parsing arguments with defaults"""
        args = parse_args([])
        assert not args.debug
        assert args.config is None
    
    def test_parse_args_debug(self):
        """Test parsing debug argument"""
        args = parse_args(["-d"])
        assert args.debug
        assert args.config is None
        
        # Test long form
        args = parse_args(["--debug"])
        assert args.debug
    
    def test_parse_args_config(self):
        """Test parsing config argument"""
        args = parse_args(["-c", "/path/to/config"])
        assert not args.debug
        assert args.config == "/path/to/config"
        
        # Test long form
        args = parse_args(["--config", "/path/to/config"])
        assert args.config == "/path/to/config"
    
    @patch('noaa_weather_app.cli.app_main')
    def test_main_success(self, mock_app_main):
        """Test main function with successful execution"""
        with patch('noaa_weather_app.cli.parse_args') as mock_parse_args:
            # Set up mock args
            mock_args = MagicMock()
            mock_args.debug = True
            mock_args.config = "/test/config"
            mock_parse_args.return_value = mock_args
            
            # Call main
            result = main()
            
            # Check result
            assert result == 0
            mock_app_main.assert_called_once_with(config_dir="/test/config")
    
    @patch('noaa_weather_app.cli.app_main')
    def test_main_error(self, mock_app_main):
        """Test main function with error"""
        with patch('noaa_weather_app.cli.parse_args') as mock_parse_args:
            # Set up mock args
            mock_args = MagicMock()
            mock_args.debug = False
            mock_args.config = None
            mock_parse_args.return_value = mock_args
            
            # Set up app_main to raise an exception
            mock_app_main.side_effect = Exception("Test error")
            
            # Call main
            with patch('logging.error') as mock_logging:
                result = main()
                
                # Check result
                assert result == 1
                mock_logging.assert_called_once()
                assert "Test error" in mock_logging.call_args[0][0]
