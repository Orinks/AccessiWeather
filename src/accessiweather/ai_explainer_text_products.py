"""NWS text-product explanation helpers for AI explainers."""

from __future__ import annotations

import hashlib
import logging
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
from .ai_explainer_openrouter import (
    DEFAULT_FREE_MODEL,
    DEFAULT_FREE_ROUTER,
    get_available_free_models,
)
from .ai_explainer_prompts import SYSTEM_PROMPTS as _SYSTEM_PROMPTS

logger = logging.getLogger(__name__)


class AIExplainerTextProductMixin:
    """Plain-language explanation helpers for NWS text products."""

    # Product-type-specific phrasing for the user-message lead-in. The AFD
    # phrasing is preserved byte-for-byte from the historical explain_afd
    # implementation to keep downstream prompt templates stable.
    _PRODUCT_USER_INTRO: dict[str, str] = {
        "AFD": "Please explain this Area Forecast Discussion for {location} in plain language:",
        "HWO": "Please explain this Hazardous Weather Outlook for {location} in plain language:",
        "SPS": "Please explain this Special Weather Statement for {location} in plain language:",
    }

    # Product-wide style instructions appended to the user prompt. Shared
    # across AFD/HWO/SPS so customization lives in one place.
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
        long AFDs/HWOs/SPSs.
        """
        text_hash = hashlib.sha256(product_text.encode("utf-8")).hexdigest()
        return f"ai_text_product:{product_type}:{location_name}:{text_hash}:{style.value}"

    async def explain_text_product(
        self,
        product_text: str,
        product_type: TextProductType,
        location_name: str,
        *,
        style: ExplanationStyle = ExplanationStyle.DETAILED,
        preserve_markdown: bool = False,
    ) -> ExplanationResult:
        """
        Generate a plain-language explanation of an NWS text product.

        Supports AFD (Area Forecast Discussion), HWO (Hazardous Weather
        Outlook), and SPS (Special Weather Statement). The system prompt is
        selected per product type from :data:`_SYSTEM_PROMPTS`. A per-product
        result cache (300 s TTL) avoids re-invoking the LLM for identical
        inputs. LLM errors propagate and are not cached — a retry will
        re-hit the model.

        Args:
            product_text: Raw product text as issued by NWS.
            product_type: One of ``"AFD"``, ``"HWO"``, ``"SPS"``.
            location_name: Human-readable location the product covers.
            style: Explanation style (brief, standard, detailed).
            preserve_markdown: Keep markdown in the response when True.

        Returns:
            :class:`ExplanationResult`. ``cached=True`` if served from the
            per-product cache.

        """
        import asyncio

        if product_type not in _SYSTEM_PROMPTS:
            raise ValueError(
                f"Unknown product_type {product_type!r}; expected one of {sorted(_SYSTEM_PROMPTS)}"
            )

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
                )

        # System prompt: custom overrides the default (preserves existing
        # explain_afd semantics — replace, not append).
        system_prompt = self.custom_system_prompt or _SYSTEM_PROMPTS[product_type]

        # User prompt: product-type-aware lead-in + raw product + style hint.
        intro_template = self._PRODUCT_USER_INTRO[product_type]
        intro = intro_template.format(location=location_name)
        style_instruction = self._PRODUCT_STYLE_INSTRUCTIONS.get(
            style, self._PRODUCT_STYLE_INSTRUCTIONS[ExplanationStyle.DETAILED]
        )
        user_prompt = f"{intro}\n\n{product_text}\n\n{style_instruction}"

        # Custom per-user instructions apply identically to all product types.
        if self.custom_instructions and self.custom_instructions.strip():
            user_prompt += f"\n\nAdditional Instructions: {self.custom_instructions}"

        # Build list of models to try: primary first, then fallbacks
        primary_model = self.get_effective_model()
        models_to_try = [primary_model]

        if primary_model != DEFAULT_FREE_MODEL:
            models_to_try.append(DEFAULT_FREE_MODEL)

        if ":free" in primary_model or primary_model in (DEFAULT_FREE_MODEL, DEFAULT_FREE_ROUTER):
            fallback_models = get_available_free_models(exclude_model=primary_model)
            for fallback in fallback_models:
                if fallback not in models_to_try:
                    models_to_try.append(fallback)

        response = None
        last_error = None
        for model in models_to_try:
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
                response = None

            except Exception as e:
                last_error = e
                logger.warning(f"Model {model} failed for {product_type}: {e}, trying fallback...")
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
        estimated_cost = self._estimate_cost(model_used, token_count)
        self._session_token_count += token_count

        result = ExplanationResult(
            text=text,
            model_used=model_used,
            token_count=token_count,
            estimated_cost=estimated_cost,
            cached=False,
            timestamp=datetime.now(),
        )

        # Cache only successful results — failures must not be memoized.
        if self.cache is not None:
            cache_data = {
                "text": result.text,
                "model_used": result.model_used,
                "token_count": result.token_count,
                "estimated_cost": result.estimated_cost,
                "timestamp": result.timestamp.isoformat(),
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
        )
