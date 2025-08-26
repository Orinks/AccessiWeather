"""GitHub App backend service integration for AccessiWeather.

This module provides integration with the AccessiWeather GitHub App backend service
for sound pack submission functionality. All GitHub operations go through the backend service.
"""


def has_github_app_credentials() -> bool:
    """Check if GitHub App authentication is available via backend service.

    This always returns True since authentication is handled by the backend service.
    The actual availability check happens when attempting to use the service.

    Returns:
        True (backend service handles authentication)

    """
    return True
