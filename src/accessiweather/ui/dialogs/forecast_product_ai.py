"""AI explainer helpers for forecast product panels."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...ai_explainer import AIExplainer

logger = logging.getLogger(__name__)


def has_openrouter_key(app: object | None = None) -> bool:
    """Return whether the active provider has a key (legacy helper name)."""
    try:
        from ...ai_settings import selected_key

        manager = getattr(app, "config_manager", None)
        settings = manager.get_settings() if manager is not None else None
        return bool(selected_key(settings))
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
        from ...ai_explainer import AIExplainer
        from ...ai_settings import explainer_options

        settings = None
        if app is not None:
            cfg_manager = getattr(app, "config_manager", None)
            if cfg_manager is not None:
                settings = cfg_manager.get_settings()

        return AIExplainer(**explainer_options(settings))
    except Exception:  # noqa: BLE001
        logger.warning("Failed to build AIExplainer", exc_info=True)
        return None
