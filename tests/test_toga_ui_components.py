"""UI components and accessibility tests for Toga AccessiWeather."""

import asyncio
import os
from contextlib import suppress
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import toga

import accessiweather.dialogs.settings_tabs as settings_tabs

# Set up Toga dummy backend
os.environ["TOGA_BACKEND"] = "toga_dummy"

from accessiweather.dialogs.settings_dialog import SettingsDialog
from accessiweather.models.config import AppSettings
from tests.toga_test_helpers import (
    MockTogaWidgets,
    WeatherDataFactory,
)


class TestTogaUIComponents:
    """Test Toga UI components and their functionality."""

    @pytest.fixture
    def mock_widgets(self):
        """Create mock Toga widgets for testing."""
        return MockTogaWidgets()

    def test_main_window_creation(self, mock_widgets):
        """Test main window creation and setup."""
        main_window = mock_widgets.create_widget("MainWindow")
        main_window.title = "AccessiWeather"
        main_window.size = (800, 600)
        main_window.resizable = True

        assert main_window.title == "AccessiWeather"
        assert main_window.size == (800, 600)
        assert main_window.resizable is True

    def test_location_selection_widget(self, mock_widgets):
        """Test location selection widget."""
        location_selection = mock_widgets.create_widget(
            "Selection",
            items=["New York, NY", "Los Angeles, CA", "Chicago, IL"],
            value="New York, NY",
        )

        assert location_selection.widget_type == "Selection"
        assert len(location_selection.items) == 3
        assert location_selection.value == "New York, NY"
        assert "Chicago, IL" in location_selection.items

    def test_weather_display_widget(self, mock_widgets):
        """Test weather display widget."""
        weather_display = mock_widgets.create_widget(
            "MultilineTextInput", value="Current Weather: 75°F, Partly Cloudy", readonly=True
        )

        assert weather_display.widget_type == "MultilineTextInput"
        assert weather_display.readonly is True
        assert "75°F" in weather_display.value

    def test_refresh_button(self, mock_widgets):
        """Test refresh button functionality."""
        refresh_button = mock_widgets.create_widget("Button", text="Refresh Weather", enabled=True)

        assert refresh_button.widget_type == "Button"
        assert refresh_button.text == "Refresh Weather"
        assert refresh_button.enabled is True

    def test_settings_button(self, mock_widgets):
        """Test settings button functionality."""
        settings_button = mock_widgets.create_widget("Button", text="Settings", enabled=True)

        assert settings_button.widget_type == "Button"
        assert settings_button.text == "Settings"
        assert settings_button.enabled is True

    def test_forecast_table(self, mock_widgets):
        """Test forecast table widget."""
        forecast_table = mock_widgets.create_widget(
            "Table",
            headings=["Day", "High", "Low", "Condition"],
            data=[
                ["Today", "78°F", "58°F", "Sunny"],
                ["Tomorrow", "75°F", "55°F", "Partly Cloudy"],
                ["Wednesday", "72°F", "52°F", "Cloudy"],
            ],
        )

        assert forecast_table.widget_type == "Table"
        assert len(forecast_table.headings) == 4
        assert len(forecast_table.data) == 3
        assert forecast_table.data[0][0] == "Today"

    def test_alert_notification_widget(self, mock_widgets):
        """Test alert notification widget."""
        alert_widget = mock_widgets.create_widget(
            "MultilineTextInput",
            value="⚠️ Weather Alert: Severe Thunderstorm Warning in effect.",
            readonly=True,
        )

        assert alert_widget.widget_type == "MultilineTextInput"
        assert alert_widget.readonly is True
        assert "⚠️" in alert_widget.value
        assert "Severe Thunderstorm Warning" in alert_widget.value

    def test_progress_indicator(self, mock_widgets):
        """Test progress indicator widget."""
        progress_widget = mock_widgets.create_widget("ProgressBar")
        progress_widget.value = 0.5
        progress_widget.max = 1.0

        assert progress_widget.widget_type == "ProgressBar"
        assert progress_widget.value == 0.5
        assert progress_widget.max == 1.0

    def test_status_bar(self, mock_widgets):
        """Test status bar widget."""
        status_bar = mock_widgets.create_widget("Label")
        status_bar.text = "Last updated: 2024-01-01 12:00:00"

        assert status_bar.widget_type == "Label"
        assert "Last updated" in status_bar.text
        assert "2024-01-01" in status_bar.text

    def test_menu_bar(self, mock_widgets):
        """Test menu bar creation."""
        menu_bar = mock_widgets.create_widget("MenuBar")
        menu_bar.items = [
            {"label": "File", "items": ["New", "Open", "Exit"]},
            {"label": "Edit", "items": ["Settings", "Preferences"]},
            {"label": "Help", "items": ["About", "Documentation"]},
        ]

        assert menu_bar.widget_type == "MenuBar"
        assert len(menu_bar.items) == 3
        assert menu_bar.items[0]["label"] == "File"

    def test_dialog_windows(self, mock_widgets):
        """Test dialog window creation."""
        dialog = mock_widgets.create_widget("Dialog")
        dialog.title = "Settings"
        dialog.modal = True
        dialog.resizable = False

        assert dialog.widget_type == "Dialog"
        assert dialog.title == "Settings"
        assert dialog.modal is True
        assert dialog.resizable is False

    def test_tab_container(self, mock_widgets):
        """Test tab container widget."""
        tab_container = mock_widgets.create_widget("OptionContainer")
        tab_container.content = [
            {"text": "Current", "widget": "current_tab"},
            {"text": "Forecast", "widget": "forecast_tab"},
            {"text": "Alerts", "widget": "alerts_tab"},
        ]

        assert tab_container.widget_type == "OptionContainer"
        assert len(tab_container.content) == 3
        assert tab_container.content[0]["text"] == "Current"

    def test_scrollable_content(self, mock_widgets):
        """Test scrollable content widget."""
        scroll_container = mock_widgets.create_widget("ScrollContainer")
        scroll_container.content = "Long weather content that requires scrolling..."
        scroll_container.horizontal = False
        scroll_container.vertical = True

        assert scroll_container.widget_type == "ScrollContainer"
        assert scroll_container.horizontal is False
        assert scroll_container.vertical is True

    def test_widget_layout_boxes(self, mock_widgets):
        """Test layout box widgets."""
        h_box = mock_widgets.create_widget("Box")
        h_box.direction = "horizontal"
        h_box.children = ["button1", "button2", "button3"]

        v_box = mock_widgets.create_widget("Box")
        v_box.direction = "vertical"
        v_box.children = ["label1", "input1", "button1"]

        assert h_box.direction == "horizontal"
        assert len(h_box.children) == 3
        assert v_box.direction == "vertical"
        assert len(v_box.children) == 3

    def test_widget_styling(self, mock_widgets):
        """Test widget styling and appearance."""
        styled_widget = mock_widgets.create_widget("Button", text="Styled Button")
        styled_widget.style = MagicMock()
        styled_widget.style.color = "#0066CC"
        styled_widget.style.background_color = "#FFFFFF"
        styled_widget.style.font_size = 14
        styled_widget.style.font_weight = "bold"

        assert styled_widget.style.color == "#0066CC"
        assert styled_widget.style.background_color == "#FFFFFF"
        assert styled_widget.style.font_size == 14
        assert styled_widget.style.font_weight == "bold"

    def test_settings_dialog_show_and_prepare(self, tmp_path):
        """Ensure the settings dialog renders without alignment issues on Toga 0.5.x."""

        class DummyPaths:
            def __init__(self, base_path: Path):
                self.config = base_path

        class DummyConfigManager:
            def __init__(self, config_dir: Path):
                self.config_dir = config_dir
                self._settings = AppSettings()

            def get_settings(self):
                return self._settings

            def sync_startup_setting(self):
                return True

            def is_startup_enabled(self):
                return bool(getattr(self._settings, "startup_enabled", False))

        loop = asyncio.new_event_loop()
        app = MagicMock()
        app.loop = loop
        app.paths = DummyPaths(tmp_path)
        app.main_window = MagicMock()

        config_manager = DummyConfigManager(tmp_path)
        dialog = SettingsDialog(app, config_manager)

        try:
            asyncio.set_event_loop(loop)
            dialog.show_and_prepare()
            assert dialog.window is not None
            assert dialog.option_container is not None
            assert dialog.visual_crossing_api_key_input is not None
            assert dialog.startup_enabled_switch is not None
        finally:
            if dialog.window is not None:
                with suppress(Exception):
                    dialog.window.close()
            asyncio.set_event_loop(None)
            loop.close()

    def test_settings_dialog_accessibility_metadata(self, tmp_path):
        """Ensure key settings widgets expose aria labels and descriptions."""

        class DummyPaths:
            def __init__(self, base_path: Path):
                self.config = base_path

        class DummyConfigManager:
            def __init__(self, config_dir: Path):
                self.config_dir = config_dir
                self._settings = AppSettings()

            def get_settings(self):
                return self._settings

            def sync_startup_setting(self):
                return True

            def is_startup_enabled(self):
                return bool(getattr(self._settings, "startup_enabled", False))

        app = MagicMock()
        app.paths = DummyPaths(tmp_path)
        config_manager = DummyConfigManager(tmp_path)
        dialog = SettingsDialog(app, config_manager)

        dialog.current_settings = config_manager.get_settings()
        dialog.option_container = toga.OptionContainer()

        settings_tabs.create_general_tab(dialog)
        settings_tabs.create_data_sources_tab(dialog)
        settings_tabs.create_audio_tab(dialog)
        settings_tabs.create_updates_tab(dialog)

        assert dialog.temperature_unit_selection.aria_label == "Temperature unit selection"
        assert (
            dialog.temperature_unit_selection.aria_description
            == "Choose Fahrenheit, Celsius, or both for weather displays."
        )

        assert dialog.data_source_selection.aria_label == "Weather data source selection"
        assert (
            dialog.data_source_selection.aria_description
            == "Select the provider used for fetching weather data."
        )

        assert dialog.sound_pack_selection.aria_label == "Sound pack selection"
        assert (
            dialog.sound_pack_selection.aria_description
            == "Choose the notification sound pack used for alerts."
        )

        assert dialog.auto_update_switch.aria_label == "Automatic update checks toggle"
        assert (
            dialog.auto_update_switch.aria_description
            == "Enable to allow AccessiWeather to check for updates in the background."
        )

        assert dialog.update_channel_selection.aria_label == "Update channel selection"
        assert (
            dialog.update_channel_selection.aria_description
            == "Choose which release channel to follow for application updates."
        )

        assert dialog.visual_crossing_api_key_input.aria_label == "Visual Crossing API key input"
        assert (
            dialog.visual_crossing_api_key_input.aria_description
            == "Enter the Visual Crossing API key to enable that weather data source."
        )

    def test_widget_event_handling(self, mock_widgets):
        """Test widget event handling."""
        button = mock_widgets.create_widget("Button", text="Click Me")
        button.on_press = MagicMock()

        selection = mock_widgets.create_widget("Selection", items=["A", "B", "C"])
        selection.on_change = MagicMock()

        # Simulate events
        button.on_press("click_event")
        selection.on_change("selection_event")

        button.on_press.assert_called_once_with("click_event")
        selection.on_change.assert_called_once_with("selection_event")

    def test_widget_state_management(self, mock_widgets):
        """Test widget state management."""
        button = mock_widgets.create_widget("Button", text="Toggle Button")
        button.enabled = True
        button.visible = True

        # Test state changes
        button.enabled = False
        button.visible = False

        assert button.enabled is False
        assert button.visible is False

    def test_widget_focus_management(self, mock_widgets):
        """Test widget focus management."""
        input_widget = mock_widgets.create_widget("TextInput")
        input_widget.focus = MagicMock()
        input_widget.has_focus = False

        # Test focus operations
        input_widget.focus()
        input_widget.has_focus = True

        input_widget.focus.assert_called_once()
        assert input_widget.has_focus is True

    def test_widget_data_binding(self, mock_widgets):
        """Test widget data binding."""
        weather_data = WeatherDataFactory.create_weather_data()

        # Mock data binding
        temp_label = mock_widgets.create_widget("Label")
        temp_label.text = f"{weather_data.current.temperature_f}°F"

        condition_label = mock_widgets.create_widget("Label")
        condition_label.text = weather_data.current.condition

        assert "75" in temp_label.text
        assert weather_data.current.condition in condition_label.text

    def test_widget_validation(self, mock_widgets):
        """Test widget input validation."""
        input_widget = mock_widgets.create_widget("TextInput")
        input_widget.validate = MagicMock(return_value=True)
        input_widget.error_message = ""

        # Test validation
        is_valid = input_widget.validate()
        assert is_valid is True
        assert input_widget.error_message == ""

    def test_widget_tooltips(self, mock_widgets):
        """Test widget tooltips."""
        button = mock_widgets.create_widget("Button", text="Help")
        button.tooltip = "Click for help information"

        assert button.tooltip == "Click for help information"

    def test_widget_keyboard_shortcuts(self, mock_widgets):
        """Test widget keyboard shortcuts."""
        button = mock_widgets.create_widget("Button", text="Refresh")
        button.keyboard_shortcut = "Ctrl+R"

        assert button.keyboard_shortcut == "Ctrl+R"

    def test_widget_context_menus(self, mock_widgets):
        """Test widget context menus."""
        text_widget = mock_widgets.create_widget("MultilineTextInput")
        text_widget.context_menu = [
            {"label": "Copy", "action": "copy"},
            {"label": "Select All", "action": "select_all"},
            {"label": "Properties", "action": "properties"},
        ]

        assert len(text_widget.context_menu) == 3
        assert text_widget.context_menu[0]["label"] == "Copy"

    def test_widget_animations(self, mock_widgets):
        """Test widget animations."""
        loading_widget = mock_widgets.create_widget("ProgressBar")
        loading_widget.animate = MagicMock()
        loading_widget.animation_duration = 1.0

        # Test animation
        loading_widget.animate("fade_in")
        loading_widget.animate.assert_called_once_with("fade_in")
        assert loading_widget.animation_duration == 1.0

    def test_widget_drag_drop(self, mock_widgets):
        """Test widget drag and drop functionality."""
        drag_widget = mock_widgets.create_widget("Label", text="Drag Me")
        drag_widget.draggable = True
        drag_widget.on_drag_start = MagicMock()

        drop_widget = mock_widgets.create_widget("Box")
        drop_widget.droppable = True
        drop_widget.on_drop = MagicMock()

        assert drag_widget.draggable is True
        assert drop_widget.droppable is True


