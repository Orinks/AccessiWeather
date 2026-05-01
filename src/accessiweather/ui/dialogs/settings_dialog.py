"""Settings dialog for application configuration using wxPython."""

from __future__ import annotations

import logging
import webbrowser  # noqa: F401 - public monkeypatch/compatibility surface
from typing import TYPE_CHECKING

import wx

from ...runtime_env import is_compiled_runtime  # noqa: F401 - public monkeypatch surface
from .settings_dialog_constants import API_KEYS_TRANSFER_NOTE  # noqa: F401
from .settings_dialog_core import SettingsDialogCoreMixin
from .settings_dialog_handlers import SettingsDialogHandlersMixin
from .settings_dialog_modals import SettingsDialogModalMixin
from .settings_dialog_portable import SettingsDialogPortableMixin
from .settings_dialog_transfer import SettingsDialogTransferMixin

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)


class AlertAdvancedSettingsDialog(wx.Dialog):
    """Small dialog for advanced alert timing settings."""

    def __init__(self, parent, controls: dict):
        """Initialize the advanced alert timing dialog."""
        super().__init__(parent, title="Advanced Alert Timing", style=wx.DEFAULT_DIALOG_STYLE)
        self._parent_controls = controls
        self._create_ui()
        self._load_values()

    def _create_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        row_gc = wx.BoxSizer(wx.HORIZONTAL)
        row_gc.Add(
            wx.StaticText(self, label="Minimum time between any alert notifications (minutes):"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._spin_global = wx.SpinCtrl(self, min=0, max=60, initial=5)
        self._spin_global.SetName("Minimum time between any alert notifications (minutes)")
        row_gc.Add(self._spin_global, 0)
        sizer.Add(row_gc, 0, wx.ALL, 10)

        row_pac = wx.BoxSizer(wx.HORIZONTAL)
        row_pac.Add(
            wx.StaticText(self, label="Re-notify for same alert after (minutes):"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._spin_per_alert = wx.SpinCtrl(self, min=0, max=1440, initial=60)
        self._spin_per_alert.SetName("Re-notify for same alert after (minutes)")
        row_pac.Add(self._spin_per_alert, 0)
        sizer.Add(row_pac, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        row_fw = wx.BoxSizer(wx.HORIZONTAL)
        row_fw.Add(
            wx.StaticText(self, label="Only notify for alerts issued within (minutes):"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self._spin_freshness = wx.SpinCtrl(self, min=0, max=120, initial=15)
        self._spin_freshness.SetName("Only notify for alerts issued within (minutes)")
        row_fw.Add(self._spin_freshness, 0)
        sizer.Add(row_fw, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(self, wx.ID_OK)
        ok_btn.SetDefault()
        ok_btn.Bind(wx.EVT_BUTTON, self._on_ok)
        btn_sizer.AddButton(ok_btn)
        cancel_btn = wx.Button(self, wx.ID_CANCEL)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(sizer)
        self.Fit()

    def _load_values(self):
        self._spin_global.SetValue(self._parent_controls["global_cooldown"].GetValue())
        self._spin_per_alert.SetValue(self._parent_controls["per_alert_cooldown"].GetValue())
        self._spin_freshness.SetValue(self._parent_controls["freshness_window"].GetValue())

    def _on_ok(self, event):
        self._parent_controls["global_cooldown"].SetValue(self._spin_global.GetValue())
        self._parent_controls["per_alert_cooldown"].SetValue(self._spin_per_alert.GetValue())
        self._parent_controls["freshness_window"].SetValue(self._spin_freshness.GetValue())
        self.EndModal(wx.ID_OK)


class SettingsDialogSimple(
    SettingsDialogCoreMixin,
    SettingsDialogModalMixin,
    SettingsDialogHandlersMixin,
    SettingsDialogPortableMixin,
    SettingsDialogTransferMixin,
    wx.Dialog,
):
    """Comprehensive settings dialog — thin coordinator over per-tab modules."""

    _TAB_DEFINITIONS = [
        ("general", "General"),
        ("display", "Display"),
        ("notifications", "Alerts"),
        ("audio", "Audio"),
        ("data_sources", "Data Sources"),
        ("ai", "AI"),
        ("updates", "Updates"),
        ("advanced", "Advanced"),
    ]

    def __init__(self, parent, app: AccessiWeatherApp):
        """Initialize the settings dialog."""
        super().__init__(
            parent,
            title="Settings",
            size=(760, 640),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.app = app
        self.config_manager = app.config_manager
        self._controls = {}
        self._selected_specific_model: str | None = None
        self._event_sound_states = self._build_default_event_sound_states()
        self._source_settings_states = self._build_default_source_settings_states()

        self._create_ui()
        self._load_settings()
        self._setup_accessibility()

    @classmethod
    def get_tab_definitions(cls) -> list[tuple[str, str]]:
        """Return notebook tab keys and visible labels in display order."""
        return list(cls._TAB_DEFINITIONS)

    # ------------------------------------------------------------------
    # Delegation helpers for backward compatibility
    # ------------------------------------------------------------------

    @classmethod
    def _build_default_event_sound_states(cls) -> dict[str, bool]:
        """Return default event sound states (delegates to AudioTab)."""
        from .settings_tabs.audio import AudioTab

        return AudioTab._build_default_event_sound_states()

    @staticmethod
    def _build_default_source_settings_states() -> dict:
        """Return default source settings state (delegates to DataSourcesTab)."""
        from .settings_tabs.data_sources import DataSourcesTab

        return DataSourcesTab._build_default_source_settings_states()


def show_settings_dialog(parent, app: AccessiWeatherApp, tab: str | None = None) -> bool:
    """
    Show the settings dialog.

    Args:
        parent: Parent window
        app: Application instance
        tab: Optional tab name to switch to (e.g., 'Updates', 'General')

    Returns:
        True if settings were changed, False otherwise

    """
    try:
        parent_ctrl = parent

        dlg = SettingsDialogSimple(parent_ctrl, app)

        if tab:
            for i in range(dlg.notebook.GetPageCount()):
                if dlg.notebook.GetPageText(i) == tab:
                    dlg.notebook.SetSelection(i)
                    break

        result = dlg.ShowModal() == wx.ID_OK
        dlg.Destroy()
        return result

    except Exception as e:
        logger.error(f"Failed to show settings dialog: {e}")
        wx.MessageBox(
            f"Failed to open settings: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
        return False
