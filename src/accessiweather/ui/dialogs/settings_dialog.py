"""Settings dialog for application configuration using wxPython."""

from __future__ import annotations

import json
import logging
import webbrowser
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

import wx

from ...runtime_env import is_compiled_runtime

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)

API_KEYS_TRANSFER_NOTE = (
    "API keys are not included here. API keys stay in this machine's secure keyring by "
    "default. To transfer them, use 'Export API keys (encrypted)' and then "
    "'Import API keys (encrypted)'."
)


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


class SettingsDialogSimple(wx.Dialog):
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

    # ------------------------------------------------------------------
    # UI creation
    # ------------------------------------------------------------------

    @staticmethod
    def _wrap_static_text(control: wx.Window, width: int = 620) -> wx.Window:
        """Wrap static text where supported to keep copy readable."""
        if hasattr(control, "Wrap"):
            with suppress(Exception):
                control.Wrap(width)
        return control

    def add_help_text(
        self,
        parent: wx.Window,
        parent_sizer: wx.Sizer,
        text: str,
        *,
        left: int = 10,
        bottom: int = 8,
    ) -> wx.StaticText:
        """Add wrapped helper text to a sizer."""
        control = wx.StaticText(parent, label=text)
        self._wrap_static_text(control)
        parent_sizer.Add(control, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, left)
        return control

    def add_labeled_row(
        self,
        parent: wx.Window,
        parent_sizer: wx.Sizer,
        label: str,
        control: wx.Window,
        *,
        expand_control: bool = False,
        bottom: int = 8,
    ) -> wx.BoxSizer:
        """Add a consistent label/control row to a sizer."""
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(
            wx.StaticText(parent, label=label),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        row.Add(control, 1 if expand_control else 0, wx.EXPAND if expand_control else 0)
        parent_sizer.Add(row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, bottom)
        return row

    def add_labeled_control_row(
        self,
        parent: wx.Window,
        parent_sizer: wx.Sizer,
        label: str,
        control_factory,
        *,
        expand_control: bool = False,
        bottom: int = 8,
    ) -> wx.Window:
        """Create the visible label before the control for wx/NVDA association stability."""
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(
            wx.StaticText(parent, label=label),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        control = control_factory(parent)
        row.Add(control, 1 if expand_control else 0, wx.EXPAND if expand_control else 0)
        parent_sizer.Add(row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, bottom)
        return control

    def create_section(
        self,
        parent: wx.Window,
        parent_sizer: wx.Sizer,
        title: str,
        description: str | None = None,
    ) -> wx.BoxSizer:
        """
        Create a titled settings section.

        We intentionally avoid StaticBoxSizer here because screen readers can
        announce the group label as part of the first interactive control in the
        section. The description parameter is accepted for call-site readability,
        but we do not auto-render it above the first interactive control.
        """
        del description
        heading = wx.StaticText(parent, label=title)
        self._wrap_static_text(heading)
        parent_sizer.Add(heading, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 5)

        section = wx.BoxSizer(wx.VERTICAL)
        parent_sizer.Add(section, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        return section

    def _create_ui(self):
        """Create the dialog UI using per-tab modules."""
        from .settings_tabs import (
            AdvancedTab,
            AITab,
            AudioTab,
            DataSourcesTab,
            DisplayTab,
            GeneralTab,
            NotificationsTab,
            UpdatesTab,
        )

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        intro = wx.StaticText(
            self,
            label=(
                "Review preferences by category. Changes are saved when you choose Save Settings."
            ),
        )
        self._wrap_static_text(intro)
        main_sizer.Add(intro, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)
        sub_intro = wx.StaticText(
            self,
            label=(
                "Everyday preferences appear first. Maintenance, backup, and reset "
                "tools are grouped on the Advanced tab."
            ),
        )
        self._wrap_static_text(sub_intro)
        main_sizer.Add(sub_intro, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)
        self.notebook = wx.Notebook(self)
        tab_classes = {
            "general": GeneralTab,
            "display": DisplayTab,
            "notifications": NotificationsTab,
            "audio": AudioTab,
            "data_sources": DataSourcesTab,
            "ai": AITab,
            "updates": UpdatesTab,
            "advanced": AdvancedTab,
        }

        self._tab_objects = []
        self._tab_objects_by_key = {}
        for tab_key, page_label in self.get_tab_definitions():
            tab = tab_classes[tab_key](self)
            self._tab_objects.append(tab)
            self._tab_objects_by_key[tab_key] = tab
            tab.create(page_label=page_label)

        # Keep named references for methods that need specific tabs
        self._audio_tab = self._tab_objects_by_key["audio"]
        self._display_tab = self._tab_objects_by_key["display"]
        self._data_sources_tab = self._tab_objects_by_key["data_sources"]

        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        ok_btn = wx.Button(self, wx.ID_OK, "Save Settings")
        ok_btn.Bind(wx.EVT_BUTTON, self._on_ok)
        cancel_btn = wx.Button(self, wx.ID_CANCEL, "Cancel")

        button_sizer.Add(ok_btn, 0, wx.RIGHT, 10)
        button_sizer.Add(cancel_btn, 0)
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.SetSizer(main_sizer)
        self.SetMinSize((700, 580))
        self.SetAffirmativeId(wx.ID_OK)
        self.SetEscapeId(wx.ID_CANCEL)
        ok_btn.SetDefault()

    # ------------------------------------------------------------------
    # Load / Save / Accessibility (delegate to tab objects)
    # ------------------------------------------------------------------

    def _load_settings(self):
        """Load current settings into UI controls."""
        try:
            settings = self.config_manager.get_settings()
            for tab in getattr(self, "_tab_objects", []):
                tab.load(settings)
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")

    def _save_settings(self) -> bool:
        """Save settings from UI controls."""
        try:
            settings_dict: dict = {}
            for tab in getattr(self, "_tab_objects", []):
                settings_dict.update(tab.save())

            # API key guard: if a key field is blank but the original was non-empty,
            # only drop it if the user explicitly cleared the field.
            for key, orig_attr, cleared_attr in (
                ("visual_crossing_api_key", "_original_vc_key", "_vc_key_cleared"),
                ("pirate_weather_api_key", "_original_pw_key", "_pw_key_cleared"),
                ("openrouter_api_key", "_original_openrouter_key", "_openrouter_key_cleared"),
            ):
                if not settings_dict.get(key) and getattr(self, orig_attr, ""):
                    if getattr(self, cleared_attr, False):
                        logger.info("API key %s explicitly cleared by user.", key)
                    else:
                        logger.warning(
                            "Skipping empty %s save — original value was non-empty; "
                            "keyring may have failed to load. Existing keyring value preserved.",
                            key,
                        )
                        settings_dict.pop(key, None)

            success = self.config_manager.update_settings(**settings_dict)
            if success:
                logger.info("Settings saved successfully")
                if hasattr(self, "app") and self._is_runtime_portable_mode():
                    self._maybe_update_portable_bundle_after_save(settings_dict)
            return success

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False

    def _setup_accessibility(self):
        """Set up accessibility labels for controls."""
        for tab in getattr(self, "_tab_objects", []):
            tab.setup_accessibility()

    # ------------------------------------------------------------------
    # Cross-tab state helpers
    # ------------------------------------------------------------------

    def _get_source_settings_summary_text(self) -> str:
        """Build source settings summary text (delegates to DataSourcesTab)."""
        return self._data_sources_tab._get_source_settings_summary_text()

    def _refresh_source_settings_summary(self) -> None:
        """Refresh the source settings summary (delegates to DataSourcesTab)."""
        self._data_sources_tab.refresh_source_settings_summary()

    def _set_event_sound_states(self, muted_sound_events: list[str] | tuple[str, ...]) -> None:
        """Apply muted event settings (delegates to AudioTab)."""
        self._audio_tab.set_event_sound_states(muted_sound_events)

    def _get_muted_sound_events(self) -> list[str]:
        """Return muted event keys (delegates to AudioTab)."""
        return self._audio_tab._get_muted_sound_events()

    def _get_event_sound_summary_text(self) -> str:
        """Build event sound summary text (delegates to AudioTab)."""
        return self._audio_tab._get_event_sound_summary_text()

    def _refresh_event_sound_summary(self) -> None:
        """Refresh event sound summary (delegates to AudioTab)."""
        self._audio_tab._refresh_event_sound_summary()

    @staticmethod
    def _get_event_sound_sections():
        """Return grouped event-sound sections (delegates to AudioTab)."""
        from .settings_tabs.audio import AudioTab

        return AudioTab._get_event_sound_sections()

    @staticmethod
    def _get_mutable_sound_events():
        """Return user-configurable event sound labels (delegates to AudioTab)."""
        from .settings_tabs.audio import AudioTab

        return AudioTab._get_mutable_sound_events()

    # ------------------------------------------------------------------
    # Modal helper dialogs
    # ------------------------------------------------------------------

    def _configure_modal_dialog_buttons(
        self,
        dialog: wx.Dialog,
        ok_btn: wx.Button,
        cancel_btn: wx.Button,
        *,
        focus_target: wx.Window | None = None,
    ) -> None:
        """Apply standard wx dialog button semantics and predictable focus."""
        dialog.SetAffirmativeId(wx.ID_OK)
        dialog.SetEscapeId(wx.ID_CANCEL)
        ok_btn.SetDefault()
        if focus_target is not None:
            focus_target.SetFocus()
        else:
            ok_btn.SetFocus()

    def _run_event_sounds_dialog(self) -> dict[str, bool] | None:
        """Show the event-sounds modal and return updated state when accepted."""
        dialog = wx.Dialog(
            self,
            title="Configure Event Sounds",
            size=(460, 420),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        dialog_controls: dict[str, wx.CheckBox] = {}
        state_map = dict(
            getattr(self, "_event_sound_states", {}) or self._build_default_event_sound_states()
        )
        label_map = dict(self._get_mutable_sound_events())

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(
            wx.StaticText(dialog, label="Choose which events can play sounds."),
            0,
            wx.ALL | wx.EXPAND,
            10,
        )

        scroll = wx.ScrolledWindow(dialog)
        scroll.SetScrollRate(0, 20)
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)

        for section_title, description, event_keys in self._get_event_sound_sections():
            section = wx.BoxSizer(wx.VERTICAL)
            heading = wx.StaticText(scroll, label=section_title)
            self._wrap_static_text(heading, width=380)
            section.Add(
                heading,
                0,
                wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
                5,
            )
            for event_key in event_keys:
                checkbox = wx.CheckBox(scroll, label=label_map.get(event_key, event_key))
                checkbox.SetValue(state_map.get(event_key, True))
                dialog_controls[event_key] = checkbox
                section.Add(checkbox, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
            description_text = wx.StaticText(scroll, label=description)
            self._wrap_static_text(description_text, width=380)
            section.Add(
                description_text,
                0,
                wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
                5,
            )
            scroll_sizer.Add(section, 0, wx.ALL | wx.EXPAND, 5)

        scroll.SetSizer(scroll_sizer)
        main_sizer.Add(scroll, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        button_row = wx.BoxSizer(wx.HORIZONTAL)
        button_row.AddStretchSpacer()
        ok_btn = wx.Button(dialog, wx.ID_OK, "OK")
        cancel_btn = wx.Button(dialog, wx.ID_CANCEL, "Cancel")
        button_row.Add(ok_btn, 0, wx.RIGHT, 10)
        button_row.Add(cancel_btn, 0)
        main_sizer.Add(button_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        dialog.SetSizer(main_sizer)
        self._configure_modal_dialog_buttons(
            dialog,
            ok_btn,
            cancel_btn,
            focus_target=next(iter(dialog_controls.values()), None),
        )

        try:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            return {
                event_key: checkbox.GetValue() for event_key, checkbox in dialog_controls.items()
            }
        finally:
            if hasattr(dialog, "Destroy"):
                dialog.Destroy()

    def _run_source_settings_dialog(self) -> dict | None:
        """Show the source settings modal (tabbed) and return updated state when accepted."""
        state = dict(
            getattr(self, "_source_settings_states", None)
            or self._build_default_source_settings_states()
        )

        dialog = wx.Dialog(
            self,
            title="Configure Source Settings",
            size=(500, 400),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        notebook = wx.Notebook(dialog)

        # Tab 1: Current Conditions
        cc_panel = wx.ScrolledWindow(notebook)
        cc_panel.SetScrollRate(0, 20)
        cc_sizer = wx.BoxSizer(wx.VERTICAL)

        cc_sizer.Add(
            wx.StaticText(
                cc_panel,
                label=(
                    "These settings control how current conditions are fetched "
                    "when using NWS (US locations)."
                ),
            ),
            0,
            wx.ALL | wx.EXPAND,
            10,
        )

        strategy_ctrl = self.add_labeled_control_row(
            cc_panel,
            cc_sizer,
            "NWS station selection strategy:",
            lambda parent: wx.Choice(
                parent,
                choices=[
                    "Hybrid default (recommended: fresh + major station with distance guardrail)",
                    "Nearest station (pure distance)",
                    "Major airport preferred (within radius, else nearest)",
                    "Freshest observation (among nearest stations)",
                ],
            ),
            expand_control=True,
            bottom=10,
        )
        strategy_ctrl.SetSelection(state.get("station_selection_strategy", 0))

        cc_panel.SetSizer(cc_sizer)
        notebook.AddPage(cc_panel, "Current Conditions")

        # Tab 2: Auto Mode
        auto_panel = wx.ScrolledWindow(notebook)
        auto_panel.SetScrollRate(0, 20)
        auto_sizer = wx.BoxSizer(wx.VERTICAL)

        auto_sizer.Add(
            wx.StaticText(
                auto_panel,
                label=(
                    "Choose how aggressively Automatic mode should spend API calls. "
                    "Max coverage keeps the historical fusion-first behavior. Economy and Balanced are reduced-call opt-in modes. "
                    "Set US and international source lists separately so each region keeps its own exact ordering."
                ),
            ),
            0,
            wx.ALL | wx.EXPAND,
            10,
        )

        auto_budget_ctrl = self.add_labeled_control_row(
            auto_panel,
            auto_sizer,
            "Automatic mode API budget:",
            lambda parent: wx.Choice(
                parent,
                choices=[
                    "Economy (use the fewest API calls that still cover the basics)",
                    "Balanced (allow one useful fallback when Automatic mode needs it)",
                    "Max coverage (fan out to every enabled source)",
                ],
            ),
            expand_control=True,
            bottom=10,
        )
        auto_budget_ctrl.SetSelection(state.get("auto_mode_api_budget", 0))

        us_sources = list(
            state.get("auto_sources_us", ["nws", "openmeteo", "visualcrossing", "pirateweather"])
        )
        intl_sources = list(
            state.get(
                "auto_sources_international", ["openmeteo", "pirateweather", "visualcrossing"]
            )
        )

        auto_sizer.Add(
            wx.StaticText(auto_panel, label="US automatic sources:"),
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )
        us_nws_cb = wx.CheckBox(auto_panel, label="National Weather Service")
        us_nws_cb.SetValue("nws" in us_sources)
        auto_sizer.Add(us_nws_cb, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)
        us_openmeteo_cb = wx.CheckBox(auto_panel, label="Open-Meteo")
        us_openmeteo_cb.SetValue("openmeteo" in us_sources)
        auto_sizer.Add(us_openmeteo_cb, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)
        us_vc_cb = wx.CheckBox(auto_panel, label="Visual Crossing (requires API key)")
        us_vc_cb.SetValue("visualcrossing" in us_sources)
        auto_sizer.Add(us_vc_cb, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)
        us_pw_cb = wx.CheckBox(auto_panel, label="Pirate Weather (requires API key)")
        us_pw_cb.SetValue("pirateweather" in us_sources)
        auto_sizer.Add(us_pw_cb, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)

        auto_sizer.Add(
            wx.StaticText(auto_panel, label="International automatic sources:"),
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )
        intl_openmeteo_cb = wx.CheckBox(auto_panel, label="Open-Meteo")
        intl_openmeteo_cb.SetValue("openmeteo" in intl_sources)
        auto_sizer.Add(intl_openmeteo_cb, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)
        intl_vc_cb = wx.CheckBox(auto_panel, label="Visual Crossing (requires API key)")
        intl_vc_cb.SetValue("visualcrossing" in intl_sources)
        auto_sizer.Add(intl_vc_cb, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)
        intl_pw_cb = wx.CheckBox(auto_panel, label="Pirate Weather (requires API key)")
        intl_pw_cb.SetValue("pirateweather" in intl_sources)
        auto_sizer.Add(intl_pw_cb, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)

        auto_panel.SetSizer(auto_sizer)
        notebook.AddPage(auto_panel, "Auto Mode")

        main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 10)

        button_row = wx.BoxSizer(wx.HORIZONTAL)
        button_row.AddStretchSpacer()
        cancel_btn = wx.Button(dialog, wx.ID_CANCEL, "Cancel")
        ok_btn = wx.Button(dialog, wx.ID_OK, "OK")
        button_row.Add(cancel_btn, 0, wx.RIGHT, 10)
        button_row.Add(ok_btn, 0)
        main_sizer.Add(button_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        dialog.SetSizer(main_sizer)
        self._configure_modal_dialog_buttons(dialog, ok_btn, cancel_btn, focus_target=notebook)

        try:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            auto_sources_us = [
                source
                for source, enabled in [
                    ("nws", us_nws_cb.GetValue()),
                    ("openmeteo", us_openmeteo_cb.GetValue()),
                    ("visualcrossing", us_vc_cb.GetValue()),
                    ("pirateweather", us_pw_cb.GetValue()),
                ]
                if enabled
            ] or ["openmeteo"]
            auto_sources_international = [
                source
                for source, enabled in [
                    ("openmeteo", intl_openmeteo_cb.GetValue()),
                    ("pirateweather", intl_pw_cb.GetValue()),
                    ("visualcrossing", intl_vc_cb.GetValue()),
                ]
                if enabled
            ] or ["openmeteo"]

            return {
                "auto_mode_api_budget": auto_budget_ctrl.GetSelection(),
                "auto_sources_us": auto_sources_us,
                "auto_sources_international": auto_sources_international,
                "station_selection_strategy": strategy_ctrl.GetSelection(),
            }
        finally:
            if hasattr(dialog, "Destroy"):
                dialog.Destroy()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_configure_event_sounds(self, event):
        """Open the event-sounds modal and persist accepted in-memory state."""
        updated_states = self._run_event_sounds_dialog()
        if updated_states is None:
            return
        self._event_sound_states = {
            event_key: updated_states.get(event_key, True)
            for event_key, _label in self._get_mutable_sound_events()
        }
        self._audio_tab._refresh_event_sound_summary()

    def _on_configure_source_settings(self, event) -> None:
        """Open the source settings modal and persist accepted in-memory state."""
        updated = self._run_source_settings_dialog()
        if updated is None:
            return
        self._source_settings_states = updated
        self._refresh_source_settings_summary()

    def _on_data_source_changed(self, event):
        """Update API key section visibility when data source changes."""
        self._update_api_key_visibility()

    def _update_api_key_visibility(self):
        """Show/hide API key sections based on selected data source."""
        selection = self._controls["data_source"].GetSelection()
        show_vc = selection in (0, 3)
        show_pw = selection in (0, 4)
        self._vc_config_sizer.ShowItems(show_vc)
        self._pw_config_sizer.ShowItems(show_pw)
        self._update_auto_source_key_state()
        parent = self._controls["data_source"].GetParent()
        parent.Layout()
        parent.FitInside()

    def _update_auto_source_key_state(self):
        """Keep the source settings summary in sync with API-key edits."""
        self._refresh_source_settings_summary()

    def _on_get_pw_api_key(self, event):
        """Open Pirate Weather signup page."""
        webbrowser.open("https://pirate-weather.apiable.io/signup")

    def _on_get_vc_api_key(self, event):
        """Open Visual Crossing signup page."""
        webbrowser.open("https://www.visualcrossing.com/sign-up")

    def _on_validate_pw_api_key(self, event):
        """Validate Pirate Weather API key."""
        key = self._controls["pw_key"].GetValue()
        if not key:
            wx.MessageBox("Please enter an API key first.", "Validation", wx.OK | wx.ICON_WARNING)
            return

        wx.BeginBusyCursor()
        try:
            import asyncio

            from ...models import Location
            from ...pirate_weather_client import PirateWeatherApiError, PirateWeatherClient

            test_location = Location(name="Test", latitude=40.7128, longitude=-74.0060)
            client = PirateWeatherClient(api_key=key)

            async def test_key():
                try:
                    await client.get_current_conditions(test_location)
                    return True, None
                except PirateWeatherApiError as e:
                    if e.status_code == 401:
                        return False, "Invalid API key"
                    if e.status_code == 429:
                        return False, "Rate limit exceeded — but key appears valid"
                    return False, str(e)
                except Exception as e:
                    return False, str(e)

            loop = asyncio.new_event_loop()
            try:
                valid, error = loop.run_until_complete(test_key())
            finally:
                loop.close()

            if valid:
                wx.MessageBox(
                    "Pirate Weather API key is valid!",
                    "Validation Successful",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    f"Pirate Weather API key validation failed: {error}",
                    "Validation Failed",
                    wx.OK | wx.ICON_ERROR,
                )
        finally:
            wx.EndBusyCursor()

    def _on_validate_vc_api_key(self, event):
        """Validate Visual Crossing API key."""
        key = self._controls["vc_key"].GetValue()
        if not key:
            wx.MessageBox("Please enter an API key first.", "Validation", wx.OK | wx.ICON_WARNING)
            return

        wx.BeginBusyCursor()
        try:
            import asyncio

            from ...models import Location
            from ...visual_crossing_client import VisualCrossingApiError, VisualCrossingClient

            test_location = Location(name="Test", latitude=40.7128, longitude=-74.0060)
            client = VisualCrossingClient(api_key=key)

            async def test_key():
                try:
                    await client.get_current_conditions(test_location)
                    return True, None
                except VisualCrossingApiError as e:
                    if e.status_code == 401:
                        return False, "Invalid API key"
                    if e.status_code == 429:
                        return False, "Rate limit exceeded - but key appears valid"
                    return False, str(e.message)
                except Exception as e:
                    return False, str(e)

            loop = asyncio.new_event_loop()
            try:
                valid, error = loop.run_until_complete(test_key())
            finally:
                loop.close()

            if valid:
                wx.MessageBox(
                    "API key is valid!",
                    "Validation Successful",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    f"API key validation failed: {error}",
                    "Validation Failed",
                    wx.OK | wx.ICON_ERROR,
                )
        except Exception as e:
            logger.error(f"Error validating Visual Crossing API key: {e}")
            wx.MessageBox(
                f"Error during validation: {e}",
                "Validation Error",
                wx.OK | wx.ICON_ERROR,
            )
        finally:
            wx.EndBusyCursor()

    def _on_validate_openrouter_key(self, event):
        """Validate OpenRouter API key."""
        key = self._controls["openrouter_key"].GetValue()
        if not key:
            wx.MessageBox("Please enter an API key first.", "Validation", wx.OK | wx.ICON_WARNING)
            return

        wx.BeginBusyCursor()
        try:
            import asyncio

            from ...ai_explainer import AIExplainer

            explainer = AIExplainer()

            loop = asyncio.new_event_loop()
            try:
                valid = loop.run_until_complete(explainer.validate_api_key(key))
            finally:
                loop.close()

            if valid:
                wx.MessageBox(
                    "API key is valid!",
                    "Validation Successful",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    "API key validation failed. Please check your key and try again.",
                    "Validation Failed",
                    wx.OK | wx.ICON_ERROR,
                )
        except Exception as e:
            logger.error(f"Error validating OpenRouter API key: {e}")
            wx.MessageBox(
                f"Error during validation: {e}",
                "Validation Error",
                wx.OK | wx.ICON_ERROR,
            )
        finally:
            wx.EndBusyCursor()

    def _on_browse_models(self, event):
        """Browse available AI models."""
        from .model_browser_dialog import show_model_browser_dialog

        api_key = self._controls["openrouter_key"].GetValue()
        selected_model_id = show_model_browser_dialog(self, api_key=api_key or None)

        if selected_model_id:
            if selected_model_id == "openrouter/free":
                self._controls["ai_model"].SetSelection(0)
            elif selected_model_id == "meta-llama/llama-3.3-70b-instruct:free":
                self._controls["ai_model"].SetSelection(1)
            elif selected_model_id == "openrouter/auto":
                self._controls["ai_model"].SetSelection(2)
            else:
                model_display = f"Selected: {selected_model_id.split('/')[-1]}"
                if self._controls["ai_model"].GetCount() > 3:
                    self._controls["ai_model"].SetString(3, model_display)
                else:
                    self._controls["ai_model"].Append(model_display)
                self._controls["ai_model"].SetSelection(3)
                self._selected_specific_model = selected_model_id

    def _on_reset_prompt(self, event):
        """Reset custom prompt to default."""
        self._controls["custom_prompt"].SetValue("")

    def _on_test_sound(self, event):
        """Play a test sound from the selected pack."""
        try:
            from ...notifications.sound_player import play_sample_sound

            pack_idx = self._controls["sound_pack"].GetSelection()
            if hasattr(self, "_sound_pack_ids") and pack_idx < len(self._sound_pack_ids):
                pack_id = self._sound_pack_ids[pack_idx]
            else:
                pack_id = "default"
            play_sample_sound(pack_id)
        except Exception as e:
            logger.error(f"Failed to play test sound: {e}")
            wx.MessageBox(f"Failed to play test sound: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_manage_soundpacks(self, event):
        """Open sound pack management."""
        try:
            from .soundpack_manager_dialog import show_soundpack_manager_dialog

            show_soundpack_manager_dialog(self, self.app)
            self._refresh_sound_pack_list()
        except Exception as e:
            logger.error(f"Failed to open sound pack manager: {e}")
            wx.MessageBox(
                f"Failed to open sound pack manager: {e}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def _refresh_sound_pack_list(self):
        """Refresh the sound pack dropdown after changes."""
        try:
            from ...notifications.sound_player import get_available_sound_packs

            current_idx = self._controls["sound_pack"].GetSelection()
            current_id = (
                self._sound_pack_ids[current_idx]
                if current_idx < len(self._sound_pack_ids)
                else "default"
            )

            packs = get_available_sound_packs()
            self._sound_pack_ids = list(packs.keys())
            pack_names = [packs[pid].get("name", pid) for pid in self._sound_pack_ids]

            self._controls["sound_pack"].Clear()
            for name in pack_names:
                self._controls["sound_pack"].Append(name)

            try:
                new_idx = self._sound_pack_ids.index(current_id)
                self._controls["sound_pack"].SetSelection(new_idx)
            except ValueError:
                if self._sound_pack_ids:
                    self._controls["sound_pack"].SetSelection(0)
        except Exception as e:
            logger.warning(f"Failed to refresh sound pack list: {e}")

    def _on_check_updates(self, event):
        """Check for updates using the UpdateService."""
        if not is_compiled_runtime():
            wx.MessageBox(
                "Update checking is only available in installed builds.\n"
                "You're running from source — use git pull to update.",
                "Running from Source",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        self._controls["update_status"].SetLabel("Checking for updates...")

        def do_update_check():
            import asyncio

            from ...services.simple_update import (
                UpdateService,
                parse_nightly_date,
            )

            try:
                current_version = getattr(self.app, "version", "0.0.0")
                build_tag = getattr(self.app, "build_tag", None)
                current_nightly_date = parse_nightly_date(build_tag) if build_tag else None
                if current_nightly_date:
                    current_version = current_nightly_date

                channel_idx = self._controls["update_channel"].GetSelection()
                channel = "nightly" if channel_idx == 1 else "stable"

                async def check():
                    service = UpdateService("AccessiWeather")
                    try:
                        return await service.check_for_updates(
                            current_version=current_version,
                            current_nightly_date=current_nightly_date,
                            channel=channel,
                        )
                    finally:
                        await service.close()

                update_info = asyncio.run(check())

                if update_info is None:
                    if current_nightly_date and channel == "stable":
                        status_msg = (
                            f"You're on nightly ({current_nightly_date}).\n"
                            "No newer stable release available."
                        )
                    elif current_nightly_date:
                        status_msg = f"You're on the latest nightly ({current_nightly_date})."
                    else:
                        status_msg = f"You're up to date ({current_version})."

                    wx.CallAfter(self._controls["update_status"].SetLabel, status_msg)
                    wx.CallAfter(
                        wx.MessageBox,
                        status_msg,
                        "No Updates Available",
                        wx.OK | wx.ICON_INFORMATION,
                    )
                    return

                wx.CallAfter(
                    self._controls["update_status"].SetLabel,
                    f"Update available: {update_info.version}",
                )

                def prompt_download():
                    from .update_dialog import UpdateAvailableDialog

                    channel_label = "Nightly" if update_info.is_nightly else "Stable"
                    dlg = UpdateAvailableDialog(
                        parent=self,
                        current_version=current_version,
                        new_version=update_info.version,
                        channel_label=channel_label,
                        release_notes=update_info.release_notes,
                    )
                    result = dlg.ShowModal()
                    dlg.Destroy()
                    if result == wx.ID_OK:
                        self.app._download_and_apply_update(update_info)

                wx.CallAfter(prompt_download)

            except Exception as e:
                logger.error(f"Error checking for updates: {e}")
                wx.CallAfter(
                    self._controls["update_status"].SetLabel,
                    "Could not check for updates",
                )
                wx.CallAfter(
                    wx.MessageBox,
                    f"Failed to check for updates:\n{e}",
                    "Update Check Failed",
                    wx.OK | wx.ICON_ERROR,
                )

        import threading

        thread = threading.Thread(target=do_update_check, daemon=True)
        thread.start()

    def _on_reset_defaults(self, event):
        """Reset settings to defaults."""
        result = wx.MessageBox(
            "Are you sure you want to reset all settings to defaults?\n\n"
            "Your saved locations will be preserved.",
            "Confirm Reset",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if result == wx.YES:
            try:
                if self.config_manager.reset_to_defaults():
                    self._load_settings()
                    wx.MessageBox(
                        "Settings have been reset to defaults.\n\n"
                        "Your locations have been preserved.",
                        "Reset Complete",
                        wx.OK | wx.ICON_INFORMATION,
                    )
                else:
                    wx.MessageBox(
                        "Failed to reset settings. Please try again.",
                        "Reset Failed",
                        wx.OK | wx.ICON_ERROR,
                    )
            except Exception as e:
                logger.error(f"Error resetting settings: {e}")
                wx.MessageBox(
                    f"Error resetting settings: {e}",
                    "Reset Error",
                    wx.OK | wx.ICON_ERROR,
                )

    def _on_full_reset(self, event):
        """Full data reset."""
        result = wx.MessageBox(
            "Are you sure you want to reset ALL application data?\n\n"
            "This will delete:\n"
            "• All settings\n"
            "• All saved locations\n"
            "• All caches\n"
            "• Alert history\n\n"
            "This action cannot be undone!",
            "Confirm Full Reset",
            wx.YES_NO | wx.ICON_WARNING,
        )
        if result == wx.YES:
            result2 = wx.MessageBox(
                "This is your last chance to cancel.\n\n"
                "Are you absolutely sure you want to delete all data?",
                "Final Confirmation",
                wx.YES_NO | wx.ICON_EXCLAMATION,
            )
            if result2 == wx.YES:
                try:
                    if self.config_manager.reset_all_data():
                        self._load_settings()
                        wx.MessageBox(
                            "All application data has been reset.\n\n"
                            "The application will now use default settings.",
                            "Reset Complete",
                            wx.OK | wx.ICON_INFORMATION,
                        )
                    else:
                        wx.MessageBox(
                            "Failed to reset application data. Please try again.",
                            "Reset Failed",
                            wx.OK | wx.ICON_ERROR,
                        )
                except Exception as e:
                    logger.error(f"Error during full reset: {e}")
                    wx.MessageBox(
                        f"Error during reset: {e}",
                        "Reset Error",
                        wx.OK | wx.ICON_ERROR,
                    )

    def _on_open_config_dir(self, event):
        """Open configuration directory."""
        import os
        import subprocess

        config_dir = str(self.config_manager.config_dir)
        if os.path.exists(config_dir):
            subprocess.Popen(["explorer", config_dir])
        else:
            wx.MessageBox(
                f"Config directory not found: {config_dir}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def _on_alert_advanced(self, event):
        """Open the advanced alert timing settings dialog."""
        dlg = AlertAdvancedSettingsDialog(self, self._controls)
        dlg.ShowModal()
        dlg.Destroy()

    def _on_ok(self, event):
        """Handle OK button press."""
        if self._save_settings():
            self.EndModal(wx.ID_OK)
        else:
            wx.MessageBox("Failed to save settings.", "Error", wx.OK | wx.ICON_ERROR)

    def _on_minimize_tray_changed(self, event):
        """Handle minimize to tray checkbox state change."""
        minimize_to_tray_enabled = self._controls["minimize_tray"].GetValue()
        self._update_minimize_on_startup_state(minimize_to_tray_enabled)
        event.Skip()

    def _on_taskbar_icon_text_enabled_changed(self, event):
        """Enable/disable taskbar text controls when main toggle changes."""
        taskbar_text_enabled = self._controls["taskbar_icon_text_enabled"].GetValue()
        self._update_taskbar_text_controls_state(taskbar_text_enabled)
        event.Skip()

    def _update_minimize_on_startup_state(self, minimize_to_tray_enabled: bool):
        """Update the enabled state of minimize_on_startup based on minimize_to_tray."""
        self._controls["minimize_on_startup"].Enable(minimize_to_tray_enabled)
        if not minimize_to_tray_enabled:
            self._controls["minimize_on_startup"].SetValue(False)

    def _update_taskbar_text_controls_state(self, taskbar_text_enabled: bool):
        """Enable/disable dependent taskbar text controls."""
        self._controls["taskbar_icon_dynamic_enabled"].Enable(taskbar_text_enabled)
        self._controls["taskbar_icon_text_format_dialog"].Enable(taskbar_text_enabled)

    def _on_edit_taskbar_text_format(self, event):
        """Open the focused tray text format dialog."""
        from ...taskbar_icon_updater import TaskbarIconUpdater
        from .tray_text_format_dialog import TrayTextFormatDialog

        current_weather = getattr(self.app, "current_weather_data", None)
        current_location = None
        if current_weather and getattr(current_weather, "location", None):
            current_location = getattr(current_weather.location, "name", None)

        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=self._controls["taskbar_icon_dynamic_enabled"].GetValue(),
            format_string=self._controls["taskbar_icon_text_format"].GetValue(),
            temperature_unit=self._get_selected_temperature_unit(),
        )

        dialog = TrayTextFormatDialog(
            self,
            updater=updater,
            weather_data=current_weather,
            location_name=current_location,
            initial_format=self._controls["taskbar_icon_text_format"].GetValue(),
        )
        if dialog.ShowModal() == wx.ID_OK:
            self._controls["taskbar_icon_text_format"].SetValue(dialog.get_format_string())
        dialog.Destroy()
        event.Skip()

    def _get_selected_temperature_unit(self) -> str:
        """Return the temperature unit selection currently shown in the dialog."""
        if hasattr(self, "_display_tab"):
            return self._display_tab.get_selected_temperature_unit()
        temp_values = ["auto", "f", "c", "both"]
        selection = self._controls["temp_unit"].GetSelection()
        if selection < 0 or selection >= len(temp_values):
            return "both"
        return temp_values[selection]

    def _get_ai_model_preference(self) -> str:
        """Get the AI model preference based on UI selection."""
        selection = self._controls["ai_model"].GetSelection()
        if selection == 0:
            return "openrouter/free"
        if selection == 1:
            return "meta-llama/llama-3.3-70b-instruct:free"
        if selection == 2:
            return "auto"
        if selection == 3 and self._selected_specific_model:
            return self._selected_specific_model
        return "openrouter/free"

    def _on_open_soundpacks_dir(self, event):
        """Open sound packs directory."""
        import subprocess

        from ...soundpack_paths import get_soundpacks_dir

        soundpacks_dir = get_soundpacks_dir()
        if soundpacks_dir.exists():
            subprocess.Popen(["explorer", str(soundpacks_dir)])
        else:
            wx.MessageBox(
                f"Sound packs directory not found: {soundpacks_dir}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    # ------------------------------------------------------------------
    # Portable mode / config file management
    # ------------------------------------------------------------------

    _PORTABLE_KEY_SETTINGS = (
        "visual_crossing_api_key",
        "pirate_weather_api_key",
        "openrouter_api_key",
        "avwx_api_key",
    )

    def _maybe_update_portable_bundle_after_save(self, settings_dict: dict) -> None:
        """After saving settings in portable mode, keep the bundle in sync."""
        changed_keys = {
            k: v for k, v in settings_dict.items() if k in self._PORTABLE_KEY_SETTINGS and v
        }
        if not changed_keys:
            return

        from ...config.secure_storage import SecureStorage

        app = self.app
        _PASSPHRASE_KEY = getattr(
            app, "_PORTABLE_PASSPHRASE_KEYRING_KEY", "portable_bundle_passphrase"
        )
        config_dir = self.config_manager.config_dir
        bundle_names = ("api-keys.keys", "api-keys.awkeys")
        bundle_path = next(
            (config_dir / n for n in bundle_names if (config_dir / n).exists()), None
        )

        passphrase = (SecureStorage.get_password(_PASSPHRASE_KEY) or "").strip()

        if not passphrase:
            if bundle_path:
                msg = (
                    "Your API keys have been updated.\n\n"
                    "Enter your bundle passphrase to re-encrypt the portable key bundle, "
                    "or Cancel to leave the bundle unchanged (keys are active this session only)."
                )
            else:
                msg = (
                    "Your API keys have been updated.\n\n"
                    "Enter a passphrase to create an encrypted key bundle so your keys "
                    "persist across launches, or Cancel to skip (keys active this session only)."
                )
            with wx.TextEntryDialog(
                self,
                msg,
                "Portable key bundle",
                style=wx.OK | wx.CANCEL | wx.TE_PASSWORD,
            ) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                passphrase = dlg.GetValue().strip()
            if not passphrase:
                return
            SecureStorage.set_password(_PASSPHRASE_KEY, passphrase)

        if bundle_path is None:
            bundle_path = config_dir / "api-keys.keys"

        try:
            ok = self.config_manager.export_encrypted_api_keys(bundle_path, passphrase)
            if ok:
                logger.info("Portable key bundle updated after settings save.")
            else:
                wx.MessageBox(
                    "No API keys found to export. Keys are active this session but won't persist.",
                    "Bundle update skipped",
                    wx.OK | wx.ICON_WARNING,
                )
        except Exception as exc:
            logger.error("Failed to update portable key bundle: %s", exc)
            wx.MessageBox(
                "Failed to update the key bundle. Keys are active this session but won't persist.",
                "Bundle update failed",
                wx.OK | wx.ICON_WARNING,
            )

    def _is_runtime_portable_mode(self) -> bool:
        """Return portable mode using runtime app/config state."""
        app_portable = getattr(self.app, "_portable_mode", None)
        if app_portable is not None:
            return bool(app_portable)
        runtime_paths = getattr(self.app, "runtime_paths", None)
        if runtime_paths is not None:
            return bool(getattr(runtime_paths, "portable_mode", False))
        return False

    def _has_meaningful_installed_config_data(
        self, installed_config_dir: Path
    ) -> tuple[bool, str | None]:
        """Pre-check whether installed config has meaningful data to transfer."""
        if not installed_config_dir.exists() or not installed_config_dir.is_dir():
            return False, "Installed config directory not found."

        try:
            has_any_entries = any(installed_config_dir.iterdir())
        except Exception:
            has_any_entries = False
        if not has_any_entries:
            return False, "Installed config directory is empty."

        config_file = installed_config_dir / "accessiweather.json"
        if not config_file.exists() or not config_file.is_file():
            return False, "Required config file accessiweather.json is missing."

        try:
            if config_file.stat().st_size <= 0:
                return False, "Config file accessiweather.json is empty."
        except Exception:
            return False, "Could not read accessiweather.json."

        try:
            config_data = self._read_config_json(installed_config_dir)
        except Exception:
            return False, "Config file accessiweather.json is invalid or unreadable."

        locations = (
            config_data.get("locations") if isinstance(config_data.get("locations"), list) else []
        )

        if len(locations) == 0:
            return False, "Installed config has no saved locations to transfer."

        return True, None

    def _get_installed_config_dir(self):
        """Return the standard installed config directory path."""
        import os

        local_appdata = os.environ.get("LOCALAPPDATA")
        author = getattr(self.app.paths, "_author", "Orinks")
        app_name = getattr(self.app.paths, "_app_name", "AccessiWeather")
        if local_appdata:
            return Path(local_appdata) / str(author) / str(app_name) / "Config"
        return Path.home() / "AppData" / "Local" / str(author) / str(app_name) / "Config"

    def _on_open_installed_config_dir(self, event):
        """Open installed config directory."""
        import subprocess

        installed_config_dir = self._get_installed_config_dir()
        if installed_config_dir.exists():
            subprocess.Popen(["explorer", str(installed_config_dir)])
        else:
            wx.MessageBox(
                f"Installed config directory not found: {installed_config_dir}",
                "Info",
                wx.OK | wx.ICON_INFORMATION,
            )

    def _read_config_json(self, config_dir: Path) -> dict:
        """Read accessiweather.json from a config directory."""
        config_file = config_dir / "accessiweather.json"
        if not config_file.exists():
            raise FileNotFoundError(f"Required config file not found: {config_file}")
        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Invalid config payload in {config_file}: expected object")
        return data

    def _validate_portable_copy(
        self, installed_config_dir: Path, portable_config_dir: Path
    ) -> tuple[bool, list[str]]:
        """Validate copied portable config has required non-secret settings/state."""
        messages: list[str] = []
        try:
            src_cfg = self._read_config_json(installed_config_dir)
            dst_cfg = self._read_config_json(portable_config_dir)
        except Exception as e:
            return False, [str(e)]

        src_settings = src_cfg.get("settings") if isinstance(src_cfg.get("settings"), dict) else {}
        dst_settings = dst_cfg.get("settings") if isinstance(dst_cfg.get("settings"), dict) else {}

        required_setting_keys = ["ai_model_preference", "data_source", "temperature_unit"]
        for key in required_setting_keys:
            src_value = src_settings.get(key)
            dst_value = dst_settings.get(key)
            if src_value != dst_value:
                messages.append(
                    f"Setting '{key}' did not copy correctly "
                    f"(installed={src_value!r}, portable={dst_value!r})."
                )

        src_locations = (
            src_cfg.get("locations") if isinstance(src_cfg.get("locations"), list) else []
        )
        dst_locations = (
            dst_cfg.get("locations") if isinstance(dst_cfg.get("locations"), list) else []
        )
        if len(src_locations) != len(dst_locations):
            messages.append(
                f"Location count mismatch after copy "
                f"(installed={len(src_locations)}, portable={len(dst_locations)})."
            )

        if messages:
            return False, messages
        return True, []

    def _build_portable_copy_summary(self, portable_config_dir: Path) -> list[str]:
        """Build concise summary lines describing migrated non-secret config values."""
        config_data = self._read_config_json(portable_config_dir)
        settings = (
            config_data.get("settings") if isinstance(config_data.get("settings"), dict) else {}
        )
        locations = (
            config_data.get("locations") if isinstance(config_data.get("locations"), list) else []
        )

        custom_prompt_present = any(
            bool(str(settings.get(key, "")).strip())
            for key in (
                "custom_system_prompt",
                "custom_instructions",
                "prompt",
                "assistant_prompt",
            )
            if key in settings
        )

        return [
            f"• locations: {len(locations)}",
            f"• data source: {settings.get('data_source', 'not set')}",
            f"• AI model preference: {settings.get('ai_model_preference', 'not set')}",
            f"• temperature unit: {settings.get('temperature_unit', 'not set')}",
            f"• custom prompt: {'yes' if custom_prompt_present else 'no'}",
        ]

    def _on_copy_installed_config_to_portable(self, event):
        """Copy installed config files into the current portable config directory."""
        import shutil

        portable_config_dir = self.config_manager.config_dir
        installed_config_dir = self._get_installed_config_dir()

        has_data, precheck_reason = self._has_meaningful_installed_config_data(installed_config_dir)
        if not has_data:
            detail = f"\n\nDetails: {precheck_reason}" if precheck_reason else ""
            wx.MessageBox(
                f"Nothing to transfer from installed config.\n{installed_config_dir}{detail}",
                "Nothing to copy",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if installed_config_dir.resolve() == portable_config_dir.resolve():
            wx.MessageBox(
                "Installed and portable config directories are the same location."
                "\n\nNo copy is needed.",
                "Nothing to copy",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        result = wx.MessageBox(
            "Copy settings and locations from installed config to this portable config?\n\n"
            "Only core config files are copied. Cache files are skipped and will regenerate.\n\n"
            "Existing files in portable config with the same name will be overwritten.",
            "Copy installed config to portable",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if result != wx.YES:
            return

        self.config_manager.save_config()

        try:
            portable_config_dir.mkdir(parents=True, exist_ok=True)

            transferable_items = ["accessiweather.json"]
            copied_items: list[str] = []

            for name in transferable_items:
                item = installed_config_dir / name
                if not item.exists():
                    continue

                dst = portable_config_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dst)
                copied_items.append(item.name)

            if not copied_items:
                wx.MessageBox(
                    "Nothing to transfer from installed config."
                    "\n\nNo transferable config files were found.",
                    "Nothing to copy",
                    wx.OK | wx.ICON_WARNING,
                )
                return

            valid, validation_errors = self._validate_portable_copy(
                installed_config_dir, portable_config_dir
            )
            if not valid:
                details = "\n".join(f"• {msg}" for msg in validation_errors)
                wx.MessageBox(
                    "Config copy completed, but validation found problems."
                    "\n\nPortable data may be incomplete."
                    f"\n\n{details}",
                    "Copy incomplete",
                    wx.OK | wx.ICON_WARNING,
                )
                return

            self.config_manager._config = None
            self.config_manager.load_config()
            self._load_settings()

            copied_list = "\n".join(f"• {name}" for name in copied_items)
            summary_lines = self._build_portable_copy_summary(portable_config_dir)
            summary_block = "\n".join(summary_lines)
            wx.MessageBox(
                "Copied these config item(s):\n"
                f"{copied_list}\n\n"
                "Copied settings summary:\n"
                f"{summary_block}\n\n"
                f"From:\n{installed_config_dir}\n\n"
                f"To:\n{portable_config_dir}",
                "Copy complete",
                wx.OK | wx.ICON_INFORMATION,
            )

            self._offer_api_key_export_after_copy(portable_config_dir)
        except Exception as e:
            logger.error(f"Failed to copy installed config to portable: {e}")
            wx.MessageBox(
                f"Failed to copy config: {e}",
                "Copy failed",
                wx.OK | wx.ICON_ERROR,
            )

    def _offer_api_key_export_after_copy(self, portable_config_dir: Path) -> None:
        """After copying installed config to portable, offer to export API keys."""
        result = wx.MessageBox(
            "Config copied. Your API keys are stored in the system keyring and were not "
            "copied.\n\n"
            "Would you like to export them to an encrypted bundle now so they work in "
            "portable mode?",
            "Export API keys?",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if result != wx.YES:
            wx.MessageBox(
                "You can export API keys later from Settings > Advanced > "
                "Export API keys (encrypted).",
                "API keys not exported",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        passphrase = self._prompt_passphrase(
            "Export API keys (encrypted)",
            "Enter a passphrase to encrypt your API keys.",
        )
        if passphrase is None:
            return

        confirm = self._prompt_passphrase(
            "Confirm passphrase",
            "Re-enter the passphrase to confirm.",
        )
        if confirm is None:
            return
        if passphrase != confirm:
            wx.MessageBox(
                "Passphrases do not match. API keys were not exported.",
                "Export cancelled",
                wx.OK | wx.ICON_WARNING,
            )
            return

        bundle_path = portable_config_dir / "api-keys.keys"
        try:
            ok = self.config_manager.export_encrypted_api_keys(bundle_path, passphrase)
            if ok:
                wx.MessageBox(
                    f"API keys exported to:\n{bundle_path}",
                    "Export complete",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    "No API keys found to export. You can add keys in Settings > Data Sources "
                    "or Settings > AI and export later.",
                    "No keys to export",
                    wx.OK | wx.ICON_WARNING,
                )
        except Exception as exc:
            logger.error("Failed to export API keys after config copy: %s", exc)
            wx.MessageBox(
                f"Failed to export API keys: {exc}",
                "Export failed",
                wx.OK | wx.ICON_ERROR,
            )

    def _prompt_passphrase(self, title: str, message: str) -> str | None:
        """Prompt for passphrase using masked text entry."""
        with wx.TextEntryDialog(
            self, message, title, style=wx.OK | wx.CANCEL | wx.TE_PASSWORD
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return None
            value = dlg.GetValue().strip()
            return value or None

    def _on_export_encrypted_api_keys(self, event):
        """Export API keys from keyring to encrypted bundle file."""
        passphrase = self._prompt_passphrase(
            "Export API keys (encrypted)",
            "Enter a passphrase to encrypt exported API keys.",
        )
        if passphrase is None:
            return

        confirm = self._prompt_passphrase(
            "Confirm passphrase",
            "Re-enter the passphrase to confirm encrypted export.",
        )
        if confirm is None:
            return
        if passphrase != confirm:
            wx.MessageBox("Passphrases do not match.", "Export Cancelled", wx.OK | wx.ICON_WARNING)
            return

        with wx.FileDialog(
            self,
            "Export API keys (encrypted)",
            wildcard="Encrypted bundle (*.keys)|*.keys|Legacy bundle (*.awkeys)|*.awkeys",
            defaultFile="accessiweather_api_keys.keys",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            export_path = Path(dlg.GetPath())
            if self.config_manager.export_encrypted_api_keys(export_path, passphrase):
                wx.MessageBox(
                    f"Encrypted API key bundle exported successfully to:\n{export_path}",
                    "Export Complete",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    "Failed to export encrypted API keys. Ensure at least one API key is saved.",
                    "Export Failed",
                    wx.OK | wx.ICON_ERROR,
                )

    def _on_import_encrypted_api_keys(self, event):
        """Import encrypted API key bundle into local secure storage."""
        with wx.FileDialog(
            self,
            "Import API keys (encrypted)",
            wildcard="Encrypted bundle (*.keys)|*.keys|Legacy bundle (*.awkeys)|*.awkeys",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            import_path = Path(dlg.GetPath())

        passphrase = self._prompt_passphrase(
            "Import API keys (encrypted)",
            "Enter the passphrase used when exporting this encrypted bundle.",
        )
        if passphrase is None:
            return

        if self.config_manager.import_encrypted_api_keys(import_path, passphrase):
            self._load_settings()
            wx.MessageBox(
                "Encrypted API keys imported successfully into this machine's secure keyring.",
                "Import Complete",
                wx.OK | wx.ICON_INFORMATION,
            )
        else:
            wx.MessageBox(
                "Failed to import encrypted API keys. Check passphrase and bundle file.",
                "Import Failed",
                wx.OK | wx.ICON_ERROR,
            )

    def _on_export_settings(self, event):
        """Export settings to file."""
        with wx.FileDialog(
            self,
            "Export Settings",
            wildcard="JSON files (*.json)|*.json",
            defaultFile="accessiweather_settings.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                export_path = Path(dlg.GetPath())
                try:
                    if self.config_manager.export_settings(export_path):
                        wx.MessageBox(
                            f"Settings exported successfully to:\n{export_path}\n\n"
                            f"Note: {API_KEYS_TRANSFER_NOTE}",
                            "Export Complete",
                            wx.OK | wx.ICON_INFORMATION,
                        )
                    else:
                        wx.MessageBox(
                            "Failed to export settings. Please try again.",
                            "Export Failed",
                            wx.OK | wx.ICON_ERROR,
                        )
                except Exception as e:
                    logger.error(f"Error exporting settings: {e}")
                    wx.MessageBox(
                        f"Error exporting settings: {e}",
                        "Export Error",
                        wx.OK | wx.ICON_ERROR,
                    )

    def _on_import_settings(self, event):
        """Import settings from file."""
        with wx.FileDialog(
            self,
            "Import Settings",
            wildcard="JSON files (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                import_path = Path(dlg.GetPath())
                result = wx.MessageBox(
                    "Importing settings will overwrite your current preferences.\n\n"
                    "Your saved locations will NOT be affected.\n\n"
                    f"Important: {API_KEYS_TRANSFER_NOTE}\n\n"
                    "Do you want to continue?",
                    "Confirm Import",
                    wx.YES_NO | wx.ICON_QUESTION,
                )
                if result == wx.YES:
                    try:
                        if self.config_manager.import_settings(import_path):
                            self._load_settings()
                            wx.MessageBox(
                                "Settings imported successfully!\n\n"
                                f"Note: {API_KEYS_TRANSFER_NOTE}",
                                "Import Complete",
                                wx.OK | wx.ICON_INFORMATION,
                            )
                        else:
                            wx.MessageBox(
                                "Failed to import settings.\n\n"
                                "The file may be invalid or corrupted.",
                                "Import Failed",
                                wx.OK | wx.ICON_ERROR,
                            )
                    except Exception as e:
                        logger.error(f"Error importing settings: {e}")
                        wx.MessageBox(
                            f"Error importing settings: {e}",
                            "Import Error",
                            wx.OK | wx.ICON_ERROR,
                        )


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
