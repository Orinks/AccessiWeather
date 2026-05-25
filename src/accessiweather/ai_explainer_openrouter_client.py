"""OpenRouter client calls and cost estimation for AI explainers."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
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
    DEFAULT_FREE_ROUTER,
    OPENROUTER_BASE_URL,
    get_available_free_models,
)

logger = logging.getLogger(__name__)


class AIExplainerOpenRouterMixin:
    """OpenRouter API integration helpers."""

    def _build_model_attempts(self, primary_model: str) -> list[str]:
        """Return the ordered model list used for a generation attempt."""
        models_to_try = [primary_model]

        if primary_model != DEFAULT_FREE_MODEL:
            models_to_try.append(DEFAULT_FREE_MODEL)

        if ":free" in primary_model or primary_model in (DEFAULT_FREE_MODEL, DEFAULT_FREE_ROUTER):
            fallback_models = get_available_free_models(exclude_model=primary_model)
            for fallback in fallback_models:
                if fallback not in models_to_try:
                    models_to_try.append(fallback)

        return models_to_try

    def _notify_generation_status(
        self,
        status_callback: Callable[[str], None] | None,
        message: str,
    ) -> None:
        """Send a generation status update without letting UI callback errors abort work."""
        if status_callback is None:
            return
        try:
            status_callback(message)
        except Exception:
            logger.debug("AI generation status callback failed", exc_info=True)

    def _describe_model_attempt(self, model: str, primary_model: str, attempt_index: int) -> str:
        """Return user-facing status text for a model attempt."""
        if attempt_index == 0:
            if model == DEFAULT_FREE_MODEL:
                return (
                    "Trying OpenRouter's free router. Free models share capacity and may "
                    "take a little while; backup free models will be tried if needed."
                )
            if ":free" in model:
                return (
                    f"Trying selected free model {model}. Free models share rate limits; "
                    "backup free models will be tried if this one is busy."
                )
            return f"Trying selected model {model}."

        if model == DEFAULT_FREE_MODEL:
            return (
                "Trying OpenRouter's free router as a backup because the selected model "
                "did not answer."
            )
        if ":free" in model:
            return f"Trying backup free model {model} because an earlier model did not answer."
        return f"Trying backup model {model} because {primary_model} did not answer."

    def _iter_error_chain(self, error: Exception):
        """Yield an exception and its chained structured causes."""
        seen: set[int] = set()
        current: BaseException | None = error
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            yield current
            current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)

    def _coerce_error_body(self, body: Any) -> dict[str, Any]:
        """Return a dict body from common SDK error payload shapes."""
        if isinstance(body, dict):
            return body
        if isinstance(body, str):
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    def _extract_api_error_details(self, error: Exception) -> dict[str, Any]:
        """Extract structured status/code/message fields from API exceptions."""
        details: dict[str, Any] = {}

        for exc in self._iter_error_chain(error):
            status_code = getattr(exc, "status_code", None)
            if status_code is not None and "status_code" not in details:
                details["status_code"] = status_code

            response = getattr(exc, "response", None)
            response_status = getattr(response, "status_code", None)
            if response_status is not None and "status_code" not in details:
                details["status_code"] = response_status

            for attr in ("code", "type", "message"):
                value = getattr(exc, attr, None)
                if value and attr not in details:
                    details[attr] = value

            body = self._coerce_error_body(getattr(exc, "body", None))
            if not body and response is not None:
                json_method = getattr(response, "json", None)
                if callable(json_method):
                    try:
                        body = self._coerce_error_body(json_method())
                    except Exception:
                        body = {}

            error_body = body.get("error") if isinstance(body.get("error"), dict) else body
            for key in ("code", "type", "message"):
                value = error_body.get(key)
                if value and key not in details:
                    details[key] = value

        return details

    def _api_error_text(self, details: dict[str, Any]) -> str:
        """Return searchable text from structured API error details."""
        return " ".join(str(value) for value in details.values() if value)

    def _api_status_code(self, details: dict[str, Any]) -> int | None:
        """Return an int status code when structured error details include one."""
        status_code = details.get("status_code")
        if isinstance(status_code, int):
            return status_code
        if isinstance(status_code, str) and status_code.isdigit():
            return int(status_code)
        return None

    def _describe_generation_error(self, error: Exception) -> str:
        """Return a short, non-technical reason for a failed model attempt."""
        details = self._extract_api_error_details(error)
        status_code = self._api_status_code(details)
        error_message = f"{self._api_error_text(details)} {error}".lower()
        if (
            status_code == 429
            or "429" in error_message
            or "rate limit" in error_message
            or "rate_limit" in error_message
            or "rate-limited" in error_message
            or "too many requests" in error_message
        ):
            return "rate limits"
        if "timed out" in error_message or "timeout" in error_message:
            return "a timeout"
        if (
            status_code == 404
            or "404" in error_message
            or "not found" in error_message
            or "does not exist" in error_message
        ):
            return "the model was unavailable"
        if "empty" in error_message or "short" in error_message or "insufficient" in error_message:
            return "an empty response"
        return "a service error"

    def _build_model_selection_reason(
        self,
        requested_model: str,
        model_used: str,
        attempted_models: list[str],
        last_error: Exception | None = None,
    ) -> str:
        """Return user-facing context for why a model answered."""
        if model_used == requested_model and len(attempted_models) <= 1:
            if requested_model == DEFAULT_FREE_MODEL:
                return "OpenRouter's free router selected the answering free model."
            return "Used the selected model."
        if requested_model == DEFAULT_FREE_MODEL and last_error is None:
            return f"OpenRouter's free router selected {model_used} from available free models."

        reason = self._describe_generation_error(last_error) if last_error else "an earlier model"
        if ":free" in requested_model:
            return (
                "Selected free model was limited by "
                f"{reason}, so AccessiWeather tried backup free models and "
                f"{model_used} answered."
            )
        if requested_model == DEFAULT_FREE_MODEL:
            return (
                "OpenRouter's free router or an earlier free model did not answer, "
                f"so {model_used} answered."
            )
        return (
            f"The selected model {requested_model} did not answer because of {reason}, "
            f"so {model_used} answered instead."
        )

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
            error_details = self._extract_api_error_details(e)
            status_code = self._api_status_code(error_details)
            error_message = f"{self._api_error_text(error_details)} {e}".lower()
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

            if (
                status_code in (401, 403)
                or "401" in error_message
                or "unauthorized" in error_message
            ):
                raise InvalidAPIKeyError(
                    "API key authentication failed.\n\n"
                    "Your API key may be expired or incorrectly entered.\n"
                    "Please check Settings → AI Explanations."
                ) from e

            # Insufficient credits
            if (
                status_code == 402
                or "insufficient" in error_message
                or "no credits" in error_message
            ):
                raise InsufficientCreditsError(
                    "Your OpenRouter account has no funds.\n\n"
                    "Options:\n"
                    "• Add credits at openrouter.ai/credits\n"
                    "• Switch to a free model in Settings → AI Explanations"
                ) from e

            # Rate limiting (429) - check for status code AND common phrases
            if (
                status_code == 429
                or "429" in error_message
                or "rate limit" in error_message
                or "rate_limit" in error_message
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
                status_code in (502, 503)
                or "502" in error_message
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
                status_code == 404
                or "404" in error_message
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
