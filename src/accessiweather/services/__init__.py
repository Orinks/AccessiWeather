"""Services package for the simple AccessiWeather Toga application.

This package contains service modules for update management, platform detection,
and other application services.
"""

from .platform_detector import PlatformDetector
from .update_service import BriefcaseUpdateService

__all__ = [
    "PlatformDetector",
    "BriefcaseUpdateService",
]
