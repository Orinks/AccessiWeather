"""Data Sources settings tab."""

from __future__ import annotations

import logging

import wx

logger = logging.getLogger(__name__)

_SOURCE_VALUES = ["auto", "nws", "openmeteo", "pirateweather"]
_SOURCE_MAP = {"auto": 0, "nws": 1, "openmeteo": 2, "pirateweather": 3}
_AUTO_MODE_BUDGET_VALUES = ["economy", "balanced", "max_coverage"]
_AUTO_MODE_BUDGET_LABELS = ["Economy", "Balanced", "Max coverage"]
_DEFAULT_AUTO_SOURCES_US = ["nws", "openmeteo", "pirateweather"]
_DEFAULT_AUTO_SOURCES_INTERNATIONAL = ["openmeteo", "pirateweather"]
_DEFAULT_BUDGET_INDEX = _AUTO_MODE_BUDGET_VALUES.index("max_coverage")
_STATION_STRATEGY_VALUES = [
    "hybrid_default",
    "nearest",
    "major_airport_preferred",
    "freshest_observation",
]
_STATION_STRATEGY_LABELS = [
    "Hybrid default",
    "Nearest station",
    "Major airport preferred",
    "Freshest observation",
]
_SOURCE_LABELS = {
    "nws": "NWS",
    "openmeteo": "Open-Meteo",
    "pirateweather": "Pirate Weather",
}


