"""UI construction helpers for AccessiWeather."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import toga
from toga.style import Pack
from travertino.constants import COLUMN, ROW

from . import app_helpers, event_handlers

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from .app import AccessiWeatherApp


logger = logging.getLogger(__name__)


def initialize_system_tray(app: AccessiWeatherApp) -> None:
    """Initialize system tray functionality."""
    try:
        logger.info("Initializing system tray")

        app.status_icon = toga.MenuStatusIcon(
            id="accessiweather_main",
            icon=app.icon,
            text="AccessiWeather",
        )

        create_system_tray_commands(app)

        app.status_icons.add(app.status_icon)

        logger.info("System tray initialized successfully")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to initialize system tray: %s", exc)
        app.status_icon = None


def create_system_tray_commands(app: AccessiWeatherApp) -> None:
    """Create commands for the system tray menu."""
    try:
        app.show_hide_command = toga.Command(
            lambda widget: asyncio.create_task(event_handlers.on_show_hide_window(app, widget)),
            text="Show AccessiWeather",
            group=app.status_icon,
            tooltip="Show or hide the main window",
        )

        app.refresh_command = toga.Command(
            lambda widget: asyncio.create_task(event_handlers.on_tray_refresh(app, widget)),
            text="Refresh Weather",
            group=app.status_icon,
            tooltip="Refresh weather data for current location",
        )

        app.tray_settings_command = toga.Command(
            lambda widget: asyncio.create_task(event_handlers.on_tray_settings(app, widget)),
            text="Settings",
            group=app.status_icon,
            tooltip="Open application settings",
        )

        app.tray_separator_group = toga.Group("Actions", parent=app.status_icon)

        app.tray_exit_command = toga.Command(
            lambda widget: asyncio.create_task(event_handlers.on_tray_exit(app, widget)),
            text="Exit AccessiWeather",
            group=app.tray_separator_group,
            tooltip="Exit the application",
        )

        app.status_icons.commands.add(
            app.show_hide_command,
            app.refresh_command,
            app.tray_settings_command,
            app.tray_exit_command,
        )

        logger.info("System tray commands created")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to create system tray commands: %s", exc)


def create_main_ui(app: AccessiWeatherApp) -> None:
    """Create the main user interface."""
    logger.info("Creating main UI")

    main_box = toga.Box(style=Pack(direction=COLUMN, margin=10))

    title_label = toga.Label(
        "AccessiWeather",
        style=Pack(text_align="center", font_size=18, font_weight="bold", margin_bottom=10),
    )
    main_box.add(title_label)

    app.status_label = toga.Label("", style=Pack(margin_bottom=10, font_style="italic"))
    main_box.add(app.status_label)

    location_box = create_location_section(app)
    main_box.add(location_box)

    weather_box = create_weather_display_section(app)
    main_box.add(weather_box)

    buttons_box = create_control_buttons_section(app)
    main_box.add(buttons_box)

    debug_mode = False
    try:
        debug_mode = app.config_manager.get_settings().debug_mode
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Could not read debug_mode from settings: %s", exc)

    if debug_mode:
        app.test_notification_button = toga.Button(
            "Send Test Notification",
            on_press=lambda widget: event_handlers.on_test_notification_pressed(app, widget),
            style=Pack(margin_top=10, background_color="#e0e0e0"),
        )
        main_box.add(app.test_notification_button)

    app.main_window = toga.MainWindow(title=app.formal_name)
    app.main_window.content = main_box
    app.main_window.on_close = app._on_window_close
    # Attach on_show handler to refresh weather when window becomes visible
    app.main_window.on_show = lambda: asyncio.create_task(event_handlers.on_window_show(app))
    app.main_window.show()

    logger.info("Main UI created successfully")


def create_location_section(app: AccessiWeatherApp) -> toga.Box:
    """Create the location selection section."""
    location_box = toga.Box(style=Pack(direction=ROW, margin_bottom=10))

    location_label = toga.Label("Location:", style=Pack(width=80, margin_right=10))

    location_names = app_helpers.get_location_choices(app)

    app.location_selection = toga.Selection(
        items=location_names,
        style=Pack(flex=1),
        on_change=lambda widget: asyncio.create_task(
            event_handlers.on_location_changed(app, widget)
        ),
    )

    # Add keyboard shortcut for Delete key to remove location on supported platforms
    def on_location_key_down(widget, key, _modifiers=None):
        """Handle keyboard shortcuts for location selection."""
        if app_helpers.is_delete_key(key):
            asyncio.create_task(event_handlers.on_remove_location_pressed(app, widget))
            return True
        return False

    try:
        app.location_selection.on_key_down = on_location_key_down
        logger.info("Keyboard shortcuts enabled for location selection")
    except AttributeError:
        # on_key_down might not be available on all platforms
        logger.warning("Keyboard shortcuts not available for location selection on this platform")

    # Add accessibility description for keyboard shortcut
    try:
        app.location_selection.aria_label = "Location selection"
        app.location_selection.aria_description = (
            "Select your weather location. Press Ctrl or Command+D to remove the selected location, "
            "or use the Remove button. The Delete key also works on platforms that support it."
        )
    except AttributeError:
        # aria properties might not be available on all platforms
        pass

    current_location = app.config_manager.get_current_location()
    if current_location and current_location.name in location_names:
        app.location_selection.value = current_location.name

    location_box.add(location_label)
    location_box.add(app.location_selection)

    return location_box


def create_weather_display_section(app: AccessiWeatherApp) -> toga.Box:
    """Create the weather display section."""
    weather_box = toga.Box(style=Pack(direction=COLUMN, flex=1))

    conditions_label = toga.Label(
        "Current Conditions:", style=Pack(font_weight="bold", margin_top=10, margin_bottom=5)
    )
    weather_box.add(conditions_label)

    app.current_conditions_display = toga.MultilineTextInput(
        readonly=True, style=Pack(height=120, margin_bottom=10)
    )
    app.current_conditions_display.value = "No current conditions data available."
    try:
        app.current_conditions_display.aria_label = "Current conditions"
        app.current_conditions_display.aria_description = "Read-only display of current weather conditions including temperature, humidity, wind speed, and pressure"
    except AttributeError:
        pass
    weather_box.add(app.current_conditions_display)

    forecast_label = toga.Label("Forecast:", style=Pack(font_weight="bold", margin_bottom=5))
    weather_box.add(forecast_label)

    app.forecast_display = toga.MultilineTextInput(
        readonly=True, style=Pack(height=200, margin_bottom=10)
    )
    app.forecast_display.value = "No forecast data available."
    try:
        app.forecast_display.aria_label = "Forecast"
        app.forecast_display.aria_description = (
            "Read-only display of extended weather forecast with detailed predictions"
        )
    except AttributeError:
        pass
    weather_box.add(app.forecast_display)

    app.discussion_button = toga.Button(
        "View Forecast Discussion",
        on_press=lambda widget: asyncio.create_task(
            event_handlers.on_discussion_pressed(app, widget)
        ),
        style=Pack(margin_bottom=10),
    )
    try:
        app.discussion_button.aria_label = "View forecast discussion"
        app.discussion_button.aria_description = (
            "Press Enter to open detailed forecast discussion from meteorologists"
        )
    except AttributeError:
        pass
    weather_box.add(app.discussion_button)

    alerts_label = toga.Label("Weather Alerts:", style=Pack(font_weight="bold", margin_bottom=5))
    weather_box.add(alerts_label)

    app.alerts_table = toga.Table(
        headings=["Event", "Severity", "Headline"],
        data=[],
        style=Pack(height=150, margin_bottom=10),
        on_select=lambda widget: event_handlers.on_alert_selected(app, widget),
    )
    try:
        app.alerts_table.aria_label = "Weather alerts"
        app.alerts_table.aria_description = "Table of active weather alerts. Select an alert and press View Alert Details button or press Enter to view full details"
    except AttributeError:
        pass
    weather_box.add(app.alerts_table)

    app.alert_details_button = toga.Button(
        "View Alert Details",
        on_press=lambda widget: asyncio.create_task(
            event_handlers.on_alert_details_pressed(app, widget)
        ),
        style=Pack(margin_bottom=10),
        enabled=False,
    )
    try:
        app.alert_details_button.aria_label = "View alert details"
        app.alert_details_button.aria_description = (
            "Press Enter to view detailed information about the selected weather alert"
        )
    except AttributeError:
        pass
    weather_box.add(app.alert_details_button)

    return weather_box


def create_control_buttons_section(app: AccessiWeatherApp) -> toga.Box:
    """Create the control buttons section (matching wx interface)."""
    buttons_box = toga.Box(style=Pack(direction=ROW, margin_top=10))

    app.add_button = toga.Button(
        "Add",
        on_press=lambda widget: asyncio.create_task(
            event_handlers.on_add_location_pressed(app, widget)
        ),
        style=Pack(margin_right=5),
    )
    try:
        app.add_button.aria_label = "Add location"
        app.add_button.aria_description = "Press Enter to add a new weather location"
    except AttributeError:
        pass
    buttons_box.add(app.add_button)

    app.remove_button = toga.Button(
        "Remove",
        on_press=lambda widget: asyncio.create_task(
            event_handlers.on_remove_location_pressed(app, widget)
        ),
        style=Pack(margin_right=5),
    )
    try:
        app.remove_button.aria_label = "Remove location"
        app.remove_button.aria_description = "Press Enter to remove the currently selected location"
    except AttributeError:
        pass
    buttons_box.add(app.remove_button)

    app.refresh_button = toga.Button(
        "Refresh",
        on_press=lambda widget: asyncio.create_task(event_handlers.on_refresh_pressed(app, widget)),
        style=Pack(margin_right=5),
    )
    try:
        app.refresh_button.aria_label = "Refresh weather"
        app.refresh_button.aria_description = (
            "Press Enter to refresh weather data for the current location"
        )
    except AttributeError:
        pass
    buttons_box.add(app.refresh_button)

    app.settings_button = toga.Button(
        "Settings",
        on_press=lambda widget: asyncio.create_task(
            event_handlers.on_settings_pressed(app, widget)
        ),
        style=Pack(),
    )
    try:
        app.settings_button.aria_label = "Settings"
        app.settings_button.aria_description = "Press Enter to open application settings dialog"
    except AttributeError:
        pass
    buttons_box.add(app.settings_button)

    return buttons_box


def create_menu_system(app: AccessiWeatherApp) -> None:
    """Create the application menu system."""
    logger.info("Creating menu system")

    settings_cmd = toga.Command(
        lambda widget: asyncio.create_task(event_handlers.on_settings_pressed(app, widget)),
        text="Settings",
        tooltip="Open application settings",
        group=toga.Group.FILE,
    )

    exit_cmd = toga.Command(
        lambda widget: app.request_exit(),
        text="Exit",
        tooltip="Exit the application",
        group=toga.Group.FILE,
        section=1,
    )

    location_group = toga.Group("Location")
    add_location_cmd = toga.Command(
        lambda widget: asyncio.create_task(event_handlers.on_add_location_pressed(app, widget)),
        text="Add Location",
        tooltip="Add a new location",
        group=location_group,
    )
    remove_location_cmd = toga.Command(
        lambda widget: asyncio.create_task(event_handlers.on_remove_location_pressed(app, widget)),
        text="Remove Location",
        tooltip="Remove the selected location",
        group=location_group,
        shortcut=toga.Key.MOD_1 + toga.Key.D.value,
    )

    refresh_cmd = toga.Command(
        lambda widget: asyncio.create_task(event_handlers.on_refresh_pressed(app, widget)),
        text="Refresh",
        tooltip="Refresh weather data",
        group=toga.Group.VIEW,
    )

    history_cmd = toga.Command(
        lambda widget: asyncio.create_task(event_handlers.on_view_weather_history(app, widget)),
        text="View Weather History",
        tooltip="Compare current weather with historical data",
        group=toga.Group.VIEW,
    )
    aviation_cmd = toga.Command(
        lambda widget: asyncio.create_task(event_handlers.on_view_aviation_pressed(app, widget)),
        text="Aviation Weather…",
        tooltip="Open the aviation weather viewer",
        group=toga.Group.VIEW,
    )

    app.commands.add(
        settings_cmd,
        exit_cmd,
        add_location_cmd,
        remove_location_cmd,
        refresh_cmd,
        history_cmd,
        aviation_cmd,
    )

    if toga.Command.ABOUT in app.commands:
        app.commands[toga.Command.ABOUT].action = lambda widget: asyncio.create_task(
            event_handlers.on_about_pressed(app, widget)
        )

    if toga.Command.EXIT in app.commands:
        app.commands[toga.Command.EXIT].action = lambda widget: app.request_exit()

    logger.info("Menu system created")