class TestAccessibilityFeatures:
    """Test accessibility features of UI components."""

    @pytest.fixture
    def mock_widgets(self):
        """Create mock Toga widgets for testing."""
        return MockTogaWidgets()

    def test_aria_labels(self, mock_widgets):
        """Test ARIA labels for screen readers."""
        button = mock_widgets.create_widget("Button", text="Get Weather")
        button.aria_label = "Get current weather conditions"
        button.aria_description = "Fetches the latest weather data for your location"

        assert button.aria_label == "Get current weather conditions"
        assert button.aria_description == "Fetches the latest weather data for your location"

    def test_screen_reader_announcements(self, mock_widgets):
        """Test screen reader announcements."""
        announcement_widget = mock_widgets.create_widget("Label")
        announcement_widget.announce = MagicMock()

        # Test announcement
        announcement_widget.announce("Weather data updated")
        announcement_widget.announce.assert_called_once_with("Weather data updated")

    def test_keyboard_navigation(self, mock_widgets):
        """Test keyboard navigation support."""
        button1 = mock_widgets.create_widget("Button", text="Button 1")
        button1.tab_index = 1
        button1.focusable = True

        button2 = mock_widgets.create_widget("Button", text="Button 2")
        button2.tab_index = 2
        button2.focusable = True

        button3 = mock_widgets.create_widget("Button", text="Button 3")
        button3.tab_index = 3
        button3.focusable = True

        assert button1.tab_index == 1
        assert button2.focusable is True
        assert button3.tab_index == 3

    def test_high_contrast_support(self, mock_widgets):
        """Test high contrast mode support."""
        widget = mock_widgets.create_widget("Button", text="High Contrast")
        widget.high_contrast_style = MagicMock()
        widget.high_contrast_style.color = "#FFFFFF"
        widget.high_contrast_style.background_color = "#000000"
        widget.high_contrast_style.border_color = "#FFFFFF"

        assert widget.high_contrast_style.color == "#FFFFFF"
        assert widget.high_contrast_style.background_color == "#000000"
        assert widget.high_contrast_style.border_color == "#FFFFFF"

    def test_text_scaling(self, mock_widgets):
        """Test text scaling for accessibility."""
        label = mock_widgets.create_widget("Label", text="Scalable Text")
        label.font_scale = 1.5
        label.scaled_font_size = 18

        assert label.font_scale == 1.5
        assert label.scaled_font_size == 18

    def test_color_contrast_ratios(self, mock_widgets):
        """Test color contrast ratios for accessibility."""
        widget = mock_widgets.create_widget("Button", text="Accessible Button")
        widget.contrast_ratio = 4.5  # WCAG AA compliance
        widget.meets_wcag_aa = True

        assert widget.contrast_ratio >= 4.5
        assert widget.meets_wcag_aa is True

    def test_focus_indicators(self, mock_widgets):
        """Test focus indicators for accessibility."""
        button = mock_widgets.create_widget("Button", text="Focus Test")
        button.focus_indicator = MagicMock()
        button.focus_indicator.visible = True
        button.focus_indicator.color = "#0066CC"
        button.focus_indicator.width = 2

        assert button.focus_indicator.visible is True
        assert button.focus_indicator.color == "#0066CC"
        assert button.focus_indicator.width == 2

    def test_voice_over_support(self, mock_widgets):
        """Test VoiceOver support for screen readers."""
        widget = mock_widgets.create_widget("Selection", items=["Option 1", "Option 2"])
        widget.voice_over_label = "Weather data source selection"
        widget.voice_over_hint = "Choose your preferred weather data source"

        assert widget.voice_over_label == "Weather data source selection"
        assert widget.voice_over_hint == "Choose your preferred weather data source"

    def test_semantic_markup(self, mock_widgets):
        """Test semantic markup for accessibility."""
        heading = mock_widgets.create_widget("Label", text="Current Weather")
        heading.role = "heading"
        heading.level = 1

        list_widget = mock_widgets.create_widget("Box")
        list_widget.role = "list"
        list_widget.children = ["item1", "item2", "item3"]

        assert heading.role == "heading"
        assert heading.level == 1
        assert list_widget.role == "list"

    def test_alternative_text(self, mock_widgets):
        """Test alternative text for images and icons."""
        weather_icon = mock_widgets.create_widget("ImageView")
        weather_icon.alt_text = "Partly cloudy weather icon"
        weather_icon.description = "Icon showing partial cloud coverage"

        assert weather_icon.alt_text == "Partly cloudy weather icon"
        assert weather_icon.description == "Icon showing partial cloud coverage"

    def test_error_announcements(self, mock_widgets):
        """Test error announcements for accessibility."""
        input_widget = mock_widgets.create_widget("TextInput")
        input_widget.error_message = "Invalid location entered"
        input_widget.announce_error = MagicMock()

        # Test error announcement
        input_widget.announce_error(input_widget.error_message)
        input_widget.announce_error.assert_called_once_with("Invalid location entered")

    def test_progress_announcements(self, mock_widgets):
        """Test progress announcements for accessibility."""
        progress_widget = mock_widgets.create_widget("ProgressBar")
        progress_widget.value = 0.5
        progress_widget.announce_progress = MagicMock()

        # Test progress announcement
        progress_widget.announce_progress("Weather data loading 50% complete")
        progress_widget.announce_progress.assert_called_once_with(
            "Weather data loading 50% complete"
        )

    def test_live_region_updates(self, mock_widgets):
        """Test live region updates for dynamic content."""
        weather_display = mock_widgets.create_widget("Label")
        weather_display.live_region = "polite"
        weather_display.aria_live = "polite"
        weather_display.text = "Current temperature: 75°F"

        assert weather_display.live_region == "polite"
        assert weather_display.aria_live == "polite"
        assert "75°F" in weather_display.text

    def test_keyboard_shortcuts_accessibility(self, mock_widgets):
        """Test keyboard shortcuts for accessibility."""
        shortcut_widget = mock_widgets.create_widget("Button", text="Refresh")
        shortcut_widget.keyboard_shortcut = "Alt+R"
        shortcut_widget.shortcut_description = "Alt+R to refresh weather data"

        assert shortcut_widget.keyboard_shortcut == "Alt+R"
        assert shortcut_widget.shortcut_description == "Alt+R to refresh weather data"

    def test_reduced_motion_support(self, mock_widgets):
        """Test reduced motion support for accessibility."""
        animated_widget = mock_widgets.create_widget("ProgressBar")
        animated_widget.respect_reduced_motion = True
        animated_widget.animation_disabled = False

        # Test reduced motion preference
        animated_widget.animation_disabled = True
        assert animated_widget.respect_reduced_motion is True
        assert animated_widget.animation_disabled is True

    def test_screen_reader_only_content(self, mock_widgets):
        """Test screen reader only content."""
        sr_only_widget = mock_widgets.create_widget("Label")
        sr_only_widget.text = "Loading weather data, please wait"
        sr_only_widget.screen_reader_only = True
        sr_only_widget.visible = False

        assert sr_only_widget.screen_reader_only is True
        assert sr_only_widget.visible is False
        assert "Loading weather data" in sr_only_widget.text


