"""
Main window for AccessiWeather using gui_builder.

This module defines the main application window using gui_builder's
declarative form syntax for clean, maintainable UI code.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx
from gui_builder import fields, forms

if TYPE_CHECKING:
    from ..app import AccessiWeatherApp

logger = logging.getLogger(__name__)


class WeatherAlertsPanel(forms.Panel):
    """Panel displaying weather alerts."""

    alerts_label = fields.StaticText(label="Weather Alerts:")
    alerts_list = fields.ListBox(label="Active Alerts")
    view_alert_button = fields.Button(label="View Alert Details")

    @view_alert_button.add_callback
    def on_view_alert(self):
        """Handle view alert button click."""
        selected = self.alerts_list.get_index()
        if selected is not None and selected >= 0:
            parent = self.get_first_ancestor()
            if hasattr(parent, "_show_alert_details"):
                parent._show_alert_details(selected)


class MainWindow(forms.SizedFrame):
    """
    Main application window using gui_builder declarative forms.

    This provides the primary UI for AccessiWeather with:
    - Location selection dropdown
    - Current conditions display
    - Forecast display
    - Weather alerts list
    - Control buttons
    """

    # Location section
    location_label = fields.StaticText(label="Location:")
    location_dropdown = fields.ComboBox(label="Select Location", read_only=True)

    # Status display
    status_label = fields.StaticText(label="")

    # Stale/cached data warning
    stale_warning_label = fields.StaticText(label="")

    # Current conditions section
    conditions_label = fields.StaticText(label="Current Conditions:")
    current_conditions = fields.Text(
        label="Current weather conditions",
        multiline=True,
        readonly=True,
    )

    # Data source attribution
    data_source_label = fields.StaticText(label="")

    # Forecast section
    forecast_label = fields.StaticText(label="Forecast:")
    forecast_display = fields.Text(
        label="Weather forecast",
        multiline=True,
        readonly=True,
    )

    # Weather alerts panel
    alerts_panel = WeatherAlertsPanel()

    # Control buttons
    add_button = fields.Button(label="&Add")
    remove_button = fields.Button(label="Re&move")
    refresh_button = fields.Button(label="&Refresh")
    explain_button = fields.Button(label="&Explain")
    discussion_button = fields.Button(label="&Discussion")
    settings_button = fields.Button(label="&Settings")

    def __init__(self, app: AccessiWeatherApp = None, **kwargs):
        """
        Initialize the main window.

        Args:
            app: The AccessiWeather application instance
            **kwargs: Additional keyword arguments passed to SizedFrame

        """
        self.app = app
        # Ensure top_level_window is set for gui_builder to return a bound instance
        kwargs.setdefault("top_level_window", True)
        kwargs.setdefault("title", "AccessiWeather")
        super().__init__(**kwargs)
        # Note: Don't call _setup_accessibility, _populate_locations, or _create_menu_bar here
        # They require widgets to be rendered first. Call them after render() in _post_render().

    def render(self, **kwargs):
        """Render the main window and set up post-render components."""
        super().render(**kwargs)
        # Now widgets are created, set up accessibility, menus, and data
        self._setup_accessibility()
        self._populate_locations()
        self._create_menu_bar()
        # Bind close event to the frame
        self.widget.control.Bind(wx.EVT_CLOSE, self._on_close)
        # Bind iconize event (minimize button) to the frame
        self.widget.control.Bind(wx.EVT_ICONIZE, self._on_iconize)
        # Bind show event to set focus when window is actually displayed
        self.widget.control.Bind(wx.EVT_SHOW, self._on_window_shown)
        # Bind key events for Escape key handling
        self.widget.control.Bind(wx.EVT_CHAR_HOOK, self._on_key_down)

    def _on_window_shown(self, event) -> None:
        """Handle window shown event to set initial focus."""
        event.Skip()  # Allow event to propagate
        if event.IsShown():
            # Use CallLater to ensure focus is set after window is fully ready
            # A small delay helps screen readers properly announce the focused control
            wx.CallLater(100, self._set_initial_focus)

    def _set_initial_focus(self) -> None:
        """Set initial focus to the location dropdown for keyboard accessibility."""
        try:
            combo = self.location_dropdown.widget.control
            combo.SetFocus()
            logger.debug("Initial focus set to location dropdown")
        except Exception as e:
            logger.debug(f"Could not set initial focus: {e}")

    def _setup_accessibility(self) -> None:
        """Set up accessibility labels for screen readers."""
        self.location_dropdown.set_accessible_label("Location selection")
        self.current_conditions.set_accessible_label("Current weather conditions")
        self.forecast_display.set_accessible_label("Weather forecast")
        self.alerts_panel.alerts_list.set_accessible_label("Weather alerts list")

    def _populate_locations(self) -> None:
        """Populate the location dropdown with saved locations."""
        try:
            locations = self.app.config_manager.get_all_locations()
            location_names = [loc.name for loc in locations]
            self.location_dropdown.set_items(location_names)

            # Select current location
            current = self.app.config_manager.get_current_location()
            if current and current.name in location_names:
                self.location_dropdown.set_index_to_item(current.name)
        except Exception as e:
            logger.error(f"Failed to populate locations: {e}")

    def _create_menu_bar(self) -> None:
        """Create the application menu bar."""
        menu_bar = wx.MenuBar()

        # File menu
        file_menu = wx.Menu()
        settings_item = file_menu.Append(wx.ID_PREFERENCES, "&Settings\tCtrl+S", "Open settings")
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, "E&xit\tCtrl+Q", "Exit the application")
        menu_bar.Append(file_menu, "&File")

        # Location menu
        location_menu = wx.Menu()
        add_item = location_menu.Append(wx.ID_ANY, "&Add Location\tCtrl+L", "Add a new location")
        remove_item = location_menu.Append(
            wx.ID_ANY, "&Remove Location\tCtrl+D", "Remove selected location"
        )
        menu_bar.Append(location_menu, "&Location")

        # View menu
        view_menu = wx.Menu()
        refresh_item = view_menu.Append(wx.ID_REFRESH, "&Refresh\tF5", "Refresh weather data")
        view_menu.AppendSeparator()
        explain_item = view_menu.Append(
            wx.ID_ANY, "&Explain Weather\tCtrl+E", "Get AI explanation of weather"
        )
        view_menu.AppendSeparator()
        history_item = view_menu.Append(
            wx.ID_ANY, "Weather &History\tCtrl+H", "View weather history"
        )
        discussion_item = view_menu.Append(
            wx.ID_ANY, "Forecast &Discussion...", "View NWS Area Forecast Discussion"
        )
        aviation_item = view_menu.Append(wx.ID_ANY, "&Aviation Weather...", "View aviation weather")
        air_quality_item = view_menu.Append(
            wx.ID_ANY, "Air &Quality...", "View air quality information"
        )
        uv_index_item = view_menu.Append(wx.ID_ANY, "&UV Index...", "View UV index information")
        menu_bar.Append(view_menu, "&View")

        # Tools menu
        tools_menu = wx.Menu()
        soundpack_item = tools_menu.Append(wx.ID_ANY, "&Soundpack Manager...", "Manage sound packs")
        menu_bar.Append(tools_menu, "&Tools")

        # Help menu
        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, "&About", "About AccessiWeather")
        menu_bar.Append(help_menu, "&Help")

        # Access the underlying wx.Frame control to set the menu bar and bind events
        frame = self.widget.control
        frame.SetMenuBar(menu_bar)

        # Bind menu events to the frame
        frame.Bind(wx.EVT_MENU, lambda e: self.on_settings(), settings_item)
        frame.Bind(wx.EVT_MENU, lambda e: self.app.request_exit(), exit_item)
        frame.Bind(wx.EVT_MENU, lambda e: self.on_add_location(), add_item)
        frame.Bind(wx.EVT_MENU, lambda e: self.on_remove_location(), remove_item)
        frame.Bind(wx.EVT_MENU, lambda e: self.on_refresh(), refresh_item)
        frame.Bind(wx.EVT_MENU, lambda e: self._on_explain_weather(), explain_item)
        frame.Bind(wx.EVT_MENU, lambda e: self.on_view_history(), history_item)
        frame.Bind(wx.EVT_MENU, lambda e: self._on_discussion(), discussion_item)
        frame.Bind(wx.EVT_MENU, lambda e: self._on_aviation(), aviation_item)
        frame.Bind(wx.EVT_MENU, lambda e: self._on_air_quality(), air_quality_item)
        frame.Bind(wx.EVT_MENU, lambda e: self._on_uv_index(), uv_index_item)
        frame.Bind(wx.EVT_MENU, lambda e: self._on_soundpack_manager(), soundpack_item)
        frame.Bind(wx.EVT_MENU, lambda e: self._on_about(), about_item)

    # Event handlers using gui_builder decorators
    @location_dropdown.add_callback
    def on_location_changed(self):
        """Handle location selection change."""
        selected = self.location_dropdown.get_choice()
        if selected:
            logger.info(f"Location changed to: {selected}")
            self._set_current_location(selected)
            self.refresh_weather_async()

    @add_button.add_callback
    def on_add_location(self):
        """Handle add location button click."""
        from .dialogs import show_add_location_dialog

        result = show_add_location_dialog(self.widget, self.app)
        if result:
            self._populate_locations()
            self.refresh_weather_async()

    @remove_button.add_callback
    def on_remove_location(self):
        """Handle remove location button click."""
        selected = self.location_dropdown.get_choice()
        if not selected:
            wx.MessageBox(
                "Please select a location to remove.",
                "No Location Selected",
                wx.OK | wx.ICON_WARNING,
            )
            return

        # Don't allow removing the last location
        locations = self.app.config_manager.get_all_locations()
        if len(locations) <= 1:
            wx.MessageBox(
                "Cannot remove the last location. Add another location first.",
                "Cannot Remove",
                wx.OK | wx.ICON_WARNING,
            )
            return

        # Confirm removal
        result = wx.MessageBox(
            f"Are you sure you want to remove '{selected}'?",
            "Confirm Removal",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if result == wx.YES:
            self.app.config_manager.remove_location(selected)
            self._populate_locations()
            self.refresh_weather_async()

    @refresh_button.add_callback
    def on_refresh(self):
        """Handle refresh button click."""
        self.refresh_weather_async()

    @explain_button.add_callback
    def on_explain(self):
        """Handle explain button click."""
        self._on_explain_weather()

    @discussion_button.add_callback
    def on_discussion(self):
        """Handle discussion button click."""
        self._on_discussion()

    @settings_button.add_callback
    def on_settings(self):
        """Handle settings button click."""
        from .dialogs import show_settings_dialog

        if show_settings_dialog(self.widget, self.app):
            self.app.refresh_runtime_settings()

    def on_view_history(self):
        """View weather history comparison."""
        from .dialogs import show_weather_history_dialog

        show_weather_history_dialog(self.widget, self.app)

    def _on_explain_weather(self):
        """Get AI explanation of current weather."""
        from .dialogs import show_explanation_dialog

        show_explanation_dialog(self.widget, self.app)

    def _on_discussion(self):
        """View NWS Area Forecast Discussion."""
        from .dialogs import show_discussion_dialog

        show_discussion_dialog(self.widget, self.app)

    def _on_aviation(self):
        """View aviation weather."""
        from .dialogs import show_aviation_dialog

        show_aviation_dialog(self.widget, self.app)

    def _on_air_quality(self):
        """View air quality information."""
        from .dialogs import show_air_quality_dialog

        show_air_quality_dialog(self.widget, self.app)

    def _on_uv_index(self):
        """View UV index information."""
        from .dialogs import show_uv_index_dialog

        show_uv_index_dialog(self.widget, self.app)

    def _on_soundpack_manager(self):
        """Open the soundpack manager dialog."""
        from .dialogs import show_soundpack_manager_dialog

        show_soundpack_manager_dialog(self.widget, self.app)

    def _on_about(self):
        """Show about dialog."""
        wx.MessageBox(
            "AccessiWeather\n\n"
            "An accessible weather application with NOAA and Open-Meteo support.\n\n"
            "Built with wxPython and gui_builder for screen reader compatibility.\n\n"
            "https://github.com/Orinks/AccessiWeather",
            "About AccessiWeather",
            wx.OK | wx.ICON_INFORMATION,
        )

    def _on_close(self, event):
        """Handle window close event."""
        # Check if minimize to tray is enabled
        if self._should_minimize_to_tray():
            self._minimize_to_tray()
            event.Veto()  # Prevent the window from being destroyed
            return

        # Otherwise, exit the application
        self.app.request_exit()

    def _on_iconize(self, event) -> None:
        """Handle window iconize (minimize) event."""
        # Check if minimize to tray is enabled and window is being minimized
        if event.IsIconized() and self._should_minimize_to_tray():
            # Use CallAfter to let the iconize event complete before hiding
            wx.CallAfter(self._minimize_to_tray)
            return
        event.Skip()  # Allow normal minimize behavior

    def _on_key_down(self, event) -> None:
        """Handle key down events for Escape key."""
        key_code = event.GetKeyCode()
        if key_code == wx.WXK_ESCAPE and self._should_minimize_to_tray():
            # Escape key pressed - minimize to tray
            self._minimize_to_tray()
            return
        event.Skip()  # Allow other key handling to proceed

    def _should_minimize_to_tray(self) -> bool:
        """
        Check if minimize to tray is enabled in settings.

        Returns:
            True if minimize to tray is enabled, False otherwise

        """
        try:
            settings = self.app.config_manager.get_settings()
            return bool(getattr(settings, "minimize_to_tray", False))
        except Exception:
            return False

    def _minimize_to_tray(self) -> None:
        """Minimize the window to the system tray."""
        try:
            frame = self.widget.control
            frame.Iconize(False)  # Restore from iconized state first
            frame.Hide()
            logger.debug("Window minimized to system tray")
        except Exception as e:
            logger.error(f"Failed to minimize to tray: {e}")

    def _set_current_location(self, location_name: str) -> None:
        """Set the current location."""
        try:
            # set_current_location expects a string (location name), not a Location object
            self.app.config_manager.set_current_location(location_name)
        except Exception as e:
            logger.error(f"Failed to set current location: {e}")

    def refresh_weather_async(self) -> None:
        """Refresh weather data asynchronously."""
        if self.app.is_updating:
            logger.debug("Already updating, skipping refresh")
            return

        self.app.is_updating = True
        self.set_status("Updating weather data...")
        self.refresh_button.disable()

        # Run async weather fetch
        self.app.run_async(self._fetch_weather_data())

    async def _fetch_weather_data(self) -> None:
        """Fetch weather data in background."""
        try:
            location = self.app.config_manager.get_current_location()
            if not location:
                wx.CallAfter(self._on_weather_error, "No location selected")
                return

            # Fetch weather data - pass the Location object directly
            weather_data = await self.app.weather_client.get_weather_data(location)

            # Update UI on main thread
            wx.CallAfter(self._on_weather_data_received, weather_data)

        except Exception as e:
            logger.error(f"Failed to fetch weather data: {e}")
            wx.CallAfter(self._on_weather_error, str(e))

    def _on_weather_data_received(self, weather_data) -> None:
        """Handle received weather data (called on main thread)."""
        try:
            self.app.current_weather_data = weather_data

            # Use presenter to create formatted presentation
            presentation = self.app.presenter.present(weather_data)

            # Update current conditions
            if presentation.current_conditions:
                self.current_conditions.set_value(presentation.current_conditions.fallback_text)
            else:
                self.current_conditions.set_value("No current conditions available.")

            # Update data source attribution
            if presentation.source_attribution and presentation.source_attribution.summary_text:
                self.data_source_label.set_label(presentation.source_attribution.summary_text)
            else:
                self.data_source_label.set_label("")

            # Update stale/cached data warning
            if presentation.status_messages:
                warning_text = " ".join(presentation.status_messages)
                self.stale_warning_label.set_label(warning_text)
            else:
                self.stale_warning_label.set_label("")

            # Update forecast
            if presentation.forecast:
                self.forecast_display.set_value(presentation.forecast.fallback_text)
            else:
                self.forecast_display.set_value("No forecast available.")

            # Update alerts
            self._update_alerts(weather_data.alerts)

            # Process alerts for desktop notifications
            if (
                weather_data.alerts
                and weather_data.alerts.has_alerts()
                and self.app.alert_notification_system
            ):
                self.app.run_async(
                    self.app.alert_notification_system.process_and_notify(weather_data.alerts)
                )

            location = self.app.config_manager.get_current_location()
            location_name = location.name if location else "Unknown"
            self.set_status(f"Weather updated for {location_name}")

            # Update system tray tooltip with current weather
            self.app.update_tray_tooltip(weather_data, location_name)

        except Exception as e:
            logger.error(f"Failed to update weather display: {e}")
            self.set_status(f"Error updating display: {e}")

        finally:
            self.app.is_updating = False
            self.refresh_button.enable()

    def _on_weather_error(self, error_message: str) -> None:
        """Handle weather fetch error (called on main thread)."""
        self.set_status(f"Error: {error_message}")
        self.app.is_updating = False
        self.refresh_button.enable()

    def _update_alerts(self, alerts) -> None:
        """Update the alerts list."""
        alert_items = []
        alert_list = []

        # Handle WeatherAlerts object or list
        if alerts:
            if hasattr(alerts, "alerts"):
                alert_list = alerts.alerts or []
            elif hasattr(alerts, "get_active_alerts"):
                alert_list = alerts.get_active_alerts() or []
            elif isinstance(alerts, list):
                alert_list = alerts

        for alert in alert_list:
            event = getattr(alert, "event", "Unknown")
            severity = getattr(alert, "severity", "Unknown")
            alert_items.append(f"{event} ({severity})")

        self.alerts_panel.alerts_list.set_items(alert_items)

        # Enable/disable view button based on alerts
        if alert_items:
            self.alerts_panel.view_alert_button.enable()
        else:
            self.alerts_panel.view_alert_button.disable()

    def _show_alert_details(self, alert_index: int) -> None:
        """Show details for the selected alert."""
        if not self.app.current_weather_data or not self.app.current_weather_data.alerts:
            return

        alerts = self.app.current_weather_data.alerts
        if 0 <= alert_index < len(alerts.alerts):
            alert = alerts.alerts[alert_index]
            from .dialogs import show_alert_dialog

            show_alert_dialog(self.widget, alert)

    def set_status(self, message: str) -> None:
        """Set the status label text."""
        self.status_label.set_label(message)
        logger.info(f"Status: {message}")
