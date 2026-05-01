"""OpenRouter model constants and free-model discovery helpers."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
# Use current working free models from OpenRouter (updated Dec 2025)
DEFAULT_FREE_MODEL = "openrouter/free"
DEFAULT_FREE_ROUTER = "openrouter/free"
FALLBACK_FREE_MODEL = "meta-llama/llama-3.3-70b-instruct:free"
DEFAULT_PAID_MODEL = "openrouter/auto"
# Static fallback models only used if dynamic fetch fails
STATIC_FALLBACK_MODELS = [
    "google/gemma-3-27b-it:free",
    "qwen/qwen3-4b:free",
]

_free_models_cache: list[str] | None = None
_free_models_cache_time: float = 0
_FREE_MODELS_CACHE_TTL = 3600  # 1 hour cache


def get_available_free_models(exclude_model: str | None = None) -> list[str]:
    """
    Fetch available free models from OpenRouter API.

    Results are cached for 1 hour to avoid excessive API calls.
    Falls back to static list if API is unavailable.

    Args:
        exclude_model: Model ID to exclude from results (e.g., the primary model)

    Returns:
        List of free model IDs, up to 3 models (OpenRouter's fallback limit)

    """
    import time

    global _free_models_cache, _free_models_cache_time

    if (
        _free_models_cache is not None
        and (time.time() - _free_models_cache_time) < _FREE_MODELS_CACHE_TTL
    ):
        models = [m for m in _free_models_cache if m != exclude_model]
        return models[:3]

    try:
        import httpx

        response = httpx.get(OPENROUTER_MODELS_URL, timeout=10.0)
        response.raise_for_status()
        data = response.json()

        free_models = []
        for model in data.get("data", []):
            model_id = model.get("id", "")
            if model_id.endswith(":free"):
                context_length = model.get("context_length", 0)
                free_models.append((model_id, context_length))

        free_models.sort(key=lambda x: x[1], reverse=True)
        _free_models_cache = [m[0] for m in free_models]
        _free_models_cache_time = time.time()

        logger.info(f"Fetched {len(_free_models_cache)} free models from OpenRouter")

        models = [m for m in _free_models_cache if m != exclude_model]
        return models[:3]

    except Exception as e:
        logger.warning(f"Failed to fetch free models from OpenRouter: {e}, using static fallbacks")
        models = [m for m in STATIC_FALLBACK_MODELS if m != exclude_model]
        return models[:3]