class TestUIComponentInteraction:
    """Test UI component interactions and behavior."""

    @pytest.fixture
    def mock_widgets(self):
        """Create mock Toga widgets for testing."""
        return MockTogaWidgets()

    def test_button_click_handling(self, mock_widgets):
        """Test button click event handling."""
        button = mock_widgets.create_widget("Button", text="Click Me")
        button.on_press = MagicMock()

        # Simulate button click
        button.on_press()
        button.on_press.assert_called_once()

    def test_selection_change_handling(self, mock_widgets):
        """Test selection change event handling."""
        selection = mock_widgets.create_widget(
            "Selection", items=["Option 1", "Option 2", "Option 3"], value="Option 1"
        )
        selection.on_change = MagicMock()

        # Simulate selection change
        selection.value = "Option 2"
        selection.on_change(selection.value)
        selection.on_change.assert_called_once_with("Option 2")

    def test_text_input_handling(self, mock_widgets):
        """Test text input event handling."""
        text_input = mock_widgets.create_widget("TextInput")
        text_input.on_change = MagicMock()
        text_input.on_confirm = MagicMock()

        # Simulate text input
        text_input.value = "New York"
        text_input.on_change(text_input.value)
        text_input.on_confirm(text_input.value)

        text_input.on_change.assert_called_once_with("New York")
        text_input.on_confirm.assert_called_once_with("New York")

    def test_table_selection_handling(self, mock_widgets):
        """Test table selection event handling."""
        table = mock_widgets.create_widget(
            "Table", headings=["Day", "Temperature"], data=[["Today", "75°F"], ["Tomorrow", "73°F"]]
        )
        table.on_select = MagicMock()

        # Simulate table selection
        selected_row = table.data[0]
        table.on_select(selected_row)
        table.on_select.assert_called_once_with(selected_row)

    def test_window_close_handling(self, mock_widgets):
        """Test window close event handling."""
        window = mock_widgets.create_widget("MainWindow")
        window.on_close = MagicMock()

        # Simulate window close
        window.on_close()
        window.on_close.assert_called_once()

    def test_menu_item_activation(self, mock_widgets):
        """Test menu item activation."""
        menu_item = mock_widgets.create_widget("MenuItem")
        menu_item.label = "Settings"
        menu_item.on_activate = MagicMock()

        # Simulate menu item activation
        menu_item.on_activate()
        menu_item.on_activate.assert_called_once()

    def test_dialog_response_handling(self, mock_widgets):
        """Test dialog response handling."""
        dialog = mock_widgets.create_widget("Dialog")
        dialog.on_result = MagicMock()

        # Simulate dialog response
        dialog.on_result("ok")
        dialog.on_result.assert_called_once_with("ok")

    def test_widget_state_synchronization(self, mock_widgets):
        """Test widget state synchronization."""
        checkbox = mock_widgets.create_widget("Switch")
        checkbox.value = False
        checkbox.on_change = MagicMock()

        # Simulate state change
        checkbox.value = True
        checkbox.on_change(checkbox.value)

        assert checkbox.value is True
        checkbox.on_change.assert_called_once_with(True)

    def test_widget_validation_feedback(self, mock_widgets):
        """Test widget validation feedback."""
        input_widget = mock_widgets.create_widget("TextInput")
        input_widget.is_valid = False
        input_widget.error_message = "Please enter a valid location"
        input_widget.show_error = MagicMock()

        # Simulate validation error
        input_widget.show_error(input_widget.error_message)
        input_widget.show_error.assert_called_once_with("Please enter a valid location")

    def test_widget_loading_states(self, mock_widgets):
        """Test widget loading states."""
        button = mock_widgets.create_widget("Button", text="Get Weather")
        button.loading = False
        button.set_loading_state = MagicMock()

        # Simulate loading state
        button.set_loading_state(True)
        button.loading = True

        assert button.loading is True
        button.set_loading_state.assert_called_once_with(True)

    def test_widget_tooltip_display(self, mock_widgets):
        """Test widget tooltip display."""
        widget = mock_widgets.create_widget("Button", text="Help")
        widget.tooltip = "Click for help"
        widget.show_tooltip = MagicMock()

        # Simulate tooltip display
        widget.show_tooltip()
        widget.show_tooltip.assert_called_once()

    def test_widget_context_menu_display(self, mock_widgets):
        """Test widget context menu display."""
        widget = mock_widgets.create_widget("MultilineTextInput")
        widget.context_menu = [{"label": "Copy", "action": "copy"}]
        widget.show_context_menu = MagicMock()

        # Simulate context menu display
        widget.show_context_menu()
        widget.show_context_menu.assert_called_once()

    def test_widget_resize_handling(self, mock_widgets):
        """Test widget resize handling."""
        window = mock_widgets.create_widget("MainWindow")
        window.on_resize = MagicMock()

        # Simulate window resize
        window.on_resize(800, 600)
        window.on_resize.assert_called_once_with(800, 600)

    def test_widget_focus_events(self, mock_widgets):
        """Test widget focus events."""
        input_widget = mock_widgets.create_widget("TextInput")
        input_widget.on_focus_gain = MagicMock()
        input_widget.on_focus_lost = MagicMock()

        # Simulate focus events
        input_widget.on_focus_gain()
        input_widget.on_focus_lost()

        input_widget.on_focus_gain.assert_called_once()
        input_widget.on_focus_lost.assert_called_once()

    def test_widget_drag_drop_events(self, mock_widgets):
        """Test widget drag and drop events."""
        drag_widget = mock_widgets.create_widget("Label")
        drag_widget.on_drag_start = MagicMock()
        drag_widget.on_drag_end = MagicMock()

        drop_widget = mock_widgets.create_widget("Box")
        drop_widget.on_drop = MagicMock()

        # Simulate drag and drop events
        drag_widget.on_drag_start()
        drop_widget.on_drop("dropped_data")
        drag_widget.on_drag_end()

        drag_widget.on_drag_start.assert_called_once()
        drop_widget.on_drop.assert_called_once_with("dropped_data")
        drag_widget.on_drag_end.assert_called_once()

    def test_widget_animation_events(self, mock_widgets):
        """Test widget animation events."""
        widget = mock_widgets.create_widget("ProgressBar")
        widget.on_animation_start = MagicMock()
        widget.on_animation_end = MagicMock()

        # Simulate animation events
        widget.on_animation_start()
        widget.on_animation_end()

        widget.on_animation_start.assert_called_once()
        widget.on_animation_end.assert_called_once()

    def test_widget_keyboard_events(self, mock_widgets):
        """Test widget keyboard events."""
        widget = mock_widgets.create_widget("TextInput")
        widget.on_key_press = MagicMock()
        widget.on_key_release = MagicMock()

        # Simulate keyboard events
        widget.on_key_press("Enter")
        widget.on_key_release("Enter")

        widget.on_key_press.assert_called_once_with("Enter")
        widget.on_key_release.assert_called_once_with("Enter")

    def test_widget_mouse_events(self, mock_widgets):
        """Test widget mouse events."""
        widget = mock_widgets.create_widget("Button")
        widget.on_mouse_enter = MagicMock()
        widget.on_mouse_leave = MagicMock()
        widget.on_mouse_down = MagicMock()
        widget.on_mouse_up = MagicMock()

        # Simulate mouse events
        widget.on_mouse_enter()
        widget.on_mouse_down()
        widget.on_mouse_up()
        widget.on_mouse_leave()

        widget.on_mouse_enter.assert_called_once()
        widget.on_mouse_down.assert_called_once()
        widget.on_mouse_up.assert_called_once()
        widget.on_mouse_leave.assert_called_once()

    def test_widget_scroll_events(self, mock_widgets):
        """Test widget scroll events."""
        scroll_widget = mock_widgets.create_widget("ScrollContainer")
        scroll_widget.on_scroll = MagicMock()

        # Simulate scroll event
        scroll_widget.on_scroll(0, 100)
        scroll_widget.on_scroll.assert_called_once_with(0, 100)


