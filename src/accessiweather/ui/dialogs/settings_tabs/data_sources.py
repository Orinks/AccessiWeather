"""Data Sources settings tab."""

from __future__ import annotations

import logging

import wx

logger = logging.getLogger(__name__)

_SOURCE_VALUES = ["auto", "nws", "openmeteo", "visualcrossing", "pirateweather"]
_SOURCE_MAP = {"auto": 0, "nws": 1, "openmeteo": 2, "visualcrossing": 3, "pirateweather": 4}
_STATION_STRATEGY_VALUES = [
    "hybrid_default",
    "nearest",
    "major_airport_preferred",
    "freshest_observation",
]


class DataSourcesTab:
    """Data Sources tab: data source selection and API key configuration."""

    def __init__(self, dialog):
        """Store reference to the parent settings dialog."""
        self.dialog = dialog

    @staticmethod
    def _build_default_source_settings_states() -> dict:
        """Return default source settings state."""
        return {
            "auto_use_nws": True,
            "auto_use_openmeteo": True,
            "auto_use_visualcrossing": True,
            "auto_use_pirateweather": True,
            "station_selection_strategy": 0,
        }

    def create(self):
        """Build the Data Sources tab panel and add it to the notebook."""
        panel = wx.ScrolledWindow(self.dialog.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = self.dialog._controls

        # Data source selection
        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row1.Add(
            wx.StaticText(panel, label="Weather Data Source:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        controls["data_source"] = wx.Choice(
            panel,
            choices=[
                "Automatic (merges all available sources)",
                "National Weather Service (US only, forecast + alerts)",
                "Open-Meteo (Global forecast, no alerts, no API key)",
                "Visual Crossing (Global forecast, US/Canada/Europe alerts, API key)",
                "Pirate Weather (Global forecast + worldwide alerts, API key)",
            ],
        )
        row1.Add(controls["data_source"], 0)
        controls["data_source"].Bind(wx.EVT_CHOICE, self.dialog._on_data_source_changed)
        sizer.Add(row1, 0, wx.ALL, 5)

        # Visual Crossing Configuration
        self.dialog._vc_config_sizer = wx.BoxSizer(wx.VERTICAL)
        self.dialog._vc_config_sizer.Add(
            wx.StaticText(panel, label="Visual Crossing API Configuration:"),
            0,
            wx.ALL,
            5,
        )

        row_key = wx.BoxSizer(wx.HORIZONTAL)
        row_key.Add(
            wx.StaticText(panel, label="Visual Crossing API Key:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        controls["vc_key"] = wx.TextCtrl(panel, style=wx.TE_PASSWORD, size=(250, -1))
        row_key.Add(controls["vc_key"], 1)
        self.dialog._vc_config_sizer.Add(row_key, 0, wx.LEFT | wx.EXPAND, 10)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        get_key_btn = wx.Button(panel, label="Get Free API Key")
        get_key_btn.Bind(wx.EVT_BUTTON, self.dialog._on_get_vc_api_key)
        btn_row.Add(get_key_btn, 0, wx.RIGHT, 10)
        validate_btn = wx.Button(panel, label="Validate API Key")
        validate_btn.Bind(wx.EVT_BUTTON, self.dialog._on_validate_vc_api_key)
        btn_row.Add(validate_btn, 0)
        self.dialog._vc_config_sizer.Add(btn_row, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 10)
        sizer.Add(self.dialog._vc_config_sizer, 0, wx.EXPAND)

        # Pirate Weather Configuration
        self.dialog._pw_config_sizer = wx.BoxSizer(wx.VERTICAL)
        self.dialog._pw_config_sizer.Add(
            wx.StaticText(panel, label="Pirate Weather API Configuration:"),
            0,
            wx.ALL,
            5,
        )

        row_pw_key = wx.BoxSizer(wx.HORIZONTAL)
        row_pw_key.Add(
            wx.StaticText(panel, label="Pirate Weather API Key:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        controls["pw_key"] = wx.TextCtrl(panel, style=wx.TE_PASSWORD, size=(250, -1))
        row_pw_key.Add(controls["pw_key"], 1)
        self.dialog._pw_config_sizer.Add(row_pw_key, 0, wx.LEFT | wx.EXPAND, 10)

        btn_row_pw = wx.BoxSizer(wx.HORIZONTAL)
        get_pw_key_btn = wx.Button(panel, label="Get Free API Key")
        get_pw_key_btn.Bind(wx.EVT_BUTTON, self.dialog._on_get_pw_api_key)
        btn_row_pw.Add(get_pw_key_btn, 0, wx.RIGHT, 10)
        validate_pw_btn = wx.Button(panel, label="Validate API Key")
        validate_pw_btn.Bind(wx.EVT_BUTTON, self.dialog._on_validate_pw_api_key)
        btn_row_pw.Add(validate_pw_btn, 0)
        self.dialog._pw_config_sizer.Add(btn_row_pw, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 10)
        sizer.Add(self.dialog._pw_config_sizer, 0, wx.EXPAND)

        # Source Settings summary + button
        sizer.Add(wx.StaticText(panel, label="Source Settings:"), 0, wx.ALL, 5)
        controls["source_settings_summary"] = wx.TextCtrl(
            panel,
            value=self._get_source_settings_summary_text(),
            size=(-1, 44),
            style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_NO_VSCROLL,
        )
        sizer.Add(controls["source_settings_summary"], 0, wx.LEFT | wx.BOTTOM | wx.EXPAND, 5)
        controls["configure_source_settings"] = wx.Button(
            panel, label="Configure Source Settings..."
        )
        controls["configure_source_settings"].Bind(
            wx.EVT_BUTTON, self.dialog._on_configure_source_settings
        )
        sizer.Add(controls["configure_source_settings"], 0, wx.LEFT | wx.BOTTOM, 5)

        panel.SetSizer(sizer)
        self.dialog.notebook.AddPage(panel, "Data Sources")
        return panel

    def _get_source_settings_summary_text(self) -> str:
        """Build summary text shown on the data sources tab."""
        state = (
            getattr(self.dialog, "_source_settings_states", None)
            or self._build_default_source_settings_states()
        )
        strategy_labels = [
            "Hybrid default",
            "Nearest station",
            "Major airport preferred",
            "Freshest observation",
        ]
        strat_idx = state.get("station_selection_strategy", 0)
        strat_text = (
            strategy_labels[strat_idx]
            if 0 <= strat_idx < len(strategy_labels)
            else strategy_labels[0]
        )
        sources = ["NWS", "Open-Meteo", "Visual Crossing", "Pirate Weather"]
        keys = [
            "auto_use_nws",
            "auto_use_openmeteo",
            "auto_use_visualcrossing",
            "auto_use_pirateweather",
        ]
        enabled = [s for s, k in zip(sources, keys, strict=True) if state.get(k, True)]
        enabled_text = ", ".join(enabled) if enabled else "None"
        return f"Auto sources: {enabled_text} | Station: {strat_text}"

    def refresh_source_settings_summary(self) -> None:
        """Refresh the source settings summary control."""
        ctrl = self.dialog._controls.get("source_settings_summary")
        if ctrl is not None:
            ctrl.SetValue(self._get_source_settings_summary_text())

    def load(self, settings):
        """Populate Data Sources tab controls from settings."""
        controls = self.dialog._controls

        data_source = getattr(settings, "data_source", "auto")
        controls["data_source"].SetSelection(_SOURCE_MAP.get(data_source, 0))

        vc_key = getattr(settings, "visual_crossing_api_key", "") or ""
        controls["vc_key"].SetValue(str(vc_key))
        self.dialog._original_vc_key = str(vc_key)
        self.dialog._vc_key_cleared = False
        if hasattr(wx, "EVT_TEXT"):

            def _on_vc_key_text(e, _dlg=self.dialog):
                _dlg._vc_key_cleared = True
                _dlg._update_auto_source_key_state()

            controls["vc_key"].Bind(wx.EVT_TEXT, _on_vc_key_text)

        pw_key = getattr(settings, "pirate_weather_api_key", "") or ""
        controls["pw_key"].SetValue(str(pw_key))
        self.dialog._original_pw_key = str(pw_key)
        self.dialog._pw_key_cleared = False
        if hasattr(wx, "EVT_TEXT"):

            def _on_pw_key_text(e, _dlg=self.dialog):
                _dlg._pw_key_cleared = True
                _dlg._update_auto_source_key_state()

            controls["pw_key"].Bind(wx.EVT_TEXT, _on_pw_key_text)

        # Source settings sub-dialog state
        saved_strategy = getattr(settings, "station_selection_strategy", "hybrid_default")
        strat_idx = (
            _STATION_STRATEGY_VALUES.index(saved_strategy)
            if saved_strategy in _STATION_STRATEGY_VALUES
            else 0
        )
        saved_us = list(
            getattr(
                settings,
                "source_priority_us",
                ["nws", "openmeteo", "visualcrossing", "pirateweather"],
            )
        )
        saved_intl = list(
            getattr(
                settings,
                "source_priority_international",
                ["openmeteo", "pirateweather", "visualcrossing"],
            )
        )
        all_sources = set(saved_us) | set(saved_intl)
        self.dialog._source_settings_states = {
            "auto_use_nws": "nws" in all_sources,
            "auto_use_openmeteo": "openmeteo" in all_sources,
            "auto_use_visualcrossing": "visualcrossing" in all_sources,
            "auto_use_pirateweather": "pirateweather" in all_sources,
            "station_selection_strategy": strat_idx,
        }
        self.refresh_source_settings_summary()
        self.dialog._update_api_key_visibility()

    def save(self) -> dict:
        """Return Data Sources tab settings as a dict."""
        controls = self.dialog._controls
        state = getattr(self.dialog, "_source_settings_states", None) or {}

        def _src_enabled(source_key: str, flag_key: str) -> bool:
            return state.get(flag_key, True)

        source_priority_us = [
            s
            for s, k in [
                ("nws", "auto_use_nws"),
                ("openmeteo", "auto_use_openmeteo"),
                ("visualcrossing", "auto_use_visualcrossing"),
                ("pirateweather", "auto_use_pirateweather"),
            ]
            if _src_enabled(s, k)
        ]
        source_priority_intl = [
            s
            for s, k in [
                ("openmeteo", "auto_use_openmeteo"),
                ("visualcrossing", "auto_use_visualcrossing"),
                ("pirateweather", "auto_use_pirateweather"),
            ]
            if _src_enabled(s, k)
        ]

        strat_idx = max(0, state.get("station_selection_strategy", 0))
        station_strategy = _STATION_STRATEGY_VALUES[strat_idx]

        return {
            "data_source": _SOURCE_VALUES[controls["data_source"].GetSelection()],
            "visual_crossing_api_key": controls["vc_key"].GetValue(),
            "pirate_weather_api_key": controls["pw_key"].GetValue(),
            "source_priority_us": source_priority_us,
            "source_priority_international": source_priority_intl,
            "auto_sources_us": source_priority_us or ["openmeteo"],
            "auto_sources_international": source_priority_intl or ["openmeteo"],
            "openmeteo_weather_model": "best_match",
            "station_selection_strategy": station_strategy,
        }

    def setup_accessibility(self):
        """Set accessibility names for Data Sources tab controls."""
        controls = self.dialog._controls
        names = {
            "data_source": "Weather Data Source",
            "vc_key": "Visual Crossing API Key",
            "pw_key": "Pirate Weather API Key",
            "source_settings_summary": "Source settings summary",
            "configure_source_settings": "Configure source settings",
        }
        for key, name in names.items():
            controls[key].SetName(name)
