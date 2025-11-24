"""
Update service package for AccessiWeather.

This package provides GitHub-based update functionality split into modular components.
"""

from .github_update_service import GitHubUpdateService, UpdateInfo
from .sync_settings import sync_update_channel_to_service

__all__ = ["GitHubUpdateService", "UpdateInfo", "sync_update_channel_to_service"]
