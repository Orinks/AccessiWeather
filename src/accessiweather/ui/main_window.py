"""
Main window for AccessiWeather using plain wxPython.

This module defines the main application window using standard wxPython
widgets for optimal screen reader compatibility.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx
from wx.lib.sized_controls import SizedFrame, SizedPanel

if TYPE_CHECKING:
    from ..app import AccessiWeatherApp

logger = logging.getLogger(__name__)


class MainWindow(SizedFrame):
    """
    Main application window using plain wxPython.

    This provides the primary UI for AccessiWeather with:
    - Location selection dropdown
    - Current conditions display
    - Forecast display
    - Weather alerts list
    - Control buttons
    """

    def __init__(self, app: AccessiWeatherApp, title: str = "AccessiWeather", **kwargs):
        """
        Initialize the main window.

        Args:
            app: The AccessiWeather application instance
            title: Window title
            **kwargs: Additional keyword arguments passed to SizedFrame

        """
        super().__init__(parent=None, title=title, **kwargs)
        self.app = app
        self._escape_id = None

        # Create the UI
        self._create_widgets()
        self._create_menu_bar()
        self._bind_events()
        self._setup_escape_accelerator()

        # Set initial window size
        self.SetSize((800, 600))

        # Populate initial data
        self._populate_locations()

    def _create_widgets(self) -> None:
        """Create all UI widgets."""
        panel = self.GetContentsPane()
        panel.SetSizerType("vertical")

        # Location section
        location_panel = SizedPanel(panel)
        location_panel.SetSizerType("horizontal")
        location_panel.SetSizerProps(expand=True)

        wx.StaticText(location_panel, label="Location:")
        self.location_dropdown = wx.ComboBox(
            location_panel,
            style=wx.CB_READONLY,
            name="Location selection",
        )
        self.location_dropdown.SetSizerProps(expand=True, proportion=1)

        # Status display
        self.status_label = wx.StaticText(panel, label="")
        self.status_label.SetSizerProps(expand=True)

        # Stale/cached data warning
        self.stale_warning_label = wx.StaticText(panel, label="")
        self.stale_warning_label.SetSizerProps(expand=True)

        # Current conditions section
        wx.StaticText(panel, label="Current Conditions:")
        self.current_conditions = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="Current weather conditions",
        )
        self.current_conditions.SetSizerProps(expand=True, proportion=1)

        # Forecast section
        wx.StaticText(panel, label="Forecast:")
        self.forecast_display = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="Weather forecast",
        )
        self.forecast_display.SetSizerProps(expand=True, proportion=1)

        # Weather alerts section
        alerts_panel = SizedPanel(panel)
        alerts_panel.SetSizerType("vertical")
        alerts_panel.SetSizerProps(expand=True)

        wx.StaticText(alerts_panel, label="Weather Alerts:")
        self.alerts_list = wx.ListBox(
            alerts_panel,
            name="Weather alerts list",
        )
        self.alerts_list.SetSizerProps(expand=True, proportion=1)

        self.view_alert_button = wx.Button(alerts_panel, label="View Alert Details")
        self.view_alert_button.Disable()  # Disabled until alerts are available

        # Control buttons
        button_panel = SizedPanel(panel)
        button_panel.SetSizerType("horizontal")
        button_panel.SetSizerProps(expand=True)

        self.add_button = wx.Button(button_panel, label="&Add")
        self.remove_button = wx.Button(button_panel, label="Re&move")
        self.refresh_button = wx.Button(button_panel, label="&Refresh")
        self.explain_button = wx.Button(button_panel, label="&Explain")
        self.discussion_button = wx.Button(button_panel, label="&Discussion")
        self.settings_button = wx.Button(button_panel, label="&Settings")

    def _bind_events(self) -> None:
        """Bind all event handlers."""
        # Window events
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_ICONIZE, self._on_iconize)
        self.Bind(wx.EVT_SHOW, self._on_window_shown)

        # Location dropdown
        self.location_dropdown.Bind(wx.EVT_COMBOBOX, self._on_location_changed)

        # Buttons
        self.add_button.Bind(wx.EVT_BUTTON, lambda e: self.on_add_location())
        self.remove_button.Bind(wx.EVT_BUTTON, lambda e: self.on_remove_location())
        self.refresh_button.Bind(wx.EVT_BUTTON, lambda e: self.on_refresh())
        self.explain_button.Bind(wx.EVT_BUTTON, lambda e: self._on_explain_weather())
        self.discussion_button.Bind(wx.EVT_BUTTON, lambda e: self._on_discussion())
        self.settings_button.Bind(wx.EVT_BUTTON, lambda e: self.on_settings())
        self.view_alert_button.Bind(wx.EVT_BUTTON, self._on_view_alert)

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
            self.location_dropdown.SetFocus()
            logger.debug("Initial focus set to location dropdown")
        except Exception as e:
            logger.debug(f"Could not set initial focus: {e}")

    def _populate_locations(self) -> None:
        """Populate the location dropdown with saved locations."""
        try:
            locations = self.app.config_manager.get_all_locations()
            location_names = [loc.name for loc in locations]
            self.location_dropdown.Clear()
            self.location_dropdown.Append(location_names)

            # Select current location
            current = self.app.config_manager.get_current_location()
            if current and current.name in location_names:
                idx = location_names.index(current.name)
                self.location_dropdown.SetSelection(idx)
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

        self.SetMenuBar(menu_bar)

        # Bind menu events
        self.Bind(wx.EVT_MENU, lambda e: self.on_settings(), settings_item)
        self.Bind(wx.EVT_MENU, lambda e: self.app.request_exit(), exit_item)
        self.Bind(wx.EVT_MENU, lambda e: self.on_add_location(), add_item)
        self.Bind(wx.EVT_MENU, lambda e: self.on_remove_location(), remove_item)
        self.Bind(wx.EVT_MENU, lambda e: self.on_refresh(), refresh_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_explain_weather(), explain_item)
        self.Bind(wx.EVT_MENU, lambda e: self.on_view_history(), history_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_discussion(), discussion_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_aviation(), aviation_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_air_quality(), air_quality_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_uv_index(), uv_index_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_soundpack_manager(), soundpack_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_about(), about_item)

    def _on_location_changed(self, event) -> None:
        """Handle location selection change."""
        selected = self.location_dropdown.GetStringSelection()
        if selected:
            logger.info(f"Location changed to: {selected}")
            self._set_current_location(selected)
            self.refresh_weather_async()

    def on_add_location(self) -> None:
        """Handle add location button click."""
        from .dialogs import show_add_location_dialog

        result = show_add_location_dialog(self, self.app)
        if result:
            self._populate_locations()
            self.refresh_weather_async()

    def on_remove_location(self) -> None:
        """Handle remove location button click."""
        selected = self.location_dropdown.GetStringSelection()
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

    def on_refresh(self) -> None:
        """Handle refresh button click."""
        self.refresh_weather_async()

    def on_settings(self) -> None:
        """Handle settings button click."""
        from .dialogs import show_settings_dialog

        if show_settings_dialog(self, self.app):
            self.app.refresh_runtime_settings()

    def on_view_history(self) -> None:
        """View weather history comparison."""
        from .dialogs import show_weather_history_dialog

        show_weather_history_dialog(self, self.app)

    def _on_explain_weather(self) -> None:
        """Get AI explanation of current weather."""
        from .dialogs import show_explanation_dialog

        show_explanation_dialog(self, self.app)

    def _on_discussion(self) -> None:
        """View NWS Area Forecast Discussion."""
        from .dialogs import show_discussion_dialog

        show_discussion_dialog(self, self.app)

    def _on_aviation(self) -> None:
        """View aviation weather."""
        from .dialogs import show_aviation_dialog

        show_aviation_dialog(self, self.app)

    def _on_air_quality(self) -> None:
        """View air quality information."""
        from .dialogs import show_air_quality_dialog

        show_air_quality_dialog(self, self.app)

    def _on_uv_index(self) -> None:
        """View UV index information."""
        from .dialogs import show_uv_index_dialog

        show_uv_index_dialog(self, self.app)

    def _on_soundpack_manager(self) -> None:
        """Open the soundpack manager dialog."""
        from .dialogs import show_soundpack_manager_dialog

        show_soundpack_manager_dialog(self, self.app)

    def _on_about(self) -> None:
        """Show about dialog."""
        wx.MessageBox(
            "AccessiWeather\n\n"
            "An accessible weather application with NOAA and Open-Meteo support.\n\n"
            "Built with wxPython for screen reader compatibility.\n\n"
            "https://github.com/Orinks/AccessiWeather",
            "About AccessiWeather",
            wx.OK | wx.ICON_INFORMATION,
        )

    def _on_view_alert(self, event) -> None:
        """Handle view alert button click."""
        selected = self.alerts_list.GetSelection()
        if selected != wx.NOT_FOUND:
            self._show_alert_details(selected)

    def _on_close(self, event) -> None:
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

    def _setup_escape_accelerator(self) -> None:
        """Set up accelerator table for Escape key to minimize to tray."""
        # Create a unique ID for the escape action
        self._escape_id = wx.NewIdRef()
        # Create accelerator table with just Escape key
        accel_tbl = wx.AcceleratorTable([(wx.ACCEL_NORMAL, wx.WXK_ESCAPE, self._escape_id)])
        self.SetAcceleratorTable(accel_tbl)
        # Bind the escape action
        self.Bind(wx.EVT_MENU, self._on_escape_pressed, id=self._escape_id)

    def _on_escape_pressed(self, event) -> None:
        """Handle Escape key press via accelerator."""
        if self._should_minimize_to_tray():
            self._minimize_to_tray()
        # If minimize to tray is disabled, do nothing (Escape has no effect)

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
            self.Iconize(False)  # Restore from iconized state first
            self.Hide()
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
        self.refresh_button.Disable()

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

            # Update current conditions (with data source attribution appended)
            current_text = ""
            if presentation.current_conditions:
                current_text = presentation.current_conditions.fallback_text
            else:
                current_text = "No current conditions available."

            # Append data source attribution to current conditions for screen reader accessibility
            if presentation.source_attribution and presentation.source_attribution.summary_text:
                current_text += f"\n\n{presentation.source_attribution.summary_text}"

            self.current_conditions.SetValue(current_text)

            # Update stale/cached data warning
            if presentation.status_messages:
                warning_text = " ".join(presentation.status_messages)
                self.stale_warning_label.SetLabel(warning_text)
            else:
                self.stale_warning_label.SetLabel("")

            # Update forecast
            if presentation.forecast:
                self.forecast_display.SetValue(presentation.forecast.fallback_text)
            else:
                self.forecast_display.SetValue("No forecast available.")

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

            # Process notification events (AFD updates, severe risk changes)
            self._process_notification_events(weather_data)

        except Exception as e:
            logger.error(f"Failed to update weather display: {e}")
            self.set_status(f"Error updating display: {e}")

        finally:
            self.app.is_updating = False
            self.refresh_button.Enable()

    def _on_weather_error(self, error_message: str) -> None:
        """Handle weather fetch error (called on main thread)."""
        self.set_status(f"Error: {error_message}")
        self.app.is_updating = False
        self.refresh_button.Enable()

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

        self.alerts_list.Clear()
        if alert_items:
            self.alerts_list.Append(alert_items)

        # Enable/disable view button based on alerts
        if alert_items:
            self.view_alert_button.Enable()
        else:
            self.view_alert_button.Disable()

    def _show_alert_details(self, alert_index: int) -> None:
        """Show details for the selected alert."""
        if not self.app.current_weather_data or not self.app.current_weather_data.alerts:
            return

        alerts = self.app.current_weather_data.alerts
        if 0 <= alert_index < len(alerts.alerts):
            alert = alerts.alerts[alert_index]
            from .dialogs import show_alert_dialog

            show_alert_dialog(self, alert)

    def set_status(self, message: str) -> None:
        """Set the status label text."""
        self.status_label.SetLabel(message)
        logger.info(f"Status: {message}")

    def _get_notification_event_manager(self):
        """Get or create the notification event manager for AFD/severe risk notifications."""
        if (
            not hasattr(self, "_notification_event_manager")
            or self._notification_event_manager is None
        ):
            from ..notifications.notification_event_manager import NotificationEventManager

            state_file = self.app.paths.config / "notification_event_state.json"
            self._notification_event_manager = NotificationEventManager(state_file=state_file)
        return self._notification_event_manager

    def _get_fallback_notifier(self):
        """Get or create a cached fallback notifier for event notifications."""
        if not hasattr(self, "_fallback_notifier") or self._fallback_notifier is None:
            from ..notifications.toast_notifier import SafeDesktopNotifier

            self._fallback_notifier = SafeDesktopNotifier()
        return self._fallback_notifier

    def _process_notification_events(self, weather_data) -> None:
        """
        Process weather data for notification events.

        Checks for:
        - Area Forecast Discussion (AFD) updates (NWS US only)
        - Severe weather risk level changes (Visual Crossing only)

        Both are opt-in notifications (disabled by default).
        """
        try:
            settings = self.app.config_manager.get_settings()

            # Skip if neither notification type is enabled
            if not settings.notify_discussion_update and not settings.notify_severe_risk_change:
                return

            location = self.app.config_manager.get_current_location()
            if not location:
                return

            # Get notifier from app or use cached fallback
            notifier = getattr(self.app, "notifier", None)
            if not notifier:
                notifier = self._get_fallback_notifier()

            # Get event manager and check for events
            event_manager = self._get_notification_event_manager()
            events = event_manager.check_for_events(weather_data, settings, location.name)

            # Send notifications for each event
            for event in events:
                try:
                    success = notifier.send_notification(
                        title=event.title,
                        message=event.message,
                        timeout=10,
                    )

                    if success and settings.sound_enabled:
                        import contextlib

                        from ..notifications.sound_player import play_notification_sound

                        with contextlib.suppress(Exception):
                            play_notification_sound(event.sound_event, settings.sound_pack)

                    if success:
                        logger.info("Sent %s notification: %s", event.event_type, event.title)

                except Exception as e:
                    logger.warning("Failed to send event notification: %s", e)

        except Exception as e:
            logger.debug("Error processing notification events: %s", e)
