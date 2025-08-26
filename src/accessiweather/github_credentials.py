"""GitHub App credentials for AccessiWeather.

This module provides GitHub App credentials for sound pack submission functionality.
The credentials are loaded from environment variables during development and
embedded during the build process for distribution.

For security:
- Development: Uses environment variables (ACCESSIWEATHER_GITHUB_APP_*)
- Distribution: Credentials are embedded during build (not in source control)
- Fallback: Returns empty credentials if none available (graceful degradation)
"""

import os

# Build-time credentials (will be replaced during packaging)
# These are placeholders that get replaced by the build script
_BUILD_TIME_APP_ID = "BUILD_PLACEHOLDER_APP_ID"
_BUILD_TIME_INSTALLATION_ID = "BUILD_PLACEHOLDER_INSTALLATION_ID"
_BUILD_TIME_PRIVATE_KEY = "BUILD_PLACEHOLDER_PRIVATE_KEY"


def get_github_app_credentials() -> tuple[str, str, str]:
    """Get GitHub App credentials from environment or build-time embedding.

    Returns:
        Tuple of (app_id, private_key, installation_id)
        Returns empty strings if credentials are not available.

    """
    # First, try environment variables (for development)
    env_app_id = os.getenv("ACCESSIWEATHER_GITHUB_APP_ID", "").strip()
    env_private_key = os.getenv("ACCESSIWEATHER_GITHUB_APP_PRIVATE_KEY", "").strip()
    env_installation_id = os.getenv("ACCESSIWEATHER_GITHUB_APP_INSTALLATION_ID", "").strip()

    if env_app_id and env_private_key and env_installation_id:
        return env_app_id, env_private_key, env_installation_id

    # Second, try build-time embedded credentials (for distribution)
    # Check if credentials have been embedded (not placeholders)
    if not _BUILD_TIME_APP_ID.startswith("BUILD_PLACEHOLDER"):
        return _BUILD_TIME_APP_ID, _BUILD_TIME_PRIVATE_KEY, _BUILD_TIME_INSTALLATION_ID

    # Fallback: return empty credentials (graceful degradation)
    return "", "", ""


def has_github_app_credentials() -> bool:
    """Check if GitHub App credentials are available.

    Returns:
        True if all required credentials are available, False otherwise.

    """
    app_id, private_key, installation_id = get_github_app_credentials()
    return bool(app_id and private_key and installation_id)
