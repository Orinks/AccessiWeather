"""Dialog components for the simple AccessiWeather Toga application.

This package contains dialog windows for user interaction, including
settings, location management, and information display dialogs.
"""

from .location_dialog import AddLocationDialog
from .settings_dialog import SettingsDialog

__all__ = [
    "AddLocationDialog",
    "SettingsDialog",
]
