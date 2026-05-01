"""SettingsDialogCoreMixin helpers for the settings dialog."""

from __future__ import annotations

import logging
from contextlib import suppress

import wx

logger = logging.getLogger("accessiweather.ui.dialogs.settings_dialog")


class SettingsDialogCoreMixin:
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
