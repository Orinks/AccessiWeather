"""Services package for the simple AccessiWeather Toga application.

This package contains service modules for update management, platform detection,
and other application services.
"""

from .github_app_client import GitHubAppClient
from .platform_detector import PlatformDetector
from .tuf_update_service import TUFUpdateService

__all__ = [
    "PlatformDetector",
    "TUFUpdateService",
    "GitHubAppClient",
]
