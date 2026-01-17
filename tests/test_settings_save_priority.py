"""Tests for saving priority settings."""

from unittest.mock import MagicMock


class TestSavePrioritySettings:
    """Test saving priority settings from dialog."""

    def test_collect_display_priority_settings(self):
        """collect_settings_from_ui should collect verbosity, order, and override settings."""
        from accessiweather.dialogs.settings_handlers import _collect_display_priority_settings
        from accessiweather.models.config import AppSettings

        dialog = MagicMock()
        dialog.verbosity_selection = MagicMock()
        dialog.verbosity_selection.value = "Standard (recommended)"
        dialog.verbosity_display_to_value = {"Standard (recommended)": "standard"}

        # Mock ListSource items with value attribute
        mock_item1 = MagicMock()
        mock_item1.value = "Temperature"
        mock_item2 = MagicMock()
        mock_item2.value = "Wind"

        dialog.category_order_list = MagicMock()
        dialog.category_order_list.items = [mock_item1, mock_item2]

        dialog.severe_weather_override_switch = MagicMock()
        dialog.severe_weather_override_switch.value = True

        current_settings = AppSettings()
        settings = _collect_display_priority_settings(dialog, current_settings)

        assert settings["verbosity_level"] == "standard"
        assert settings["category_order"] == ["temperature", "wind"]
        assert settings["severe_weather_override"] is True

    def test_collect_display_priority_settings_minimal(self):
        """collect_settings_from_ui should handle minimal verbosity."""
        from accessiweather.dialogs.settings_handlers import _collect_display_priority_settings
        from accessiweather.models.config import AppSettings

        dialog = MagicMock()
        dialog.verbosity_selection = MagicMock()
        dialog.verbosity_selection.value = "Minimal (essentials only)"
        dialog.verbosity_display_to_value = {"Minimal (essentials only)": "minimal"}

        # Mock ListSource items
        mock_items = []
        for name in ["Wind", "Temperature", "Precipitation"]:
            item = MagicMock()
            item.value = name
            mock_items.append(item)

        dialog.category_order_list = MagicMock()
        dialog.category_order_list.items = mock_items

        dialog.severe_weather_override_switch = MagicMock()
        dialog.severe_weather_override_switch.value = False

        current_settings = AppSettings()
        settings = _collect_display_priority_settings(dialog, current_settings)

        assert settings["verbosity_level"] == "minimal"
        assert settings["category_order"] == ["wind", "temperature", "precipitation"]
        assert settings["severe_weather_override"] is False

    def test_collect_display_priority_settings_detailed(self):
        """collect_settings_from_ui should handle detailed verbosity."""
        from accessiweather.dialogs.settings_handlers import _collect_display_priority_settings
        from accessiweather.models.config import AppSettings

        dialog = MagicMock()
        dialog.verbosity_selection = MagicMock()
        dialog.verbosity_selection.value = "Detailed (all available info)"
        dialog.verbosity_display_to_value = {"Detailed (all available info)": "detailed"}

        dialog.category_order_list = None  # Test fallback to current_settings

        dialog.severe_weather_override_switch = MagicMock()
        dialog.severe_weather_override_switch.value = True

        current_settings = AppSettings(
            category_order=["uv_index", "humidity_pressure", "temperature"]
        )
        settings = _collect_display_priority_settings(dialog, current_settings)

        assert settings["verbosity_level"] == "detailed"
        # Should fall back to current_settings when list is None
        assert settings["category_order"] == ["uv_index", "humidity_pressure", "temperature"]
        assert settings["severe_weather_override"] is True

    def test_apply_display_priority_settings(self):
        """apply_settings_to_ui should set verbosity, order, and override widgets."""
        from accessiweather.dialogs.settings_handlers import _apply_display_priority_settings
        from accessiweather.models.config import AppSettings

        dialog = MagicMock()
        dialog.verbosity_selection = MagicMock()
        dialog.verbosity_value_to_display = {
            "minimal": "Minimal (essentials only)",
            "standard": "Standard (recommended)",
            "detailed": "Detailed (all available info)",
        }
        dialog.category_order_list = MagicMock()
        dialog.severe_weather_override_switch = MagicMock()

        settings = AppSettings(
            verbosity_level="minimal",
            category_order=["wind", "temperature"],
            severe_weather_override=False,
        )

        _apply_display_priority_settings(dialog, settings)

        assert dialog.verbosity_selection.value == "Minimal (essentials only)"
        assert dialog.category_order_list.items == ["Wind", "Temperature"]
        assert dialog.severe_weather_override_switch.value is False