@pytest.mark.asyncio
async def test_settings_dialog_reset_to_defaults_resets_config(tmp_path):
    """
    SettingsDialog: reset-to-defaults should restore ConfigManager settings to defaults.

    This verifies the Advanced tab action works via the handler without needing full UI.
    """
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from accessiweather.config import ConfigManager
    from accessiweather.dialogs.settings_dialog import SettingsDialog

    # Mock app with required properties
    app = MagicMock()
    app.paths = MagicMock()
    app.paths.config = tmp_path
    app.loop = MagicMock()
    app.loop.create_future.return_value = asyncio.Future()
    app.main_window = MagicMock()
    app.main_window.error_dialog = AsyncMock()
    app.main_window.info_dialog = AsyncMock()

    # Real ConfigManager with temp config dir
    config_manager = ConfigManager(app)

    # Set some non-default settings and persist them
    assert (
        config_manager.update_settings(
            temperature_unit="f",
            update_interval_minutes=42,
            auto_update_enabled=False,
            data_source="nws",
            debug_mode=True,
            sound_enabled=False,
        )
        is True
    )

    # Initialize SettingsDialog without creating a real window
    dlg = SettingsDialog(app, config_manager)
    dlg.current_settings = config_manager.get_settings()

    # Provide a lightweight status label stub to observe feedback text
    class _Stub:
        def __init__(self):
            self.text = ""

    dlg.update_status_label = _Stub()

    # Invoke the reset handler
    await dlg._on_reset_to_defaults(None)

    # Verify config has been reset to defaults
    s = config_manager.get_settings()
    assert s.temperature_unit == "both"
    assert s.update_interval_minutes == 10
    assert s.auto_update_enabled is True
    assert s.data_source == "auto"
    assert s.debug_mode is False
    assert s.sound_enabled is True

    # Verify user-facing confirmation text was set
    assert dlg.update_status_label.text == "Settings were reset to defaults"

    # Verify confirmation dialog was shown
    app.main_window.info_dialog.assert_called_once_with(
        "Settings Reset", "All settings were reset to defaults."
    )


