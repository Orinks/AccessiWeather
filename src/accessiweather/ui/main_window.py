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
    from ..models.location import Location

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
        self._fetch_generation = 0  # Tracks which fetch is current (prevents stale updates)

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
        self.location_dropdown = wx.Choice(
            location_panel,
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
        self.location_dropdown.Bind(wx.EVT_CHOICE, self._on_location_changed)

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
        self._noaa_radio_id = wx.NewIdRef()
        noaa_radio_item = view_menu.Append(
            self._noaa_radio_id, "NOAA Weather &Radio...\tCtrl+R", "Listen to NOAA Weather Radio"
        )
        view_menu.AppendSeparator()
        weather_chat_item = view_menu.Append(
            wx.ID_ANY, "Weather &Assistant...\tCtrl+T", "Chat with AI weather assistant"
        )
        menu_bar.Append(view_menu, "&View")

        # Tools menu
        tools_menu = wx.Menu()
        soundpack_item = tools_menu.Append(wx.ID_ANY, "&Soundpack Manager...", "Manage sound packs")
        menu_bar.Append(tools_menu, "&Tools")

        # Help menu
        help_menu = wx.Menu()

        # Check for updates - show current channel in label
        channel = self._get_update_channel()
        self._check_updates_item = help_menu.Append(
            wx.ID_ANY,
            f"Check for &Updates ({channel.title()})...",
            "Check for application updates",
        )
        help_menu.AppendSeparator()

        report_issue_item = help_menu.Append(
            wx.ID_ANY, "&Report Issue...", "Report a bug or request a feature"
        )
        help_menu.AppendSeparator()
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
        self.Bind(wx.EVT_MENU, lambda e: self._on_noaa_radio(), noaa_radio_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_weather_chat(), weather_chat_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_soundpack_manager(), soundpack_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_check_updates(), self._check_updates_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_report_issue(), report_issue_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_about(), about_item)

    def _on_location_changed(self, event) -> None:
        """Handle location selection change with debounce for rapid switching."""
        selected = self.location_dropdown.GetStringSelection()
        if not selected:
            return

        logger.info(f"Location changed to: {selected}")
        self._set_current_location(selected)

        # Show cached data instantly if available
        location = self.app.config_manager.get_current_location()
        if location and hasattr(self.app, "weather_client") and self.app.weather_client:
            cached = self.app.weather_client.get_cached_weather(location)
            if cached and cached.has_any_data():
                logger.info(f"Showing cached data for {selected} while refreshing")
                self._on_weather_data_received(cached)

        # Debounce: cancel pending fetch, wait 500ms before fetching
        if hasattr(self, "_location_debounce_timer") and self._location_debounce_timer.IsRunning():
            self._location_debounce_timer.Stop()

        if not hasattr(self, "_location_debounce_timer"):
            self._location_debounce_timer = wx.Timer(self)
            self.Bind(
                wx.EVT_TIMER, self._on_debounced_location_fetch, self._location_debounce_timer
            )

        self._location_debounce_timer.StartOnce(500)

    def _on_debounced_location_fetch(self, event) -> None:
        """Fetch weather data after debounce period for the currently selected location."""
        self.refresh_weather_async(force_refresh=True)

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
        self.open_settings()

    def open_settings(self, tab: str | None = None) -> None:
        """
        Open the settings dialog, optionally to a specific tab.

        Args:
            tab: Optional tab name to switch to (e.g., 'Updates', 'General').

        """
        from .dialogs import show_settings_dialog

        if show_settings_dialog(self, self.app, tab=tab):
            self.app.refresh_runtime_settings()
            # Update menu label in case update channel changed
            self.update_check_updates_menu_label()

    def on_view_history(self) -> None:
        """View weather history comparison."""
        from .dialogs import show_weather_history_dialog

        show_weather_history_dialog(self, self.app)

    def _on_explain_weather(self) -> None:
        """Get AI explanation of current weather."""
        from .dialogs import show_explanation_dialog

        show_explanation_dialog(self, self.app)

    def _on_discussion(self) -> None:
        """View NWS Area Forecast Discussion, or Nationwide discussions if Nationwide is selected."""
        current = self.app.config_manager.get_current_location()
        if current and current.name == "Nationwide":
            from .dialogs.nationwide_discussion_dialog import NationwideDiscussionDialog

            dlg = NationwideDiscussionDialog(parent=self, service=self._get_discussion_service())
            dlg.ShowModal()
            dlg.Destroy()
        else:
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

    def _on_noaa_radio(self) -> None:
        """Open NOAA Weather Radio dialog."""
        location = self.app.config_manager.get_current_location()
        if not location:
            wx.MessageBox(
                "Please select a location first.",
                "No Location Selected",
                wx.OK | wx.ICON_WARNING,
            )
            return

        from .dialogs import show_noaa_radio_dialog

        show_noaa_radio_dialog(self, location.latitude, location.longitude)

    def _on_weather_chat(self) -> None:
        """Open Weather Assistant dialog."""
        from .dialogs import show_weather_assistant_dialog

        show_weather_assistant_dialog(self, self.app)

    def _on_soundpack_manager(self) -> None:
        """Open the soundpack manager dialog."""
        from .dialogs import show_soundpack_manager_dialog

        show_soundpack_manager_dialog(self, self.app)

    def _get_update_channel(self) -> str:
        """Get the configured update channel from settings."""
        try:
            settings = self.app.config_manager.get_settings()
            return getattr(settings, "update_channel", "stable")
        except Exception:
            return "stable"

    def _on_check_updates(self) -> None:
        """Check for updates from the Help menu."""
        import asyncio
        import sys

        from ..services.simple_update import UpdateService, parse_nightly_date

        # Skip update checks when running from source
        if not getattr(sys, "frozen", False):
            wx.MessageBox(
                "Update checking is only available in installed builds.\n"
                "You're running from source — use git pull to update.",
                "Running from Source",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        channel = self._get_update_channel()
        current_version = getattr(self.app, "version", "0.0.0")
        build_tag = getattr(self.app, "build_tag", None)
        current_nightly_date = parse_nightly_date(build_tag) if build_tag else None
        # Show nightly date as the display version when running a nightly build
        display_version = current_nightly_date if current_nightly_date else current_version

        # Show checking status
        wx.BeginBusyCursor()

        def do_check():
            try:

                async def check():
                    service = UpdateService("AccessiWeather")
                    try:
                        return await service.check_for_updates(
                            current_version=current_version,
                            current_nightly_date=current_nightly_date,
                            channel=channel,
                        )
                    finally:
                        await service.close()

                update_info = asyncio.run(check())
                wx.CallAfter(wx.EndBusyCursor)

                if update_info is None:
                    # No update available - show appropriate message
                    if current_nightly_date and channel == "stable":
                        msg = (
                            f"You're on nightly ({current_nightly_date}).\n"
                            "No newer stable release available."
                        )
                    elif current_nightly_date:
                        msg = f"You're on the latest nightly ({current_nightly_date})."
                    else:
                        msg = f"You're up to date ({display_version})."

                    wx.CallAfter(
                        wx.MessageBox,
                        msg,
                        "No Updates Available",
                        wx.OK | wx.ICON_INFORMATION,
                    )
                else:
                    # Update available
                    channel_label = "nightly" if update_info.is_nightly else "stable"

                    def prompt():
                        result = wx.MessageBox(
                            f"A new {channel_label} update is available!\n\n"
                            f"Current: {display_version}\n"
                            f"Latest: {update_info.version}\n\n"
                            "Download now?",
                            "Update Available",
                            wx.YES_NO | wx.ICON_INFORMATION,
                        )
                        if result == wx.YES:
                            self.app._download_and_apply_update(update_info)

                    wx.CallAfter(prompt)

            except Exception as e:
                wx.CallAfter(wx.EndBusyCursor)
                wx.CallAfter(
                    wx.MessageBox,
                    f"Failed to check for updates:\n{e}",
                    "Update Check Failed",
                    wx.OK | wx.ICON_ERROR,
                )

        import threading

        thread = threading.Thread(target=do_check, daemon=True)
        thread.start()

    def update_check_updates_menu_label(self) -> None:
        """Update the Check for Updates menu item label with current channel."""
        channel = self._get_update_channel()
        self._check_updates_item.SetItemLabel(f"Check for &Updates ({channel.title()})...")

    def _on_report_issue(self) -> None:
        """Open the report issue dialog."""
        from .dialogs.report_issue_dialog import ReportIssueDialog

        dialog = ReportIssueDialog(self)
        dialog.ShowModal()
        dialog.Destroy()

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
        """
        Set up accelerator table for Escape key and menu shortcuts.

        wxPython's SetAcceleratorTable replaces the implicit menu accelerators,
        so we must include all Ctrl+ shortcuts here alongside Escape.
        """
        self._escape_id = wx.NewIdRef()
        entries = [
            (wx.ACCEL_NORMAL, wx.WXK_ESCAPE, self._escape_id),
        ]
        # Re-register menu accelerators that would otherwise be lost
        if hasattr(self, "_noaa_radio_id"):
            entries.append((wx.ACCEL_CTRL, ord("R"), self._noaa_radio_id))
        accel_tbl = wx.AcceleratorTable(entries)
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
        """Set the current location and persist to config."""
        try:
            # set_current_location expects a string (location name), not a Location object
            result = self.app.config_manager.set_current_location(location_name)
            if not result:
                logger.error(
                    f"Failed to set current location '{location_name}': "
                    "location not found or save failed"
                )
            else:
                logger.info(f"Current location set and saved: {location_name}")
        except Exception as e:
            logger.error(f"Failed to set current location: {e}")

    def refresh_weather_async(self, force_refresh: bool = False) -> None:
        """Refresh weather data asynchronously."""
        # Increment generation to invalidate any in-flight fetches
        self._fetch_generation += 1

        if self.app.is_updating and not force_refresh:
            logger.debug("Already updating, skipping refresh")
            return

        self.app.is_updating = True
        self.set_status("Updating weather data...")
        self.refresh_button.Disable()

        # Run async weather fetch with current generation
        generation = self._fetch_generation
        self.app.run_async(
            self._fetch_weather_data(force_refresh=force_refresh, generation=generation)
        )

    async def _fetch_weather_data(self, force_refresh: bool = False, generation: int = 0) -> None:
        """Fetch weather data in background."""
        try:
            location = self.app.config_manager.get_current_location()
            if not location:
                wx.CallAfter(self._on_weather_error, "No location selected")
                return

            # For Nationwide location, fetch discussion summaries instead of weather
            if location.name == "Nationwide":
                wx.CallAfter(
                    self.current_conditions.SetValue,
                    "Fetching nationwide weather discussions from NWS, SPC, NHC, and CPC...\n"
                    "This may take a moment.",
                )
                wx.CallAfter(self.forecast_display.SetValue, "")
                await self._fetch_nationwide_discussions(generation)
                return

            # Fetch weather data - pass the Location object directly
            # force_refresh=True bypasses cache (used when switching locations)
            weather_data = await self.app.weather_client.get_weather_data(
                location, force_refresh=force_refresh
            )

            # Only update UI if this fetch is still current (not superseded by a newer one)
            if generation != self._fetch_generation:
                logger.debug(
                    f"Discarding stale fetch for {location.name} "
                    f"(gen {generation} < {self._fetch_generation})"
                )
                return

            # Update UI on main thread
            wx.CallAfter(self._on_weather_data_received, weather_data)

            # Pre-warm cache for other locations in background (non-blocking)
            if not force_refresh:
                await self._pre_warm_other_locations(location)

        except Exception as e:
            logger.error(f"Failed to fetch weather data: {e}")
            wx.CallAfter(self._on_weather_error, str(e))

    def _get_discussion_service(self):
        """Get or create the shared NationalDiscussionService instance."""
        if not hasattr(self, "_discussion_service") or self._discussion_service is None:
            from ..services.national_discussion_service import NationalDiscussionService

            self._discussion_service = NationalDiscussionService()
        return self._discussion_service

    async def _fetch_nationwide_discussions(self, generation: int) -> None:
        """Fetch nationwide discussion summaries and display in weather fields."""
        import asyncio

        try:
            service = self._get_discussion_service()
            # Run synchronous fetch in thread to avoid blocking
            discussions = await asyncio.to_thread(service.fetch_all_discussions)

            if generation != self._fetch_generation:
                return

            # Build current conditions text (short range + SPC day 1)
            current_parts = ["=== Nationwide Weather Summary ===\n"]
            wpc = discussions.get("wpc", {})
            if wpc.get("short_range", {}).get("text"):
                current_parts.append(
                    f"--- {wpc['short_range']['title']} ---\n{wpc['short_range']['text']}\n"
                )
            spc = discussions.get("spc", {})
            if spc.get("day1", {}).get("text"):
                current_parts.append(f"--- {spc['day1']['title']} ---\n{spc['day1']['text']}\n")
            current_text = "\n".join(current_parts)

            # Build forecast text (extended + CPC outlooks)
            forecast_parts = ["=== Extended Outlook ===\n"]
            if wpc.get("extended", {}).get("text"):
                forecast_parts.append(
                    f"--- {wpc['extended']['title']} ---\n{wpc['extended']['text']}\n"
                )
            cpc = discussions.get("cpc", {})
            if cpc.get("outlook", {}).get("text"):
                forecast_parts.append(
                    f"--- {cpc['outlook']['title']} ---\n{cpc['outlook']['text']}\n"
                )
            forecast_text = "\n".join(forecast_parts)

            wx.CallAfter(self._on_nationwide_data_received, current_text, forecast_text)

        except Exception as e:
            logger.error(f"Failed to fetch nationwide discussions: {e}")
            wx.CallAfter(self._on_weather_error, str(e))

    def _on_nationwide_data_received(self, current_text: str, forecast_text: str) -> None:
        """Handle received nationwide discussion data (called on main thread)."""
        try:
            self.current_conditions.SetValue(current_text)
            self.forecast_display.SetValue(forecast_text)
            self.stale_warning_label.SetLabel("")
            self.set_status("Nationwide discussions updated")
        except Exception as e:
            logger.error(f"Error updating nationwide display: {e}")
        finally:
            self.app.is_updating = False
            self.refresh_button.Enable()

    async def _pre_warm_other_locations(self, current_location: Location) -> None:
        """Pre-warm cache for non-current locations so switching is instant."""
        try:
            all_locations = self.app.config_manager.get_all_locations()
            for loc in all_locations:
                if loc.name != current_location.name:
                    # Check if already cached
                    cached = self.app.weather_client.get_cached_weather(loc)
                    if not cached or not cached.has_any_data():
                        logger.debug(f"Pre-warming cache for {loc.name}")
                        await self.app.weather_client.pre_warm_cache(loc)
        except Exception as e:
            logger.debug(f"Cache pre-warm failed (non-critical): {e}")

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
