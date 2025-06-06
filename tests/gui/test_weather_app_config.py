"""Tests for WeatherApp configuration and settings handling."""

import json
import os
import tempfile
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.gui.weather_app import WeatherApp
from accessiweather.services.location_service import LocationService
from accessiweather.services.notification_service import NotificationService
from accessiweather.services.weather_service import WeatherService


@contextmanager
def mock_wx_components():
    """Context manager to mock all wx components needed for WeatherApp initialization."""
    with patch("accessiweather.gui.weather_app.UIManager"):
        with patch.object(WeatherApp, "CreateStatusBar"):
            with patch.object(WeatherApp, "SetStatusText"):
                with patch("wx.Timer"):
                    with patch.object(WeatherApp, "Bind"):
                        with patch.object(WeatherApp, "SetName"):
                            with patch.object(WeatherApp, "GetAccessible", return_value=None):
                                # Mock wx.App.Get() to return a mock app instance
                                mock_app = MagicMock()
                                with patch("wx.App.Get", return_value=mock_app):
                                    # Mock the entire TaskBarIcon class and its methods
                                    with patch(
                                        "accessiweather.gui.system_tray.TaskBarIcon"
                                    ) as mock_taskbar:
                                        # Configure the mock to have the methods we need
                                        mock_instance = MagicMock()
                                        mock_instance.cleanup = MagicMock()
                                        mock_taskbar.return_value = mock_instance
                                        mock_taskbar.cleanup_existing_instance = MagicMock()
                                        yield


@pytest.fixture
def mock_services():
    """Create mock services for WeatherApp."""
    weather_service = MagicMock(spec=WeatherService)
    location_service = MagicMock(spec=LocationService)
    notification_service = MagicMock(spec=NotificationService)

    # Configure the notification service mock to have a notifier attribute
    notification_service.notifier = MagicMock()

    return {
        "weather_service": weather_service,
        "location_service": location_service,
        "notification_service": notification_service,
    }


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir

    # Cleanup
    import shutil

    try:
        shutil.rmtree(temp_dir)
    except OSError:
        pass


@pytest.fixture
def sample_config():
    """Create a sample configuration."""
    return {
        "settings": {
            "temperature_unit": "celsius",
            "update_interval_minutes": 15,
            "minimize_to_tray": True,
            "data_source": "auto",
            "alert_radius": 25,
            "precise_location_alerts": True,
        },
        "api_settings": {"api_contact": "user@example.com"},
        "api_keys": {"weatherapi": "test_key_123"},
        "locations": [
            {"name": "New York", "lat": 40.7128, "lon": -74.0060},
            {"name": "Los Angeles", "lat": 34.0522, "lon": -118.2437},
        ],
    }


