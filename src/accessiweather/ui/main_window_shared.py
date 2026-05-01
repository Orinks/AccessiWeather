"""Shared imports and constants for main window mixins."""
# ruff: noqa: F401

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

import wx
from wx.lib.sized_controls import SizedPanel

from ..display.presentation.formatters import get_temperature_precision
from ..runtime_env import is_compiled_runtime
from ..units import resolve_temperature_unit_preference
from ..user_manual import open_user_manual
from ..utils.temperature_utils import format_temperature
from . import main_window_notification_events
from .dialogs.location_dialog import show_edit_location_dialog

if TYPE_CHECKING:
    from ..app import AccessiWeatherApp
    from ..models.location import Location

logger = logging.getLogger("accessiweather.ui.main_window")

QUICK_ACTION_LABELS = {
    "add": "&Add Location",
    "edit": "&Edit Location",
    "remove": "&Remove Location",
    "refresh": "Re&fresh Weather",
    "explain": "Explain &Conditions",
    "discussion": "Forecaster &Notes",
    "settings": "&Settings",
}

ALL_LOCATIONS_SENTINEL = "All Locations"

__all__ = [
    "ALL_LOCATIONS_SENTINEL",
    "QUICK_ACTION_LABELS",
    "SizedPanel",
    "datetime",
    "format_temperature",
    "get_temperature_precision",
    "is_compiled_runtime",
    "logger",
    "main_window_notification_events",
    "open_user_manual",
    "resolve_temperature_unit_preference",
    "show_edit_location_dialog",
    "wx",
]
