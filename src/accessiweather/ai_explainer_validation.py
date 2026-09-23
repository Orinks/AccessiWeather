"""Validation and data-source helpers for AI explainers."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .ai_explainer_openrouter import DEFAULT_FREE_MODEL

logger = logging.getLogger(__name__)


async def validate_openrouter_api_key(api_key: str) -> tuple[bool, str]:
    """Check authentication without generating text or exposing remote error details."""
    if not api_key or not api_key.strip():
        return False, "Please enter your OpenRouter API key first."
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://openrouter.ai/api/v1/key",
                headers={"Authorization": f"Bearer {api_key.strip()}"},
            )
        status = response.status_code
        if status == 200:
            try:
                payload = response.json()
                data = payload.get("data") if isinstance(payload, dict) else None
                remaining = data.get("limit_remaining") if isinstance(data, dict) else None
            except ValueError:
                remaining = None
            if (
                isinstance(remaining, (int, float))
                and not isinstance(remaining, bool)
                and remaining <= 0
            ):
                return True, (
                    "OpenRouter API key is valid, but its spending allowance is exhausted. "
                    "Paid models may fail; free models may still work."
                )
            return True, (
                "OpenRouter API key is valid. Account credits and model access "
                "are checked when you use a model."
            )
        if status == 401:
            return False, "OpenRouter rejected this API key. Check your key and try again."
        if status == 403:
            return False, "OpenRouter denied access. Check your key and account permissions."
        if status == 429:
            return False, "OpenRouter rate limit reached. Wait a moment and try validation again."
        return False, "OpenRouter key validation is unavailable. Please try again later."
    except httpx.TimeoutException:
        return False, "OpenRouter key validation timed out. Please try again."
    except httpx.RequestError:
        return False, "Could not reach OpenRouter. Check your connection and try again."
    except Exception:
        # Exception text can contain credentials, request headers, or response bodies.
        logger.warning("OpenRouter key validation could not be completed")
        return False, "Unable to validate the OpenRouter key. Please try again later."


class AIExplainerValidationMixin:
    """API-key, model, and source-selection helpers."""

    async def validate_api_key(self, api_key: str) -> bool:
        """Return whether provider authentication was successfully verified."""
        if self.provider == "venice":
            from .ai_provider import validate_venice_api_key

            valid, _message = await validate_venice_api_key(api_key)
            return valid

        valid, _message = await validate_openrouter_api_key(api_key)
        return valid

    @staticmethod
    async def validate_model_id(model_id: str) -> bool:
        """
        Validate that a model ID exists in OpenRouter's model list.

        Args:
            model_id: The model ID to validate

        Returns:
            True if the model exists, False otherwise

        """
        from .api.openrouter_models import OpenRouterModelsClient

        client = OpenRouterModelsClient()
        return await client.validate_model_id(model_id)

    @staticmethod
    async def get_valid_free_models() -> list[str]:
        """
        Get a list of valid free model IDs from OpenRouter.

        Returns:
            List of free model IDs

        """
        from .api.openrouter_models import OpenRouterModelsClient

        client = OpenRouterModelsClient()
        models = await client.get_free_models()
        return [m.id for m in models]

    @staticmethod
    async def validate_and_get_fallback(model_id: str) -> tuple[str, bool]:
        """
        Validate a model ID and return a fallback if invalid.

        Args:
            model_id: The model ID to validate

        Returns:
            Tuple of (valid_model_id, was_fallback_used)
            If the model is valid, returns (model_id, False)
            If invalid, returns (DEFAULT_FREE_MODEL, True)

        """
        # Special cases that are always valid
        if model_id in ("auto", "openrouter/auto", DEFAULT_FREE_MODEL):
            return model_id, False

        from .api.openrouter_models import OpenRouterModelsClient

        client = OpenRouterModelsClient()
        is_valid = await client.validate_model_id(model_id)

        if is_valid:
            return model_id, False
        logger.warning(
            f"Model '{model_id}' not found in OpenRouter. "
            f"Falling back to default: {DEFAULT_FREE_MODEL}"
        )
        return DEFAULT_FREE_MODEL, True

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
