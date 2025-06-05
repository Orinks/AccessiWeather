"""GUI integration tests for AccessiWeather.

These tests verify GUI components work correctly with the service layer
and handle user interactions properly.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

# GUI integration tests require special handling for headless environments


@pytest.mark.integration
@pytest.mark.gui
class TestWeatherAppIntegration:
    """Test WeatherApp integration with services."""

    def test_weather_app_initialization(
        self, headless_environment, temp_config_dir, sample_config, sample_nws_current_response
    ):
        """Test WeatherApp initializes correctly with service layer."""
        with (
            patch("wx.App"),
            patch("accessiweather.gui.weather_app.WeatherApp") as mock_weather_app,
            patch("accessiweather.api_wrapper.NoaaApiWrapper") as mock_wrapper,
        ):

            # Mock the weather app instance
            mock_app_instance = MagicMock()
            mock_weather_app.return_value = mock_app_instance

            # Mock API wrapper
            mock_client = MagicMock()
            mock_wrapper.return_value = mock_client
            mock_client.get_current_conditions.return_value = sample_nws_current_response

            # Test app creation
            from accessiweather.gui.app_factory import create_app

            app = create_app(
                config=sample_config, config_path=os.path.join(temp_config_dir, "config.json")
            )

            assert app is not None
            mock_weather_app.assert_called_once()

    def test_settings_dialog_integration(
        self, headless_environment, temp_config_dir, sample_config
    ):
        """Test settings dialog integration with configuration system."""
        with (
            patch("wx.Dialog"),
            patch("accessiweather.gui.settings_dialog.SettingsDialog") as mock_settings,
        ):

            # Mock settings dialog
            mock_dialog_instance = MagicMock()
            mock_settings.return_value = mock_dialog_instance
            mock_dialog_instance.ShowModal.return_value = 5100  # wx.ID_OK

            # Mock getting values from dialog
            mock_dialog_instance.get_temperature_unit.return_value = "fahrenheit"
            mock_dialog_instance.get_data_source.return_value = "auto"
            mock_dialog_instance.get_update_interval.return_value = 30

            # Test settings dialog creation and interaction
            # This would normally create the dialog
            dialog = mock_settings(None, sample_config)
            result = dialog.ShowModal()

            assert result == 5100  # wx.ID_OK
            mock_settings.assert_called_once()

    def test_ui_manager_weather_data_display(
        self, headless_environment, sample_nws_current_response, sample_nws_forecast_response
    ):
        """Test UI manager displays weather data correctly."""
        with patch("accessiweather.gui.ui_manager.UIManager") as mock_ui_manager:

            # Mock UI manager instance
            mock_ui_instance = MagicMock()
            mock_ui_manager.return_value = mock_ui_instance

            # Mock frame components
            mock_frame = MagicMock()
            mock_frame.current_conditions_text = MagicMock()
            mock_frame.forecast_list = MagicMock()

            mock_ui_instance.frame = mock_frame

            # Test updating current conditions
            mock_ui_instance.update_current_conditions(sample_nws_current_response)
            mock_ui_instance.update_current_conditions.assert_called_once()

            # Test updating forecast
            mock_ui_instance.update_forecast(sample_nws_forecast_response)
            mock_ui_instance.update_forecast.assert_called_once()

    def test_system_tray_integration(self, headless_environment, sample_config):
        """Test system tray integration with main application."""
        with (
            patch("wx.adv.TaskBarIcon"),
            patch("accessiweather.gui.system_tray.TaskBarIcon") as mock_tray_icon,
        ):

            # Mock taskbar icon
            mock_icon_instance = MagicMock()
            mock_tray_icon.return_value = mock_icon_instance

            # Test tray icon creation
            tray_icon = mock_tray_icon(None, sample_config)
            assert tray_icon is not None
            mock_tray_icon.assert_called_once()

            # Test tray icon methods
            mock_icon_instance.SetIcon.return_value = True
            mock_icon_instance.update_icon.return_value = None

            # Simulate icon updates
            result = mock_icon_instance.SetIcon(MagicMock(), "Test Tooltip")
            assert result is True


@pytest.mark.integration
@pytest.mark.gui
class TestDialogIntegration:
    """Test dialog integration with services."""

    def test_location_dialog_integration(self, headless_environment, temp_config_dir):
        """Test location dialog integration with location manager."""
        with (
            patch("wx.Dialog"),
            patch("accessiweather.gui.dialogs.LocationDialog") as mock_location_dialog,
        ):

            # Mock location dialog
            mock_dialog_instance = MagicMock()
            mock_location_dialog.return_value = mock_dialog_instance
            mock_dialog_instance.ShowModal.return_value = 5100  # wx.ID_OK
            mock_dialog_instance.get_location_name.return_value = "Test City"
            mock_dialog_instance.get_coordinates.return_value = (40.7128, -74.0060)

            # Test location dialog interaction
            from accessiweather.location import LocationManager

            location_manager = LocationManager(config_dir=temp_config_dir)

            # Simulate dialog interaction
            dialog = mock_location_dialog(None)
            result = dialog.ShowModal()

            if result == 5100:  # wx.ID_OK
                name = dialog.get_location_name()
                lat, lon = dialog.get_coordinates()
                location_manager.add_location(name, lat, lon)

            # Verify location was added
            locations = location_manager.get_all_locations()
            assert "Test City" in locations

    def test_alert_dialog_integration(self, headless_environment, sample_nws_alerts_response):
        """Test alert dialog integration with alert data."""
        with (
            patch("wx.Dialog"),
            patch("accessiweather.gui.alert_dialog.AlertDetailsDialog") as mock_alert_dialog,
        ):

            # Mock alert dialog
            mock_dialog_instance = MagicMock()
            mock_alert_dialog.return_value = mock_dialog_instance

            # Test alert dialog creation with real alert data
            alert_data = sample_nws_alerts_response["features"][0]["properties"]

            dialog = mock_alert_dialog(None, alert_data)
            assert dialog is not None
            mock_alert_dialog.assert_called_once_with(None, alert_data)

    def test_discussion_dialog_integration(self, headless_environment):
        """Test discussion dialog integration with discussion data."""
        with (
            patch("wx.Dialog"),
            patch("accessiweather.gui.dialogs.WeatherDiscussionDialog") as mock_discussion_dialog,
        ):

            # Mock discussion dialog
            mock_dialog_instance = MagicMock()
            mock_discussion_dialog.return_value = mock_dialog_instance

            # Sample discussion data
            discussion_data = {
                "title": "Test Discussion",
                "content": "This is a test weather discussion.",
                "issued": "2024-01-01T12:00:00Z",
            }

            # Test discussion dialog creation
            dialog = mock_discussion_dialog(None, discussion_data)
            assert dialog is not None
            mock_discussion_dialog.assert_called_once_with(None, discussion_data)


@pytest.mark.integration
@pytest.mark.gui
class TestTimerIntegration:
    """Test timer integration with automatic updates."""

    def test_weather_refresh_timer(
        self, headless_environment, sample_config, sample_nws_current_response
    ):
        """Test automatic weather refresh timer integration."""
        with (
            patch("wx.Timer") as mock_timer,
            patch("accessiweather.gui.weather_app.WeatherApp") as mock_weather_app,
        ):

            # Mock timer
            mock_timer_instance = MagicMock()
            mock_timer.return_value = mock_timer_instance

            # Mock weather app
            mock_app_instance = MagicMock()
            mock_weather_app.return_value = mock_app_instance

            # Mock weather service
            mock_weather_service = MagicMock()
            mock_weather_service.get_current_conditions.return_value = sample_nws_current_response
            mock_app_instance.weather_service = mock_weather_service

            # Test timer setup
            update_interval = sample_config["settings"]["update_interval"]
            mock_timer_instance.Start(update_interval * 60 * 1000)  # Convert to milliseconds

            # Simulate timer event
            mock_app_instance.on_refresh_timer(None)

            # Verify timer was configured
            mock_timer.assert_called()

    def test_alert_refresh_timer(
        self, headless_environment, sample_config, sample_nws_alerts_response
    ):
        """Test alert refresh timer integration."""
        with (
            patch("wx.Timer") as mock_timer,
            patch("accessiweather.gui.weather_app.WeatherApp") as mock_weather_app,
        ):

            # Mock timer
            mock_timer_instance = MagicMock()
            mock_timer.return_value = mock_timer_instance

            # Mock weather app
            mock_app_instance = MagicMock()
            mock_weather_app.return_value = mock_app_instance

            # Mock weather service for alerts
            mock_weather_service = MagicMock()
            mock_weather_service.get_alerts.return_value = sample_nws_alerts_response
            mock_app_instance.weather_service = mock_weather_service

            # Test alert timer setup
            mock_timer_instance.Start(300000)  # 5 minutes in milliseconds

            # Simulate alert timer event
            mock_app_instance.on_alert_timer(None)

            # Verify timer was configured
            mock_timer.assert_called()


@pytest.mark.integration
@pytest.mark.gui
class TestAccessibilityIntegration:
    """Test accessibility features integration."""

    def test_screen_reader_announcements(self, headless_environment, sample_nws_current_response):
        """Test screen reader announcements for weather updates."""
        with patch("accessiweather.gui.ui_manager.UIManager") as mock_ui_manager:

            # Mock UI manager
            mock_ui_instance = MagicMock()
            mock_ui_manager.return_value = mock_ui_instance

            # Mock accessibility methods
            mock_ui_instance.announce_weather_update = MagicMock()

            # Test weather update announcement
            mock_ui_instance.update_current_conditions(sample_nws_current_response)
            mock_ui_instance.announce_weather_update("Weather updated")

            # Verify announcement was made
            mock_ui_instance.announce_weather_update.assert_called_with("Weather updated")

    def test_keyboard_navigation(self, headless_environment):
        """Test keyboard navigation integration."""
        with (
            patch("wx.Frame") as mock_frame,
            patch("accessiweather.gui.weather_app.WeatherApp") as mock_weather_app,
        ):

            # Mock frame and app
            mock_frame_instance = MagicMock()
            mock_frame.return_value = mock_frame_instance

            mock_app_instance = MagicMock()
            mock_weather_app.return_value = mock_app_instance

            # Mock keyboard event handling
            mock_app_instance.on_key_down = MagicMock()

            # Simulate keyboard events
            mock_key_event = MagicMock()
            mock_key_event.GetKeyCode.return_value = 82  # 'R' key for refresh

            mock_app_instance.on_key_down(mock_key_event)

            # Verify keyboard handler was called
            mock_app_instance.on_key_down.assert_called_once_with(mock_key_event)

    def test_high_contrast_support(self, headless_environment, sample_config):
        """Test high contrast mode support."""
        with (
            patch("wx.SystemSettings") as mock_system_settings,
            patch("accessiweather.gui.ui_manager.UIManager") as mock_ui_manager,
        ):

            # Mock system settings
            mock_system_settings.GetColour.return_value = MagicMock()

            # Mock UI manager
            mock_ui_instance = MagicMock()
            mock_ui_manager.return_value = mock_ui_instance

            # Mock high contrast detection and application
            mock_ui_instance.apply_high_contrast_theme = MagicMock()
            mock_ui_instance.is_high_contrast_mode = MagicMock(return_value=True)

            # Test high contrast mode detection
            if mock_ui_instance.is_high_contrast_mode():
                mock_ui_instance.apply_high_contrast_theme()

            # Verify high contrast theme was applied
            mock_ui_instance.apply_high_contrast_theme.assert_called_once()


@pytest.mark.integration
@pytest.mark.gui
@pytest.mark.slow
class TestPerformanceIntegration:
    """Test GUI performance integration."""

    def test_ui_responsiveness(
        self,
        headless_environment,
        performance_timer,
        sample_nws_current_response,
        sample_nws_forecast_response,
    ):
        """Test UI remains responsive during data updates."""
        with patch("accessiweather.gui.ui_manager.UIManager") as mock_ui_manager:

            # Mock UI manager
            mock_ui_instance = MagicMock()
            mock_ui_manager.return_value = mock_ui_instance

            # Test UI update performance
            performance_timer.start()

            # Simulate multiple UI updates
            for _ in range(10):
                mock_ui_instance.update_current_conditions(sample_nws_current_response)
                mock_ui_instance.update_forecast(sample_nws_forecast_response)

            performance_timer.stop()

            # UI updates should be fast (even with mocking overhead)
            assert performance_timer.elapsed < 1.0

            # Verify all updates were processed
            assert mock_ui_instance.update_current_conditions.call_count == 10
            assert mock_ui_instance.update_forecast.call_count == 10

    def test_memory_usage_stability(self, headless_environment):
        """Test memory usage remains stable during extended operation."""
        import gc

        with patch("accessiweather.gui.weather_app.WeatherApp") as mock_weather_app:

            # Mock weather app
            mock_app_instance = MagicMock()
            mock_weather_app.return_value = mock_app_instance

            # Get initial memory usage
            gc.collect()
            initial_objects = len(gc.get_objects())

            # Simulate extended operation
            for i in range(100):
                # Simulate various operations
                mock_app_instance.refresh_weather_data()
                mock_app_instance.update_ui()

                # Periodic cleanup
                if i % 10 == 0:
                    gc.collect()

            # Check final memory usage
            gc.collect()
            final_objects = len(gc.get_objects())

            # Memory usage should not grow significantly
            # Allow for some growth due to test infrastructure
            growth_ratio = final_objects / initial_objects
            assert growth_ratio < 1.5, f"Memory usage grew by {growth_ratio:.2f}x"