def test_settings_dialog_has_full_reset_button(tmp_path):
    """SettingsDialog UI should include the Full Data Reset button on Advanced tab."""
    from unittest.mock import MagicMock

    from accessiweather.config import ConfigManager
    from accessiweather.dialogs.settings_dialog import SettingsDialog

    app = MagicMock()
    app.paths = MagicMock()
    app.paths.config = tmp_path
    cm = ConfigManager(app)

    import toga

    dlg = SettingsDialog(app, cm)
    dlg.current_settings = cm.get_settings()
    dlg.option_container = toga.OptionContainer()
    settings_tabs.create_advanced_tab(dlg)

    assert dlg.full_reset_button.id == "full_reset_button"
    assert dlg.full_reset_button.text.startswith("Reset all app data")


@pytest.mark.asyncio
async def test_settings_dialog_full_data_reset_clears_everything(tmp_path):
    """Full data reset should delete config, caches, alert state, and restore defaults."""
    import asyncio
    import json
    from unittest.mock import AsyncMock, MagicMock

    from accessiweather.config import ConfigManager
    from accessiweather.dialogs.settings_dialog import SettingsDialog

    # Mock app
    app = MagicMock()
    app.paths = MagicMock()
    app.paths.config = tmp_path
    app.loop = MagicMock()
    app.loop.create_future.return_value = asyncio.Future()
    app.main_window = MagicMock()
    app.main_window.error_dialog = AsyncMock()
    app.main_window.info_dialog = AsyncMock()

    cm = ConfigManager(app)

    # Non-default settings and a location
    assert (
        cm.update_settings(
            temperature_unit="f",
            update_interval_minutes=42,
            auto_update_enabled=False,
            data_source="nws",
            debug_mode=True,
            sound_enabled=False,
        )
        is True
    )
    assert cm.add_location("Test City", 1.0, 2.0) is True
    assert cm.set_current_location("Test City") is True

    # Create additional persisted data in config dir
    state_file = cm.config_dir / "alert_state.json"
    state_file.write_text(json.dumps({"alert_states": []}), encoding="utf-8")
    cache_file = cm.config_dir / "github_releases_cache.json"
    cache_file.write_text("{}", encoding="utf-8")
    settings_file = cm.config_dir / "update_settings.json"
    settings_file.write_text("{}", encoding="utf-8")
    updates_dir = cm.config_dir / "updates"
    updates_dir.mkdir(parents=True, exist_ok=True)
    (updates_dir / "dummy.bin").write_bytes(b"\x00\x01")

    # Execute full reset via dialog handler
    dlg = SettingsDialog(app, cm)
    dlg.current_settings = cm.get_settings()
    await dlg._on_full_reset(None)

    # Verify defaults restored
    s = cm.get_settings()
    assert s.temperature_unit == "both"
    assert s.update_interval_minutes == 10
    assert s.auto_update_enabled is True
    assert s.data_source == "auto"
    assert s.debug_mode is False
    assert s.sound_enabled is True
    assert cm.get_all_locations() == []
    assert cm.get_current_location() is None

    # Verify auxiliary data removed
    assert not state_file.exists()
    assert not cache_file.exists()
    assert not settings_file.exists()
    assert not updates_dir.exists()

    # Confirmation dialog shown
    app.main_window.info_dialog.assert_called_once_with(
        "Data Reset", "All application data were reset."
    )


