"""
Helper utilities for the AccessiWeather application.

This module contains pure utility functions that don't depend on any UI framework.
Toga-specific UI helpers have been removed during the wxPython migration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from .app import AccessiWeatherApp


logger = logging.getLogger(__name__)


def is_delete_key(key: object) -> bool:
    """Return True if the provided key represents the Delete key."""
    key_value = getattr(key, "value", key)
    if not isinstance(key_value, str):
        key_value = str(key_value)

    normalized = key_value.strip().lower()
    if normalized.startswith("<") and normalized.endswith(">"):
        normalized = normalized[1:-1]

    for prefix in ("key.", "vk_"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]

    return normalized in {"delete", "del"}


def is_escape_key(key: object) -> bool:
    """Return True if the provided key represents the Escape key."""
    key_value = getattr(key, "value", key)
    if not isinstance(key_value, str):
        key_value = str(key_value)

    normalized = key_value.strip().lower()
    if normalized.startswith("<") and normalized.endswith(">"):
        normalized = normalized[1:-1]

    for prefix in ("key.", "vk_"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]

    return normalized in {"escape", "esc"}


def get_location_choices(app: AccessiWeatherApp) -> list[str]:
    """Return the list of available location names for selection widgets."""
    try:
        location_names = app.config_manager.get_location_names()
        return location_names if location_names else ["No locations available"]
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to get location choices: %s", exc)
        return ["Error loading locations"]
