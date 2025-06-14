"""Exception classes for NOAA API client."""

from typing import Optional


class ApiClientError(Exception):
    """Custom exception for API client errors."""

    pass


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

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_type: Optional[str] = None,
        url: Optional[str] = None,
    ):
        """Initialize the NoaaApiError.

        Args:
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