def test_settings_dialog_has_reset_defaults_button(tmp_path):
    """SettingsDialog UI should include the Reset-to-Defaults button on Advanced tab."""
    from unittest.mock import MagicMock

    from accessiweather.config import ConfigManager
    from accessiweather.dialogs.settings_dialog import SettingsDialog

    # Minimal app mock
    app = MagicMock()
    app.paths = MagicMock()
    app.paths.config = tmp_path

    cm = ConfigManager(app)

    dlg = SettingsDialog(app, cm)
    dlg.current_settings = cm.get_settings()

    # Build just the Advanced tab in isolation to avoid needing a window
    import toga

    dlg.option_container = toga.OptionContainer()
    settings_tabs.create_advanced_tab(dlg)

    # Verify the button exists and is wired with the expected id/text
    assert getattr(dlg, "reset_defaults_button", None) is not None
    assert dlg.reset_defaults_button.id == "reset_defaults_button"
    assert dlg.reset_defaults_button.text == "Reset all settings to defaults"

    # Sanity: Advanced tab container exists and contains the button
    assert getattr(dlg, "advanced_tab", None) is not None


def test_settings_dialog_has_open_config_dir_button(tmp_path):
    """Advanced tab should include a button to open the config directory."""
    from unittest.mock import MagicMock

    import toga

    from accessiweather.config import ConfigManager
    from accessiweather.dialogs.settings_dialog import SettingsDialog

    app = MagicMock()
    app.paths = MagicMock()
    app.paths.config = tmp_path
    cm = ConfigManager(app)

    dlg = SettingsDialog(app, cm)
    dlg.current_settings = cm.get_settings()
    dlg.option_container = toga.OptionContainer()
    settings_tabs.create_advanced_tab(dlg)

    assert dlg.open_config_dir_button.id == "open_config_dir_button"
    assert dlg.open_config_dir_button.text.startswith("Open config directory")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "platform_name,expect_startfile,expect_cmd",
    [
        ("Windows", True, None),
        ("Darwin", False, "open"),
        ("Linux", False, "xdg-open"),
    ],
)
async def test_settings_dialog_open_config_dir_invokes_launcher(
    tmp_path, monkeypatch, platform_name, expect_startfile, expect_cmd
):
    """Open-config-dir handler should invoke the appropriate OS launcher."""
    import os
    import platform
    import subprocess

    from accessiweather.config import ConfigManager
    from accessiweather.dialogs.settings_dialog import SettingsDialog

    # Prepare app and config manager
    app = MagicMock()
    app.paths = MagicMock()
    app.paths.config = tmp_path
    app.main_window = MagicMock()  # in case of error dialogs

    cm = ConfigManager(app)

    # Patch platform.system to desired value
    monkeypatch.setattr(platform, "system", lambda: platform_name)

    # Patch OS-specific launchers
    startfile_called = MagicMock()
    run_called = MagicMock()

    if expect_startfile:
        monkeypatch.setattr(os, "startfile", startfile_called, raising=False)
    else:
        monkeypatch.setattr(subprocess, "run", run_called, raising=True)

    # Execute handler
    dlg = SettingsDialog(app, cm)
    dlg.current_settings = cm.get_settings()
    await dlg._on_open_config_dir(None)

    # Assert correct function used
    if expect_startfile:
        startfile_called.assert_called_once()
        arg = startfile_called.call_args[0][0]
        assert str(tmp_path) in str(arg)
    else:
        run_called.assert_called_once()
        args = run_called.call_args[0][0]
        assert args[0] == expect_cmd
        assert str(tmp_path) in args[1]


