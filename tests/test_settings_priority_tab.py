"""Tests for Display Priority settings (now integrated into Display tab)."""

from unittest.mock import MagicMock

import toga


class MockOptionContainerContent:
    """Mock for OptionContainer.content that supports append(title, box)."""

    def __init__(self):
        """Initialize with empty items list."""
        self._items = []

    def append(self, title, box):
        self._items.append((title, box))

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(self._items)


def create_mock_dialog(
    verbosity_level="standard",
    category_order=None,
    severe_weather_override=True,
):
    """Create a mock dialog with specified settings for testing."""
    if category_order is None:
        category_order = ["temperature", "wind"]

    dialog = MagicMock()
    dialog.current_settings = MagicMock()
    # Display Priority settings
    dialog.current_settings.verbosity_level = verbosity_level
    dialog.current_settings.category_order = category_order
    dialog.current_settings.severe_weather_override = severe_weather_override
    # Other Display tab settings
    dialog.current_settings.temperature_unit = "both"
    dialog.current_settings.show_dewpoint = True
    dialog.current_settings.show_visibility = True
    dialog.current_settings.show_uv_index = True
    dialog.current_settings.show_pressure_trend = True
    dialog.current_settings.show_detailed_forecast = True
    dialog.current_settings.time_display_mode = "local"
    dialog.current_settings.time_format_12hour = True
    dialog.current_settings.show_timezone_suffix = False
    dialog.current_settings.html_render_current_conditions = True
    dialog.current_settings.html_render_forecast = True
    dialog.current_settings.taskbar_icon_text_enabled = False
    dialog.current_settings.taskbar_icon_dynamic_enabled = True
    dialog.current_settings.taskbar_icon_text_format = "{temp} {condition}"
    dialog.option_container = MagicMock()
    dialog.option_container.content = MockOptionContainerContent()
    return dialog


