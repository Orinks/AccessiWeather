"""Tests for weather source selection fixes."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from accessiweather.models import AppConfig, Location
from accessiweather.simple_config import ConfigManager
from accessiweather.weather_client import WeatherClient


class MockApp:
    """Mock app for testing."""

    def __init__(self, config_dir: Path):
        """Initialize mock app with config directory."""
        self.paths = MagicMock()
        self.paths.config = config_dir


class TestSourceSelectionFixes:
    """Test the source selection fixes."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary config directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def mock_app(self, temp_config_dir):
        """Create a mock app with temporary config directory."""
        return MockApp(temp_config_dir)

    @pytest.fixture
    def config_manager(self, mock_app):
        """Create a config manager with temporary directory."""
        return ConfigManager(mock_app)

    @pytest.fixture
    def us_location(self):
        """Create a US test location."""
        return Location(name="Philadelphia, PA", latitude=39.9526, longitude=-75.1652)

    @pytest.fixture
    def intl_location(self):
        """Create an international test location."""
        return Location(name="London, UK", latitude=51.5074, longitude=-0.1278)

    def test_config_validation_invalid_data_source(self, config_manager, temp_config_dir):
        """Test that invalid data sources are corrected."""
        # Create config with invalid data source
        config_file = temp_config_dir / "accessiweather.json"
        invalid_config = {
            "settings": {
                "data_source": "invalid_source",
                "visual_crossing_api_key": "",
                "temperature_unit": "both",
                "update_interval_minutes": 10,
                "show_detailed_forecast": True,
                "enable_alerts": True,
                "minimize_to_tray": True,
                "auto_update_enabled": True,
                "update_channel": "stable",
                "update_check_interval_hours": 24,
                "debug_mode": False,
                "sound_enabled": True,
                "sound_pack": "default",
                "alert_notifications_enabled": True,
                "alert_notify_extreme": True,
                "alert_notify_severe": True,
                "alert_notify_moderate": True,
                "alert_notify_minor": False,
                "alert_notify_unknown": False,
                "alert_global_cooldown_minutes": 5,
                "alert_per_alert_cooldown_minutes": 60,
                "alert_escalation_cooldown_minutes": 15,
                "alert_max_notifications_per_hour": 10,
                "alert_ignored_categories": [],
            },
            "locations": [],
            "current_location": None,
        }

        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(invalid_config, f)

        # Load config - should auto-correct
        config = config_manager.load_config()

        # Verify correction
        assert config.settings.data_source == "auto"

    def test_config_validation_visualcrossing_without_key(self, config_manager, temp_config_dir):
        """Test that Visual Crossing without API key is corrected."""
        # Create config with Visual Crossing but no API key
        config_file = temp_config_dir / "accessiweather.json"
        invalid_config = {
            "settings": {
                "data_source": "visualcrossing",
                "visual_crossing_api_key": "",
                "temperature_unit": "both",
                "update_interval_minutes": 10,
                "show_detailed_forecast": True,
                "enable_alerts": True,
                "minimize_to_tray": True,
                "auto_update_enabled": True,
                "update_channel": "stable",
                "update_check_interval_hours": 24,
                "debug_mode": False,
                "sound_enabled": True,
                "sound_pack": "default",
                "alert_notifications_enabled": True,
                "alert_notify_extreme": True,
                "alert_notify_severe": True,
                "alert_notify_moderate": True,
                "alert_notify_minor": False,
                "alert_notify_unknown": False,
                "alert_global_cooldown_minutes": 5,
                "alert_per_alert_cooldown_minutes": 60,
                "alert_escalation_cooldown_minutes": 15,
                "alert_max_notifications_per_hour": 10,
                "alert_ignored_categories": [],
            },
            "locations": [],
            "current_location": None,
        }

        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(invalid_config, f)

        # Load config - should auto-correct
        config = config_manager.load_config()

        # Verify correction
        assert config.settings.data_source == "auto"

    def test_config_validation_clears_unused_api_key(self, config_manager, temp_config_dir):
        """Test that Visual Crossing API key is cleared when not using Visual Crossing."""
        # Create config with NWS but Visual Crossing API key
        config_file = temp_config_dir / "accessiweather.json"
        invalid_config = {
            "settings": {
                "data_source": "nws",
                "visual_crossing_api_key": "unused_key",
                "temperature_unit": "both",
                "update_interval_minutes": 10,
                "show_detailed_forecast": True,
                "enable_alerts": True,
                "minimize_to_tray": True,
                "auto_update_enabled": True,
                "update_channel": "stable",
                "update_check_interval_hours": 24,
                "debug_mode": False,
                "sound_enabled": True,
                "sound_pack": "default",
                "alert_notifications_enabled": True,
                "alert_notify_extreme": True,
                "alert_notify_severe": True,
                "alert_notify_moderate": True,
                "alert_notify_minor": False,
                "alert_notify_unknown": False,
                "alert_global_cooldown_minutes": 5,
                "alert_per_alert_cooldown_minutes": 60,
                "alert_escalation_cooldown_minutes": 15,
                "alert_max_notifications_per_hour": 10,
                "alert_ignored_categories": [],
            },
            "locations": [],
            "current_location": None,
        }

        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(invalid_config, f)

        # Load config - should auto-correct
        config = config_manager.load_config()

        # Verify correction
        assert config.settings.data_source == "nws"
        assert config.settings.visual_crossing_api_key == ""

    def test_weather_client_invalid_data_source(self, us_location):
        """Test weather client handles invalid data source."""
        client = WeatherClient(data_source="invalid_source")

        # Should fallback to auto behavior
        api_choice = client._determine_api_choice(us_location)
        assert api_choice == "nws"  # US location should use NWS

    def test_weather_client_visualcrossing_without_key(self, us_location):
        """Test weather client handles Visual Crossing without API key."""
        client = WeatherClient(data_source="visualcrossing", visual_crossing_api_key="")

        # Should fallback to auto behavior
        api_choice = client._determine_api_choice(us_location)
        assert api_choice == "nws"  # US location should use NWS

    def test_weather_client_auto_source_us_location(self, us_location):
        """Test auto source correctly selects NWS for US location."""
        client = WeatherClient(data_source="auto")
        api_choice = client._determine_api_choice(us_location)
        assert api_choice == "nws"

    def test_weather_client_auto_source_intl_location(self, intl_location):
        """Test auto source correctly selects Open-Meteo for international location."""
        client = WeatherClient(data_source="auto")
        api_choice = client._determine_api_choice(intl_location)
        assert api_choice == "openmeteo"

    def test_weather_client_explicit_nws(self, us_location, intl_location):
        """Test explicit NWS source works for both US and international locations."""
        client = WeatherClient(data_source="nws")

        assert client._determine_api_choice(us_location) == "nws"
        assert client._determine_api_choice(intl_location) == "nws"

    def test_weather_client_explicit_openmeteo(self, us_location, intl_location):
        """Test explicit Open-Meteo source works for both US and international locations."""
        client = WeatherClient(data_source="openmeteo")

        assert client._determine_api_choice(us_location) == "openmeteo"
        assert client._determine_api_choice(intl_location) == "openmeteo"

    def test_weather_client_visualcrossing_with_key(self, us_location):
        """Test Visual Crossing works when API key is provided."""
        client = WeatherClient(data_source="visualcrossing", visual_crossing_api_key="test_key")

        api_choice = client._determine_api_choice(us_location)
        assert api_choice == "visualcrossing"
        assert client.visual_crossing_client is not None

    def test_us_location_detection(self):
        """Test US location detection logic."""
        client = WeatherClient()

        # Test US locations
        assert client._is_us_location(Location("NYC", 40.7128, -74.0060)) is True
        assert client._is_us_location(Location("LA", 34.0522, -118.2437)) is True
        assert client._is_us_location(Location("Miami", 25.7617, -80.1918)) is True

        # Test international locations
        assert client._is_us_location(Location("London", 51.5074, -0.1278)) is False
        assert client._is_us_location(Location("Tokyo", 35.6762, 139.6503)) is False
        assert client._is_us_location(Location("Sydney", -33.8688, 151.2093)) is False

    def test_config_default_values(self):
        """Test that default configuration has correct values."""
        config = AppConfig.default()

        assert config.settings.data_source == "auto"
        assert config.settings.visual_crossing_api_key == ""
        assert len(config.locations) == 0
        assert config.current_location is None