@pytest.mark.gui
@pytest.mark.unit
class TestWeatherAppConfig:
    """Test WeatherApp configuration handling."""

    @patch("wx.Frame.__init__", return_value=None)
    @patch("accessiweather.gui.weather_app.WeatherApp._create_menu_bar")
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateLocationDropdown")
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateWeatherData")
    @patch("accessiweather.gui.weather_app.WeatherApp._check_api_contact_configured")
    def test_load_config_from_file(
        self,
        mock_check_api,
        mock_update_weather,
        mock_update_dropdown,
        mock_create_menu,
        mock_frame_init,
        mock_services,
        temp_config_dir,
        sample_config,
    ):
        """Test loading configuration from file."""
        # Create config file
        config_path = os.path.join(temp_config_dir, "config.json")
        with open(config_path, "w") as f:
            json.dump(sample_config, f)

        with mock_wx_components():
            with patch("accessiweather.gui.weather_app.CONFIG_PATH", config_path):
                with patch("accessiweather.gui.weather_app.TaskBarIcon") as mock_taskbar:
                    # Configure the mock TaskBarIcon
                    mock_instance = MagicMock()
                    mock_instance.cleanup = MagicMock()
                    mock_taskbar.return_value = mock_instance
                    mock_taskbar.cleanup_existing_instance = MagicMock()

                    app = WeatherApp(
                        weather_service=mock_services["weather_service"],
                        location_service=mock_services["location_service"],
                        notification_service=mock_services["notification_service"],
                        config_path=config_path,
                    )

                # Verify config is loaded correctly
                assert app.config["settings"]["temperature_unit"] == "celsius"
                assert app.config["settings"]["update_interval_minutes"] == 15
                assert app.config["api_settings"]["api_contact"] == "user@example.com"

    @patch("wx.Frame.__init__", return_value=None)
    @patch("accessiweather.gui.weather_app.WeatherApp._create_menu_bar")
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateLocationDropdown")
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateWeatherData")
    @patch("accessiweather.gui.weather_app.WeatherApp._check_api_contact_configured")
    def test_save_config_to_file(
        self,
        mock_check_api,
        mock_update_weather,
        mock_update_dropdown,
        mock_create_menu,
        mock_frame_init,
        mock_services,
        temp_config_dir,
        sample_config,
    ):
        """Test saving configuration to file."""
        config_path = os.path.join(temp_config_dir, "config.json")

        with mock_wx_components():
            with patch("accessiweather.gui.weather_app.TaskBarIcon") as mock_taskbar:
                # Configure the mock TaskBarIcon
                mock_instance = MagicMock()
                mock_instance.cleanup = MagicMock()
                mock_taskbar.return_value = mock_instance

                app = WeatherApp(
                    weather_service=mock_services["weather_service"],
                    location_service=mock_services["location_service"],
                    notification_service=mock_services["notification_service"],
                    config=sample_config,
                    config_path=config_path,
                )

            # Save config
            app._save_config()

            # Verify file was created and contains correct data
            assert os.path.exists(config_path)
            with open(config_path, "r") as f:
                saved_config = json.load(f)

            assert saved_config["settings"]["temperature_unit"] == "celsius"
            assert saved_config["api_settings"]["api_contact"] == "user@example.com"

    @patch("wx.Frame.__init__", return_value=None)
    @patch("accessiweather.gui.weather_app.WeatherApp._create_menu_bar")
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateLocationDropdown")
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateWeatherData")
    @patch("accessiweather.gui.weather_app.WeatherApp._check_api_contact_configured")
    def test_config_defaults_when_file_missing(
        self,
        mock_check_api,
        mock_update_weather,
        mock_update_dropdown,
        mock_create_menu,
        mock_frame_init,
        mock_services,
        temp_config_dir,
    ):
        """Test that default configuration is used when config file is missing."""
        config_path = os.path.join(temp_config_dir, "nonexistent_config.json")

        with mock_wx_components():
            with patch("accessiweather.gui.weather_app.TaskBarIcon") as mock_taskbar:
                # Configure the mock TaskBarIcon
                mock_instance = MagicMock()
                mock_instance.cleanup = MagicMock()
                mock_taskbar.return_value = mock_instance

                app = WeatherApp(
                    weather_service=mock_services["weather_service"],
                    location_service=mock_services["location_service"],
                    notification_service=mock_services["notification_service"],
                    config_path=config_path,
                )

            # Verify default config is used
            assert "settings" in app.config
            assert "api_settings" in app.config
            assert "locations" in app.config

    @patch("wx.Frame.__init__", return_value=None)
    @patch("accessiweather.gui.weather_app.WeatherApp._create_menu_bar")
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateLocationDropdown")
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateWeatherData")
    @patch("accessiweather.gui.weather_app.WeatherApp._check_api_contact_configured")
    def test_config_validation_and_migration(
        self,
        mock_check_api,
        mock_update_weather,
        mock_update_dropdown,
        mock_create_menu,
        mock_frame_init,
        mock_services,
        temp_config_dir,
    ):
        """Test configuration validation and migration of old config formats."""
        # Create old format config
        old_config = {
            "temperature_unit": "fahrenheit",  # Old format without settings wrapper
            "locations": [],
        }

        config_path = os.path.join(temp_config_dir, "config.json")
        with open(config_path, "w") as f:
            json.dump(old_config, f)

        with mock_wx_components():
            with patch("accessiweather.gui.weather_app.TaskBarIcon") as mock_taskbar:
                # Configure the mock TaskBarIcon
                mock_instance = MagicMock()
                mock_instance.cleanup = MagicMock()
                mock_taskbar.return_value = mock_instance

                app = WeatherApp(
                    weather_service=mock_services["weather_service"],
                    location_service=mock_services["location_service"],
                    notification_service=mock_services["notification_service"],
                    config_path=config_path,
                )

            # Verify config is migrated to new format
            assert "settings" in app.config
            assert "api_settings" in app.config

    @patch("wx.Frame.__init__", return_value=None)
    @patch("accessiweather.gui.weather_app.WeatherApp._create_menu_bar")
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateLocationDropdown")
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateWeatherData")
    @patch("accessiweather.gui.weather_app.WeatherApp._check_api_contact_configured")
    def test_api_contact_check_configured(
        self,
        mock_check_api,
        mock_update_weather,
        mock_update_dropdown,
        mock_create_menu,
        mock_frame_init,
        mock_services,
        sample_config,
    ):
        """Test API contact configuration check."""
        with mock_wx_components():
            with patch("accessiweather.gui.weather_app.TaskBarIcon") as mock_taskbar:
                # Configure the mock TaskBarIcon
                mock_instance = MagicMock()
                mock_instance.cleanup = MagicMock()
                mock_taskbar.return_value = mock_instance

                app = WeatherApp(  # noqa: F841
                    weather_service=mock_services["weather_service"],
                    location_service=mock_services["location_service"],
                    notification_service=mock_services["notification_service"],
                    config=sample_config,
                )

            # Verify the check was called during initialization
            mock_check_api.assert_called_once()

    @patch("wx.Frame.__init__", return_value=None)
    @patch("accessiweather.gui.weather_app.WeatherApp._create_menu_bar")
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateLocationDropdown")
    @patch("accessiweather.gui.weather_app.WeatherApp.UpdateWeatherData")
    @patch("accessiweather.gui.weather_app.WeatherApp._check_api_contact_configured")
    def test_config_error_handling(
        self,
        mock_check_api,
        mock_update_weather,
        mock_update_dropdown,
        mock_create_menu,
        mock_frame_init,
        mock_services,
        temp_config_dir,
    ):
        """Test handling of corrupted config files."""
        # Create corrupted config file
        config_path = os.path.join(temp_config_dir, "config.json")
        with open(config_path, "w") as f:
            f.write("invalid json content {")

        with mock_wx_components():
            with patch("accessiweather.gui.weather_app.TaskBarIcon") as mock_taskbar:
                # Configure the mock TaskBarIcon
                mock_instance = MagicMock()
                mock_instance.cleanup = MagicMock()
                mock_taskbar.return_value = mock_instance

                # Should not raise exception, should use defaults
                app = WeatherApp(
                    weather_service=mock_services["weather_service"],
                    location_service=mock_services["location_service"],
                    notification_service=mock_services["notification_service"],
                    config_path=config_path,
                )

            # Verify default config is used when file is corrupted
            assert "settings" in app.config
            assert "api_settings" in app.config
