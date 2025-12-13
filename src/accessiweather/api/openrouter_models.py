"""
OpenRouter Models API client.

This module provides functionality to fetch and filter available models
from the OpenRouter API, including support for free model filtering.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


@dataclass
class OpenRouterModel:
    """Represents an OpenRouter model with its properties."""

    id: str
    name: str
    description: str
    context_length: int | None
    pricing_prompt: float  # Cost per 1M tokens
    pricing_completion: float  # Cost per 1M tokens
    is_free: bool
    is_moderated: bool  # Whether content moderation is applied
    input_modalities: list[str]
    output_modalities: list[str]

    @property
    def display_name(self) -> str:
        """Get a user-friendly display name."""
        suffix = " (Free)" if self.is_free else ""
        return f"{self.name}{suffix}"

    @property
    def context_display(self) -> str:
        """Get context length as a readable string."""
        if self.context_length is None:
            return "Unknown"
        if self.context_length >= 1_000_000:
            return f"{self.context_length / 1_000_000:.1f}M"
        if self.context_length >= 1000:
            return f"{self.context_length / 1000:.0f}K"
        return str(self.context_length)


class OpenRouterModelsError(Exception):
    """Base exception for OpenRouter models API errors."""


class OpenRouterModelsClient:
    """Client for fetching OpenRouter models."""

    def __init__(self, api_key: str | None = None, timeout: float = 30.0):
        """
        Initialize the models client.

        Args:
            api_key: Optional OpenRouter API key (not required for models endpoint)
            timeout: Request timeout in seconds

        """
        self.api_key = api_key
        self.timeout = timeout
        self._cached_models: list[OpenRouterModel] | None = None

    def _parse_pricing(self, value: Any) -> float:
        """Parse pricing value which can be string or number."""
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return 0.0
        return 0.0

    def _parse_model(self, data: dict[str, Any]) -> OpenRouterModel:
        """Parse a model from API response data."""
        model_id = data.get("id", "")
        pricing = data.get("pricing", {})
        architecture = data.get("architecture", {})
        top_provider = data.get("top_provider", {})

        # Determine if model is free based on :free suffix or zero pricing
        is_free = model_id.endswith(":free")
        if not is_free:
            prompt_price = self._parse_pricing(pricing.get("prompt"))
            completion_price = self._parse_pricing(pricing.get("completion"))
            is_free = prompt_price == 0 and completion_price == 0

        # Get moderation status from top_provider
        # is_moderated=True means content moderation is applied (censored)
        # is_moderated=False means no moderation (uncensored/unfiltered)
        is_moderated = top_provider.get("is_moderated", True)  # Default to moderated if unknown

        return OpenRouterModel(
            id=model_id,
            name=data.get("name", model_id),
            description=data.get("description", ""),
            context_length=data.get("context_length"),
            pricing_prompt=self._parse_pricing(pricing.get("prompt")),
            pricing_completion=self._parse_pricing(pricing.get("completion")),
            is_free=is_free,
            is_moderated=is_moderated,
            input_modalities=architecture.get("input_modalities", ["text"]),
            output_modalities=architecture.get("output_modalities", ["text"]),
        )

    async def fetch_models(self, force_refresh: bool = False) -> list[OpenRouterModel]:
        """
        Fetch all available models from OpenRouter.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            List of OpenRouterModel objects

        Raises:
            OpenRouterModelsError: If the API request fails

        """
        if self._cached_models is not None and not force_refresh:
            return self._cached_models

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(OPENROUTER_MODELS_URL, headers=headers)
                response.raise_for_status()
                data = response.json()

            models_data = data.get("data", [])
            models = [self._parse_model(m) for m in models_data]

            # Sort by name for consistent ordering
            models.sort(key=lambda m: m.name.lower())

            self._cached_models = models
            logger.info(f"Fetched {len(models)} models from OpenRouter")
            return models

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching models: {e}")
            raise OpenRouterModelsError(
                f"Failed to fetch models: HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            logger.error(f"Request error fetching models: {e}")
            raise OpenRouterModelsError(f"Failed to fetch models: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching models: {e}")
            raise OpenRouterModelsError(f"Failed to fetch models: {e}") from e

    async def get_free_models(self, force_refresh: bool = False) -> list[OpenRouterModel]:
        """
        Get only free models (those with :free suffix or zero pricing).

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            List of free OpenRouterModel objects

        """
        all_models = await self.fetch_models(force_refresh)
        return [m for m in all_models if m.is_free]

    async def get_paid_models(self, force_refresh: bool = False) -> list[OpenRouterModel]:
        """
        Get only paid models.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            List of paid OpenRouterModel objects

        """
        all_models = await self.fetch_models(force_refresh)
        return [m for m in all_models if not m.is_free]

    async def get_text_models(self, force_refresh: bool = False) -> list[OpenRouterModel]:
        """
        Get models that support text input and output (suitable for chat).

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            List of text-capable OpenRouterModel objects

        """
        all_models = await self.fetch_models(force_refresh)
        return [
            m for m in all_models if "text" in m.input_modalities and "text" in m.output_modalities
        ]

    async def search_models(
        self,
        query: str,
        free_only: bool = False,
        force_refresh: bool = False,
    ) -> list[OpenRouterModel]:
        """
        Search models by name or description.

        Args:
            query: Search query string
            free_only: If True, only return free models
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            List of matching OpenRouterModel objects

        """
        if free_only:
            models = await self.get_free_models(force_refresh)
        else:
            models = await self.fetch_models(force_refresh)

        if not query:
            return models

        query_lower = query.lower()
        return [
            m
            for m in models
            if query_lower in m.name.lower()
            or query_lower in m.id.lower()
            or query_lower in m.description.lower()
        ]

    def clear_cache(self) -> None:
        """Clear the cached models."""
        self._cached_models = None
