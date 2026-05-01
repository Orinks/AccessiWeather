"""AI explainer helpers for forecast product panels."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...ai_explainer import AIExplainer

logger = logging.getLogger(__name__)


def has_openrouter_key() -> bool:
    """Return True when the OpenRouter API key is available in SecureStorage."""
    try:
        from ...config.secure_storage import SecureStorage

        return bool(SecureStorage.get_password("openrouter_api_key"))
    except Exception:  # noqa: BLE001
        return False


def build_explainer(
    injected_explainer: AIExplainer | None,
    app: object | None,
) -> Any:
    """Build or return an injected AIExplainer for forecast product summaries."""
    if injected_explainer is not None:
        return injected_explainer

    try:
        from ...ai_explainer import DEFAULT_FREE_MODEL, AIExplainer
        from ...config.secure_storage import SecureStorage

        api_key = SecureStorage.get_password("openrouter_api_key")
        if not api_key:
            return None

        settings = None
        if app is not None:
            cfg_manager = getattr(app, "config_manager", None)
            if cfg_manager is not None:
                settings = cfg_manager.get_settings()

        model_pref = getattr(settings, "ai_model_preference", None) if settings else None
        if model_pref == "auto":
            model = "openrouter/auto"
        elif model_pref:
            model = model_pref
        else:
            model = DEFAULT_FREE_MODEL

        return AIExplainer(
            api_key=api_key,
            model=model,
            custom_system_prompt=getattr(settings, "custom_system_prompt", None)
            if settings
            else None,
            custom_instructions=getattr(settings, "custom_instructions", None)
            if settings
            else None,
        )
    except Exception:  # noqa: BLE001
        logger.warning("Failed to build AIExplainer", exc_info=True)
        return None
