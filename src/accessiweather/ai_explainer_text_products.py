"""NWS text-product explanation helpers for AI explainers."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from datetime import datetime

from .ai_explainer_models import (
    EmptyResponseError,
    ExplanationResult,
    ExplanationStyle,
    InvalidAPIKeyError,
    InvalidModelError,
    NetworkError,
    RateLimitError,
    RequestTimeoutError,
    TextProductType,
)

logger = logging.getLogger(__name__)


class AIExplainerTextProductMixin:
    """Plain-language explanation helpers for NWS text products."""

    # Product-wide style instructions appended to the user prompt. Shared
    # across all text products so customization lives in one place.
    _PRODUCT_STYLE_INSTRUCTIONS: dict[ExplanationStyle, str] = {
        ExplanationStyle.BRIEF: "Provide a 2-3 sentence summary of the key points.",
        ExplanationStyle.STANDARD: "Provide a clear 1-2 paragraph summary.",
        ExplanationStyle.DETAILED: (
            "Provide a comprehensive summary covering all major points "
            "from the discussion, organized by topic."
        ),
    }

    def _text_product_cache_key(
        self,
        product_type: str,
        location_name: str,
        product_text: str,
        style: ExplanationStyle,
    ) -> str:
        """
        Compute the cache key for explain_text_product results.

        Key shape: ``ai_text_product:<TYPE>:<location>:<sha256>:<style>``.
        Hashing the product text keeps the key bounded and deterministic for
        long NWS text products.
        """
        text_hash = hashlib.sha256(product_text.encode("utf-8")).hexdigest()
        return f"ai_text_product:{product_type}:{location_name}:{text_hash}:{style.value}"

    def _text_product_system_prompt(
        self,
        product_type: str,
        style: ExplanationStyle,
    ) -> str:
        """Return the system prompt for any text product."""
        del product_type
        return self.get_effective_system_prompt(style)

    def _text_product_user_intro(self, product_type: str, location_name: str) -> str:
        """Return the user-prompt lead-in for any text product."""
        product_label = product_type or "unknown type"
        return (
            "Please explain this National Weather Service text product "
            f"({product_label}) for {location_name} in plain language:"
        )

    def _build_text_product_user_prompt(
        self,
        product_text: str,
        product_type: str,
        location_name: str,
        style: ExplanationStyle,
    ) -> str:
        """Build the user prompt for any text product."""
        intro = self._text_product_user_intro(product_type, location_name)
        style_instruction = self._PRODUCT_STYLE_INSTRUCTIONS.get(
            style, self._PRODUCT_STYLE_INSTRUCTIONS[ExplanationStyle.DETAILED]
        )
        user_prompt = f"{intro}\n\n{product_text}\n\n{style_instruction}"

        if self.custom_instructions and self.custom_instructions.strip():
            user_prompt += f"\n\nAdditional Instructions: {self.custom_instructions}"

        return user_prompt

    async def explain_text_product(
        self,
        product_text: str,
        product_type: TextProductType,
        location_name: str,
        *,
        style: ExplanationStyle = ExplanationStyle.DETAILED,
        preserve_markdown: bool = False,
        status_callback: Callable[[str], None] | None = None,
    ) -> ExplanationResult:
        """
        Generate a plain-language explanation of an NWS text product.

        Supports any NWS/IEM text product ID. System prompts are selected the
        same way for every product: user custom prompt first, product default
        when available, then the app default AI explanation prompt. A
        per-product result cache (300 s TTL) avoids re-invoking the LLM for
        identical inputs. LLM errors propagate and are not cached — a retry
        will re-hit the model.

        Args:
            product_text: Raw product text as issued by NWS.
            product_type: NWS/IEM text product ID, such as ``"AFD"`` or ``"CLI"``.
            location_name: Human-readable location the product covers.
            style: Explanation style (brief, standard, detailed).
            preserve_markdown: Keep markdown in the response when True.
            status_callback: Optional callback for user-facing generation progress.

        Returns:
            :class:`ExplanationResult`. ``cached=True`` if served from the
            per-product cache.

        """
        import asyncio

        # Cache lookup (custom prompts + instructions are applied per-instance
        # and already reflected in the request; keying off product_type /
        # location / text / style is sufficient for a single explainer).
        cache_key = self._text_product_cache_key(product_type, location_name, product_text, style)
        if self.cache is not None:
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for text product explanation: {cache_key}")
                return ExplanationResult(
                    text=cached["text"],
                    model_used=cached["model_used"],
                    token_count=cached["token_count"],
                    estimated_cost=cached["estimated_cost"],
                    cached=True,
                    timestamp=datetime.fromisoformat(cached["timestamp"]),
                    requested_model=cached.get("requested_model"),
                    model_attempts=tuple(cached.get("model_attempts", ())),
                    model_selection_reason=cached.get("model_selection_reason"),
                )

        system_prompt = self._text_product_system_prompt(product_type, style)
        user_prompt = self._build_text_product_user_prompt(
            product_text, product_type, location_name, style
        )

        # Build list of models to try: primary first, then fallbacks
        primary_model = self.get_effective_model()
        models_to_try = self._build_model_attempts(primary_model)

        response = None
        last_error = None
        attempted_models: list[str] = []
        for attempt_index, model in enumerate(models_to_try):
            attempted_models.append(model)
            self._notify_generation_status(
                status_callback,
                self._describe_model_attempt(model, primary_model, attempt_index),
            )
            try:
                model_override = model if model != primary_model else None
                response = await asyncio.to_thread(
                    self._call_openrouter, system_prompt, user_prompt, model_override
                )

                content = response["content"]
                if content and len(content.strip()) >= 20:
                    logger.info(f"Got valid {product_type} response from model: {model}")
                    break

                logger.warning(
                    f"Model {model} returned insufficient {product_type} response "
                    f"(len={len(content) if content else 0}), trying fallback..."
                )
                last_error = EmptyResponseError("empty or too-short response")
                self._notify_generation_status(
                    status_callback,
                    f"{model} returned an empty response; trying another available model.",
                )
                response = None

            except Exception as e:
                last_error = e
                logger.warning(f"Model {model} failed for {product_type}: {e}, trying fallback...")
                if attempt_index + 1 < len(models_to_try):
                    reason = self._describe_generation_error(e)
                    self._notify_generation_status(
                        status_callback,
                        f"{model} could not generate a summary because of {reason}; "
                        "trying another available model.",
                    )
                continue

        if response is None:
            if last_error:
                logger.error(
                    f"All models failed for {product_type}. Last error: {last_error}",
                    exc_info=True,
                )
                error_message = str(last_error).lower()

                if "api key" in error_message or "api_key" in error_message:
                    raise InvalidAPIKeyError(
                        "OpenRouter API key is required.\n\n"
                        "Please add your API key in Settings → AI Explanations.\n"
                        "Get a free key at: openrouter.ai/keys"
                    ) from last_error

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

                if "timed out" in error_message or "timeout" in error_message:
                    raise RequestTimeoutError(
                        "Request timed out.\n\n"
                        "The AI service is taking too long to respond.\n"
                        "This usually means the servers are busy. Please try again."
                    ) from last_error

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

                # Re-raise the original error
                raise last_error

            raise EmptyResponseError(
                "All AI models returned empty responses.\n\n"
                "This can happen when models are overloaded.\n"
                "Please try again in a few minutes."
            )

        # Success: format + build result
        raw_content = response["content"]
        text = self._format_response(raw_content, preserve_markdown)
        token_count = response["total_tokens"]
        model_used = response["model"]
        model_selection_reason = self._build_model_selection_reason(
            primary_model,
            model_used,
            attempted_models,
            last_error,
        )
        estimated_cost = self._estimate_cost(model_used, token_count)
        self._session_token_count += token_count

        result = ExplanationResult(
            text=text,
            model_used=model_used,
            token_count=token_count,
            estimated_cost=estimated_cost,
            cached=False,
            timestamp=datetime.now(),
            requested_model=primary_model,
            model_attempts=tuple(attempted_models),
            model_selection_reason=model_selection_reason,
        )

        # Cache only successful results — failures must not be memoized.
        if self.cache is not None:
            cache_data = {
                "text": result.text,
                "model_used": result.model_used,
                "token_count": result.token_count,
                "estimated_cost": result.estimated_cost,
                "timestamp": result.timestamp.isoformat(),
                "requested_model": result.requested_model,
                "model_attempts": list(result.model_attempts),
                "model_selection_reason": result.model_selection_reason,
            }
            self.cache.set(cache_key, cache_data, ttl=300)
            logger.debug(f"Cached text product explanation: {cache_key}")

        return result

    async def explain_afd(
        self,
        afd_text: str,
        location_name: str,
        style: ExplanationStyle = ExplanationStyle.DETAILED,
        preserve_markdown: bool = False,
        status_callback: Callable[[str], None] | None = None,
    ) -> ExplanationResult:
        """
        Generate a plain-language explanation of an Area Forecast Discussion.

        Thin wrapper around :meth:`explain_text_product` with
        ``product_type="AFD"``. Kept as a public method to preserve the
        existing call-site signature.
        """
        return await self.explain_text_product(
            afd_text,
            "AFD",
            location_name,
            style=style,
            preserve_markdown=preserve_markdown,
            status_callback=status_callback,
        )
