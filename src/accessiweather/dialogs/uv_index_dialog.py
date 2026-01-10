"""
UV Index Dialog for displaying comprehensive UV index information.

This dialog provides detailed UV index data including current UV index,
hourly forecasts with peak times, and sun safety recommendations.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from ..models import AppSettings, EnvironmentalConditions, HourlyUVIndex

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from ..app import AccessiWeatherApp


logger = logging.getLogger(__name__)


class UVIndexDialog:
    """Modal dialog for comprehensive UV index information."""

    def __init__(
        self,
        app: AccessiWeatherApp,
        location_name: str,
        environmental: EnvironmentalConditions,
        settings: AppSettings | None = None,
    ) -> None:
        """
        Initialize the UV index dialog.

        Args:
            app: The main application instance.
            location_name: Name of the current location.
            environmental: Environmental conditions data.
            settings: Application settings for formatting preferences.

        """
        self.app = app
        self.location_name = location_name
        self.environmental = environmental
        self.settings = settings
        self.window: toga.Window | None = None
        self._close_button: toga.Button | None = None
