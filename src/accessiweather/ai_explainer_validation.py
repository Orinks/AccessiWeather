"""Validation and data-source helpers for AI explainers."""

from __future__ import annotations

import logging
from typing import Any

from .ai_explainer_models import InvalidAPIKeyError
from .ai_explainer_openrouter import DEFAULT_FREE_MODEL

logger = logging.getLogger(__name__)


class AIExplainerValidationMixin:
    """API-key, model, and source-selection helpers."""

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
