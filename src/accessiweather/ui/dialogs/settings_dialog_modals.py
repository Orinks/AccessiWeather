"""SettingsDialogModalMixin helpers for the settings dialog."""

from __future__ import annotations

import wx


class SettingsDialogModalMixin:
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

        us_sources = list(state.get("auto_sources_us", ["nws", "openmeteo", "pirateweather"]))
        intl_sources = list(state.get("auto_sources_international", ["openmeteo", "pirateweather"]))

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
                    ("pirateweather", us_pw_cb.GetValue()),
                ]
                if enabled
            ] or ["openmeteo"]
            auto_sources_international = [
                source
                for source, enabled in [
                    ("openmeteo", intl_openmeteo_cb.GetValue()),
                    ("pirateweather", intl_pw_cb.GetValue()),
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
