"""MainWindowLocationMixin helpers for the main window."""
# ruff: noqa: F403, F405

from __future__ import annotations

from .main_window_shared import *  # noqa: F403


class MainWindowLocationMixin:
    def _on_location_changed(self, event) -> None:
        """Handle location selection change with debounce for rapid switching."""
        selected = self.location_dropdown.GetStringSelection()
        if not selected:
            return

        logger.info(f"Location changed to: {selected}")
        # Clear lifecycle labels when switching locations so stale labels never bleed across
        self._alert_lifecycle_labels = {}

        # --- All Locations special case ---
        if selected == ALL_LOCATIONS_SENTINEL:
            from . import main_window as base_module

            self._all_locations_active = True
            self._update_title_for_location(ALL_LOCATIONS_SENTINEL)
            base_module.MainWindow._safe_update_forecast_products_button_state(self)
            base_module.MainWindow._update_precipitation_timeline_menu_state(self)
            # Increment generation to invalidate any in-flight fetches for the previous location
            self._fetch_generation += 1
            # Use CallAfter so the summary renders after any already-queued wx.CallAfter
            # callbacks (e.g. a just-completed fetch posting _on_weather_data_received) are
            # drained first, preventing stale data from overwriting the summary.
            base_module.wx.CallAfter(self._show_all_locations_summary)
            self.app.run_async(self._fetch_all_locations_data())
            return

        # Switching away from All Locations view → clear the flag and stored data.
        self._all_locations_active = False
        self._all_locations_alerts_data = []
        self._last_single_location_name = selected
        self._set_forecast_sections_visible(True)
        self._update_title_for_location(selected)

        self._set_current_location(selected)
        from . import main_window as base_module

        base_module.MainWindow._safe_update_forecast_products_button_state(self)

        # Show cached data instantly if available
        location = self.app.config_manager.get_current_location()
        if location and hasattr(self.app, "weather_client") and self.app.weather_client:
            cached = self.app.weather_client.get_cached_weather(location)
            if cached and cached.has_any_data():
                logger.info(f"Showing cached data for {selected} while refreshing")
                self._on_weather_data_received(cached)

        # Fire an immediate alert/event check for the new location (lightweight)
        if location and hasattr(self.app, "weather_client") and self.app.weather_client:
            self.refresh_notification_events_async()

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
            # Auto-select the newly added location so the user lands on it immediately
            new_name = result
            if new_name:
                idx = self.location_dropdown.FindString(new_name)
                if idx != wx.NOT_FOUND:
                    self.location_dropdown.SetSelection(idx)
                    self._set_current_location(new_name)
            self.refresh_weather_async()

    def on_edit_location(self) -> None:
        """Handle edit location button click — currently edits marine_mode."""
        selected = self.location_dropdown.GetStringSelection()
        if not selected or selected == ALL_LOCATIONS_SENTINEL:
            from . import main_window as base_module

            base_module.wx.MessageBox(
                "Please select a specific location to edit.",
                "No Location Selected",
                base_module.wx.OK | base_module.wx.ICON_WARNING,
            )
            return

        location = next(
            (loc for loc in self.app.config_manager.get_all_locations() if loc.name == selected),
            None,
        )
        if location is None:
            return

        from . import main_window as base_module

        new_marine_mode = base_module.show_edit_location_dialog(self, self.app, location)
        if new_marine_mode is None:
            return

        self.app.config_manager.update_location_marine_mode(selected, new_marine_mode)
        self.refresh_weather_async(force_refresh=True)

    def on_remove_location(self) -> None:
        """Handle remove location button click."""
        selected = self.location_dropdown.GetStringSelection()
        if not selected or selected == ALL_LOCATIONS_SENTINEL:
            from . import main_window as base_module

            base_module.wx.MessageBox(
                "Please select a specific location to remove.",
                "No Location Selected",
                base_module.wx.OK | base_module.wx.ICON_WARNING,
            )
            return

        # Don't allow removing the last location
        locations = self.app.config_manager.get_all_locations()
        if len(locations) <= 1:
            from . import main_window as base_module

            base_module.wx.MessageBox(
                "Cannot remove the last location. Add another location first.",
                "Cannot Remove",
                base_module.wx.OK | base_module.wx.ICON_WARNING,
            )
            return

        # Confirm removal
        from . import main_window as base_module

        result = base_module.wx.MessageBox(
            f"Are you sure you want to remove '{selected}'?",
            "Confirm Removal",
            base_module.wx.YES_NO | base_module.wx.ICON_QUESTION,
        )
        if result == base_module.wx.YES:
            self.app.config_manager.remove_location(selected)
            self._populate_locations()
            self.refresh_weather_async()

    def on_refresh(self) -> None:
        """Handle refresh button click."""
        self.refresh_weather_async(force_refresh=True)

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
            # Immediately refresh weather so source/key changes take effect
            self.refresh_weather_async(force_refresh=True)

    def on_view_history(self) -> None:
        """View weather history comparison."""
        from .dialogs import show_weather_history_dialog

        show_weather_history_dialog(self, self.app)
