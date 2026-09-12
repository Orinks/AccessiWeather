"""Resolve the selected AI provider without mixing credentials or model choices."""

from __future__ import annotations

from typing import Any

from .ai_explainer_models import AIExplainerError
from .ai_provider import DEFAULT_VENICE_MODEL


def selected_provider(settings: Any) -> str:
    """Validate provider selection rather than silently switching services."""
    provider = getattr(settings, "ai_provider", "openrouter")
    if provider not in ("openrouter", "venice"):
        raise AIExplainerError(
            "Unknown AI provider. Choose a provider in Settings > AI Explanations."
        )
    return provider


def selected_model(settings: Any) -> str:
    """Use the model saved for the active provider."""
    if selected_provider(settings) == "venice":
        return getattr(settings, "venice_model", "") or DEFAULT_VENICE_MODEL
    model = getattr(settings, "ai_model_preference", "openrouter/free")
    return "openrouter/auto" if model == "auto" else model or "openrouter/free"


def selected_key(settings: Any) -> str:
    """Read only the selected provider's key, including portable in-memory keys."""
    key_name = f"{selected_provider(settings)}_api_key"
    if settings is not None:
        return str(getattr(settings, key_name, "") or "")
    from .config.secure_storage import SecureStorage

    return SecureStorage.get_password(key_name) or ""


def explainer_options(settings: Any) -> dict[str, Any]:
    """Return shared constructor options for every weather explanation surface."""
    return {
        "provider": selected_provider(settings),
        "api_key": selected_key(settings) or None,
        "model": selected_model(settings),
        "custom_system_prompt": getattr(settings, "custom_system_prompt", None),
        "custom_instructions": getattr(settings, "custom_instructions", None),
    }
