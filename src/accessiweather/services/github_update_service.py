"""GitHub update service backward compatibility re-export."""

# This module exists to preserve the original import path used throughout the codebase.
# The implementation now lives in the update_service package.

from .update_service.github_update_service import GitHubUpdateService, UpdateInfo

__all__ = ["GitHubUpdateService", "UpdateInfo"]
