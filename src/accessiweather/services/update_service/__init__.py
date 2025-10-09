"""Update service package for AccessiWeather.

This package provides GitHub-based update functionality split into modular components.
"""

from .github_update_service import GitHubUpdateService, UpdateInfo

__all__ = ["GitHubUpdateService", "UpdateInfo"]
