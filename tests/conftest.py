# tests/conftest.py
import pytest
import os
import tempfile
import json
 
 
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
            "locations": {
                "Test City": {"lat": 35.0, "lon": -80.0}
            },
            "current": "Test City",
            "settings": {
                "update_interval_minutes": 30
            },
            "api_settings": {
                "contact_info": "test@example.com"
            }
        }

        with open(config_path, "w") as f:
            json.dump(config_data, f)

        yield config_path