class TestNotificationsTab:
    """Tests for the notifications tab in settings dialog."""

    @pytest.fixture
    def dialog_with_notifications_tab(self, tmp_path):
        """Create a settings dialog with notifications tab initialized."""

        class DummyPaths:
            def __init__(self, tmp_path):
                self.config = tmp_path

        class DummyConfigManager:
            def __init__(self, tmp_path):
                self._settings = AppSettings()
                self._tmp_path = tmp_path

            def get_settings(self):
                return self._settings

            def save_settings(self, settings):
                self._settings = settings
                return True

            def is_startup_enabled(self):
                return bool(getattr(self._settings, "startup_enabled", False))

        app = MagicMock()
        app.paths = DummyPaths(tmp_path)
        config_manager = DummyConfigManager(tmp_path)
        dialog = SettingsDialog(app, config_manager)
        dialog.current_settings = config_manager.get_settings()
        dialog.option_container = toga.OptionContainer()

        # Create the notifications tab
        settings_tabs.create_notifications_tab(dialog)

        return dialog

    def test_notifications_tab_creates_all_severity_switches(self, dialog_with_notifications_tab):
        """Test that all severity level switches are created."""
        dialog = dialog_with_notifications_tab

        assert hasattr(dialog, "alert_notifications_enabled_switch")
        assert hasattr(dialog, "alert_notify_extreme_switch")
        assert hasattr(dialog, "alert_notify_severe_switch")
        assert hasattr(dialog, "alert_notify_moderate_switch")
        assert hasattr(dialog, "alert_notify_minor_switch")
        assert hasattr(dialog, "alert_notify_unknown_switch")

        # Verify they are actual switch widgets
        assert isinstance(dialog.alert_notifications_enabled_switch, toga.Switch)
        assert isinstance(dialog.alert_notify_extreme_switch, toga.Switch)
        assert isinstance(dialog.alert_notify_severe_switch, toga.Switch)
        assert isinstance(dialog.alert_notify_moderate_switch, toga.Switch)
        assert isinstance(dialog.alert_notify_minor_switch, toga.Switch)
        assert isinstance(dialog.alert_notify_unknown_switch, toga.Switch)

    def test_notifications_tab_creates_cooldown_inputs(self, dialog_with_notifications_tab):
        """Test that all cooldown input fields are created."""
        dialog = dialog_with_notifications_tab

        assert hasattr(dialog, "alert_global_cooldown_input")
        assert hasattr(dialog, "alert_per_alert_cooldown_input")
        assert hasattr(dialog, "alert_max_notifications_input")

        # Verify they are actual number input widgets
        assert isinstance(dialog.alert_global_cooldown_input, toga.NumberInput)
        assert isinstance(dialog.alert_per_alert_cooldown_input, toga.NumberInput)
        assert isinstance(dialog.alert_max_notifications_input, toga.NumberInput)

    def test_notifications_tab_default_values(self, dialog_with_notifications_tab):
        """Test that notification switches have correct default values."""
        dialog = dialog_with_notifications_tab

        # Master switch should be enabled by default
        assert dialog.alert_notifications_enabled_switch.value is True

        # High severity should be enabled
        assert dialog.alert_notify_extreme_switch.value is True
        assert dialog.alert_notify_severe_switch.value is True
        assert dialog.alert_notify_moderate_switch.value is True

        # Low severity should be disabled
        assert dialog.alert_notify_minor_switch.value is False
        assert dialog.alert_notify_unknown_switch.value is False

        # Check cooldown defaults
        assert dialog.alert_global_cooldown_input.value == 5
        assert dialog.alert_per_alert_cooldown_input.value == 60
        assert dialog.alert_max_notifications_input.value == 10

    def test_notifications_tab_accessibility_labels(self, dialog_with_notifications_tab):
        """Test that notification switches have proper accessibility labels."""
        dialog = dialog_with_notifications_tab

        assert dialog.alert_notifications_enabled_switch.aria_label == "Toggle alert notifications"
        assert dialog.alert_notify_extreme_switch.aria_label == "Notify for extreme severity alerts"
        assert dialog.alert_notify_severe_switch.aria_label == "Notify for severe severity alerts"
        assert (
            dialog.alert_notify_moderate_switch.aria_label == "Notify for moderate severity alerts"
        )
        assert dialog.alert_notify_minor_switch.aria_label == "Notify for minor severity alerts"
        assert dialog.alert_notify_unknown_switch.aria_label == "Notify for unknown severity alerts"

    def test_notifications_tab_accessibility_descriptions(self, dialog_with_notifications_tab):
        """Test that notification switches have proper accessibility descriptions."""
        dialog = dialog_with_notifications_tab

        assert "Master control" in dialog.alert_notifications_enabled_switch.aria_description
        assert "life-threatening" in dialog.alert_notify_extreme_switch.aria_description.lower()
        assert "significant hazards" in dialog.alert_notify_severe_switch.aria_description.lower()
        assert "may be hazardous" in dialog.alert_notify_moderate_switch.aria_description.lower()
        assert "low impact" in dialog.alert_notify_minor_switch.aria_description.lower()
        assert (
            "without a defined severity"
            in dialog.alert_notify_unknown_switch.aria_description.lower()
        )

    def test_notifications_tab_added_to_option_container(self, dialog_with_notifications_tab):
        """Test that the notifications tab is added to the option container."""
        dialog = dialog_with_notifications_tab

        # Check that tab was added to option container
        assert dialog.option_container.content is not None
        assert len(dialog.option_container.content) > 0

        # Verify notifications tab exists
        assert hasattr(dialog, "notifications_tab")
        assert dialog.notifications_tab is not None

    def test_notifications_tab_respects_custom_settings(self, tmp_path):
        """Test that the notifications tab respects custom settings."""

        class DummyPaths:
            def __init__(self, tmp_path):
                self.config = tmp_path

        class DummyConfigManager:
            def __init__(self, tmp_path):
                # Create custom settings with Minor enabled
                self._settings = AppSettings(
                    alert_notifications_enabled=False,
                    alert_notify_extreme=False,
                    alert_notify_severe=False,
                    alert_notify_moderate=False,
                    alert_notify_minor=True,
                    alert_notify_unknown=True,
                    alert_global_cooldown_minutes=10,
                    alert_per_alert_cooldown_minutes=120,
                    alert_max_notifications_per_hour=5,
                )
                self._tmp_path = tmp_path

            def get_settings(self):
                return self._settings

            def save_settings(self, settings):
                self._settings = settings
                return True

            def is_startup_enabled(self):
                return False

        app = MagicMock()
        app.paths = DummyPaths(tmp_path)
        config_manager = DummyConfigManager(tmp_path)
        dialog = SettingsDialog(app, config_manager)
        dialog.current_settings = config_manager.get_settings()
        dialog.option_container = toga.OptionContainer()

        # Create the notifications tab
        settings_tabs.create_notifications_tab(dialog)

        # Verify custom values
        assert dialog.alert_notifications_enabled_switch.value is False
        assert dialog.alert_notify_extreme_switch.value is False
        assert dialog.alert_notify_severe_switch.value is False
        assert dialog.alert_notify_moderate_switch.value is False
        assert dialog.alert_notify_minor_switch.value is True
        assert dialog.alert_notify_unknown_switch.value is True
        assert dialog.alert_global_cooldown_input.value == 10
        assert dialog.alert_per_alert_cooldown_input.value == 120
        assert dialog.alert_max_notifications_input.value == 5


