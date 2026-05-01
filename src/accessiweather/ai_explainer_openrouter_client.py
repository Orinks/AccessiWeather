"""OpenRouter client calls and cost estimation for AI explainers."""

from __future__ import annotations

import logging
from typing import Any

from .ai_explainer_models import (
    AIExplainerError,
    InsufficientCreditsError,
    InvalidAPIKeyError,
    InvalidModelError,
    NetworkError,
    RateLimitError,
    RequestTimeoutError,
)
from .ai_explainer_openrouter import (
    DEFAULT_FREE_MODEL,
    OPENROUTER_BASE_URL,
    get_available_free_models,
)

logger = logging.getLogger(__name__)


class AIExplainerOpenRouterMixin:
    """OpenRouter API integration helpers."""

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
                    timeout=30.0,  # 30 second timeout to prevent hanging
                )
            except ImportError as e:
                logger.error("OpenAI package not installed")
                raise AIExplainerError(
                    "AI explanation feature requires the openai package. "
                    "Please install it with: pip install openai"
                ) from e
        return self._client

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

            logger.info(
                f"OpenRouter request: model={model}, system_prompt_len={len(system_prompt)}, user_prompt_len={len(user_prompt)}"
            )

            # Build extra_body with fallback models for free tier
            # Only use fallbacks for default model, not user-configured models
            extra_body = {}
            if model == DEFAULT_FREE_MODEL and ":free" in model:
                # Use OpenRouter's native models parameter for automatic fallback
                fallback_models = get_available_free_models(exclude_model=model)
                if fallback_models:
                    extra_body["models"] = fallback_models
                    logger.debug(f"Using fallback models: {fallback_models}")

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=4000,  # Increased for models with thinking/reasoning features
                extra_headers={
                    "HTTP-Referer": "https://accessiweather.orinks.net",
                    "X-Title": "AccessiWeather",
                },
                extra_body=extra_body if extra_body else None,
            )

            # Log full response for debugging
            logger.debug(f"OpenRouter raw response: {response}")

            # Extract content - handle potential None values
            if not response.choices:
                logger.warning(
                    f"OpenRouter returned empty choices. Full response: model={response.model}, id={getattr(response, 'id', 'N/A')}, usage={response.usage}"
                )
                return {
                    "content": "",
                    "model": response.model or "unknown",
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                }

            content = response.choices[0].message.content
            finish_reason = getattr(response.choices[0], "finish_reason", "unknown")

            if content is None:
                logger.warning(
                    f"OpenRouter returned None content. finish_reason={finish_reason}, model={response.model}"
                )
                content = ""
            elif len(content.strip()) < 20:
                logger.warning(
                    f"OpenRouter returned short content ({len(content)} chars). finish_reason={finish_reason}, content={content[:100]!r}"
                )

            logger.info(
                f"OpenRouter response: model={response.model}, content_len={len(content)}, finish_reason={finish_reason}"
            )

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
            # Note: Check API key errors FIRST to avoid false matches on "connection" in suggestion text

            # Missing API key (check first - most common user error)
            if "api key required" in error_message or "api key" in error_message:
                raise InvalidAPIKeyError(
                    "OpenRouter API key is required.\n\n"
                    "Please add your API key in Settings → AI Explanations.\n"
                    "Get a free key at: openrouter.ai/keys"
                ) from e

            # Invalid API key / authentication errors (401)
            if "invalid api key" in error_message or "authentication" in error_message:
                raise InvalidAPIKeyError(
                    "Your OpenRouter API key is invalid.\n\n"
                    "Please check Settings → AI Explanations and verify your API key.\n"
                    "Get a free key at: openrouter.ai/keys"
                ) from e

            if "401" in error_message or "unauthorized" in error_message:
                raise InvalidAPIKeyError(
                    "API key authentication failed.\n\n"
                    "Your API key may be expired or incorrectly entered.\n"
                    "Please check Settings → AI Explanations."
                ) from e

            # Insufficient credits
            if "insufficient" in error_message or "no credits" in error_message:
                raise InsufficientCreditsError(
                    "Your OpenRouter account has no funds.\n\n"
                    "Options:\n"
                    "• Add credits at openrouter.ai/credits\n"
                    "• Switch to a free model in Settings → AI Explanations"
                ) from e

            # Rate limiting (429) - check for status code AND common phrases
            if (
                "429" in error_message
                or "rate limit" in error_message
                or "too many requests" in error_message
                or "rate-limited" in error_message
            ):
                model_used = model_override or self.get_effective_model()
                is_free = ":free" in model_used
                raise RateLimitError(
                    "Rate limit exceeded.\n\n"
                    + (
                        "Free models share rate limits with all users and may be busy.\n\n"
                        "Options:\n"
                        "• Wait a few minutes and try again\n"
                        "• Add credits to get your own rate limit\n"
                        "• Switch to a paid model for faster access"
                        if is_free
                        else "Please wait a few minutes and try again."
                    )
                ) from e

            # Timeout errors - check before generic network errors
            if "timed out" in error_message or "timeout" in error_message:
                raise RequestTimeoutError(
                    "Request timed out.\n\n"
                    "The AI service is taking too long to respond.\n"
                    "This usually means the servers are busy. Please try again."
                ) from e

            # Network/connection errors - use specific phrases to avoid false matches
            if (
                "502" in error_message
                or "503" in error_message
                or "network error" in error_message
                or "connection refused" in error_message
                or "connection reset" in error_message
            ):
                raise NetworkError(
                    "Network connection error.\n\n"
                    "Could not reach the AI service. This is usually temporary.\n"
                    "Please check your internet connection and try again."
                ) from e

            # Model not found (404)
            if (
                "404" in error_message
                or "not found" in error_message
                or "no endpoints found" in error_message
                or "does not exist" in error_message
            ):
                model_used = model_override or self.get_effective_model()
                raise InvalidModelError(
                    f"The AI model '{model_used}' was not found.\n\n"
                    "It may have been removed or renamed by OpenRouter.\n"
                    "Please go to Settings → AI Explanations and select a different model."
                ) from e

            # Generic error - log full details and show user-friendly message
            logger.error(f"OpenRouter API error: {e}", exc_info=True)
            raise AIExplainerError(
                f"Unable to generate explanation.\n\n"
                f"Error: {original_error}\n\n"
                "If this persists, try:\n"
                "• Checking your internet connection\n"
                "• Selecting a different AI model in Settings\n"
                "• Trying again in a few minutes"
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
