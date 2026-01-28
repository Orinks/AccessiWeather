"""
AI-powered weather explanation module using OpenRouter.

This module provides natural language explanations of weather conditions
using OpenRouter's unified API gateway for AI models.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .cache import Cache

logger = logging.getLogger(__name__)

# OpenRouter API configuration
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Use current working free models from OpenRouter (updated Dec 2025)
DEFAULT_FREE_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
DEFAULT_PAID_MODEL = "openrouter/auto"
# Fallback free models to try if primary returns empty response (max 3 for OpenRouter)
FALLBACK_FREE_MODELS = [
    "google/gemma-3-27b-it:free",
    "qwen/qwen3-235b-a22b:free",
]


class AIExplainerError(Exception):
    """Base exception for AI explainer errors."""


class InsufficientCreditsError(AIExplainerError):
    """Raised when OpenRouter account has no funds."""


class RateLimitError(AIExplainerError):
    """Raised when rate limits are exceeded."""


class InvalidAPIKeyError(AIExplainerError):
    """Raised when API key is invalid or malformed."""


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


class AIExplainer:
    """Generates natural language weather explanations using OpenRouter."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_FREE_MODEL,
        cache: Cache | None = None,
        custom_system_prompt: str | None = None,
        custom_instructions: str | None = None,
    ):
        """
        Initialize with optional API key and model preference.

        Args:
            api_key: OpenRouter API key (optional for free models)
            model: Model identifier (default: openrouter/auto:free)
            cache: Optional cache instance for explanation caching
            custom_system_prompt: Custom system prompt to use instead of default
            custom_instructions: Custom instructions to append to user prompts

        """
        self.api_key = api_key
        self.model = model
        self.cache = cache
        self.custom_system_prompt = custom_system_prompt
        self.custom_instructions = custom_instructions
        self._session_token_count = 0
        self._client = None

    def get_effective_model(self) -> str:
        """
        Get the effective model based on API key and preference.

        Returns:
            Model identifier to use for API calls

        """
        # Without API key, always use free model
        if not self.api_key:
            return DEFAULT_FREE_MODEL

        # With API key, use configured preference (fall back to default if None)
        return self.model if self.model else DEFAULT_FREE_MODEL

    def _get_client(self):
        """Get or create OpenAI client configured for OpenRouter."""
        if self._client is None:
            # OpenRouter requires an API key for ALL requests, including free models
            # The :free suffix only means no charges, not no authentication
            if not self.api_key:
                raise AIExplainerError(
                    "OpenRouter API key required. Get a free key at openrouter.ai/keys - "
                    "free models won't charge your account."
                )

            try:
                from openai import OpenAI

                self._client = OpenAI(
                    base_url=OPENROUTER_BASE_URL,
                    api_key=self.api_key,
                )
            except ImportError as e:
                logger.error("OpenAI package not installed")
                raise AIExplainerError(
                    "AI explanation feature requires the openai package. "
                    "Please install it with: pip install openai"
                ) from e
        return self._client

    def get_effective_system_prompt(self, style: ExplanationStyle) -> str:
        """
        Get the system prompt to use, preferring custom over default.

        Args:
            style: Explanation style for default prompt

        Returns:
            Custom system prompt if configured, otherwise default prompt

        """
        if self.custom_system_prompt:
            return self.custom_system_prompt
        return self._build_default_system_prompt(style)

    def _build_default_system_prompt(self, style: ExplanationStyle) -> str:
        """Build the default system prompt based on explanation style."""
        base_prompt = self.get_default_system_prompt()

        style_instructions = {
            ExplanationStyle.BRIEF: "Keep your response to 1-2 sentences.",
            ExplanationStyle.STANDARD: "Provide a 3-4 sentence explanation.",
            ExplanationStyle.DETAILED: (
                "Provide a comprehensive paragraph with context about "
                "how the weather might affect daily activities."
            ),
        }

        return f"{base_prompt}\n\n{style_instructions.get(style, style_instructions[ExplanationStyle.STANDARD])}"

    @staticmethod
    def get_default_system_prompt() -> str:
        """
        Return the default system prompt text for display in UI.

        Returns:
            The default system prompt string

        """
        return (
            "You are a helpful weather assistant that explains weather conditions "
            "in plain, accessible language. Your explanations should be easy to "
            "understand for screen reader users and people who prefer audio descriptions. "
            "Avoid using visual-only descriptions. Focus on how the weather will feel "
            "and what activities it's suitable for.\n\n"
            "IMPORTANT: Do NOT repeat the location name, date, time, or timezone in your response. "
            "The user already sees this information. Jump straight into describing the weather "
            "conditions and what to expect.\n\n"
            "IMPORTANT: Respond in plain text only. Do NOT use markdown formatting such as "
            "bold (**text**), italic (*text*), headers (#), bullet points, or any other "
            "markdown syntax. Use simple paragraph text."
        )

    def get_prompt_preview(
        self,
        style: ExplanationStyle = ExplanationStyle.STANDARD,
    ) -> dict[str, str]:
        """
        Generate a preview of the prompts that will be sent to the AI.

        Args:
            style: Explanation style to use for the preview

        Returns:
            Dict with 'system_prompt' and 'user_prompt' keys

        """
        sample_weather = {
            "temperature": 72,
            "temperature_unit": "F",
            "conditions": "Partly Cloudy",
            "humidity": 65,
            "wind_speed": 8,
            "wind_direction": "NW",
            "visibility": 10,
        }
        return {
            "system_prompt": self.get_effective_system_prompt(style),
            "user_prompt": self._build_prompt(sample_weather, "Sample Location", style),
        }

    def _build_prompt(
        self,
        weather_data: dict[str, Any],
        location_name: str,
        style: ExplanationStyle,
    ) -> str:
        """Construct prompt from weather data."""
        # Extract weather context from data
        context = WeatherContext(
            location=location_name,
            timestamp=datetime.now(),
            temperature=weather_data.get("temperature"),
            temperature_unit=weather_data.get("temperature_unit", "F"),
            conditions=weather_data.get("conditions"),
            humidity=weather_data.get("humidity"),
            wind_speed=weather_data.get("wind_speed"),
            wind_direction=weather_data.get("wind_direction"),
            visibility=weather_data.get("visibility"),
            pressure=weather_data.get("pressure"),
            alerts=weather_data.get("alerts", []),
            forecast_summary=weather_data.get("forecast_summary"),
            local_time=weather_data.get("local_time"),
            utc_time=weather_data.get("utc_time"),
            timezone=weather_data.get("timezone"),
            time_of_day=weather_data.get("time_of_day"),
        )

        prompt_parts = [
            "Please explain the following weather conditions:\n",
            context.to_prompt_text(),
        ]

        # Add forecast periods if available
        forecast_periods = weather_data.get("forecast_periods", [])
        if forecast_periods:
            prompt_parts.append("\n\nUpcoming Forecast:")
            for period in forecast_periods:
                period_text = f"\n- {period.get('name', 'Unknown')}: "
                period_text += (
                    f"{period.get('temperature', 'N/A')}°{period.get('temperature_unit', 'F')}"
                )
                if period.get("short_forecast"):
                    period_text += f", {period['short_forecast']}"
                if period.get("wind_speed"):
                    period_text += f" (Wind: {period['wind_speed']}"
                    if period.get("wind_direction"):
                        period_text += f" {period['wind_direction']}"
                    period_text += ")"
                prompt_parts.append(period_text)

        prompt_parts.append(
            "\n\nProvide a natural language explanation of the current conditions "
            "and what to expect over the coming days for someone planning their activities."
        )

        # Add custom instructions if configured
        if self.custom_instructions and self.custom_instructions.strip():
            prompt_parts.append(f"\n\nAdditional Instructions: {self.custom_instructions}")

        return "".join(prompt_parts)

    def _format_response(self, response_text: str, preserve_markdown: bool) -> str:
        """
        Format AI response based on HTML rendering setting.

        Args:
            response_text: Raw response from AI
            preserve_markdown: If True, keep markdown; if False, strip it

        Returns:
            Formatted response text

        """
        if preserve_markdown:
            return response_text

        # Strip markdown formatting for plain text output
        text = response_text

        # Remove bold/italic markers
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # **bold**
        text = re.sub(r"\*(.+?)\*", r"\1", text)  # *italic*
        text = re.sub(r"__(.+?)__", r"\1", text)  # __bold__
        text = re.sub(r"_(.+?)_", r"\1", text)  # _italic_

        # Remove headers
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

        # Remove code blocks
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"`(.+?)`", r"\1", text)

        # Remove links but keep text
        text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)

        # Remove bullet points
        text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)

        # Clean up extra whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def _generate_cache_key(self, weather_data: dict[str, Any], location_name: str) -> str:
        """Generate a cache key for the explanation."""
        # Create a key based on significant weather values
        key_parts = [
            f"loc:{location_name}",
            f"temp:{weather_data.get('temperature')}",
            f"cond:{weather_data.get('conditions')}",
            f"model:{self.get_effective_model()}",
        ]
        return "ai_explanation:" + ":".join(key_parts)

    @property
    def session_token_count(self) -> int:
        """Get total tokens used in this session."""
        return self._session_token_count

    async def explain_weather(
        self,
        weather_data: dict[str, Any],
        location_name: str,
        style: ExplanationStyle = ExplanationStyle.STANDARD,
        preserve_markdown: bool = False,
    ) -> ExplanationResult:
        """
        Generate explanation for weather data.

        Args:
            weather_data: Current weather conditions dict
            location_name: Human-readable location name
            style: Explanation style (brief, standard, detailed)
            preserve_markdown: Whether to preserve markdown in output

        Returns:
            ExplanationResult with text, model used, and metadata

        Raises:
            AIExplainerError: Base exception for all AI-related errors
            InsufficientCreditsError: When account has no funds
            RateLimitError: When rate limits exceeded
            InvalidAPIKeyError: When API key is invalid

        """
        import asyncio

        # Check cache first
        cache_key = self._generate_cache_key(weather_data, location_name)
        if self.cache:
            cached_result = self.cache.get(cache_key)
            if cached_result:
                logger.debug(f"Cache hit for explanation: {cache_key}")
                # Return cached result with cached=True
                return ExplanationResult(
                    text=cached_result["text"],
                    model_used=cached_result["model_used"],
                    token_count=cached_result["token_count"],
                    estimated_cost=cached_result["estimated_cost"],
                    cached=True,
                    timestamp=datetime.fromisoformat(cached_result["timestamp"]),
                )

        # Build prompts
        system_prompt = self.get_effective_system_prompt(style)
        user_prompt = self._build_prompt(weather_data, location_name, style)

        # Build list of models to try: primary first, then fallbacks for free models
        primary_model = self.get_effective_model()
        models_to_try = [primary_model]
        # Only use fallbacks for default free model, not user-configured models
        # User may have chosen a specific model (e.g., uncensored) for a reason
        if primary_model == DEFAULT_FREE_MODEL and ":free" in primary_model:
            models_to_try.extend(FALLBACK_FREE_MODELS)

        # Try each model until we get a non-empty response
        response = None
        last_error = None
        for model in models_to_try:
            try:
                model_override = model if model != primary_model else None
                response = await asyncio.to_thread(
                    self._call_openrouter, system_prompt, user_prompt, model_override
                )

                # Check if we got actual content (minimum 20 chars for meaningful response)
                content = response["content"]
                if content and len(content.strip()) >= 20:
                    logger.info(f"Got valid response from model: {model}")
                    break

                # Empty or too short response - log and try next model
                logger.warning(
                    f"Model {model} returned insufficient response "
                    f"(len={len(content) if content else 0}), trying fallback..."
                )
                response = None

            except Exception as e:
                last_error = e
                logger.warning(f"Model {model} failed: {e}, trying fallback...")
                continue

        # If all models failed
        if response is None:
            if last_error:
                logger.error(f"All models failed. Last error: {last_error}", exc_info=True)
                raise last_error
            raise AIExplainerError(
                "All AI models returned empty responses. Please try again later."
            )

        # Process response
        raw_content = response["content"]
        text = self._format_response(raw_content, preserve_markdown)

        if not text:
            logger.warning(f"Empty text after formatting. Raw content length: {len(raw_content)}")

        token_count = response["total_tokens"]
        model_used = response["model"]

        # Calculate estimated cost
        estimated_cost = self._estimate_cost(model_used, token_count)

        # Update session token count
        self._session_token_count += token_count

        # Create result
        result = ExplanationResult(
            text=text,
            model_used=model_used,
            token_count=token_count,
            estimated_cost=estimated_cost,
            cached=False,
            timestamp=datetime.now(),
        )

        # Cache the result
        if self.cache:
            cache_data = {
                "text": result.text,
                "model_used": result.model_used,
                "token_count": result.token_count,
                "estimated_cost": result.estimated_cost,
                "timestamp": result.timestamp.isoformat(),
            }
            self.cache.set(cache_key, cache_data, ttl=300)  # 5 minute TTL
            logger.debug(f"Cached explanation: {cache_key}")

        return result

    async def explain_afd(
        self,
        afd_text: str,
        location_name: str,
        style: ExplanationStyle = ExplanationStyle.DETAILED,
        preserve_markdown: bool = False,
    ) -> ExplanationResult:
        """
        Generate plain language explanation of an Area Forecast Discussion.

        Args:
            afd_text: The raw AFD text from NWS
            location_name: Human-readable location name
            style: Explanation style (brief, standard, detailed)
            preserve_markdown: Whether to preserve markdown in output (default: False)

        Returns:
            ExplanationResult with text, model used, and metadata

        """
        import asyncio

        # Build AFD-specific prompts - use custom system prompt if configured
        if self.custom_system_prompt:
            system_prompt = self.custom_system_prompt
        else:
            system_prompt = (
                "You are a helpful weather assistant that explains National Weather Service "
                "Area Forecast Discussions (AFDs) in plain, accessible language. AFDs contain "
                "technical meteorological terminology that most people don't understand. "
                "Your job is to translate this into clear, everyday language that anyone can "
                "understand. Focus on:\n"
                "- What weather to expect and when\n"
                "- Any significant weather events or changes\n"
                "- How confident forecasters are in their predictions\n"
                "- What this means for daily activities\n\n"
                "Avoid using technical jargon. If you must use a technical term, explain it.\n\n"
                "IMPORTANT: Do NOT start with a preamble like 'Here is a summary...' or "
                "'This forecast discussion explains...'. Do NOT repeat the location name. "
                "Jump straight into explaining the weather. The user already knows what they asked for.\n\n"
                "IMPORTANT: Respond in plain text only. Do NOT use markdown formatting such as "
                "bold (**text**), italic (*text*), headers (#), bullet points, or any other "
                "markdown syntax. Use simple paragraph text that can be read directly."
            )

        style_instructions = {
            ExplanationStyle.BRIEF: "Provide a 2-3 sentence summary of the key points.",
            ExplanationStyle.STANDARD: "Provide a clear 1-2 paragraph summary.",
            ExplanationStyle.DETAILED: (
                "Provide a comprehensive summary covering all major points "
                "from the discussion, organized by topic."
            ),
        }

        user_prompt = (
            f"Please explain this Area Forecast Discussion for {location_name} "
            f"in plain language:\n\n{afd_text}\n\n"
            f"{style_instructions.get(style, style_instructions[ExplanationStyle.DETAILED])}"
        )

        # Add custom instructions if configured
        if self.custom_instructions and self.custom_instructions.strip():
            user_prompt += f"\n\nAdditional Instructions: {self.custom_instructions}"

        # Build list of models to try
        primary_model = self.get_effective_model()
        models_to_try = [primary_model]
        # Only use fallbacks for default free model, not user-configured models
        # User may have chosen a specific model (e.g., uncensored) for a reason
        if primary_model == DEFAULT_FREE_MODEL and ":free" in primary_model:
            models_to_try.extend(FALLBACK_FREE_MODELS)

        # Try each model until we get a non-empty response
        response = None
        last_error = None
        for model in models_to_try:
            try:
                model_override = model if model != primary_model else None
                response = await asyncio.to_thread(
                    self._call_openrouter, system_prompt, user_prompt, model_override
                )

                # Check if we got actual content (minimum 20 chars for meaningful response)
                content = response["content"]
                if content and len(content.strip()) >= 20:
                    logger.info(f"Got valid AFD response from model: {model}")
                    break

                logger.warning(
                    f"Model {model} returned insufficient AFD response "
                    f"(len={len(content) if content else 0}), trying fallback..."
                )
                response = None

            except Exception as e:
                last_error = e
                logger.warning(f"Model {model} failed for AFD: {e}, trying fallback...")
                continue

        if response is None:
            if last_error:
                logger.error(f"All models failed for AFD. Last error: {last_error}", exc_info=True)
                raise last_error
            raise AIExplainerError(
                "All AI models returned empty responses. Please try again later."
            )

        # Process response - strip markdown formatting for plain text display
        raw_content = response["content"]
        text = self._format_response(raw_content, preserve_markdown)
        token_count = response["total_tokens"]
        model_used = response["model"]
        estimated_cost = self._estimate_cost(model_used, token_count)
        self._session_token_count += token_count

        return ExplanationResult(
            text=text,
            model_used=model_used,
            token_count=token_count,
            estimated_cost=estimated_cost,
            cached=False,
            timestamp=datetime.now(),
        )

    def _call_openrouter(
        self, system_prompt: str, user_prompt: str, model_override: str | None = None
    ) -> dict[str, Any]:
        """
        Make synchronous call to OpenRouter API.

        Args:
            system_prompt: System message for the AI
            user_prompt: User message with weather data
            model_override: Optional model to use instead of configured model

        Returns:
            Dict with content, model, and token counts

        Raises:
            Various AIExplainerError subclasses based on error type

        """
        try:
            client = self._get_client()
            model = model_override or self.get_effective_model()

            # Build extra_body with fallback models for free tier
            extra_body = {}
            if ":free" in model:
                # Use OpenRouter's native models parameter for automatic fallback
                extra_body["models"] = FALLBACK_FREE_MODELS

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1000,  # Allow complete explanations without cutoff
                extra_headers={
                    "HTTP-Referer": "https://accessiweather.orinks.net",
                    "X-Title": "AccessiWeather",
                },
                extra_body=extra_body if extra_body else None,
            )

            # Extract content - handle potential None values
            if not response.choices:
                logger.warning("OpenRouter returned empty choices in response")
                return {
                    "content": "",
                    "model": response.model or "unknown",
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                }
            content = response.choices[0].message.content
            if content is None:
                logger.warning("OpenRouter returned None content in response")
                content = ""

            logger.info(f"OpenRouter response: model={response.model}, content_len={len(content)}")

            # Handle potential None usage
            usage = response.usage
            return {
                "content": content,
                "model": response.model or "unknown",
                "total_tokens": usage.total_tokens if usage else 0,
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
            }

        except Exception as e:
            error_message = str(e).lower()
            original_error = str(e)

            # Map specific errors to custom exceptions
            if "invalid api key" in error_message or "authentication" in error_message:
                raise InvalidAPIKeyError(
                    f"API key is invalid. Please check your settings.\n\nDetails: {original_error}"
                ) from e

            if "401" in error_message or "unauthorized" in error_message:
                raise InvalidAPIKeyError(
                    f"API key authentication failed.\n\nDetails: {original_error}"
                ) from e

            if "insufficient" in error_message or "no credits" in error_message:
                raise InsufficientCreditsError(
                    f"Your OpenRouter account has no funds. "
                    f"Add credits or switch to free models in settings.\n\nDetails: {original_error}"
                ) from e

            if "rate limit" in error_message or "too many requests" in error_message:
                raise RateLimitError(
                    f"Rate limit exceeded. Try again in a few minutes.\n\nDetails: {original_error}"
                ) from e

            # Generic error - include the actual error message
            logger.error(f"OpenRouter API error: {e}", exc_info=True)
            raise AIExplainerError(
                f"Unable to generate explanation.\n\nAPI Error: {original_error}"
            ) from e

    def _estimate_cost(self, model: str, token_count: int) -> float:
        """
        Estimate cost based on model and token count.

        Args:
            model: Model identifier
            token_count: Total tokens used

        Returns:
            Estimated cost in USD (0.0 for free models)

        """
        # Free models have no cost
        if ":free" in model:
            return 0.0

        # Rough estimates for common models (per 1M tokens)
        # These are approximations - actual costs vary
        cost_per_million = {
            "openrouter/auto": 0.5,  # Average estimate
            "gpt-4": 30.0,
            "gpt-3.5-turbo": 0.5,
            "claude-3-opus": 15.0,
            "claude-3-sonnet": 3.0,
            "claude-3-haiku": 0.25,
        }

        # Find matching cost or use default
        rate = 0.5  # Default rate
        for model_prefix, model_rate in cost_per_million.items():
            if model_prefix in model:
                rate = model_rate
                break

        return (token_count / 1_000_000) * rate

    async def validate_api_key(self, api_key: str) -> bool:
        """
        Test if API key is valid by making a minimal API call.

        Args:
            api_key: API key to validate

        Returns:
            True if valid, False otherwise

        """
        import asyncio

        # Temporarily set the API key
        original_key = self.api_key
        self.api_key = api_key
        self._client = None  # Reset client to use new key

        try:
            # Make a minimal API call
            await asyncio.to_thread(
                self._call_openrouter,
                "You are a test assistant.",
                "Say 'OK' if you can hear me.",
            )
            return True
        except InvalidAPIKeyError:
            return False
        except Exception as e:
            logger.warning(f"API key validation failed: {e}")
            return False
        finally:
            # Restore original key
            self.api_key = original_key
            self._client = None

    def select_best_data_source(self, sources: list[dict[str, Any]]) -> dict[str, Any] | None:
        """
        Select the most recent data source from multiple sources.

        Args:
            sources: List of weather data sources with optional timestamps

        Returns:
            The source with the most recent timestamp, or None if empty

        """
        if not sources:
            return None

        # Filter sources with valid timestamps
        sources_with_timestamps = [s for s in sources if s.get("timestamp") is not None]

        if not sources_with_timestamps:
            # If no timestamps, return first source
            return sources[0] if sources else None

        # Sort by timestamp descending and return most recent
        sorted_sources = sorted(
            sources_with_timestamps,
            key=lambda s: s["timestamp"],
            reverse=True,
        )

        return sorted_sources[0]


def has_valid_api_key(api_key: str | None) -> bool:
    """
    Check if a valid API key is configured.

    Args:
        api_key: The API key to check

    Returns:
        True if API key exists and is not empty, False otherwise

    """
    return bool(api_key and api_key.strip())
