"""
Services package for the simple AccessiWeather Toga application.

This package contains service modules for update management, platform detection,
and other application services.

Imports are lazy-loaded to improve startup performance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Define what's available for import
__all__ = [
    "PlatformDetector",
    "GitHubUpdateService",
    "EnvironmentalDataClient",
    "StartupManager",
    "sync_update_channel_to_service",
    "NationalDiscussionService",
]

# Type hints for static type checkers (not evaluated at runtime)
if TYPE_CHECKING:
    from .environmental_client import EnvironmentalDataClient as EnvironmentalDataClient
    from .national_discussion_service import NationalDiscussionService as NationalDiscussionService
    from .platform_detector import PlatformDetector as PlatformDetector
    from .startup_utils import StartupManager as StartupManager
    from .update_service import (
        GitHubUpdateService as GitHubUpdateService,
        sync_update_channel_to_service as sync_update_channel_to_service,
    )


# Lazy import implementation - modules are only imported when accessed
def __getattr__(name: str) -> type:
    """Lazily import modules on first access to improve startup performance."""
    if name == "EnvironmentalDataClient":
        from .environmental_client import EnvironmentalDataClient

        return EnvironmentalDataClient
    if name == "PlatformDetector":
        from .platform_detector import PlatformDetector

        return PlatformDetector
    if name == "StartupManager":
        from .startup_utils import StartupManager

        return StartupManager
    if name == "GitHubUpdateService":
        from .update_service import GitHubUpdateService

        return GitHubUpdateService
    if name == "sync_update_channel_to_service":
        from .update_service import sync_update_channel_to_service

        return sync_update_channel_to_service
    if name == "NationalDiscussionService":
        from .national_discussion_service import NationalDiscussionService

        return NationalDiscussionService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