class DataSourcesTab:
    """Data Sources tab: data source selection and API key configuration."""

    def __init__(self, dialog):
        """Store reference to the parent settings dialog."""
        self.dialog = dialog

    @staticmethod
    def _build_default_source_settings_states() -> dict:
        """Return default source settings state."""
        return {
            "auto_mode_api_budget": _DEFAULT_BUDGET_INDEX,
            "auto_sources_us": list(_DEFAULT_AUTO_SOURCES_US),
            "auto_sources_international": list(_DEFAULT_AUTO_SOURCES_INTERNATIONAL),
            "station_selection_strategy": 0,
        }

    @staticmethod
    def _get_state_sources(state: dict, region: str) -> list[str]:
        """Return the normalized configured source order for a region."""
        key = "auto_sources_us" if region == "us" else "auto_sources_international"
        default_sources = (
            _DEFAULT_AUTO_SOURCES_US if region == "us" else _DEFAULT_AUTO_SOURCES_INTERNATIONAL
        )
        saved_sources = state.get(key, default_sources)
        if not isinstance(saved_sources, list):
            return list(default_sources)
        valid_sources = set(_SOURCE_LABELS)
        normalized = [source for source in saved_sources if source in valid_sources]
        return normalized or list(default_sources)

    @staticmethod
    def build_source_settings_summary_text(state: dict) -> str:
        """Build plain-language summary text shown on the data sources tab."""
        budget_idx = state.get("auto_mode_api_budget", _DEFAULT_BUDGET_INDEX)
        if 0 <= budget_idx < len(_AUTO_MODE_BUDGET_LABELS):
            budget_text = _AUTO_MODE_BUDGET_LABELS[budget_idx]
        else:
            budget_text = _AUTO_MODE_BUDGET_LABELS[_DEFAULT_BUDGET_INDEX]

        strat_idx = state.get("station_selection_strategy", 0)
        if 0 <= strat_idx < len(_STATION_STRATEGY_LABELS):
            strat_text = _STATION_STRATEGY_LABELS[strat_idx]
        else:
            strat_text = _STATION_STRATEGY_LABELS[0]

        us_enabled = DataSourcesTab._get_state_sources(state, "us")
        intl_enabled = DataSourcesTab._get_state_sources(state, "international")
        us_text = ", ".join(_SOURCE_LABELS[source] for source in us_enabled)
        intl_text = ", ".join(_SOURCE_LABELS[source] for source in intl_enabled)
        return (
            f"Automatic mode budget: {budget_text}. "
            f"US automatic sources: {us_text}. "
            f"International automatic sources: {intl_text}. "
            f"NWS station strategy: {strat_text}."
        )

    def create(self, page_label: str = "Data Sources"):
        """Build the Data Sources tab panel and add it to the notebook."""
        panel = wx.ScrolledWindow(self.dialog.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = self.dialog._controls

        self.dialog.add_help_text(
            panel,
            sizer,
            "Choose where weather data comes from and manage provider-specific API keys.",
            left=5,
        )

        source_section = self.dialog.create_section(
            panel,
            sizer,
            "Choose a weather source",
            "Automatic mode combines available providers. Single-source options keep behavior predictable when you prefer one provider.",
        )
        controls["data_source"] = self.dialog.add_labeled_control_row(
            panel,
            source_section,
            "Weather source:",
            lambda parent: wx.Choice(
                parent,
                choices=[
                    "Automatic (combine all available sources)",
                    "National Weather Service (US only, forecast and alerts)",
                    "Open-Meteo (global forecast, no alerts, no API key)",
                    "Pirate Weather (global forecast and alerts, API key)",
                ],
            ),
        )
        controls["data_source"].Bind(wx.EVT_CHOICE, self.dialog._on_data_source_changed)

        auto_section = self.dialog.create_section(
            panel,
            sizer,
            "Automatic mode",
            "Choose how aggressively Automatic mode uses APIs, then fine-tune which sources it may use and how NWS picks a station for current conditions.",
        )
        controls["source_settings_summary"] = wx.TextCtrl(
            panel,
            value=self._get_source_settings_summary_text(),
            size=(-1, 52),
            style=wx.TE_MULTILINE | wx.TE_NO_VSCROLL | wx.TE_READONLY,
        )
        auto_section.Add(
            controls["source_settings_summary"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )
        controls["configure_source_settings"] = wx.Button(
            panel,
            label="Configure automatic mode budget and sources...",
        )
        controls["configure_source_settings"].Bind(
            wx.EVT_BUTTON,
            self.dialog._on_configure_source_settings,
        )
        auto_section.Add(
            controls["configure_source_settings"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )

        keys_section = self.dialog.create_section(
            panel,
            sizer,
            "Provider API keys",
            "Pirate Weather needs a key. Stored keys stay in secure storage unless you explicitly export them.",
        )

        self.dialog._pw_config_sizer = wx.BoxSizer(wx.VERTICAL)
        self.dialog._pw_config_sizer.Add(
            wx.StaticText(panel, label="Pirate Weather"),
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )
        controls["pw_key"] = self.dialog.add_labeled_control_row(
            panel,
            self.dialog._pw_config_sizer,
            "Pirate Weather API key:",
            lambda parent: wx.TextCtrl(parent, style=wx.TE_PASSWORD, size=(280, -1)),
            expand_control=True,
        )
        pw_button_row = wx.BoxSizer(wx.HORIZONTAL)
        get_pw_key_btn = wx.Button(panel, label="Get Pirate Weather key")
        get_pw_key_btn.Bind(wx.EVT_BUTTON, self.dialog._on_get_pw_api_key)
        pw_button_row.Add(get_pw_key_btn, 0, wx.RIGHT, 10)
        validate_pw_btn = wx.Button(panel, label="Validate Pirate Weather key")
        validate_pw_btn.Bind(wx.EVT_BUTTON, self.dialog._on_validate_pw_api_key)
        pw_button_row.Add(validate_pw_btn, 0)
        self.dialog._pw_config_sizer.Add(
            pw_button_row,
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )
        self.dialog.add_help_text(
            panel,
            self.dialog._pw_config_sizer,
            "Use this provider for global forecasts and broader alert coverage.",
            left=10,
            bottom=10,
        )
        keys_section.Add(self.dialog._pw_config_sizer, 0, wx.EXPAND)

        panel.SetSizer(sizer)
        self.dialog.notebook.AddPage(panel, page_label)
        return panel

    def _get_source_settings_summary_text(self) -> str:
        """Build summary text shown on the data sources tab."""
        state = (
            getattr(self.dialog, "_source_settings_states", None)
            or self._build_default_source_settings_states()
        )
        return self.build_source_settings_summary_text(state)

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

        pw_key = getattr(settings, "pirate_weather_api_key", "") or ""
        controls["pw_key"].SetValue(str(pw_key))
        self.dialog._original_pw_key = str(pw_key)
        self.dialog._pw_key_cleared = False
        if hasattr(wx, "EVT_TEXT"):

            def _on_pw_key_text(_event, _dlg=self.dialog):
                _dlg._pw_key_cleared = True
                _dlg._update_auto_source_key_state()

            controls["pw_key"].Bind(wx.EVT_TEXT, _on_pw_key_text)

        saved_strategy = getattr(settings, "station_selection_strategy", "hybrid_default")
        strat_idx = (
            _STATION_STRATEGY_VALUES.index(saved_strategy)
            if saved_strategy in _STATION_STRATEGY_VALUES
            else 0
        )
        saved_budget = getattr(settings, "auto_mode_api_budget", "max_coverage")
        budget_idx = (
            _AUTO_MODE_BUDGET_VALUES.index(saved_budget)
            if saved_budget in _AUTO_MODE_BUDGET_VALUES
            else _DEFAULT_BUDGET_INDEX
        )
        saved_us = list(getattr(settings, "auto_sources_us", _DEFAULT_AUTO_SOURCES_US))
        saved_intl = list(
            getattr(settings, "auto_sources_international", _DEFAULT_AUTO_SOURCES_INTERNATIONAL)
        )
        self.dialog._source_settings_states = {
            "auto_mode_api_budget": budget_idx,
            "auto_sources_us": saved_us or list(_DEFAULT_AUTO_SOURCES_US),
            "auto_sources_international": saved_intl or list(_DEFAULT_AUTO_SOURCES_INTERNATIONAL),
            "station_selection_strategy": strat_idx,
        }
        self.refresh_source_settings_summary()
        self.dialog._update_api_key_visibility()

    def save(self) -> dict:
        """Return Data Sources tab settings as a dict."""
        controls = self.dialog._controls
        state = getattr(self.dialog, "_source_settings_states", None) or {}

        source_priority_us = self._get_state_sources(state, "us")
        source_priority_intl = self._get_state_sources(state, "international")

        strat_idx = max(0, state.get("station_selection_strategy", 0))
        station_strategy = _STATION_STRATEGY_VALUES[strat_idx]
        budget_idx = max(0, state.get("auto_mode_api_budget", _DEFAULT_BUDGET_INDEX))
        auto_mode_api_budget = _AUTO_MODE_BUDGET_VALUES[
            min(budget_idx, len(_AUTO_MODE_BUDGET_VALUES) - 1)
        ]

        return {
            "data_source": _SOURCE_VALUES[controls["data_source"].GetSelection()],
            "pirate_weather_api_key": controls["pw_key"].GetValue(),
            "source_priority_us": source_priority_us,
            "source_priority_international": source_priority_intl,
            "auto_mode_api_budget": auto_mode_api_budget,
            "auto_sources_us": source_priority_us or ["openmeteo"],
            "auto_sources_international": source_priority_intl or ["openmeteo"],
            "openmeteo_weather_model": "best_match",
            "station_selection_strategy": station_strategy,
        }

    def setup_accessibility(self):
        """Set accessibility names for Data Sources tab controls."""
        controls = self.dialog._controls
        names = {
            "data_source": "Weather source",
            "pw_key": "Pirate Weather API key",
            "source_settings_summary": "Automatic mode source summary",
            "configure_source_settings": "Configure automatic mode budget and sources",
        }
        for key, name in names.items():
            controls[key].SetName(name)
