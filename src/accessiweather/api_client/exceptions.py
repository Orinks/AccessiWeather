"""
Exception classes for AccessiWeather API Client.

This module contains all exception classes and constants used by the API client
for error handling and location type identification.
"""

# Constants for alert location types
LOCATION_TYPE_COUNTY = "county"
LOCATION_TYPE_FORECAST = "forecast"
LOCATION_TYPE_FIRE = "fire"
LOCATION_TYPE_STATE = "state"


class ApiClientError(Exception):
    """Custom exception for API client errors."""


class NoaaApiError(ApiClientError):
    """Custom exception for NOAA API client errors with detailed information."""

    # Error type constants
    NETWORK_ERROR = "network"
    TIMEOUT_ERROR = "timeout"
    CONNECTION_ERROR = "connection"
    AUTHENTICATION_ERROR = "authentication"
    RATE_LIMIT_ERROR = "rate_limit"
    CLIENT_ERROR = "client"
    SERVER_ERROR = "server"
    PARSE_ERROR = "parse"
    UNKNOWN_ERROR = "unknown"
    HTTP_ERROR = "http"
    NOT_FOUND_ERROR = "not_found"
    API_ERROR = "api"

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_type: str | None = None,
        url: str | None = None,
    ):
        """
        Initialize the NoaaApiError.

        Args:
        ----
            message: Error message
            status_code: HTTP status code if applicable
            error_type: Type of error (use class constants)
            url: URL that caused the error

        """
        self.status_code = status_code
        self.error_type = error_type or self.UNKNOWN_ERROR
        self.url = url
        super().__init__(message)

    def __str__(self) -> str:
        """Return a string representation of the error."""
        parts = [super().__str__()]
        if self.status_code:
            parts.append(f"Status code: {self.status_code}")
        if self.error_type:
            parts.append(f"Error type: {self.error_type}")
        if self.url:
            parts.append(f"URL: {self.url}")
        return " | ".join(parts)
