"""OpenWeatherMap API client exceptions.

This module defines custom exception classes for OpenWeatherMap API errors
with detailed error information and proper error type classification.
"""

from typing import Optional

from accessiweather.api_client import ApiClientError


class OpenWeatherMapError(ApiClientError):
    """Base exception for OpenWeatherMap API errors with detailed information."""

    # Error type constants
    NETWORK_ERROR = "network"
    TIMEOUT_ERROR = "timeout"
    CONNECTION_ERROR = "connection"
    AUTHENTICATION_ERROR = "authentication"
    RATE_LIMIT_ERROR = "rate_limit"
    CLIENT_ERROR = "client"
    SERVER_ERROR = "server"
    PARSE_ERROR = "parse"
    NOT_FOUND_ERROR = "not_found"
    VALIDATION_ERROR = "validation"
    UNKNOWN_ERROR = "unknown"

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_type: Optional[str] = None,
        url: Optional[str] = None,
        error_code: Optional[str] = None,
    ):
        """Initialize the OpenWeatherMapError.

        Args:
            message: Error message
            status_code: HTTP status code if applicable
            error_type: Type of error (use class constants)
            url: URL that caused the error
            error_code: OpenWeatherMap-specific error code
        """
        self.status_code = status_code
        self.error_type = error_type or self.UNKNOWN_ERROR
        self.url = url
        self.error_code = error_code
        super().__init__(message)

    def __str__(self) -> str:
        """Return a string representation of the error."""
        parts = [super().__str__()]
        if self.status_code:
            parts.append(f"Status code: {self.status_code}")
        if self.error_type:
            parts.append(f"Error type: {self.error_type}")
        if self.error_code:
            parts.append(f"Error code: {self.error_code}")
        if self.url:
            parts.append(f"URL: {self.url}")
        return " | ".join(parts)


class AuthenticationError(OpenWeatherMapError):
    """Exception for authentication-related errors (401 Unauthorized)."""

    def __init__(self, message: str = "Invalid API key", **kwargs):
        kwargs.setdefault("error_type", self.AUTHENTICATION_ERROR)
        kwargs.setdefault("status_code", 401)
        super().__init__(message, **kwargs)


class RateLimitError(OpenWeatherMapError):
    """Exception for rate limiting errors (429 Too Many Requests)."""

    def __init__(self, message: str = "Rate limit exceeded", **kwargs):
        kwargs.setdefault("error_type", self.RATE_LIMIT_ERROR)
        kwargs.setdefault("status_code", 429)
        super().__init__(message, **kwargs)


class NotFoundError(OpenWeatherMapError):
    """Exception for not found errors (404 Not Found)."""

    def __init__(self, message: str = "Resource not found", **kwargs):
        kwargs.setdefault("error_type", self.NOT_FOUND_ERROR)
        kwargs.setdefault("status_code", 404)
        super().__init__(message, **kwargs)


class ValidationError(OpenWeatherMapError):
    """Exception for validation errors (400 Bad Request)."""

    def __init__(self, message: str = "Invalid request parameters", **kwargs):
        kwargs.setdefault("error_type", self.VALIDATION_ERROR)
        kwargs.setdefault("status_code", 400)
        super().__init__(message, **kwargs)
