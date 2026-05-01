"""
AI-powered weather explanation module using OpenRouter.

This module provides natural language explanations of weather conditions
using OpenRouter's unified API gateway for AI models.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .ai_explainer_models import (
    AIExplainerError,
    EmptyResponseError,
    ExplanationResult,
    ExplanationStyle,
    InsufficientCreditsError,
    InvalidAPIKeyError,
    InvalidModelError,
    NetworkError,
    RateLimitError,
    RequestTimeoutError,
    TextProductType,
    WeatherContext,
)
from .ai_explainer_openrouter import (
    DEFAULT_FREE_MODEL,
    DEFAULT_FREE_ROUTER,
    get_available_free_models,
)
from .ai_explainer_openrouter_client import AIExplainerOpenRouterMixin
from .ai_explainer_prompting import AIExplainerPromptMixin
from .ai_explainer_prompts import SYSTEM_PROMPTS as _SYSTEM_PROMPTS
from .ai_explainer_text_products import AIExplainerTextProductMixin
from .ai_explainer_validation import AIExplainerValidationMixin

if TYPE_CHECKING:
    from .cache import Cache

logger = logging.getLogger(__name__)

__all__ = [
    "AIExplainer",
    "AIExplainerError",
    "EmptyResponseError",
    "ExplanationResult",
    "ExplanationStyle",
    "InsufficientCreditsError",
    "InvalidAPIKeyError",
    "InvalidModelError",
    "NetworkError",
    "RateLimitError",
    "RequestTimeoutError",
    "TextProductType",
    "WeatherContext",
    "_SYSTEM_PROMPTS",
    "get_available_free_models",
    "has_valid_api_key",
]


class AIExplainer(
    AIExplainerPromptMixin,
    AIExplainerOpenRouterMixin,
    AIExplainerTextProductMixin,
    AIExplainerValidationMixin,
):
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
        self.custom_system_prompt = self._sanitize_prompt(custom_system_prompt)
        self.custom_instructions = self._sanitize_prompt(custom_instructions)
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

        # Build list of models to try: primary first, then fallbacks
        primary_model = self.get_effective_model()
        models_to_try = [primary_model]

        # Add default model as fallback if using a custom model
        # This provides auto-recovery when a user's configured model is removed
        if primary_model != DEFAULT_FREE_MODEL:
            models_to_try.append(DEFAULT_FREE_MODEL)

        # Add additional fallbacks for free models (dynamically fetched)
        if ":free" in primary_model or primary_model in (DEFAULT_FREE_MODEL, DEFAULT_FREE_ROUTER):
            fallback_models = get_available_free_models(exclude_model=primary_model)
            for fallback in fallback_models:
                if fallback not in models_to_try:
                    models_to_try.append(fallback)

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
                # Convert common errors to specific exceptions
                error_message = str(last_error).lower()

                # API key errors (check FIRST to avoid matching "connection" in suggestion text)
                if "api key" in error_message or "api_key" in error_message:
                    raise InvalidAPIKeyError(
                        "OpenRouter API key is required.\n\n"
                        "Please add your API key in Settings → AI Explanations.\n"
                        "Get a free key at: openrouter.ai/keys"
                    ) from last_error

                # Model not found
                if (
                    "404" in error_message
                    or "not found" in error_message
                    or "no endpoints found" in error_message
                    or "does not exist" in error_message
                ):
                    raise InvalidModelError(
                        f"The AI model '{primary_model}' was not found.\n\n"
                        "It may have been removed or renamed by OpenRouter.\n"
                        "Please go to Settings → AI Explanations and select a different model."
                    ) from last_error

                # Rate limiting
                if (
                    "429" in error_message
                    or "rate limit" in error_message
                    or "rate-limited" in error_message
                ):
                    raise RateLimitError(
                        "All AI models are currently rate-limited.\n\n"
                        "Free models share rate limits with all users.\n\n"
                        "Options:\n"
                        "• Wait a few minutes and try again\n"
                        "• Add credits to your OpenRouter account\n"
                        "• Switch to a paid model in Settings"
                    ) from last_error

                # Timeout errors - check before generic network errors
                if "timed out" in error_message or "timeout" in error_message:
                    raise RequestTimeoutError(
                        "Request timed out.\n\n"
                        "The AI service is taking too long to respond.\n"
                        "This usually means the servers are busy. Please try again."
                    ) from last_error

                # Network errors (check for specific codes/phrases, not just "connection")
                if (
                    "502" in error_message
                    or "503" in error_message
                    or "network error" in error_message
                    or "connection refused" in error_message
                    or "connection reset" in error_message
                ):
                    raise NetworkError(
                        "Network connection error while contacting AI service.\n\n"
                        "Please check your internet connection and try again."
                    ) from last_error

                # Re-raise the original error with context
                raise last_error

            # No error but empty responses from all models
            raise EmptyResponseError(
                "All AI models returned empty responses.\n\n"
                "This can happen when models are overloaded.\n"
                "Please try again in a few minutes."
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


def has_valid_api_key(api_key: str | None) -> bool:
    """
    Check if a valid API key is configured.

    Args:
        api_key: The API key to check

    Returns:
        True if API key exists and is not empty, False otherwise

    """
    return bool(api_key and api_key.strip())
