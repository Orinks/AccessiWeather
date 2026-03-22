"""Tests for the All Locations summary view feature."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_window():
    """Create a minimal MainWindow instance with all UI mocked out."""
    from accessiweather.ui.main_window import MainWindow

    with patch.object(MainWindow, "__init__", lambda self, *a, **kw: None):
        win = MainWindow.__new__(MainWindow)

    win.app = MagicMock()
    win.app.is_updating = False
    win.app.config_manager.get_settings.return_value = MagicMock(
        sound_enabled=False,
        sound_pack="default",
        muted_sound_events=[],
    )

    # UI widgets
    win.location_dropdown = MagicMock()
    win.current_conditions = MagicMock()
    win._daily_forecast_label = MagicMock()
    win.daily_forecast_display = MagicMock()
    win._hourly_forecast_label = MagicMock()
    win.hourly_forecast_display = MagicMock()
    win.alerts_list = MagicMock()
    win.view_alert_button = MagicMock()
    win.refresh_button = MagicMock()
    win.status_label = MagicMock()
    win.stale_warning_label = MagicMock()

    # State
    win._all_locations_active = False
    win._all_locations_alerts_data = []
    win._alert_lifecycle_labels = {}
    win._fetch_generation = 0

    # Delegate the real implementations we want to test.
    win.set_status = MainWindow.set_status.__get__(win, MainWindow)
    win._set_forecast_sections = MainWindow._set_forecast_sections.__get__(win, MainWindow)
    win._set_forecast_sections_visible = MainWindow._set_forecast_sections_visible.__get__(
        win, MainWindow
    )
    win._show_all_locations_summary = MainWindow._show_all_locations_summary.__get__(
        win, MainWindow
    )
    win._update_all_locations_alerts = MainWindow._update_all_locations_alerts.__get__(
        win, MainWindow
    )
    win._show_alert_details = MainWindow._show_alert_details.__get__(win, MainWindow)
    win.refresh_weather_async = MainWindow.refresh_weather_async.__get__(win, MainWindow)

    return win


def _make_location(name: str, lat: float = 40.0, lon: float = -75.0):
    loc = MagicMock()
    loc.name = name
    loc.latitude = lat
    loc.longitude = lon
    return loc


def _make_current_conditions(temp_f: float = 72.0, condition: str = "Sunny"):
    cc = MagicMock()
    cc.temperature_f = temp_f
    cc.condition = condition
    return cc


def _make_alert(event: str = "Flood Warning", severity: str = "Moderate"):
    alert = MagicMock()
    alert.event = event
    alert.severity = severity
    alert.get_unique_id = MagicMock(return_value=f"uid-{event}")
    return alert


def _make_weather_data(loc, temp_f=72.0, condition="Sunny", alerts=None, stale=False):
    wd = MagicMock()
    wd.location = loc
    wd.current = _make_current_conditions(temp_f, condition)
    wd.has_any_data.return_value = True
    wd.stale = stale

    if alerts is not None:
        alert_obj = MagicMock()
        alert_obj.get_active_alerts.return_value = alerts
        alert_obj.alerts = alerts
        wd.alerts = alert_obj
    else:
        wd.alerts = None

    return wd


# ---------------------------------------------------------------------------
# _populate_locations
# ---------------------------------------------------------------------------


class TestPopulateLocations:
    """The dropdown always starts with 'All Locations'."""

    def test_all_locations_is_first_entry(self):
        from accessiweather.ui.main_window import ALL_LOCATIONS_SENTINEL, MainWindow

        win = _make_window()
        locs = [_make_location("Boston"), _make_location("Austin")]
        win.app.config_manager.get_all_locations.return_value = locs
        win.app.config_manager.get_current_location.return_value = locs[0]

        MainWindow._populate_locations(win)

        call_args = win.location_dropdown.Append.call_args[0][0]
        assert call_args[0] == ALL_LOCATIONS_SENTINEL

    def test_real_locations_follow_all_locations(self):
        from accessiweather.ui.main_window import MainWindow

        win = _make_window()
        locs = [_make_location("Boston"), _make_location("Austin")]
        win.app.config_manager.get_all_locations.return_value = locs
        win.app.config_manager.get_current_location.return_value = locs[0]

        MainWindow._populate_locations(win)

        call_args = win.location_dropdown.Append.call_args[0][0]
        assert "Boston" in call_args
        assert "Austin" in call_args
        assert call_args.index("Boston") > 0
        assert call_args.index("Austin") > 0

    def test_selects_current_location_when_set(self):
        from accessiweather.ui.main_window import MainWindow

        win = _make_window()
        locs = [_make_location("Boston"), _make_location("Austin")]
        win.app.config_manager.get_all_locations.return_value = locs
        win.app.config_manager.get_current_location.return_value = locs[1]  # Austin

        MainWindow._populate_locations(win)

        # Austin is at index 2 (0=All Locations, 1=Boston, 2=Austin)
        win.location_dropdown.SetSelection.assert_called_with(2)

    def test_falls_back_to_index_zero_when_no_current(self):
        from accessiweather.ui.main_window import MainWindow

        win = _make_window()
        locs = [_make_location("Boston")]
        win.app.config_manager.get_all_locations.return_value = locs
        win.app.config_manager.get_current_location.return_value = None

        MainWindow._populate_locations(win)

        win.location_dropdown.SetSelection.assert_called_with(0)


# ---------------------------------------------------------------------------
# _show_all_locations_summary — basic rendering
# ---------------------------------------------------------------------------


class TestShowAllLocationsSummary:
    def test_displays_summary_for_each_location(self):
        win = _make_window()
        locs = [_make_location("Boston"), _make_location("Austin")]
        win.app.config_manager.get_all_locations.return_value = locs

        wd_boston = _make_weather_data(locs[0], temp_f=55.0, condition="Cloudy")
        wd_austin = _make_weather_data(locs[1], temp_f=80.0, condition="Sunny")

        def get_cached(loc):
            return wd_boston if loc.name == "Boston" else wd_austin

        win.app.weather_client.get_cached_weather.side_effect = get_cached

        win._show_all_locations_summary()

        text = win.current_conditions.SetValue.call_args[0][0]
        assert "Boston" in text
        assert "55°F" in text
        assert "Cloudy" in text
        assert "Austin" in text
        assert "80°F" in text
        assert "Sunny" in text

    def test_nationwide_excluded_from_summary(self):
        win = _make_window()
        nationwide = _make_location("Nationwide", lat=39.8283, lon=-98.5795)
        boston = _make_location("Boston")
        win.app.config_manager.get_all_locations.return_value = [nationwide, boston]

        wd_boston = _make_weather_data(boston, temp_f=55.0, condition="Cloudy")
        win.app.weather_client.get_cached_weather.return_value = wd_boston

        win._show_all_locations_summary()

        text = win.current_conditions.SetValue.call_args[0][0]
        assert "Nationwide" not in text
        assert "Boston" in text

    def test_shows_placeholder_when_no_cached_data(self):
        win = _make_window()
        locs = [_make_location("Boston")]
        win.app.config_manager.get_all_locations.return_value = locs
        win.app.weather_client.get_cached_weather.return_value = None

        win._show_all_locations_summary()

        text = win.current_conditions.SetValue.call_args[0][0]
        assert "No cached data" in text

    def test_forecast_sections_hidden_in_all_locations_view(self):
        win = _make_window()
        locs = [_make_location("Boston")]
        win.app.config_manager.get_all_locations.return_value = locs
        win.app.weather_client.get_cached_weather.return_value = None

        win._show_all_locations_summary()

        win._daily_forecast_label.Show.assert_called_with(False)
        win.daily_forecast_display.Show.assert_called_with(False)
        win._hourly_forecast_label.Show.assert_called_with(False)
        win.hourly_forecast_display.Show.assert_called_with(False)

    def test_no_locations_shows_informative_message(self):
        win = _make_window()
        win.app.config_manager.get_all_locations.return_value = []

        win._show_all_locations_summary()

        text = win.current_conditions.SetValue.call_args[0][0]
        assert "No locations configured" in text
        win.view_alert_button.Disable.assert_called()

    def test_status_shows_location_count(self):
        win = _make_window()
        locs = [_make_location("Boston"), _make_location("Austin")]
        win.app.config_manager.get_all_locations.return_value = locs
        win.app.weather_client.get_cached_weather.return_value = None

        win._show_all_locations_summary()

        win.status_label.SetLabel.assert_called_with("All Locations summary — 2 location(s)")

    def test_refresh_button_enabled_after_summary(self):
        win = _make_window()
        win.app.config_manager.get_all_locations.return_value = [_make_location("Boston")]
        win.app.weather_client.get_cached_weather.return_value = None

        win._show_all_locations_summary()

        win.refresh_button.Enable.assert_called()


# ---------------------------------------------------------------------------
# Alerts aggregation
# ---------------------------------------------------------------------------


class TestAllLocationsAlerts:
    def test_alerts_aggregated_from_all_locations(self):
        win = _make_window()
        loc_a = _make_location("Boston")
        loc_b = _make_location("Austin")
        win.app.config_manager.get_all_locations.return_value = [loc_a, loc_b]

        alert_a = _make_alert("Flood Warning", "Moderate")
        alert_b = _make_alert("Tornado Watch", "Severe")

        wd_a = _make_weather_data(loc_a, alerts=[alert_a])
        wd_b = _make_weather_data(loc_b, alerts=[alert_b])

        def get_cached(loc):
            return wd_a if loc.name == "Boston" else wd_b

        win.app.weather_client.get_cached_weather.side_effect = get_cached

        win._show_all_locations_summary()

        assert len(win._all_locations_alerts_data) == 2
        loc_names = [name for name, _ in win._all_locations_alerts_data]
        assert "Boston" in loc_names
        assert "Austin" in loc_names

    def test_alerts_list_prefixed_with_location_name(self):
        win = _make_window()
        loc = _make_location("Boston")
        win.app.config_manager.get_all_locations.return_value = [loc]

        alert = _make_alert("Flood Warning", "Moderate")
        wd = _make_weather_data(loc, alerts=[alert])
        win.app.weather_client.get_cached_weather.return_value = wd

        win._show_all_locations_summary()

        items = win.alerts_list.Append.call_args[0][0]
        assert any("Boston" in item and "Flood Warning" in item for item in items)

    def test_view_alert_button_enabled_when_alerts_present(self):
        win = _make_window()
        loc = _make_location("Boston")
        win.app.config_manager.get_all_locations.return_value = [loc]
        alert = _make_alert()
        wd = _make_weather_data(loc, alerts=[alert])
        win.app.weather_client.get_cached_weather.return_value = wd

        win._show_all_locations_summary()

        win.view_alert_button.Enable.assert_called()

    def test_view_alert_button_disabled_when_no_alerts(self):
        win = _make_window()
        loc = _make_location("Boston")
        win.app.config_manager.get_all_locations.return_value = [loc]
        wd = _make_weather_data(loc, alerts=[])
        win.app.weather_client.get_cached_weather.return_value = wd

        win._show_all_locations_summary()

        win.view_alert_button.Disable.assert_called()


# ---------------------------------------------------------------------------
# _show_alert_details in All Locations mode
# ---------------------------------------------------------------------------


class TestShowAlertDetailsAllLocations:
    def test_aggregated_data_is_indexed_correctly(self):
        """Verify that _all_locations_alerts_data is stored and accessible by index."""
        win = _make_window()
        win._all_locations_active = True
        alert = _make_alert("Flood Warning", "Moderate")
        win._all_locations_alerts_data = [("Boston", alert)]

        assert win._all_locations_alerts_data[0] == ("Boston", alert)

    def test_show_alert_details_uses_all_locations_data_when_active(self):
        """In All Locations mode the method opens the alert from the aggregated list."""
        win = _make_window()
        win._all_locations_active = True
        alert = _make_alert("Tornado Watch", "Severe")
        win._all_locations_alerts_data = [("Austin", alert)]

        from accessiweather.ui.main_window import MainWindow

        with patch("accessiweather.ui.dialogs.show_alert_dialog") as mock_dialog:
            MainWindow._show_alert_details(win, 0)
            mock_dialog.assert_called_once_with(win, alert)

    def test_out_of_range_index_does_nothing(self):
        """An out-of-range alert index in All Locations mode silently returns."""
        win = _make_window()
        win._all_locations_active = True
        win._all_locations_alerts_data = []

        from accessiweather.ui.main_window import MainWindow

        # Should not raise
        MainWindow._show_alert_details(win, 5)


# ---------------------------------------------------------------------------
# on_remove_location — guards All Locations sentinel
# ---------------------------------------------------------------------------


class TestRemoveLocationGuard:
    def test_remove_location_blocks_all_locations_sentinel(self):
        import accessiweather.ui.main_window as mw_module
        from accessiweather.ui.main_window import ALL_LOCATIONS_SENTINEL, MainWindow

        win = _make_window()
        win.location_dropdown.GetStringSelection.return_value = ALL_LOCATIONS_SENTINEL

        mock_wx = MagicMock()
        with patch.object(mw_module, "wx", mock_wx):
            MainWindow.on_remove_location(win)
            mock_wx.MessageBox.assert_called_once()
            # Should NOT proceed to remove anything
            win.app.config_manager.remove_location.assert_not_called()

    def test_remove_location_empty_selection_also_blocked(self):
        """Empty selection (none chosen) also shows a message."""
        import accessiweather.ui.main_window as mw_module
        from accessiweather.ui.main_window import MainWindow

        win = _make_window()
        win.location_dropdown.GetStringSelection.return_value = ""

        mock_wx = MagicMock()
        with patch.object(mw_module, "wx", mock_wx):
            MainWindow.on_remove_location(win)
            mock_wx.MessageBox.assert_called_once()
            win.app.config_manager.remove_location.assert_not_called()


# ---------------------------------------------------------------------------
# refresh_weather_async — All Locations mode
# ---------------------------------------------------------------------------


class TestRefreshWeatherAsyncAllLocations:
    def test_refresh_in_all_locations_mode_starts_async_fetch(self):
        win = _make_window()
        win._all_locations_active = True
        win._show_all_locations_summary = MagicMock()

        win.refresh_weather_async()

        # Should fire an async fetch for all locations, not just re-render from cache
        win.app.run_async.assert_called_once()
        win.refresh_button.Disable.assert_called_once()

    def test_refresh_in_normal_mode_starts_async_fetch(self):
        win = _make_window()
        win._all_locations_active = False
        win.app.is_updating = False
        win._show_all_locations_summary = MagicMock()

        win.refresh_weather_async(force_refresh=True)

        win._show_all_locations_summary.assert_not_called()
        win.app.run_async.assert_called_once()


# ---------------------------------------------------------------------------
# _on_location_changed — routing
# ---------------------------------------------------------------------------


class TestOnLocationChanged:
    def _make_event(self):
        return MagicMock()

    def test_all_locations_sentinel_sets_flag_and_shows_summary(self):
        from accessiweather.ui.main_window import ALL_LOCATIONS_SENTINEL, MainWindow

        win = _make_window()
        win.location_dropdown.GetStringSelection.return_value = ALL_LOCATIONS_SENTINEL
        win._show_all_locations_summary = MagicMock()

        MainWindow._on_location_changed(win, self._make_event())

        assert win._all_locations_active is True
        win._show_all_locations_summary.assert_called_once()
        # Should NOT call _set_current_location for the sentinel
        win.app.config_manager.set_current_location.assert_not_called()

    def test_normal_location_clears_all_locations_flag(self):
        from accessiweather.ui.main_window import MainWindow

        win = _make_window()
        win._all_locations_active = True
        win._all_locations_alerts_data = [("Boston", MagicMock())]
        win.location_dropdown.GetStringSelection.return_value = "Boston"
        win.app.config_manager.get_current_location.return_value = _make_location("Boston")
        win.app.weather_client.get_cached_weather.return_value = None
        win.refresh_notification_events_async = MagicMock()

        # Debounce timer
        win._location_debounce_timer = MagicMock()
        win._location_debounce_timer.IsRunning.return_value = False

        MainWindow._on_location_changed(win, self._make_event())

        assert win._all_locations_active is False
        assert win._all_locations_alerts_data == []


# ---------------------------------------------------------------------------
# refresh_weather_async — All Locations refresh triggers fetch
# ---------------------------------------------------------------------------


class TestAllLocationsRefresh:
    def test_refresh_triggers_fetch_for_all_locations(self):
        """Refresh in All Locations mode fires _fetch_all_locations_data, not just cache render."""
        from accessiweather.ui.main_window import MainWindow

        win = _make_window()
        win._all_locations_active = True
        win.app.run_async = MagicMock()

        MainWindow.refresh_weather_async(win)

        win.refresh_button.Disable.assert_called_once()
        win.app.run_async.assert_called_once()

    def test_on_all_locations_refresh_complete_rerenders_summary(self):
        """_on_all_locations_refresh_complete re-renders summary when view is still active."""
        from accessiweather.ui.main_window import MainWindow

        win = _make_window()
        win._all_locations_active = True
        win._show_all_locations_summary = MagicMock()

        MainWindow._on_all_locations_refresh_complete(win)

        win._show_all_locations_summary.assert_called_once()
        win.refresh_button.Enable.assert_called_once()

    def test_on_all_locations_refresh_complete_skips_render_if_view_changed(self):
        """_on_all_locations_refresh_complete does not render if user switched away."""
        from accessiweather.ui.main_window import MainWindow

        win = _make_window()
        win._all_locations_active = False
        win._show_all_locations_summary = MagicMock()

        MainWindow._on_all_locations_refresh_complete(win)

        win._show_all_locations_summary.assert_not_called()
        win.refresh_button.Enable.assert_called_once()
