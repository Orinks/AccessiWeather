"""Synchronization helpers for UpdateSettings and AppSettings."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...config.config_manager import ConfigManager
    from .github_update_service import GitHubUpdateService

logger = logging.getLogger(__name__)


def sync_update_channel_to_service(
    config_manager: ConfigManager | None,
    update_service: GitHubUpdateService | None,
) -> None:
    """
    Synchronize AppSettings.update_channel to UpdateSettings.channel.

    This ensures that when the user changes the update channel setting in the
    main settings, the UpdateSettings used by the update service reflects that
    change immediately. Also invalidates the release cache to ensure fresh data
    is fetched with the new channel.

    Args:
        config_manager: The application's ConfigManager (may be None)
        update_service: The GitHubUpdateService (may be None)

    """
    if not config_manager or not update_service:
        return

    try:
        config = config_manager.get_config()
        if config and config.settings:
            app_channel = getattr(config.settings, "update_channel", "stable")
            old_channel = update_service.settings.channel

            # Update the channel
            update_service.settings.channel = app_channel

            # If the channel changed, invalidate the cache
            if old_channel != app_channel:
                logger.info(
                    f"Update channel changed from '{old_channel}' to '{app_channel}', invalidating release cache"
                )
                # Clear the in-memory cache
                update_service.release_manager._cache = None
                # The disk cache will be automatically invalidated on next load because
                # the channel in the cached data won't match the new channel
            else:
                logger.debug(f"Update channel is already set to: {app_channel}")
    except Exception as exc:
        logger.warning(f"Failed to sync update channel: {exc}")
