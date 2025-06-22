"""Update service for AccessiWeather.

This module provides functionality to check for application updates
from GitHub releases and handle update notifications.

This module has been refactored for better maintainability. The actual
implementation is now in the update_service package.
"""

# Import from the new modular structure for backward compatibility
from .update_service import UpdateInfo, UpdateService

__all__ = ["UpdateService", "UpdateInfo"]
