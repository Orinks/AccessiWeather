"""MainWindowDisplayMixin helpers for the main window."""
# ruff: noqa: F403, F405

from __future__ import annotations

from .main_window_shared import *  # noqa: F403


class MainWindowDisplayMixin:
    def _set_forecast_sections(self, daily_text: str, hourly_text: str) -> None:
        """Update the daily and hourly forecast controls together."""
        self.daily_forecast_display.SetValue(daily_text)
        self.hourly_forecast_display.SetValue(hourly_text)

    def append_event_center_entry(self, text: str, *, category: str | None = None) -> None:
        """Append a timestamped reviewable line to the Event Center."""
        if not text:
            return
        timestamp = datetime.now().strftime("%I:%M %p").lstrip("0")
        prefix = f"{category}: " if category else ""
        entry = f"[{timestamp}] {prefix}{text}\n"
        self.event_center_display.AppendText(entry)

    def toggle_event_center(self) -> None:
        """Show or hide the Event Center section."""
        visible = not getattr(self, "_event_center_visible", True)
        self._event_center_visible = visible
        self._event_center_label.Show(visible)
        self.event_center_display.Show(visible)
        self.Layout()

    def focus_event_center(self) -> None:
        """Reveal and focus the Event Center section."""
        if not getattr(self, "_event_center_visible", True):
            self._event_center_visible = True
            self._event_center_label.Show(True)
            self.event_center_display.Show(True)
            self.Layout()
        self.event_center_display.SetFocus()

    def get_visible_top_level_sections(self) -> list[tuple[str, wx.Window]]:
        """Return the canonical visible top-level weather sections in focus order."""
        sections: list[tuple[str, wx.Window]] = [
            ("Location", self.location_dropdown),
            ("Current conditions", self.current_conditions),
            ("Hourly / near-term", self.hourly_forecast_display),
            ("Daily forecast", self.daily_forecast_display),
            ("Alerts", self.alerts_list),
        ]
        if getattr(self, "_event_center_visible", True):
            sections.append(("Event Center", self.event_center_display))
        return sections

    def focus_section_by_number(self, number: int) -> None:
        """Focus a canonical top-level section by its 1-based shortcut number."""
        if number == 5 and not getattr(self, "_event_center_visible", True):
            return

        sections = self.get_visible_top_level_sections()
        index = len(sections) - 1 if number == 5 else number
        if 0 <= index < len(sections):
            _label, widget = sections[index]
            widget.SetFocus()

    def cycle_section_focus(self) -> None:
        """Move focus to the next visible top-level section, wrapping at the end."""
        sections = self.get_visible_top_level_sections()
        if not sections:
            return

        next_index = getattr(self, "_section_focus_index", -1) + 1
        if next_index >= len(sections):
            next_index = 0

        self._section_focus_index = next_index
        _label, widget = sections[next_index]
        widget.SetFocus()

    def _set_forecast_sections_visible(self, visible: bool) -> None:
        """Show or hide the daily/hourly forecast labels and controls."""
        for attr in (
            "_daily_forecast_label",
            "daily_forecast_display",
            "_hourly_forecast_label",
            "hourly_forecast_display",
        ):
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.Show(visible)
        sizer = self.GetSizer() if callable(getattr(self, "GetSizer", None)) else None
        if sizer:
            sizer.Layout()

    def _on_weather_error(self, error_message: str) -> None:
        """Handle weather fetch error (called on main thread)."""
        self.set_status(f"Error: {error_message}")
        self.app.is_updating = False
        self.refresh_button.Enable()

        # Play fetch_error sound on weather data fetch failure
        try:
            settings = self.app.config_manager.get_settings()
            if getattr(settings, "sound_enabled", True):
                from accessiweather.notifications.sound_player import play_fetch_error_sound

                sound_pack = getattr(settings, "sound_pack", "default")
                muted_events = getattr(settings, "muted_sound_events", [])
                play_fetch_error_sound(sound_pack, muted_events=muted_events)
        except Exception as sound_exc:
            logger.debug(f"Failed to play fetch_error sound: {sound_exc}")

    def _update_alerts(self, alerts, lifecycle_labels: dict[str, str] | None = None) -> None:
        """
        Update the alerts list.

        Args:
            alerts: WeatherAlerts, a list of WeatherAlert, or None.
            lifecycle_labels: Optional mapping of alert_id -> label (e.g.
                "New", "Updated", "Escalated", "Extended").  When provided,
                the label is appended to each matching list item:
                "Dense Fog Advisory (Moderate) (Extended)".

        """
        alert_items = []
        alert_list = []

        # Handle WeatherAlerts object or list.
        # Prefer get_active_alerts() so expired alerts are never shown in the
        # listbox (cached data may contain alerts that expired while cached).
        if alerts:
            if hasattr(alerts, "get_active_alerts"):
                alert_list = alerts.get_active_alerts() or []
            elif hasattr(alerts, "alerts"):
                alert_list = alerts.alerts or []
            elif isinstance(alerts, list):
                alert_list = alerts

        for alert in alert_list:
            event = getattr(alert, "event", "Unknown")
            severity = getattr(alert, "severity", "Unknown")
            item = f"{event} ({severity})"
            if lifecycle_labels:
                get_uid = getattr(alert, "get_unique_id", None)
                if callable(get_uid):
                    label = lifecycle_labels.get(get_uid())
                    if label:
                        item = f"{item} ({label})"
            alert_items.append(item)

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
        # In All Locations mode alerts come from the aggregated list, not current_weather_data.
        if getattr(self, "_all_locations_active", False):
            data = getattr(self, "_all_locations_alerts_data", [])
            if 0 <= alert_index < len(data):
                _loc_name, alert = data[alert_index]
                from .dialogs import show_alert_dialog

                show_alert_dialog(self, alert, self.app.config_manager.get_settings())
            return

        if not self.app.current_weather_data or not self.app.current_weather_data.alerts:
            return

        alerts = self.app.current_weather_data.alerts
        active = alerts.get_active_alerts()
        if 0 <= alert_index < len(active):
            alert = active[alert_index]
            from .dialogs import show_alert_dialog

            show_alert_dialog(self, alert, self.app.config_manager.get_settings())

    def _show_all_locations_summary(self) -> None:
        """
        Build and display a cached-data summary for every saved location.

        No network requests are made.  The daily and hourly forecast sections
        are replaced with a short explanatory message because per-location
        forecasts are not meaningful in this aggregate view.  Alerts from all
        locations are collected and shown in the alerts list with the location
        name as a prefix so screen-reader users can identify the source.

        Nationwide is excluded from the summary because it is a special
        aggregate view of its own, not an individual saved location.
        """
        try:
            all_locs = [
                loc
                for loc in self.app.config_manager.get_all_locations()
                if loc.name != "Nationwide"
            ]
        except Exception as e:
            logger.error(f"Failed to get locations for All Locations summary: {e}")
            all_locs = []

        if not all_locs:
            self.current_conditions.SetValue(
                "No locations configured.\nUse the Add button or Ctrl+L to add a location."
            )
            self._set_forecast_sections("", "")
            self.alerts_list.Clear()
            self.view_alert_button.Disable()
            from . import main_window as base_module

            base_module.MainWindow._update_precipitation_timeline_menu_state(self)
            return

        lines: list[str] = ["All Locations Summary", ""]
        location_alerts: list[tuple[str, object]] = []

        weather_client = (
            self.app.weather_client
            if hasattr(self.app, "weather_client") and self.app.weather_client
            else None
        )

        for loc in all_locs:
            lines.append(f"--- {loc.name} ---")
            cached = weather_client.get_cached_weather(loc) if weather_client else None

            if cached and cached.has_any_data() and cached.current:
                cc = cached.current
                settings = self.app.config_manager.get_settings()
                temp_unit_pref = settings.temperature_unit
                temp_unit = resolve_temperature_unit_preference(temp_unit_pref, loc)
                round_values = getattr(settings, "round_values", False) if settings else False
                precision = 0 if round_values else get_temperature_precision(temp_unit)
                temp_str = format_temperature(
                    cc.temperature_f,
                    unit=temp_unit,
                    temperature_c=cc.temperature_c,
                    precision=precision,
                )
                cond_str = cc.condition or "Unknown"
                lines.append(f"  Temperature: {temp_str}")
                lines.append(f"  Condition: {cond_str}")

                # Collect active alerts for this location.
                active_alerts: list[object] = []
                if cached.alerts is not None:
                    if hasattr(cached.alerts, "get_active_alerts"):
                        active_alerts = cached.alerts.get_active_alerts() or []
                    elif hasattr(cached.alerts, "alerts"):
                        active_alerts = cached.alerts.alerts or []

                if active_alerts:
                    lines.append(f"  Active Alerts: {len(active_alerts)}")
                    for alert in active_alerts:
                        event = getattr(alert, "event", "Unknown")
                        severity = getattr(alert, "severity", "Unknown")
                        lines.append(f"    • {event} ({severity})")
                        location_alerts.append((loc.name, alert))
                else:
                    lines.append("  Active Alerts: None")

                if getattr(cached, "stale", False):
                    lines.append("  (Cached — data may be outdated)")
            else:
                lines.append("  (No cached data — select this location to load current conditions)")

            lines.append("")

        summary_text = "\n".join(lines)
        self.current_conditions.SetValue(summary_text)

        self._set_forecast_sections_visible(False)

        self._all_locations_alerts_data = location_alerts
        self._update_all_locations_alerts(location_alerts)

        # Update tray icon with data from the highest-priority location.
        tray_data, tray_loc_name = self._get_all_locations_tray_data()
        self.app.update_tray_tooltip(tray_data, tray_loc_name)

        self.stale_warning_label.SetLabel("")
        from . import main_window as base_module

        base_module.MainWindow._update_precipitation_timeline_menu_state(self)

        # Ensure the refresh button stays enabled in this view.
        self.app.is_updating = False
        self.refresh_button.Enable()

    def _update_all_locations_alerts(self, location_alerts: list[tuple[str, object]]) -> None:
        """
        Populate the alerts list from aggregated all-locations alert data.

        Each item is prefixed with the location name so screen-reader users
        know which location triggered the alert without having to open details.

        Args:
            location_alerts: List of (location_name, WeatherAlert) pairs.

        """
        self.alerts_list.Clear()

        if location_alerts:
            items = []
            for loc_name, alert in location_alerts:
                event = getattr(alert, "event", "Unknown")
                severity = getattr(alert, "severity", "Unknown")
                items.append(f"{loc_name}: {event} ({severity})")
            self.alerts_list.Append(items)
            self.view_alert_button.Enable()
        else:
            self.view_alert_button.Disable()

    def _get_all_locations_tray_data(self):
        """
        Return (weather_data, location_name) for the highest-priority location for tray display.

        Priority order:
        1. Location with the most severe active alert (Extreme > Severe > Moderate > Minor > Unknown)
        2. First location that has any cached data (fallback when no alerts exist)

        Returns None, None when no cached data is available at all.
        """
        SEVERITY_ORDER = ["Extreme", "Severe", "Moderate", "Minor", "Unknown"]

        weather_client = (
            self.app.weather_client
            if hasattr(self.app, "weather_client") and self.app.weather_client
            else None
        )

        try:
            all_locs = [
                loc
                for loc in self.app.config_manager.get_all_locations()
                if loc.name != "Nationwide"
            ]
        except Exception:
            return None, None

        best_data = None
        best_name = None
        best_severity_idx = len(SEVERITY_ORDER)  # sentinel: no alert yet

        first_with_data = None
        first_with_data_name = None

        for loc in all_locs:
            cached = weather_client.get_cached_weather(loc) if weather_client else None
            if not cached or not cached.has_any_data():
                continue

            if first_with_data is None:
                first_with_data = cached
                first_with_data_name = loc.name

            # Find the most severe alert for this location.
            active_alerts: list = []
            if cached.alerts is not None:
                if hasattr(cached.alerts, "get_active_alerts"):
                    active_alerts = cached.alerts.get_active_alerts() or []
                elif hasattr(cached.alerts, "alerts"):
                    active_alerts = cached.alerts.alerts or []

            for alert in active_alerts:
                severity = getattr(alert, "severity", None) or "Unknown"
                if severity not in SEVERITY_ORDER:
                    severity = "Unknown"
                idx = SEVERITY_ORDER.index(severity)
                if idx < best_severity_idx:
                    best_severity_idx = idx
                    best_data = cached
                    best_name = loc.name

        if best_data is not None:
            return best_data, best_name

        # Fallback: use the last single location the user was viewing
        last_name = getattr(self, "_last_single_location_name", None)
        if last_name and weather_client:
            for loc in all_locs:
                if loc.name == last_name:
                    cached = weather_client.get_cached_weather(loc)
                    if cached and cached.has_any_data():
                        return cached, last_name

        return first_with_data, first_with_data_name

    def set_status(self, message: str) -> None:
        """Set the status bar text and announce via screen reader."""
        self.GetStatusBar().SetStatusText(message, 0)
        logger.info(f"Status: {message}")
        if message:
            self._announcer.announce(message)

    def _set_last_updated_status(self, when: datetime | None = None) -> None:
        """
        Write 'Last updated HH:MM' to the main status field silently.

        Unlike set_status(), this does not invoke the screen-reader
        announcer — refresh success is already conveyed by the
        data_updated sound and a re-announcement on every refresh would
        be noisy.  The timestamp is formatted in the user's local time
        using 12-hour format to match Event Center entries.
        """
        stamp = (when or datetime.now()).strftime("%I:%M %p").lstrip("0")
        self.GetStatusBar().SetStatusText(f"Last updated {stamp}", 0)

    def _update_precipitation_timeline_menu_state(self, weather_data=None) -> None:
        """Enable the precipitation timeline menu item when minutely data is available."""
        menu_item = getattr(self, "_precipitation_timeline_item", None)
        if menu_item is None:
            return

        is_enabled = False
        if not getattr(self, "_all_locations_active", False):
            data = (
                weather_data
                if weather_data is not None
                else getattr(self.app, "current_weather_data", None)
            )
            forecast = getattr(data, "minutely_precipitation", None)
            if forecast is not None:
                has_data = getattr(forecast, "has_data", None)
                if callable(has_data):
                    is_enabled = bool(has_data())
                else:
                    is_enabled = bool(getattr(forecast, "points", None))

        menu_item.Enable(is_enabled)

    def _get_notification_event_manager(self):
        """Get or create the notification event manager for AFD/severe risk notifications."""
        return main_window_notification_events.get_notification_event_manager(self)

    def _get_fallback_notifier(self):
        """Get or create a cached fallback notifier for event notifications."""
        return main_window_notification_events.get_fallback_notifier(self)

    def _on_notification_event_data_received(self, weather_data) -> None:
        """Handle lightweight event data without refreshing the visible weather UI."""
        main_window_notification_events.on_notification_event_data_received(self, weather_data)

    def _process_notification_events(self, weather_data) -> None:
        """
        Process weather data for notification events.

        Checks for:
        - Area Forecast Discussion (AFD) updates (NWS US only)
        - Severe weather risk level changes

        Both are opt-in notifications (disabled by default).
        """
        main_window_notification_events.process_notification_events(self, weather_data)
