"""UI construction helpers for AccessiWeather."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

import toga
from toga.style import Pack
from travertino.constants import COLUMN, ROW

from . import app_helpers, event_handlers

if TYPE_CHECKING:  # pragma: no cover - circular import guard
    from .app import AccessiWeatherApp
    from .display.weather_presenter import ForecastPresentation
    from .models import WeatherData


logger = logging.getLogger(__name__)


def render_forecast_with_headings(
    presentation: ForecastPresentation | None,
    container: toga.Box,
) -> list[toga.Label]:
    """
    Render forecast with semantic heading structure for screen reader navigation.

    Creates a structured display where each forecast day is marked with a heading
    element, allowing screen reader users to navigate between days using heading
    shortcuts (H key in NVDA/JAWS).

    Args:
        presentation: Structured forecast data from WeatherPresenter
        container: Parent Box widget to add forecast elements to

    Returns:
        List of heading Label widgets created for each forecast day

    """
    # Clear existing children from container
    while container.children:
        container.remove(container.children[0])

    heading_labels: list[toga.Label] = []

    if presentation is None or not presentation.periods:
        # No forecast data - show fallback message
        no_data_label = toga.Label(
            "No forecast data available.",
            style=Pack(margin_bottom=5),
        )
        with contextlib.suppress(AttributeError):
            no_data_label.aria_label = "No forecast data available"
        container.add(no_data_label)
        return heading_labels

    # Add hourly summary if available
    if presentation.hourly_periods:
        hourly_heading = toga.Label(
            "Next 6 Hours:",
            style=Pack(font_weight="bold", margin_bottom=3, margin_top=5),
        )
        try:
            hourly_heading.aria_role = "heading"
            hourly_heading.aria_level = 2
            hourly_heading.aria_label = "Next 6 Hours forecast"
        except AttributeError:
            pass
        container.add(hourly_heading)
        heading_labels.append(hourly_heading)

        for hourly in presentation.hourly_periods:
            parts = [hourly.time]
            if hourly.temperature:
                parts.append(hourly.temperature)
            if hourly.conditions:
                parts.append(hourly.conditions)
            if hourly.wind:
                parts.append(f"Wind {hourly.wind}")
            hourly_text = " - ".join(parts)

            hourly_label = toga.Label(
                f"  {hourly_text}",
                style=Pack(margin_bottom=2),
            )
            with contextlib.suppress(AttributeError):
                hourly_label.aria_label = hourly_text
            container.add(hourly_label)

    # Add each forecast period with heading structure
    for period in presentation.periods:
        # Create heading label for the day name
        day_heading = toga.Label(
            period.name,
            style=Pack(font_weight="bold", margin_top=8, margin_bottom=3),
        )
        try:
            day_heading.aria_role = "heading"
            day_heading.aria_level = 2
            day_heading.aria_label = f"{period.name} forecast"
        except AttributeError:
            pass
        container.add(day_heading)
        heading_labels.append(day_heading)

        # Temperature line
        if period.temperature:
            temp_label = toga.Label(
                f"  Temperature: {period.temperature}",
                style=Pack(margin_bottom=2),
            )
            with contextlib.suppress(AttributeError):
                temp_label.aria_label = f"Temperature {period.temperature}"
            container.add(temp_label)

        # Conditions line
        if period.conditions:
            conditions_label = toga.Label(
                f"  Conditions: {period.conditions}",
                style=Pack(margin_bottom=2),
            )
            with contextlib.suppress(AttributeError):
                conditions_label.aria_label = f"Conditions {period.conditions}"
            container.add(conditions_label)

        # Wind line
        if period.wind:
            wind_label = toga.Label(
                f"  Wind: {period.wind}",
                style=Pack(margin_bottom=2),
            )
            with contextlib.suppress(AttributeError):
                wind_label.aria_label = f"Wind {period.wind}"
            container.add(wind_label)

        # Details line (if different from conditions)
        if period.details:
            details_label = toga.Label(
                f"  {period.details}",
                style=Pack(margin_bottom=2),
            )
            with contextlib.suppress(AttributeError):
                details_label.aria_label = period.details
            container.add(details_label)

    # Add generated timestamp if available
    if presentation.generated_at:
        generated_label = toga.Label(
            f"\nForecast generated: {presentation.generated_at}",
            style=Pack(margin_top=5, font_style="italic"),
        )
        with contextlib.suppress(AttributeError):
            generated_label.aria_label = f"Forecast generated at {presentation.generated_at}"
        container.add(generated_label)

    logger.debug(
        "Rendered forecast with %d heading elements for %d periods",
        len(heading_labels),
        len(presentation.periods),
    )
    return heading_labels


def initialize_system_tray(app: AccessiWeatherApp) -> bool:
    """
    Initialize system tray with Windows 11 compatibility.

    Creates a system tray icon with context menu for background operation.
    On Windows 11, ensures the icon is properly registered and visible.

    Args:
        app: The AccessiWeather application instance

    Returns:
        True if system tray initialized successfully, False otherwise

    """
    try:
        logger.info("Initializing system tray")

        # Check if system tray is available on this platform
        if not hasattr(app, "status_icons"):
            logger.warning("System tray not available on this platform")
            app.status_icon = None
            app.system_tray_available = False
            return False

        initial_text = "AccessiWeather"
        try:
            settings = app.config_manager.get_settings()
            if settings.taskbar_icon_text_enabled and hasattr(app, "current_weather_data"):
                weather_data = getattr(app, "current_weather_data", None)
                if weather_data:
                    pass
        except Exception:
            pass

        app.status_icon = toga.MenuStatusIcon(
            id="accessiweather_main",
            icon=app.icon,
            text=initial_text,
        )

        create_system_tray_commands(app)

        app.status_icons.add(app.status_icon)

        app.system_tray_available = True

        app.window_visible = True

        if hasattr(app, "current_weather_data") and app.current_weather_data:
            update_tray_icon_tooltip(app, app.current_weather_data)

        logger.info("System tray initialized successfully")
        return True
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to initialize system tray: %s", exc)
        app.status_icon = None
        app.system_tray_available = False
        return False


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

        app.status_icons.commands.add(
            app.show_hide_command,
            app.refresh_command,
            app.tray_settings_command,
        )

        logger.info("System tray commands created")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to create system tray commands: %s", exc)


def _set_status_icon_text(status_icon: toga.MenuStatusIcon, text: str) -> bool:
    """
    Set the text/tooltip on a status icon, working around Toga's lack of a text setter.

    Toga's StatusIcon.text property is read-only after creation. This function
    directly accesses the native control to update the tooltip text.

    Supported platforms:
    - Windows (sys.platform == 'win32'): Sets NotifyIcon.Text via WinForms
    - macOS (sys.platform == 'darwin'): Sets NSStatusItem.button.toolTip

    Args:
        status_icon: The Toga MenuStatusIcon instance
        text: The text to set as the tooltip

    Returns:
        True if successfully set, False otherwise

    """
    import sys

    try:
        impl = getattr(status_icon, "_impl", None)
        if impl is None:
            logger.debug("Status icon has no _impl attribute")
            return False
        native = getattr(impl, "native", None)
        if native is None:
            logger.debug("Status icon impl has no native attribute")
            return False
        type_name = type(native).__name__

        # Skip mock objects in tests
        if "Mock" in type_name:
            return False

        # Log the native object type for debugging
        logger.debug("Native status icon type: %s on platform %s", type_name, sys.platform)

        # Use sys.platform for reliable platform detection
        # sys.platform returns 'win32' on both 32-bit and 64-bit Windows
        if sys.platform == "win32":
            # Windows: Toga uses WinForms NotifyIcon
            # The native object should have a .Text property for the tooltip
            if hasattr(native, "Text"):
                old_text = native.Text
                native.Text = text
                logger.info(
                    "Updated Windows NotifyIcon.Text: '%s' -> '%s'",
                    old_text[:30] if old_text else "(empty)",
                    text[:30] if text else "(empty)",
                )

                # On Windows 11, sometimes the tooltip doesn't update visually
                # until the icon is "refreshed". Try toggling visibility or
                # re-setting the icon to force a refresh.
                if hasattr(native, "Visible"):
                    # Force Windows to recognize the change by briefly toggling
                    # This is a workaround for Windows 11 tooltip caching
                    try:
                        current_icon = native.Icon
                        if current_icon is not None:
                            # Re-set the icon to force Windows to refresh the tooltip
                            native.Icon = current_icon
                            logger.debug("Refreshed icon to force tooltip update")
                    except Exception as refresh_exc:
                        logger.debug("Icon refresh failed (non-critical): %s", refresh_exc)
            else:
                logger.debug("Windows native object (%s) has no Text attribute", type_name)
                return False
        elif sys.platform == "darwin":
            # macOS: Toga uses NSStatusItem
            # The tooltip is set via button.toolTip
            if hasattr(native, "button") and hasattr(native.button, "toolTip"):
                native.button.toolTip = text
                logger.debug("Set macOS NSStatusItem tooltip to: %s", text[:50])
            else:
                logger.debug("macOS native object (%s) has no button.toolTip", type_name)
                return False
        else:
            # Linux/other platforms - try generic approaches
            # GTK/XApp status icons may have different APIs
            if hasattr(native, "set_tooltip_text"):
                native.set_tooltip_text(text)
                logger.debug("Set GTK tooltip via set_tooltip_text: %s", text[:50])
            elif hasattr(native, "Text"):
                # Fallback to .Text if available
                native.Text = text
                logger.debug("Set tooltip via .Text fallback: %s", text[:50])
            else:
                logger.debug(
                    "Platform %s: native object (%s) has no known tooltip API",
                    sys.platform,
                    type_name,
                )
                return False

        # Update Toga's internal _text attribute if it exists
        if hasattr(status_icon, "_text"):
            status_icon._text = text
        return True
    except Exception as exc:
        logger.warning("Failed to set native status icon text: %s", exc, exc_info=True)
    return False


def update_tray_icon_tooltip(
    app: AccessiWeatherApp, weather_data: WeatherData | None = None
) -> None:
    """
    Update the system tray icon tooltip with weather information.

    Uses platform-specific methods to update the tooltip text on the system tray icon.
    On Windows (sys.platform == 'win32'), this updates the NotifyIcon.Text property.
    On macOS (sys.platform == 'darwin'), this updates NSStatusItem.button.toolTip.

    Args:
        app: The AccessiWeather application instance
        weather_data: Optional weather data to format into tooltip. If None, uses default text.

    """
    if not getattr(app, "status_icon", None):
        return

    if not getattr(app, "system_tray_available", False):
        return

    try:
        settings = app.config_manager.get_settings()

        # Log settings for debugging
        logger.debug(
            "Tooltip settings: text_enabled=%s, dynamic_enabled=%s, format='%s'",
            settings.taskbar_icon_text_enabled,
            settings.taskbar_icon_dynamic_enabled,
            settings.taskbar_icon_text_format,
        )

        from .taskbar_icon_updater import TaskbarIconUpdater

        updater = TaskbarIconUpdater(
            text_enabled=settings.taskbar_icon_text_enabled,
            dynamic_enabled=settings.taskbar_icon_dynamic_enabled,
            format_string=settings.taskbar_icon_text_format,
            temperature_unit=settings.temperature_unit,
        )

        location = app.config_manager.get_current_location()
        location_name = location.name if location else None

        tooltip_text = updater.format_tooltip(weather_data, location_name)
        logger.debug(
            "Formatted tooltip text: '%s'", tooltip_text[:50] if tooltip_text else "(empty)"
        )

        # Try native method first, fall back to Toga's text property
        if not _set_status_icon_text(app.status_icon, tooltip_text):
            # Toga's text property may be read-only after creation on some backends
            # but we try it as a fallback
            try:
                app.status_icon.text = tooltip_text
                logger.debug("Set tooltip via Toga text property: %s", tooltip_text[:50])
            except AttributeError:
                logger.debug("Toga text property is read-only, native method also failed")

    except Exception as exc:
        logger.debug("Failed to update tray icon tooltip: %s", exc)
        with contextlib.suppress(Exception):
            _set_status_icon_text(app.status_icon, "AccessiWeather")


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

    # Add global Escape key handler for minimize-to-tray
    def on_main_window_key_down(widget, key, _modifiers=None):
        """Handle global keyboard shortcuts for main window."""
        if app_helpers.is_escape_key(key):
            return app_helpers.handle_escape_key(app)
        return False

    try:
        app.main_window.on_key_down = on_main_window_key_down
        logger.info("Escape key handler enabled for main window")
    except AttributeError:
        # on_key_down might not be available on all platforms
        logger.warning("Escape key handler not available on this platform")

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
    """
    Create the weather display section.

    Uses WebView (HTML) or MultilineTextInput based on user settings.
    HTML rendering provides better accessibility with semantic headings.
    """
    weather_box = toga.Box(style=Pack(direction=COLUMN, flex=1))
    # Store reference for dynamic button management (e.g., AI explain button)
    app.weather_box = weather_box

    # Get user preferences for rendering mode
    use_html_conditions = True
    use_html_forecast = True
    if hasattr(app, "config_manager") and app.config_manager:
        try:
            config = app.config_manager.get_config()
            use_html_conditions = getattr(config.settings, "html_render_current_conditions", True)
            use_html_forecast = getattr(config.settings, "html_render_forecast", True)
        except Exception:
            pass  # Use defaults if config unavailable

    conditions_label = toga.Label(
        "Current Conditions:", style=Pack(font_weight="bold", margin_top=10, margin_bottom=5)
    )
    weather_box.add(conditions_label)

    # Create current conditions display based on user preference
    if use_html_conditions:
        from .ui.webview_weather import create_conditions_webview

        app.current_conditions_webview = create_conditions_webview(height=120)
        weather_box.add(app.current_conditions_webview)
        app.current_conditions_display = None
    else:
        # Use traditional MultilineTextInput for users who prefer it
        app.current_conditions_display = toga.MultilineTextInput(
            readonly=True,
            style=Pack(height=120, margin_bottom=5),
        )
        try:
            app.current_conditions_display.aria_label = "Current weather conditions"
            app.current_conditions_display.aria_description = (
                "Read-only text area showing current weather conditions"
            )
        except AttributeError:
            pass
        weather_box.add(app.current_conditions_display)
        app.current_conditions_webview = None

    forecast_label = toga.Label("Forecast:", style=Pack(font_weight="bold", margin_bottom=5))
    weather_box.add(forecast_label)

    # Create forecast display based on user preference
    if use_html_forecast:
        from .ui.webview_weather import create_forecast_webview

        app.forecast_webview = create_forecast_webview(height=200)
        weather_box.add(app.forecast_webview)
        app.forecast_container = None
        app.forecast_scroll = None
        app.forecast_display = None
    else:
        # Use traditional MultilineTextInput for users who prefer it
        app.forecast_display = toga.MultilineTextInput(
            readonly=True,
            style=Pack(height=200, margin_bottom=5),
        )
        try:
            app.forecast_display.aria_label = "Weather forecast"
            app.forecast_display.aria_description = (
                "Read-only text area showing extended weather forecast"
            )
        except AttributeError:
            pass
        weather_box.add(app.forecast_display)
        app.forecast_webview = None
        app.forecast_container = None
        app.forecast_scroll = None

    # Add "Explain Weather" button if API key is configured
    try:
        config = app.config_manager.get_config()
        api_key = getattr(config.settings, "openrouter_api_key", "")
        if api_key and api_key.strip():
            from .ai_explainer import create_explain_weather_button
            from .handlers.ai_handlers import on_explain_weather_pressed

            app.explain_weather_button = create_explain_weather_button(
                on_press=lambda widget: asyncio.create_task(on_explain_weather_pressed(app, widget))
            )
            weather_box.add(app.explain_weather_button)
        else:
            app.explain_weather_button = None
    except Exception as exc:
        logger.warning(f"Could not add AI explanation button: {exc}")
        app.explain_weather_button = None

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

    air_quality_cmd = toga.Command(
        lambda widget: asyncio.create_task(event_handlers.on_view_air_quality(app, widget)),
        text="Air Quality…",
        tooltip="View detailed air quality information",
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
        air_quality_cmd,
    )

    if toga.Command.ABOUT in app.commands:
        app.commands[toga.Command.ABOUT].action = lambda widget: asyncio.create_task(
            event_handlers.on_about_pressed(app, widget)
        )

    if toga.Command.EXIT in app.commands:
        app.commands[toga.Command.EXIT].action = lambda widget: app.request_exit()

    logger.info("Menu system created")
