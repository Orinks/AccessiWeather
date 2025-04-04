"""Test configuration and fixtures for AccessiWeather."""

import json
import os
import tempfile

import pytest

# Only skip wx import on Linux/Mac CI environments
should_skip_wx = os.environ.get("ACCESSIWEATHER_TESTING") == "1" and os.name != "nt"  # Not Windows

if not should_skip_wx:
    import wx


@pytest.fixture(scope="function")
def wx_app():
    """Create a wx App for testing."""
    if not should_skip_wx:
        app = wx.App()
        yield app
    else:
        yield None


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a temporary config file
        config_path = os.path.join(temp_dir, "config.json")
        config_data = {
            "locations": {"Test City": {"lat": 35.0, "lon": -80.0}},
            "current": "Test City",
            "settings": {"update_interval_minutes": 30},
            "api_settings": {"contact_info": "test@example.com"},
        }

        with open(config_path, "w") as f:
            json.dump(config_data, f)

        yield config_path
