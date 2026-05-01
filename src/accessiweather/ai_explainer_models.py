"""Shared data types and exceptions for AI weather explanations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Literal

# Product-type literal used by explain_text_product. Keep in sync with
# ai_explainer_prompts.SYSTEM_PROMPTS keys.
TextProductType = Literal["AFD", "HWO", "SPS"]


class AIExplainerError(Exception):
    """Base exception for AI explainer errors."""


class InsufficientCreditsError(AIExplainerError):
    """Raised when OpenRouter account has no funds."""


class RateLimitError(AIExplainerError):
    """Raised when rate limits are exceeded."""


class InvalidAPIKeyError(AIExplainerError):
    """Raised when API key is invalid or malformed."""


class InvalidModelError(AIExplainerError):
    """Raised when the specified model ID does not exist."""


class NetworkError(AIExplainerError):
    """Raised when network connectivity issues occur."""


class RequestTimeoutError(AIExplainerError):
    """Raised when API request times out."""


class EmptyResponseError(AIExplainerError):
    """Raised when all models return empty or insufficient responses."""


class ExplanationStyle(Enum):
    """Available explanation styles."""

    BRIEF = "brief"  # 1-2 sentences
    STANDARD = "standard"  # 3-4 sentences (default)
    DETAILED = "detailed"  # Full paragraph with context


@dataclass
class ExplanationResult:
    """Result of an explanation generation."""

    text: str
    model_used: str
    token_count: int
    estimated_cost: float
    cached: bool
    timestamp: datetime


@dataclass
class WeatherContext:
    """Structured weather data for AI explanation."""

    location: str
    timestamp: datetime
    temperature: float | None
    temperature_unit: str
    conditions: str | None
    humidity: int | None
    wind_speed: float | None
    wind_direction: str | None
    visibility: float | None
    pressure: float | None
    alerts: list[dict[str, Any]]
    forecast_summary: str | None = None
    local_time: str | None = None
    utc_time: str | None = None
    timezone: str | None = None
    time_of_day: str | None = None

    def to_prompt_text(self) -> str:
        """Convert to natural language for AI prompt."""
        parts = [f"Location: {self.location}"]

        # Add time context so AI knows if it's morning/afternoon/evening/night
        if self.local_time and self.timezone:
            parts.append(f"Local Time: {self.local_time} ({self.timezone})")
        if self.utc_time:
            parts.append(f"UTC Time: {self.utc_time}")
        if self.time_of_day:
            parts.append(f"Time of Day: {self.time_of_day}")

        if self.temperature is not None:
            parts.append(f"Temperature: {self.temperature}°{self.temperature_unit}")

        if self.conditions:
            parts.append(f"Conditions: {self.conditions}")

        if self.humidity is not None:
            parts.append(f"Humidity: {self.humidity}%")

        if self.wind_speed is not None:
            wind_info = f"Wind: {self.wind_speed} mph"
            if self.wind_direction:
                wind_info += f" from {self.wind_direction}"
            parts.append(wind_info)

        if self.visibility is not None:
            parts.append(f"Visibility: {self.visibility} miles")

        if self.pressure is not None:
            parts.append(f"Pressure: {self.pressure} inHg")

        if self.alerts:
            alert_texts = []
            for alert in self.alerts:
                title = alert.get("title", "Weather Alert")
                severity = alert.get("severity", "Unknown")
                alert_texts.append(f"- {title} (Severity: {severity})")
            parts.append("Active Alerts:\n" + "\n".join(alert_texts))

        if self.forecast_summary:
            parts.append(f"Forecast: {self.forecast_summary}")

        return "\n".join(parts)
