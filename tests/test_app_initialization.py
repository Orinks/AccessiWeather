"""Unit tests for cache-first startup behavior in app_initialization.py.

Tests cover:
- Cache-first data loading during startup
- Synchronous display of cached data
- Background async refresh after cache display
- Graceful handling when no cache exists
- Error handling during cache operations
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from accessiweather.models import CurrentConditions, Location, WeatherData
from accessiweather.models.config import AppConfig, AppSettings


def _create_mock_app():
    """Create a mock AccessiWeatherApp with required attributes."""
    app = Mock()
    app.config_manager = Mock()
    app.weather_client = Mock()
    app.presenter = Mock()
    app.status_label = Mock()
    app.current_conditions_display = Mock()
    app.forecast_display = Mock()
    app.alerts_table = Mock()
    app.alert_details_button = Mock()
    app.current_weather_data = None
    app.current_alerts_data = None
    app.main_window = Mock()
    app.main_window.visible = True
    return app


def _create_sample_location():
    """Create a sample location for testing."""
    return Location(name="Test City", latitude=40.7128, longitude=-74.0060)


def _create_sample_weather_data(location):
    """Create sample weather data for testing."""
    current = CurrentConditions(
        temperature_f=72.0,
        temperature_c=22.2,
        condition="Partly Cloudy",
        humidity=65,
    )
    return WeatherData(location=location, current=current)


def _create_sample_config(location=None, locations=None):
    """Create a sample AppConfig for testing."""
    if locations is None:
        locations = [location] if location else []
    return AppConfig(
        settings=AppSettings(),
        locations=locations,
        current_location=location,
    )


class TestLoadInitialDataCacheFirst:
    """Test load_initial_data with cache-first behavior."""

    def test_load_initial_data_with_cached_data(self):
        """Should display cached data synchronously during startup."""
        app = _create_mock_app()
        location = _create_sample_location()
        weather_data = _create_sample_weather_data(location)
        config = _create_sample_config(location=location)

        app.config_manager.get_config.return_value = config
        app.weather_client.get_cached_weather.return_value = weather_data

        # Mock the presenter
        mock_presentation = Mock()
        mock_presentation.current_conditions = Mock()
        mock_presentation.current_conditions.fallback_text = "72°F - Partly Cloudy"
        mock_presentation.current_conditions.trends = []
        mock_presentation.status_messages = []
        mock_presentation.source_attribution = None
        mock_presentation.forecast = None
        mock_presentation.aviation = None
        app.presenter.present.return_value = mock_presentation

        with (
            patch("accessiweather.app_initialization.app_helpers") as mock_helpers,
            patch("accessiweather.app_initialization.event_handlers") as mock_event_handlers,
            patch("accessiweather.app_initialization.background_tasks") as mock_bg_tasks,
            patch("asyncio.create_task") as mock_create_task,
        ):
            mock_helpers.should_show_dialog.return_value = True
            mock_helpers.sync_update_weather_displays = Mock()
            mock_helpers.update_status = Mock()
            mock_task = Mock()
            mock_task.add_done_callback = Mock()
            mock_create_task.return_value = mock_task

            from accessiweather.app_initialization import load_initial_data

            load_initial_data(app)

            # Verify cached data was requested
            app.weather_client.get_cached_weather.assert_called_once_with(location)

            # Verify cached data was set on app
            assert app.current_weather_data == weather_data

            # Verify sync display update was called
            mock_helpers.sync_update_weather_displays.assert_called_once_with(app, weather_data)

            # Verify status was updated to show background refresh
            mock_helpers.update_status.assert_called()
            status_call_args = mock_helpers.update_status.call_args_list[-1][0]
            assert "Updating weather" in status_call_args[1]

            # Verify async refresh task was created
            mock_create_task.assert_called()

    def test_load_initial_data_no_cached_data(self):
        """Should handle gracefully when no cached data exists."""
        app = _create_mock_app()
        location = _create_sample_location()
        config = _create_sample_config(location=location)

        app.config_manager.get_config.return_value = config
        app.weather_client.get_cached_weather.return_value = None

        with (
            patch("accessiweather.app_initialization.app_helpers") as mock_helpers,
            patch("accessiweather.app_initialization.event_handlers") as mock_event_handlers,
            patch("accessiweather.app_initialization.background_tasks") as mock_bg_tasks,
            patch("asyncio.create_task") as mock_create_task,
        ):
            mock_helpers.should_show_dialog.return_value = True
            mock_helpers.sync_update_weather_displays = Mock()
            mock_helpers.update_status = Mock()
            mock_task = Mock()
            mock_task.add_done_callback = Mock()
            mock_create_task.return_value = mock_task

            from accessiweather.app_initialization import load_initial_data

            load_initial_data(app)

            # Verify cached data was requested
            app.weather_client.get_cached_weather.assert_called_once_with(location)

            # Verify sync_update was NOT called (no cached data)
            mock_helpers.sync_update_weather_displays.assert_not_called()

            # Verify app.current_weather_data was NOT set
            assert app.current_weather_data is None

            # Verify status shows loading message
            mock_helpers.update_status.assert_called()
            status_call_args = mock_helpers.update_status.call_args_list[-1][0]
            assert "Loading weather" in status_call_args[1]

            # Verify async refresh task was still created
            mock_create_task.assert_called()

    def test_load_initial_data_stale_cache(self):
        """Should display stale cached data immediately."""
        app = _create_mock_app()
        location = _create_sample_location()
        weather_data = _create_sample_weather_data(location)
        weather_data.stale = True
        weather_data.stale_reason = "Cache expired"
        config = _create_sample_config(location=location)

        app.config_manager.get_config.return_value = config
        app.weather_client.get_cached_weather.return_value = weather_data

        mock_presentation = Mock()
        mock_presentation.current_conditions = Mock()
        mock_presentation.current_conditions.fallback_text = "72°F - Partly Cloudy"
        mock_presentation.current_conditions.trends = []
        mock_presentation.status_messages = ["Data may be stale"]
        mock_presentation.source_attribution = None
        mock_presentation.forecast = None
        mock_presentation.aviation = None
        app.presenter.present.return_value = mock_presentation

        with (
            patch("accessiweather.app_initialization.app_helpers") as mock_helpers,
            patch("accessiweather.app_initialization.event_handlers") as mock_event_handlers,
            patch("accessiweather.app_initialization.background_tasks") as mock_bg_tasks,
            patch("asyncio.create_task") as mock_create_task,
        ):
            mock_helpers.should_show_dialog.return_value = True
            mock_helpers.sync_update_weather_displays = Mock()
            mock_helpers.update_status = Mock()
            mock_task = Mock()
            mock_task.add_done_callback = Mock()
            mock_create_task.return_value = mock_task

            from accessiweather.app_initialization import load_initial_data

            load_initial_data(app)

            # Verify stale cached data was displayed
            assert app.current_weather_data == weather_data
            assert app.current_weather_data.stale is True
            mock_helpers.sync_update_weather_displays.assert_called_once_with(app, weather_data)

            # Verify async refresh was started for fresh data
            mock_create_task.assert_called()

    def test_load_initial_data_triggers_async_refresh(self):
        """Should create async task for background refresh after cache display."""
        app = _create_mock_app()
        location = _create_sample_location()
        weather_data = _create_sample_weather_data(location)
        config = _create_sample_config(location=location)

        app.config_manager.get_config.return_value = config
        app.weather_client.get_cached_weather.return_value = weather_data

        mock_presentation = Mock()
        mock_presentation.current_conditions = Mock()
        mock_presentation.current_conditions.fallback_text = "72°F"
        mock_presentation.current_conditions.trends = []
        mock_presentation.status_messages = []
        mock_presentation.source_attribution = None
        mock_presentation.forecast = None
        mock_presentation.aviation = None
        app.presenter.present.return_value = mock_presentation

        with (
            patch("accessiweather.app_initialization.app_helpers") as mock_helpers,
            patch("accessiweather.app_initialization.event_handlers") as mock_event_handlers,
            patch("accessiweather.app_initialization.background_tasks") as mock_bg_tasks,
            patch("asyncio.create_task") as mock_create_task,
        ):
            mock_helpers.should_show_dialog.return_value = True
            mock_helpers.sync_update_weather_displays = Mock()
            mock_helpers.update_status = Mock()
            mock_task = Mock()
            mock_task.add_done_callback = Mock()
            mock_create_task.return_value = mock_task

            from accessiweather.app_initialization import load_initial_data

            load_initial_data(app)

            # Verify async task was created for refresh
            mock_create_task.assert_called()

            # Verify the task has a done callback for error handling
            mock_task.add_done_callback.assert_called_once()


class TestLoadInitialDataEdgeCases:
    """Test edge cases in load_initial_data."""

    def test_load_initial_data_no_locations(self):
        """Should handle gracefully when no locations are configured."""
        app = _create_mock_app()
        config = _create_sample_config()  # No locations
        app.config_manager.get_config.return_value = config

        with (
            patch("accessiweather.app_initialization.app_helpers") as mock_helpers,
            patch("asyncio.create_task") as mock_create_task,
        ):
            mock_helpers.update_status = Mock()

            from accessiweather.app_initialization import load_initial_data

            load_initial_data(app)

            # Verify status shows "add a location" message
            mock_helpers.update_status.assert_called()
            status_call = mock_helpers.update_status.call_args[0][1]
            assert "Add a location" in status_call

            # Verify no async task was created
            mock_create_task.assert_not_called()

            # Verify weather client was never called
            app.weather_client.get_cached_weather.assert_not_called()

    def test_load_initial_data_no_current_location(self):
        """Should handle gracefully when no current location is set."""
        app = _create_mock_app()
        location = _create_sample_location()
        # Has locations but no current location selected
        config = AppConfig(
            settings=AppSettings(),
            locations=[location],
            current_location=None,
        )
        app.config_manager.get_config.return_value = config

        with (
            patch("accessiweather.app_initialization.app_helpers") as mock_helpers,
            patch("asyncio.create_task") as mock_create_task,
        ):
            from accessiweather.app_initialization import load_initial_data

            load_initial_data(app)

            # Verify no async task was created
            mock_create_task.assert_not_called()

            # Verify weather client was never called
            app.weather_client.get_cached_weather.assert_not_called()

    def test_load_initial_data_cache_lookup_exception(self):
        """Should handle cache lookup exceptions gracefully."""
        app = _create_mock_app()
        location = _create_sample_location()
        config = _create_sample_config(location=location)

        app.config_manager.get_config.return_value = config
        app.weather_client.get_cached_weather.side_effect = Exception("Cache read error")

        with (
            patch("accessiweather.app_initialization.app_helpers") as mock_helpers,
            patch("accessiweather.app_initialization.event_handlers") as mock_event_handlers,
            patch("accessiweather.app_initialization.background_tasks") as mock_bg_tasks,
            patch("asyncio.create_task") as mock_create_task,
        ):
            mock_helpers.should_show_dialog.return_value = True
            mock_helpers.sync_update_weather_displays = Mock()
            mock_helpers.update_status = Mock()
            mock_task = Mock()
            mock_task.add_done_callback = Mock()
            mock_create_task.return_value = mock_task

            from accessiweather.app_initialization import load_initial_data

            # Should not raise exception
            load_initial_data(app)

            # Verify sync_update was NOT called (cache failed)
            mock_helpers.sync_update_weather_displays.assert_not_called()

            # Verify app.current_weather_data was NOT set
            assert app.current_weather_data is None

            # Verify async refresh was still started
            mock_create_task.assert_called()

    def test_load_initial_data_no_weather_client(self):
        """Should handle gracefully when weather client is not initialized."""
        app = _create_mock_app()
        app.weather_client = None
        location = _create_sample_location()
        config = _create_sample_config(location=location)
        app.config_manager.get_config.return_value = config

        with (
            patch("accessiweather.app_initialization.app_helpers") as mock_helpers,
            patch("accessiweather.app_initialization.event_handlers") as mock_event_handlers,
            patch("accessiweather.app_initialization.background_tasks") as mock_bg_tasks,
            patch("asyncio.create_task") as mock_create_task,
        ):
            mock_helpers.should_show_dialog.return_value = True
            mock_helpers.sync_update_weather_displays = Mock()
            mock_helpers.update_status = Mock()
            mock_task = Mock()
            mock_task.add_done_callback = Mock()
            mock_create_task.return_value = mock_task

            from accessiweather.app_initialization import load_initial_data

            # Should not raise exception
            load_initial_data(app)

            # Verify sync_update was NOT called
            mock_helpers.sync_update_weather_displays.assert_not_called()

            # Verify async task was still created for refresh
            mock_create_task.assert_called()


class TestLoadInitialDataMultipleLocations:
    """Test load_initial_data with multiple configured locations."""

    def test_load_initial_data_prewarms_other_locations(self):
        """Should start background task to prewarm cache for other locations."""
        app = _create_mock_app()
        location1 = _create_sample_location()
        location2 = Location(name="Other City", latitude=34.0522, longitude=-118.2437)
        weather_data = _create_sample_weather_data(location1)
        config = _create_sample_config(location=location1, locations=[location1, location2])

        app.config_manager.get_config.return_value = config
        app.weather_client.get_cached_weather.return_value = weather_data

        mock_presentation = Mock()
        mock_presentation.current_conditions = Mock()
        mock_presentation.current_conditions.fallback_text = "72°F"
        mock_presentation.current_conditions.trends = []
        mock_presentation.status_messages = []
        mock_presentation.source_attribution = None
        mock_presentation.forecast = None
        mock_presentation.aviation = None
        app.presenter.present.return_value = mock_presentation

        with (
            patch("accessiweather.app_initialization.app_helpers") as mock_helpers,
            patch("accessiweather.app_initialization.event_handlers") as mock_event_handlers,
            patch("accessiweather.app_initialization.background_tasks") as mock_bg_tasks,
            patch("asyncio.create_task") as mock_create_task,
        ):
            mock_helpers.should_show_dialog.return_value = True
            mock_helpers.sync_update_weather_displays = Mock()
            mock_helpers.update_status = Mock()
            mock_task = Mock()
            mock_task.add_done_callback = Mock()
            mock_create_task.return_value = mock_task

            from accessiweather.app_initialization import load_initial_data

            load_initial_data(app)

            # Verify at least 2 async tasks were created:
            # 1. refresh_weather_data for current location
            # 2. _pre_warm_other_locations for other locations
            assert mock_create_task.call_count >= 2

    def test_load_initial_data_single_location_no_prewarm(self):
        """Should not start prewarm task when only one location exists."""
        app = _create_mock_app()
        location = _create_sample_location()
        weather_data = _create_sample_weather_data(location)
        config = _create_sample_config(location=location, locations=[location])

        app.config_manager.get_config.return_value = config
        app.weather_client.get_cached_weather.return_value = weather_data

        mock_presentation = Mock()
        mock_presentation.current_conditions = Mock()
        mock_presentation.current_conditions.fallback_text = "72°F"
        mock_presentation.current_conditions.trends = []
        mock_presentation.status_messages = []
        mock_presentation.source_attribution = None
        mock_presentation.forecast = None
        mock_presentation.aviation = None
        app.presenter.present.return_value = mock_presentation

        with (
            patch("accessiweather.app_initialization.app_helpers") as mock_helpers,
            patch("accessiweather.app_initialization.event_handlers") as mock_event_handlers,
            patch("accessiweather.app_initialization.background_tasks") as mock_bg_tasks,
            patch("asyncio.create_task") as mock_create_task,
        ):
            mock_helpers.should_show_dialog.return_value = True
            mock_helpers.sync_update_weather_displays = Mock()
            mock_helpers.update_status = Mock()
            mock_task = Mock()
            mock_task.add_done_callback = Mock()
            mock_create_task.return_value = mock_task

            from accessiweather.app_initialization import load_initial_data

            load_initial_data(app)

            # Verify only 1 async task was created (refresh only, no prewarm)
            assert mock_create_task.call_count == 1


class TestPreWarmOtherLocations:
    """Test the _pre_warm_other_locations async function."""

    @pytest.mark.asyncio
    async def test_pre_warm_skips_when_no_config_manager(self):
        """Should exit early when config_manager is not available."""
        app = Mock()
        app.config_manager = None
        app.weather_client = Mock()

        from accessiweather.app_initialization import _pre_warm_other_locations

        # Should not raise exception
        await _pre_warm_other_locations(app)

        # weather_client should not have been called
        app.weather_client.pre_warm_cache.assert_not_called()

    @pytest.mark.asyncio
    async def test_pre_warm_skips_when_no_weather_client(self):
        """Should exit early when weather_client is not available."""
        app = Mock()
        app.config_manager = Mock()
        app.weather_client = None

        from accessiweather.app_initialization import _pre_warm_other_locations

        # Should not raise exception
        await _pre_warm_other_locations(app)

    @pytest.mark.asyncio
    async def test_pre_warm_handles_exceptions_gracefully(self):
        """Should handle pre-warm exceptions without crashing."""
        app = Mock()
        app.config_manager = Mock()
        app.weather_client = Mock()
        app.weather_client.pre_warm_cache = AsyncMock(side_effect=Exception("Pre-warm error"))

        location1 = _create_sample_location()
        location2 = Location(name="Other City", latitude=34.0522, longitude=-118.2437)

        app.config_manager.get_current_location.return_value = location1
        app.config_manager.get_all_locations.return_value = [location1, location2]

        from accessiweather.app_initialization import _pre_warm_other_locations

        # Patch asyncio.sleep to speed up test
        with patch("asyncio.sleep", new_callable=AsyncMock):
            # Should not raise exception
            await _pre_warm_other_locations(app)

    @pytest.mark.asyncio
    async def test_pre_warm_skips_current_location(self):
        """Should only pre-warm non-current locations."""
        app = Mock()
        app.config_manager = Mock()
        app.weather_client = Mock()
        app.weather_client.pre_warm_cache = AsyncMock()

        location1 = _create_sample_location()
        location2 = Location(name="Other City", latitude=34.0522, longitude=-118.2437)

        app.config_manager.get_current_location.return_value = location1
        app.config_manager.get_all_locations.return_value = [location1, location2]

        from accessiweather.app_initialization import _pre_warm_other_locations

        # Patch asyncio.sleep to speed up test
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await _pre_warm_other_locations(app)

        # Should only pre-warm location2 (not current location1)
        app.weather_client.pre_warm_cache.assert_called_once_with(location2)
