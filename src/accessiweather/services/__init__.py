"""Services package for the simple AccessiWeather Toga application.

This package contains service modules for update management, platform detection,
and other application services.
"""

from .github_update_service import GitHubUpdateService
from .platform_detector import PlatformDetector

__all__ = [
    "PlatformDetector",
    "GitHubUpdateService",
]