class TestDisplayPriorityInDisplayTab:
    """Test Display Priority settings integrated in Display tab."""

    def test_verbosity_dropdown_exists(self):
        """Settings dialog should have verbosity dropdown in Display tab."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog()
        create_display_tab(dialog)

        assert hasattr(dialog, "verbosity_selection")
        assert hasattr(dialog, "category_order_list")
        assert hasattr(dialog, "severe_weather_override_switch")

    def test_tab_added_to_option_container(self):
        """Tab should be added to option container with title 'Display'."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog()
        create_display_tab(dialog)

        assert len(dialog.option_container.content) == 1
        title, box = dialog.option_container.content._items[0]
        assert title == "Display"
        assert box is dialog.display_tab

    def test_verbosity_selection_items(self):
        """Verbosity selection should have the correct options."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog()
        create_display_tab(dialog)

        assert isinstance(dialog.verbosity_selection, toga.Selection)
        # Selection.items is a ListSource with Row objects; get the value attribute
        items_list = [item.value for item in dialog.verbosity_selection.items]
        assert "Minimal (essentials only)" in items_list
        assert "Standard (recommended)" in items_list
        assert "Detailed (all available info)" in items_list

    def test_verbosity_selection_default_value(self):
        """Verbosity selection should default to standard."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog(verbosity_level="standard")
        create_display_tab(dialog)

        assert dialog.verbosity_selection.value == "Standard (recommended)"

    def test_verbosity_selection_minimal(self):
        """Verbosity selection should show minimal when configured."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog(verbosity_level="minimal")
        create_display_tab(dialog)

        assert dialog.verbosity_selection.value == "Minimal (essentials only)"

    def test_verbosity_selection_detailed(self):
        """Verbosity selection should show detailed when configured."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog(verbosity_level="detailed")
        create_display_tab(dialog)

        assert dialog.verbosity_selection.value == "Detailed (all available info)"

    def test_verbosity_display_to_value_mapping(self):
        """Verbosity display to value mapping should be correct."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog()
        create_display_tab(dialog)

        assert dialog.verbosity_display_to_value == {
            "Minimal (essentials only)": "minimal",
            "Standard (recommended)": "standard",
            "Detailed (all available info)": "detailed",
        }

    def test_verbosity_value_to_display_mapping(self):
        """Verbosity value to display mapping should be the inverse."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog()
        create_display_tab(dialog)

        assert dialog.verbosity_value_to_display == {
            "minimal": "Minimal (essentials only)",
            "standard": "Standard (recommended)",
            "detailed": "Detailed (all available info)",
        }

    def test_category_order_list_exists(self):
        """Category order list should be created as a Selection widget."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog(category_order=["temperature", "precipitation", "wind"])
        create_display_tab(dialog)

        assert isinstance(dialog.category_order_list, toga.Selection)
        items_list = [item.value for item in dialog.category_order_list.items]
        assert "Temperature" in items_list
        assert "Precipitation" in items_list
        assert "Wind" in items_list

    def test_category_order_list_uses_display_names(self):
        """Category order list should use friendly display names."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog(
            category_order=["humidity_pressure", "visibility_clouds", "uv_index"]
        )
        create_display_tab(dialog)

        items_list = [item.value for item in dialog.category_order_list.items]
        assert "Humidity & Pressure" in items_list
        assert "Visibility & Clouds" in items_list
        assert "UV Index" in items_list

    def test_category_up_button_exists(self):
        """Up button should exist for category reordering."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog()
        create_display_tab(dialog)

        assert isinstance(dialog.category_up_button, toga.Button)
        assert dialog.category_up_button.text == "Up"

    def test_category_down_button_exists(self):
        """Down button should exist for category reordering."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog()
        create_display_tab(dialog)

        assert isinstance(dialog.category_down_button, toga.Button)
        assert dialog.category_down_button.text == "Down"

    def test_reset_order_button_exists(self):
        """Reset to default order button should exist."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog()
        create_display_tab(dialog)

        assert isinstance(dialog.reset_order_button, toga.Button)
        assert dialog.reset_order_button.text == "Reset to Default Order"

    def test_severe_weather_override_switch_exists(self):
        """Severe weather override switch should exist."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog(severe_weather_override=True)
        create_display_tab(dialog)

        assert isinstance(dialog.severe_weather_override_switch, toga.Switch)
        assert dialog.severe_weather_override_switch.value is True

    def test_severe_weather_override_switch_disabled(self):
        """Severe weather override switch should reflect disabled state."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog(severe_weather_override=False)
        create_display_tab(dialog)

        assert dialog.severe_weather_override_switch.value is False

    def test_accessibility_labels_exist(self):
        """All interactive elements should have aria labels for accessibility."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog()
        create_display_tab(dialog)

        assert dialog.verbosity_selection.aria_label == "Verbosity level selection"
        assert dialog.category_order_list.aria_label == "Category order"
        assert dialog.severe_weather_override_switch.aria_label == "Severe weather override toggle"

    def test_accessibility_descriptions_exist(self):
        """Interactive elements should have aria descriptions for screen readers."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog()
        create_display_tab(dialog)

        assert dialog.verbosity_selection.aria_description is not None
        assert len(dialog.verbosity_selection.aria_description) > 0
        assert dialog.category_order_list.aria_description is not None
        assert len(dialog.category_order_list.aria_description) > 0
        assert dialog.severe_weather_override_switch.aria_description is not None
        assert len(dialog.severe_weather_override_switch.aria_description) > 0

    def test_button_handlers_connected(self):
        """Up/Down/Reset buttons should be connected to dialog handlers."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog()
        create_display_tab(dialog)

        # Buttons should have handlers assigned (toga wraps them)
        assert dialog.category_up_button.on_press is not None
        assert dialog.category_down_button.on_press is not None
        assert dialog.reset_order_button.on_press is not None

    def test_display_tab_box_exists(self):
        """The display tab box should be stored on the dialog."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog()
        create_display_tab(dialog)

        assert hasattr(dialog, "display_tab")
        assert isinstance(dialog.display_tab, toga.Box)

    def test_unknown_category_uses_raw_name(self):
        """Unknown categories should fall back to raw name."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog(category_order=["unknown_category"])
        create_display_tab(dialog)

        items_list = [item.value for item in dialog.category_order_list.items]
        assert "unknown_category" in items_list

    def test_verbosity_selection_has_id(self):
        """Verbosity selection should have an ID for testing/automation."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog()
        create_display_tab(dialog)

        assert dialog.verbosity_selection.id == "verbosity_selection"

    def test_category_order_list_has_id(self):
        """Category order list should have an ID for testing/automation."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog()
        create_display_tab(dialog)

        assert dialog.category_order_list.id == "category_order_list"

    def test_severe_weather_switch_has_id(self):
        """Severe weather override switch should have an ID."""
        from accessiweather.dialogs.settings_tabs import create_display_tab

        dialog = create_mock_dialog()
        create_display_tab(dialog)

        assert dialog.severe_weather_override_switch.id == "severe_weather_override_switch"
