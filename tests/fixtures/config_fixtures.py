"""Configuration-related test fixtures."""

import json
import os
import tempfile

import pytest

from accessiweather.utils.temperature_utils import TemperatureUnit


@pytest.fixture
def temp_config_dir():
    """Create a temporary configuration directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "location": {"name": "Test City", "lat": 40.7128, "lon": -74.0060},
        "settings": {
            "update_interval": 30,
            "temperature_unit": TemperatureUnit.FAHRENHEIT.value,
            "data_source": "auto",
            "minimize_to_tray": False,
            "show_nationwide_location": True,
            "alert_radius": 50,
            "precise_location_alerts": False,
        },
        "api_settings": {"contact_info": "test@example.com"},
    }


@pytest.fixture
def config_file(temp_config_dir, sample_config):
    """Create a configuration file in temp directory."""
    config_path = os.path.join(temp_config_dir, "config.json")
    os.makedirs(temp_config_dir, exist_ok=True)

    with open(config_path, "w") as f:
        json.dump(sample_config, f)

    return config_path
