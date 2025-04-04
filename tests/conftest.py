# tests/conftest.py
import json
import os
import tempfile
from unittest import mock  # Added for mocking

import pytest
import wx  # Added for wx types

# We need a wx App for testing wx components
# The pytest-wx plugin provides this fixture automatically.
# Defining it here can cause conflicts.
# @pytest.fixture(scope="session")  # Use session scope for efficiency
# def wx_app():
#     """Create a wx App for testing (session-scoped)"""
#     app = wx.App()
#     yield app
#     # Optional cleanup if needed, though usually pytest handles it.
#     # wx.CallLater(100, app.ExitMainLoop)
#     # app.MainLoop()


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing"""
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


@pytest.fixture(autouse=True)
def mock_wx_accessibility(mocker):
    """
    Mock wx.Window.GetAccessible to prevent NotImplementedError in headless CI
    where accessibility services (like AT-SPI) might not be running.
    We patch it to return None, as the specific return value doesn't seem
    immediately necessary for the failing initialization path.
    """
    if hasattr(wx, "Window"):
        mocker.patch("wx.Window.GetAccessible", return_value=None, create=True)
