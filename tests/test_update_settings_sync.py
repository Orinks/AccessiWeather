"""Tests for update settings synchronization between AppSettings and UpdateSettings."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from accessiweather.models import AppSettings
from accessiweather.services.update_service import sync_update_channel_to_service
from accessiweather.services.update_service.settings import UpdateSettings


@pytest.fixture
def mock_config_manager():
    """Create a mock ConfigManager."""
    manager = Mock()
    app_settings = AppSettings(update_channel="stable")
    app_config = Mock()
    app_config.settings = app_settings
    manager.get_config.return_value = app_config
    manager.settings = Mock()
    return manager


@pytest.fixture
def mock_update_service():
    """Create a mock GitHubUpdateService."""
    service = Mock()
    service.settings = UpdateSettings(channel="stable")
    service.release_manager = Mock()
    service.release_manager._cache = {"releases": []}
    return service


def test_sync_with_none_managers():
    """Test sync function handles None managers gracefully."""
    # Should not raise
    sync_update_channel_to_service(None, None)
    sync_update_channel_to_service(Mock(), None)
    sync_update_channel_to_service(None, Mock())


def test_sync_updates_channel_same(mock_config_manager, mock_update_service):
    """Test sync when channel is already correct."""
    # Both are "stable"
    assert mock_config_manager.get_config().settings.update_channel == "stable"
    assert mock_update_service.settings.channel == "stable"

    sync_update_channel_to_service(mock_config_manager, mock_update_service)

    # Channel should still be stable
    assert mock_update_service.settings.channel == "stable"
    # Cache should NOT be cleared when channel doesn't change
    assert mock_update_service.release_manager._cache == {"releases": []}


def test_sync_updates_channel_different(mock_config_manager, mock_update_service):
    """Test sync when channel needs to be updated from stable to dev."""
    # AppSettings has "dev", UpdateSettings has "stable"
    mock_config_manager.get_config().settings.update_channel = "dev"
    mock_update_service.settings.channel = "stable"

    sync_update_channel_to_service(mock_config_manager, mock_update_service)

    # Channel should be updated to dev
    assert mock_update_service.settings.channel == "dev"
    # Cache should be cleared when channel changes
    assert mock_update_service.release_manager._cache is None


def test_sync_nightly_to_dev(mock_config_manager, mock_update_service):
    """Test sync converts nightly channel to dev (via AppSettings)."""
    # Simulate user having "dev" in AppSettings (after migration from nightly)
    mock_config_manager.get_config().settings.update_channel = "dev"
    mock_update_service.settings.channel = "stable"

    sync_update_channel_to_service(mock_config_manager, mock_update_service)

    # Channel should be dev
    assert mock_update_service.settings.channel == "dev"
    # Cache cleared because channel changed
    assert mock_update_service.release_manager._cache is None


def test_sync_handles_missing_settings():
    """Test sync handles missing config or settings."""
    manager = Mock()
    manager.get_config.return_value = None
    service = Mock()
    service.settings = UpdateSettings()

    # Should not raise
    sync_update_channel_to_service(manager, service)


def test_sync_handles_missing_update_channel():
    """Test sync handles missing update_channel attribute."""
    manager = Mock()
    app_config = Mock()
    app_config.settings = Mock(spec=[])  # No update_channel attribute
    manager.get_config.return_value = app_config
    service = Mock()
    service.settings = UpdateSettings(channel="stable")

    # getattr with default should handle this
    sync_update_channel_to_service(manager, service)
    # Should default to "stable"
    assert service.settings.channel == "stable"


@pytest.mark.parametrize("channel", ["stable", "dev", "beta", "nightly"])
def test_sync_various_channels(mock_config_manager, mock_update_service, channel):
    """Test sync with various channel values."""
    mock_config_manager.get_config().settings.update_channel = channel
    mock_update_service.settings.channel = "stable"

    sync_update_channel_to_service(mock_config_manager, mock_update_service)

    # Channel should be updated (whether valid or not - sync doesn't validate)
    assert mock_update_service.settings.channel == channel

    if channel == "stable":
        # Cache should NOT be cleared when already on stable
        assert mock_update_service.release_manager._cache == {"releases": []}
    else:
        # Cache cleared because channel changed from stable
        assert mock_update_service.release_manager._cache is None
