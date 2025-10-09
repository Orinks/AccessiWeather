"""Services package for the simple AccessiWeather Toga application.

This package contains service modules for update management, platform detection,
and other application services.
"""

from .environmental_client import EnvironmentalDataClient
from .github_update_service import GitHubUpdateService
from .meteoalarm_client import MeteoAlarmClient
from .platform_detector import PlatformDetector
from .startup_utils import StartupManager

__all__ = [
    "PlatformDetector",
    "GitHubUpdateService",
    "EnvironmentalDataClient",
    "MeteoAlarmClient",
    "StartupManager",
]
