"""
Main window for AccessiWeather using plain wxPython.

This module defines the main application window using standard wxPython
widgets for optimal screen reader compatibility.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx  # noqa: F401 - public monkeypatch surface
from wx.lib.sized_controls import SizedFrame

from ..runtime_env import is_compiled_runtime  # noqa: F401 - public monkeypatch surface
from ..screen_reader import ScreenReaderAnnouncer
from ..user_manual import open_user_manual  # noqa: F401 - public monkeypatch surface
from .dialogs.location_dialog import show_edit_location_dialog  # noqa: F401
from .main_window_commands import MainWindowCommandMixin
from .main_window_display import MainWindowDisplayMixin
from .main_window_locations import MainWindowLocationMixin
from .main_window_refresh import MainWindowRefreshMixin
from .main_window_ui import MainWindowUIMixin

if TYPE_CHECKING:
    from ..app import AccessiWeatherApp

logger = logging.getLogger(__name__)

QUICK_ACTION_LABELS = {
    "add": "&Add Location",
    "edit": "&Edit Location",
    "remove": "&Remove Location",
    "refresh": "Re&fresh Weather",
    "explain": "Explain &Conditions",
    "discussion": "Forecaster &Notes",
    "settings": "&Settings",
}

# Sentinel string used for the "All Locations" summary entry in the dropdown.
ALL_LOCATIONS_SENTINEL = "All Locations"

# The Help menu label "User &Manual" is created in MainWindowUIMixin and binds
# to _on_open_user_manual in MainWindowCommandMixin.


class _StaleWarningProxy:
    """Delegates SetLabel() calls to the second field of the wx.StatusBar."""

    def __init__(self, window: MainWindow) -> None:
        self._window = window

    def SetLabel(self, text: str) -> None:
        self._window.GetStatusBar().SetStatusText(text, 1)


class MainWindow(
    MainWindowUIMixin,
    MainWindowLocationMixin,
    MainWindowCommandMixin,
    MainWindowRefreshMixin,
    MainWindowDisplayMixin,
    SizedFrame,
):
    """
    Main application window using plain wxPython.

    This provides the primary UI for AccessiWeather with:
    - Location selection dropdown
    - Current conditions display
    - Forecast display
    - Weather alerts list
    - Control buttons
    """

    def __init__(self, app: AccessiWeatherApp, title: str = "AccessiWeather", **kwargs):
        """
        Initialize the main window.

        Args:
            app: The AccessiWeather application instance
            title: Window title
            **kwargs: Additional keyword arguments passed to SizedFrame

        """
        super().__init__(parent=None, title=title, **kwargs)
        self.app = app
        self._escape_id = None
        self._fetch_generation = 0  # Tracks which fetch is current (prevents stale updates)
        # Persistent map of alert_id -> lifecycle label ("New", "Updated", "Escalated", "Extended").
        # Updated on each successful weather fetch; cleared when the location changes.
        self._alert_lifecycle_labels: dict[str, str] = {}
        # True when "All Locations" is the active view (no real location selected).
        self._all_locations_active: bool = False
        self._last_single_location_name: str | None = None
        # Aggregated (location_name, alert) pairs shown in All Locations mode.
        self._all_locations_alerts_data: list[tuple[str, object]] = []

        # Screen reader announcer for dynamic status updates
        self._announcer = ScreenReaderAnnouncer()

        # Create the UI
        self._create_widgets()
        self._create_menu_bar()
        self._bind_events()
        self._setup_escape_accelerator()

        # Set initial window size.  The main window stacks five multi-line text
        # sections (current conditions, hourly, daily, alerts, event center) plus
        # the location row and button row; 600px of height caused every section
        # to clip its content.  Minimum size keeps the layout usable if the
        # window is resized down.
        self.SetSize((900, 820))
        self.SetMinSize((800, 700))

        # Populate initial data
        self._populate_locations()