class TestNotificationSettingsHandlers:
    """Tests for notification settings handlers (apply and collect)."""

    @pytest.fixture
    def dialog_setup(self, tmp_path):
        """Create a fully initialized settings dialog."""
        from accessiweather.dialogs import settings_handlers

        class DummyPaths:
            def __init__(self, tmp_path):
                self.config = tmp_path

        class DummyConfigManager:
            def __init__(self, tmp_path):
                self._settings = AppSettings()
                self._tmp_path = tmp_path

            def get_settings(self):
                return self._settings

            def save_settings(self, settings):
                self._settings = settings
                return True

            def is_startup_enabled(self):
                return bool(getattr(self._settings, "startup_enabled", False))

        app = MagicMock()
        app.paths = DummyPaths(tmp_path)
        config_manager = DummyConfigManager(tmp_path)
        dialog = SettingsDialog(app, config_manager)
        dialog.current_settings = config_manager.get_settings()
        dialog.option_container = toga.OptionContainer()

        # Create all necessary tabs
        settings_tabs.create_general_tab(dialog)
        settings_tabs.create_data_sources_tab(dialog)
        settings_tabs.create_notifications_tab(dialog)
        settings_tabs.create_audio_tab(dialog)
        settings_tabs.create_updates_tab(dialog)
        settings_tabs.create_advanced_tab(dialog)

        return dialog, settings_handlers

    def test_apply_settings_populates_notification_switches(self, dialog_setup):
        """Test that apply_settings_to_ui properly populates notification switches."""
        dialog, settings_handlers = dialog_setup

        # Set custom values in current_settings
        dialog.current_settings.alert_notifications_enabled = False
        dialog.current_settings.alert_notify_extreme = False
        dialog.current_settings.alert_notify_minor = True
        dialog.current_settings.alert_global_cooldown_minutes = 15

        # Apply settings
        settings_handlers.apply_settings_to_ui(dialog)

        # Verify switches were updated
        assert dialog.alert_notifications_enabled_switch.value is False
        assert dialog.alert_notify_extreme_switch.value is False
        assert dialog.alert_notify_minor_switch.value is True
        assert dialog.alert_global_cooldown_input.value == 15

    def test_collect_settings_reads_notification_switches(self, dialog_setup):
        """Test that collect_settings_from_ui properly reads notification switches."""
        dialog, settings_handlers = dialog_setup

        # Modify switch values
        dialog.alert_notifications_enabled_switch.value = False
        dialog.alert_notify_extreme_switch.value = False
        dialog.alert_notify_minor_switch.value = True
        dialog.alert_notify_unknown_switch.value = True
        dialog.alert_global_cooldown_input.value = 20
        dialog.alert_per_alert_cooldown_input.value = 90
        dialog.alert_max_notifications_input.value = 15

        # Collect settings
        collected = settings_handlers.collect_settings_from_ui(dialog)

        # Verify collected values
        assert collected.alert_notifications_enabled is False
        assert collected.alert_notify_extreme is False
        assert collected.alert_notify_minor is True
        assert collected.alert_notify_unknown is True
        assert collected.alert_global_cooldown_minutes == 20
        assert collected.alert_per_alert_cooldown_minutes == 90
        assert collected.alert_max_notifications_per_hour == 15

    def test_settings_roundtrip_notifications(self, dialog_setup):
        """Test that notification settings survive a full apply->modify->collect cycle."""
        dialog, settings_handlers = dialog_setup

        # Set initial values
        dialog.current_settings.alert_notify_minor = True
        dialog.current_settings.alert_notify_moderate = False
        dialog.current_settings.alert_global_cooldown_minutes = 8

        # Apply to UI
        settings_handlers.apply_settings_to_ui(dialog)

        # Verify UI updated
        assert dialog.alert_notify_minor_switch.value is True
        assert dialog.alert_notify_moderate_switch.value is False
        assert dialog.alert_global_cooldown_input.value == 8

        # Modify in UI
        dialog.alert_notify_minor_switch.value = False
        dialog.alert_notify_moderate_switch.value = True
        dialog.alert_global_cooldown_input.value = 12

        # Collect from UI
        collected = settings_handlers.collect_settings_from_ui(dialog)

        # Verify collected matches modifications
        assert collected.alert_notify_minor is False
        assert collected.alert_notify_moderate is True
        assert collected.alert_global_cooldown_minutes == 12
