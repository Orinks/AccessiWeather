"""MainWindowUIMixin helpers for the main window."""
# ruff: noqa: F403, F405

from __future__ import annotations

from .main_window_shared import *  # noqa: F403


class MainWindowUIMixin:
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

        # Optional: place Add/Edit/Remove on the location row instead of the
        # bottom button panel.  Grouped spatially with the dropdown they act on,
        # at the cost of inserting buttons between the dropdown and the forecast
        # content in the tab order.
        location_buttons_on_top = getattr(
            self.app.config_manager.get_settings(),
            "location_buttons_on_top",
            False,
        )
        if location_buttons_on_top:
            self.add_button = wx.Button(location_panel, label=QUICK_ACTION_LABELS["add"])
            self.edit_button = wx.Button(location_panel, label=QUICK_ACTION_LABELS["edit"])
            self.remove_button = wx.Button(location_panel, label=QUICK_ACTION_LABELS["remove"])

        # Current conditions section
        wx.StaticText(panel, label="Current Conditions:")
        self.current_conditions = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="Current weather conditions",
        )
        self.current_conditions.SetSizerProps(expand=True, proportion=1)

        # Forecast section
        self._hourly_forecast_label = wx.StaticText(panel, label="Hourly Forecast:")
        self.hourly_forecast_display = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="Hourly weather forecast",
        )
        self.hourly_forecast_display.SetSizerProps(expand=True, proportion=1)

        self._daily_forecast_label = wx.StaticText(panel, label="Daily Forecast:")
        self.daily_forecast_display = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="Daily weather forecast",
        )
        self.daily_forecast_display.SetSizerProps(expand=True, proportion=1)
        self.forecast_display = self.daily_forecast_display

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

        # Event Center section — displayed as "Recent Events" so users
        # immediately understand it's a reviewable log of recent notifications
        # and app events, not a live feed.
        self._event_center_visible = True
        self._event_center_label = wx.StaticText(panel, label="Recent Events:")
        self._event_center_tooltip_text = (
            "Reviewable log of recent weather notifications, AFD updates, "
            "forecast briefings, and other in-app events."
        )
        self._event_center_label.SetToolTip(self._event_center_tooltip_text)
        self.event_center_display = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="Recent events",
        )
        self.event_center_display.SetToolTip(self._event_center_tooltip_text)
        self.event_center_display.SetSizerProps(expand=True, proportion=1)

        # Control buttons
        button_panel = SizedPanel(panel)
        button_panel.SetSizerType("horizontal")
        button_panel.SetSizerProps(expand=True)

        if not location_buttons_on_top:
            self.add_button = wx.Button(button_panel, label=QUICK_ACTION_LABELS["add"])
            self.edit_button = wx.Button(button_panel, label=QUICK_ACTION_LABELS["edit"])
            self.remove_button = wx.Button(button_panel, label=QUICK_ACTION_LABELS["remove"])
        self.refresh_button = wx.Button(button_panel, label=QUICK_ACTION_LABELS["refresh"])
        self.explain_button = wx.Button(button_panel, label=QUICK_ACTION_LABELS["explain"])
        self.discussion_button = wx.Button(button_panel, label=QUICK_ACTION_LABELS["discussion"])
        self.settings_button = wx.Button(button_panel, label=QUICK_ACTION_LABELS["settings"])

        # Adjacent StaticText explaining why the Forecast Products button is
        # disabled for non-US locations. Screen readers announce adjacent
        # StaticText, which is the accessibility affordance for this reason
        # label (SetName/tooltips are ignored in this project).
        self.forecast_products_us_only_label = wx.StaticText(
            panel, label="Forecaster Notes are US-only"
        )
        self.forecast_products_us_only_label.Hide()

        # Status bar — two fields: [0] main status, [1] stale/cached warning
        self.CreateStatusBar(2)
        self.GetStatusBar().SetStatusWidths([-2, -1])
        self.stale_warning_label = _StaleWarningProxy(self)

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
        self.edit_button.Bind(wx.EVT_BUTTON, lambda e: self.on_edit_location())
        self.remove_button.Bind(wx.EVT_BUTTON, lambda e: self.on_remove_location())
        self.refresh_button.Bind(wx.EVT_BUTTON, lambda e: self.on_refresh())
        self.explain_button.Bind(wx.EVT_BUTTON, lambda e: self._on_explain_weather())
        self.discussion_button.Bind(wx.EVT_BUTTON, lambda e: self._on_discussion())
        self.settings_button.Bind(wx.EVT_BUTTON, lambda e: self.on_settings())
        self.view_alert_button.Bind(wx.EVT_BUTTON, self._on_view_alert)

        # Alerts list: open details on double-click or Enter/Space key.
        # EVT_CHAR_HOOK fires before the screen reader can consume the event,
        # so Enter/Space reach the handler even when NVDA is in forms mode.
        self.alerts_list.Bind(wx.EVT_LISTBOX_DCLICK, self._on_view_alert)
        self.alerts_list.Bind(wx.EVT_CHAR_HOOK, self._on_alerts_list_key)

    def _on_alerts_list_key(self, event) -> None:
        """Handle key presses in alerts list — Enter/Space opens details."""
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER, wx.WXK_SPACE):
            self._on_view_alert(event)
        else:
            event.Skip()

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
        """
        Populate the location dropdown with saved locations.

        "All Locations" is always the first entry.  Nationwide is not shown
        while the All Locations view is active (it is excluded from the
        per-location summary and does not make sense as a summary entry).
        """
        try:
            locations = self.app.config_manager.get_all_locations()
            # Exclude Nationwide from the per-location summary list but keep it
            # in the dropdown as its own selectable entry.
            location_names = [loc.name for loc in locations]
            all_names = [ALL_LOCATIONS_SENTINEL] + location_names
            self.location_dropdown.Clear()
            self.location_dropdown.Append(all_names)

            # Select current location if set; otherwise land on "All Locations".
            current = self.app.config_manager.get_current_location()
            if current and current.name in all_names:
                idx = all_names.index(current.name)
                self.location_dropdown.SetSelection(idx)
                self._update_title_for_location(current.name)
            else:
                self.location_dropdown.SetSelection(0)
                self._update_title_for_location(ALL_LOCATIONS_SENTINEL)
            self._update_forecast_products_button_state()
        except Exception as e:
            logger.error(f"Failed to populate locations: {e}")

    def _update_title_for_location(self, location_name: str | None) -> None:
        """
        Set the window title to include the active location.

        The title is used by the taskbar, screen readers on window focus,
        and Alt+Tab, so surfacing the active location there gives users
        orientation without needing to read the location dropdown.
        """
        base = "AccessiWeather"
        if location_name and location_name != ALL_LOCATIONS_SENTINEL:
            self.SetTitle(f"{base} \u2014 {location_name}")
        else:
            self.SetTitle(base)

    def _create_menu_bar(self) -> None:
        """Create the application menu bar."""
        menu_bar = wx.MenuBar()

        # File menu
        file_menu = wx.Menu()
        self._settings_id = wx.ID_PREFERENCES
        settings_item = file_menu.Append(self._settings_id, "&Settings\tCtrl+S", "Open settings")
        file_menu.AppendSeparator()
        self._exit_id = wx.ID_EXIT
        exit_item = file_menu.Append(self._exit_id, "E&xit\tCtrl+Q", "Exit the application")
        menu_bar.Append(file_menu, "&File")

        # Location menu
        location_menu = wx.Menu()
        self._add_location_id = wx.NewIdRef()
        add_item = location_menu.Append(
            self._add_location_id, "&Add Location\tCtrl+L", "Add a new location"
        )
        self._edit_location_id = wx.NewIdRef()
        edit_item = location_menu.Append(
            self._edit_location_id,
            "&Edit Location...",
            "Edit the selected location (e.g. enable Marine Mode)",
        )
        self._remove_location_id = wx.NewIdRef()
        remove_item = location_menu.Append(
            self._remove_location_id, "&Remove Location\tCtrl+D", "Remove selected location"
        )
        menu_bar.Append(location_menu, "&Location")

        # View menu
        view_menu = wx.Menu()
        refresh_item = view_menu.Append(wx.ID_REFRESH, "Re&fresh\tF5", "Refresh weather data")
        view_menu.AppendSeparator()
        self._explain_id = wx.NewIdRef()
        explain_item = view_menu.Append(
            self._explain_id, "&Explain Weather\tCtrl+E", "Get AI explanation of weather"
        )
        view_menu.AppendSeparator()
        self._history_id = wx.NewIdRef()
        history_item = view_menu.Append(
            self._history_id, "Weather &History\tCtrl+H", "View weather history"
        )
        self._precipitation_timeline_id = wx.NewIdRef()
        self._precipitation_timeline_item = view_menu.Append(
            self._precipitation_timeline_id,
            "Precipitation &Timeline...",
            "View Pirate Weather minute-by-minute precipitation guidance",
        )
        self._toggle_event_center_id = wx.NewIdRef()
        toggle_event_center_item = view_menu.AppendCheckItem(
            self._toggle_event_center_id,
            "Event &Center",
            "Show or hide the Event Center",
        )
        toggle_event_center_item.Check(True)
        discussion_item = view_menu.Append(
            wx.ID_ANY,
            "Forecaster &Notes...",
            "View NWS forecaster notes (AFD, HWO, SPS)",
        )
        aviation_item = view_menu.Append(wx.ID_ANY, "&Aviation Weather...", "View aviation weather")
        air_quality_item = view_menu.Append(
            wx.ID_ANY, "Air &Quality...", "View air quality information"
        )
        uv_index_item = view_menu.Append(wx.ID_ANY, "&UV Index...", "View UV index information")
        self._noaa_radio_id = wx.NewIdRef()
        view_menu.Append(
            self._noaa_radio_id,
            "NOAA Weather &Radio...\tCtrl+Shift+R",
            "Listen to NOAA Weather Radio",
        )
        view_menu.AppendSeparator()
        self._weather_chat_id = wx.NewIdRef()
        weather_chat_item = view_menu.Append(
            self._weather_chat_id, "Weather Assistan&t...\tCtrl+T", "Chat with AI weather assistant"
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
        user_manual_item = help_menu.Append(
            wx.ID_ANY,
            "User &Manual",
            "Open the AccessiWeather user manual",
        )
        self._debug_menu_items: dict[str, wx.MenuItem] = {}
        if getattr(self.app, "debug_mode", False):
            debug_menu = wx.Menu()
            self._debug_menu_items["discussion"] = debug_menu.Append(
                wx.ID_ANY,
                "Test: &Discussion Updated",
                "Fire a test notification as if the NWS discussion was updated",
            )
            self._debug_menu_items["alert"] = debug_menu.Append(
                wx.ID_ANY,
                "Test: &Alert Notification...",
                "Send a test alert notification (choose type and severity)",
            )
            self._debug_menu_items["simulate_alert"] = debug_menu.Append(
                wx.ID_ANY,
                "Test: &Simulate Alert Change (poll cycle)",
                "Inject a mock alert into the next event check cycle to test the full polling path",
            )
            debug_menu.AppendSeparator()
            self._debug_menu_items["diagnostics"] = debug_menu.Append(
                wx.ID_ANY,
                "Run Notification &Diagnostics",
                "Run pass/fail notification system diagnostics",
            )
            help_menu.AppendSubMenu(debug_menu, "&Debug", "Debug and test tools")
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
        self.Bind(wx.EVT_MENU, lambda e: self.on_edit_location(), edit_item)
        self.Bind(wx.EVT_MENU, lambda e: self.on_remove_location(), remove_item)
        self.Bind(wx.EVT_MENU, lambda e: self.on_refresh(), refresh_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_explain_weather(), explain_item)
        self.Bind(wx.EVT_MENU, lambda e: self.on_view_history(), history_item)
        self.Bind(
            wx.EVT_MENU,
            lambda e: self._on_precipitation_timeline(),
            id=self._precipitation_timeline_id,
        )
        self.Bind(
            wx.EVT_MENU, lambda e: self.toggle_event_center(), id=self._toggle_event_center_id
        )
        self.Bind(wx.EVT_MENU, lambda e: self._on_discussion(), discussion_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_aviation(), aviation_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_air_quality(), air_quality_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_uv_index(), uv_index_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_noaa_radio(), id=self._noaa_radio_id)
        self.Bind(wx.EVT_MENU, lambda e: self._on_weather_chat(), weather_chat_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_soundpack_manager(), soundpack_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_check_updates(), self._check_updates_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_open_user_manual(), user_manual_item)
        if self._debug_menu_items:
            self.Bind(
                wx.EVT_MENU,
                lambda e: self._on_test_discussion_notification(),
                self._debug_menu_items["discussion"],
            )
            self.Bind(
                wx.EVT_MENU,
                lambda e: self._on_test_alert_notification(),
                self._debug_menu_items["alert"],
            )
            self.Bind(
                wx.EVT_MENU,
                lambda e: self._on_test_notifications(),
                self._debug_menu_items["diagnostics"],
            )
            self.Bind(
                wx.EVT_MENU,
                lambda e: self._on_debug_simulate_alert(),
                self._debug_menu_items["simulate_alert"],
            )
        self.Bind(wx.EVT_MENU, lambda e: self._on_report_issue(), report_issue_item)
        self.Bind(wx.EVT_MENU, lambda e: self._on_about(), about_item)
        self._update_precipitation_timeline_menu_state(self)

    def _setup_escape_accelerator(self) -> None:
        """
        Set up accelerator table for Escape key and menu shortcuts.

        wxPython's SetAcceleratorTable replaces the implicit menu accelerators,
        so we must include all Ctrl+ shortcuts here alongside Escape.
        """
        self._escape_id = wx.NewIdRef()
        entries = [
            (wx.ACCEL_NORMAL, wx.WXK_ESCAPE, self._escape_id),
            (wx.ACCEL_NORMAL, wx.WXK_F5, wx.ID_REFRESH),
        ]
        # Re-register all Ctrl+ menu accelerators (SetAcceleratorTable replaces them)
        ctrl_shortcuts = [
            (wx.ACCEL_CTRL, "S", "_settings_id"),
            (wx.ACCEL_CTRL, "Q", "_exit_id"),
            (wx.ACCEL_CTRL, "L", "_add_location_id"),
            (wx.ACCEL_CTRL, "D", "_remove_location_id"),
            (wx.ACCEL_CTRL, "E", "_explain_id"),
            (wx.ACCEL_CTRL, "H", "_history_id"),
            (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, "R", "_noaa_radio_id"),
            (wx.ACCEL_CTRL, "T", "_weather_chat_id"),
        ]
        for flags, key, attr in ctrl_shortcuts:
            if hasattr(self, attr):
                entries.append((flags, ord(key), getattr(self, attr)))
        accel_tbl = wx.AcceleratorTable(entries)
        self.SetAcceleratorTable(accel_tbl)
        # Bind the escape action
        self.Bind(wx.EVT_MENU, self._on_escape_pressed, id=self._escape_id)

    def _on_escape_pressed(self, event) -> None:
        """Handle Escape key press via accelerator."""
        if self._should_minimize_to_tray():
            self._minimize_to_tray()

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
