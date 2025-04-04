"""Test configuration and fixtures for AccessiWeather."""

import json
import os
import tempfile

import pytest

# Only import wx if we're not in CI/headless mode
if os.environ.get("ACCESSIWEATHER_TESTING") != "1":
    import wx  # Make sure wx is imported


# We need a wx App for testing wx components
@pytest.fixture(scope="session")  # Use session scope for efficiency
def wx_app():
    """Create a wx App for testing (session-scoped)."""
    if os.environ.get("ACCESSIWEATHER_TESTING") != "1":
        app = wx.App()
        yield app
        # Optional cleanup if needed, though usually pytest handles it.
        # wx.CallLater(100, app.ExitMainLoop)
        # app.MainLoop() # MainLoop should not be called in tests
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
