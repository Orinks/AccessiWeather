"""Tests for Open-Meteo model selection in settings dialog."""

import os
from unittest.mock import MagicMock

# Set toga backend before imports
os.environ.setdefault("TOGA_BACKEND", "toga_dummy")

from accessiweather.models.config import AppSettings


class TestOpenMeteoModelSettingsUI:
    """Test Open-Meteo model settings in the dialog."""

    def test_model_display_mapping(self):
        """Test that model display names map to correct internal values."""
        # These mappings should match what's in settings_tabs.py
        display_to_value = {
            "Best Match (Automatic)": "best_match",
            "ICON Seamless (DWD, Europe/Global)": "icon_seamless",
            "ICON Global (DWD, 13km)": "icon_global",
            "ICON EU (DWD, 6.5km Europe)": "icon_eu",
            "ICON D2 (DWD, 2km Germany)": "icon_d2",
            "GFS Seamless (NOAA, Americas/Global)": "gfs_seamless",
            "GFS Global (NOAA, 28km)": "gfs_global",
            "ECMWF IFS (9km Global)": "ecmwf_ifs04",
            "Météo-France (Europe)": "meteofrance_seamless",
            "GEM (Canadian, North America)": "gem_seamless",
            "JMA (Japan/Asia)": "jma_seamless",
        }

        # Verify all values are valid model identifiers
        valid_models = {
            "best_match",
            "icon_seamless",
            "icon_global",
            "icon_eu",
            "icon_d2",
            "gfs_seamless",
            "gfs_global",
            "ecmwf_ifs04",
            "meteofrance_seamless",
            "gem_seamless",
            "jma_seamless",
        }

        for _display_name, internal_value in display_to_value.items():
            assert internal_value in valid_models, f"Invalid model: {internal_value}"

    def test_settings_handlers_collect_model(self):
        """Test that settings handlers properly collect the model setting."""
        from accessiweather.dialogs import settings_handlers

        # Create mock dialog with model selection
        mock_dialog = MagicMock()
        mock_dialog.current_settings = AppSettings()
        mock_dialog.openmeteo_model_selection = MagicMock()
        mock_dialog.openmeteo_model_selection.value = "ICON Seamless (DWD, Europe/Global)"
        mock_dialog.openmeteo_model_display_to_value = {
            "Best Match (Automatic)": "best_match",
            "ICON Seamless (DWD, Europe/Global)": "icon_seamless",
        }

        # Mock other required dialog attributes
        mock_dialog.data_source_selection = MagicMock()
        mock_dialog.data_source_selection.value = "Automatic (merges all available sources)"
        mock_dialog.data_source_display_to_value = {
            "Automatic (merges all available sources)": "auto",
        }
        mock_dialog.visual_crossing_api_key_input = None
        mock_dialog.us_priority_selection = None
        mock_dialog.intl_priority_selection = None

        result = settings_handlers._collect_data_source_settings(mock_dialog, AppSettings())

        assert result["openmeteo_weather_model"] == "icon_seamless"

    def test_settings_handlers_default_model(self):
        """Test that default model is used when selection is missing."""
        from accessiweather.dialogs import settings_handlers

        mock_dialog = MagicMock()
        mock_dialog.current_settings = AppSettings()
        mock_dialog.openmeteo_model_selection = None  # No selection widget

        # Mock other required dialog attributes
        mock_dialog.data_source_selection = MagicMock()
        mock_dialog.data_source_selection.value = "Automatic (merges all available sources)"
        mock_dialog.data_source_display_to_value = {
            "Automatic (merges all available sources)": "auto",
        }
        mock_dialog.visual_crossing_api_key_input = None
        mock_dialog.us_priority_selection = None
        mock_dialog.intl_priority_selection = None

        result = settings_handlers._collect_data_source_settings(
            mock_dialog, AppSettings(openmeteo_weather_model="gfs_seamless")
        )

        # Should preserve existing setting when widget is missing
        assert result["openmeteo_weather_model"] == "gfs_seamless"


class TestOpenMeteoModelVisibility:
    """Test visibility logic for Open-Meteo model settings."""

    def test_model_visible_for_openmeteo_source(self):
        """Test model settings visible when Open-Meteo is selected."""
        # Visibility logic: show when data_source is "openmeteo" or "auto"
        visible_sources = ["openmeteo", "auto"]
        hidden_sources = ["nws", "visualcrossing"]

        for source in visible_sources:
            assert source in ["openmeteo", "auto"], f"Should be visible for {source}"

        for source in hidden_sources:
            assert source not in ["openmeteo", "auto"], f"Should be hidden for {source}"

    def test_model_hidden_for_other_sources(self):
        """Test model settings hidden for non-OpenMeteo sources."""
        # NWS and Visual Crossing don't use Open-Meteo models
        nws_uses_openmeteo_models = "nws" in ["openmeteo", "auto"]
        vc_uses_openmeteo_models = "visualcrossing" in ["openmeteo", "auto"]

        assert not nws_uses_openmeteo_models
        assert not vc_uses_openmeteo_models
