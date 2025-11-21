"""Integration tests for secure storage configuration."""

import json
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.config.config_manager import ConfigManager
from accessiweather.config.secure_storage import SERVICE_NAME


@pytest.fixture
def mock_keyring():
    """Mock the keyring module."""
    with patch("accessiweather.config.secure_storage.keyring") as mock:
        # Setup a dict to simulate keyring storage
        storage = {}

        def set_password(service, username, password):
            if service != SERVICE_NAME:
                return
            storage[username] = password

        def get_password(service, username):
            if service != SERVICE_NAME:
                return None
            return storage.get(username)

        def delete_password(service, username):
            if service != SERVICE_NAME:
                return
            if username in storage:
                del storage[username]

        mock.set_password.side_effect = set_password
        mock.get_password.side_effect = get_password
        mock.delete_password.side_effect = delete_password
        yield mock


@pytest.fixture
def mock_app(tmp_path):
    """Mock Toga app with temporary config path."""
    app = MagicMock()
    app.paths.config = tmp_path
    return app


def test_secure_storage_migration(mock_app, mock_keyring):
    """Test that legacy secrets in JSON are not migrated (users must re-add them)."""
    # Create a legacy config file with secrets
    config_dir = mock_app.paths.config
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "accessiweather.json"

    legacy_data = {
        "settings": {
            "visual_crossing_api_key": "secret_api_key",
            "github_app_id": "123456",
            "data_source": "visualcrossing",
            "startup_enabled": True,
        }
    }

    with open(config_file, "w") as f:
        json.dump(legacy_data, f)

    # Initialize ConfigManager (no migration happens)
    manager = ConfigManager(mock_app)
    manager.load_config()

    # Verify secrets are NOT migrated to keyring
    assert mock_keyring.set_password.call_count == 0

    # Verify keys are loaded from JSON as-is (no migration)
    config = manager.get_config()
    assert config.settings.visual_crossing_api_key == "secret_api_key"
    assert config.settings.github_app_id == "123456"

    # Verify JSON file is not modified (no removal of secrets)
    with open(config_file) as f:
        saved_data = json.load(f)

    saved_settings = saved_data["settings"]
    # Keys remain in JSON since we don't migrate
    assert saved_settings["visual_crossing_api_key"] == "secret_api_key"
    assert saved_settings["github_app_id"] == "123456"
    assert saved_settings["data_source"] == "visualcrossing"


def test_update_settings_saves_to_keyring(mock_app, mock_keyring):
    """Test that updating settings saves secrets to keyring."""
    manager = ConfigManager(mock_app)
    manager.load_config()

    # Update a secret setting
    manager.update_settings(visual_crossing_api_key="new_secret_key")

    # Verify it was saved to keyring
    mock_keyring.set_password.assert_called_with(
        SERVICE_NAME, "visual_crossing_api_key", "new_secret_key"
    )

    # Verify it is NOT in the JSON file
    config_file = mock_app.paths.config / "accessiweather.json"
    with open(config_file) as f:
        saved_data = json.load(f)

    assert "visual_crossing_api_key" not in saved_data.get("settings", {})


def test_github_config_saves_to_keyring(mock_app, mock_keyring):
    """Test that GitHub config operations save to keyring."""
    manager = ConfigManager(mock_app)
    manager.load_config()

    manager.set_github_app_config("123", "private_key_pem", "456")

    # Verify calls
    calls = mock_keyring.set_password.call_args_list
    # We expect calls for id, key, installation_id
    keys_set = {call.args[1] for call in calls}
    assert "github_app_id" in keys_set
    assert "github_app_private_key" in keys_set
    assert "github_app_installation_id" in keys_set

    # Verify values
    assert manager.get_config().settings.github_app_private_key == "private_key_pem"


def test_clear_secrets_removes_from_keyring(mock_app, mock_keyring):
    """Test that clearing secrets removes them from keyring."""
    manager = ConfigManager(mock_app)
    manager.load_config()

    # Set then clear
    manager.update_settings(visual_crossing_api_key="temp_key")
    manager.update_settings(visual_crossing_api_key="")

    # Should have called delete_password (or set_password with empty, which our SecureStorage logic handles)
    # In SecureStorage implementation, we call delete_password if password is empty.
    # mock_keyring.delete_password should be called.

    mock_keyring.delete_password.assert_called_with(SERVICE_NAME, "visual_crossing_api_key")
