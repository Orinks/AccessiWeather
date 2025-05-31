"""Tests for settings change handling in WeatherApp."""

from unittest.mock import MagicMock, patch

from accessiweather.gui.settings_dialog import (
    API_KEYS_SECTION,
    DATA_SOURCE_AUTO,
    DATA_SOURCE_KEY,
    DATA_SOURCE_NWS,
)


class TestSettingsChangeHandling:
    """Tests for settings change handling in WeatherApp."""

    def test_handle_data_source_change_nws(self):
        """Test handling data source change to NWS."""
        # Create mocks
        mock_weather_service = MagicMock()
        mock_location_service = MagicMock()
        mock_notification_service = MagicMock()

        mock_forecast_fetcher = MagicMock()
        mock_alerts_fetcher = MagicMock()
        mock_discussion_fetcher = MagicMock()
        mock_current_conditions_fetcher = MagicMock()
        mock_hourly_forecast_fetcher = MagicMock()
        mock_national_forecast_fetcher = MagicMock()

        # Create config
        mock_config = {
            "settings": {
                DATA_SOURCE_KEY: DATA_SOURCE_NWS,
            },
            "api_settings": {"api_contact": "test@example.com"},
            API_KEYS_SECTION: {},
        }

        # Create mock NoaaApiClient and WeatherService
        mock_nws_client = MagicMock()
        mock_new_weather_service = MagicMock()

        # Set up patches
        with (
            patch("accessiweather.api_client.NoaaApiClient", return_value=mock_nws_client),
            patch(
                "accessiweather.services.weather_service.WeatherService",
                return_value=mock_new_weather_service,
            ),
        ):

            # Create a mock WeatherApp
            mock_app = MagicMock()
            mock_app.weather_service = mock_weather_service
            mock_app.location_service = mock_location_service
            mock_app.notification_service = mock_notification_service
            mock_app.config = mock_config
            mock_app.forecast_fetcher = mock_forecast_fetcher
            mock_app.alerts_fetcher = mock_alerts_fetcher
            mock_app.discussion_fetcher = mock_discussion_fetcher
            mock_app.current_conditions_fetcher = mock_current_conditions_fetcher
            mock_app.hourly_forecast_fetcher = mock_hourly_forecast_fetcher
            mock_app.national_forecast_fetcher = mock_national_forecast_fetcher

            # Import the method here to avoid import issues
            from accessiweather.gui.weather_app import WeatherApp

            # Call the method
            WeatherApp._handle_data_source_change(mock_app)

            # Verify that the weather service was updated
            assert mock_app.weather_service == mock_new_weather_service

            # Verify that the location service data source was updated
            mock_location_service.update_data_source.assert_called_once_with(DATA_SOURCE_NWS)

            # Verify that the fetchers were updated
            assert mock_forecast_fetcher.service == mock_new_weather_service
            assert mock_alerts_fetcher.service == mock_new_weather_service
            assert mock_discussion_fetcher.service == mock_new_weather_service
            assert mock_current_conditions_fetcher.service == mock_new_weather_service
            assert mock_hourly_forecast_fetcher.service == mock_new_weather_service
            assert mock_national_forecast_fetcher.service == mock_new_weather_service

            # Verify that weather data was refreshed
            mock_app.UpdateWeatherData.assert_called_once()

    def test_handle_data_source_change_auto(self):
        """Test handling data source change to AUTO mode."""
        # Create mocks
        mock_weather_service = MagicMock()
        mock_location_service = MagicMock()
        mock_notification_service = MagicMock()

        mock_forecast_fetcher = MagicMock()
        mock_alerts_fetcher = MagicMock()
        mock_discussion_fetcher = MagicMock()
        mock_current_conditions_fetcher = MagicMock()
        mock_hourly_forecast_fetcher = MagicMock()
        mock_national_forecast_fetcher = MagicMock()

        # Create config for AUTO mode
        mock_config = {
            "settings": {
                DATA_SOURCE_KEY: DATA_SOURCE_AUTO,
            },
            "api_settings": {"api_contact": "test@example.com"},
            API_KEYS_SECTION: {},
        }

        # Create mock clients and service
        mock_nws_client = MagicMock()
        mock_new_weather_service = MagicMock()

        # Set up patches
        with (
            patch("accessiweather.api_client.NoaaApiClient", return_value=mock_nws_client),
            patch(
                "accessiweather.services.weather_service.WeatherService",
                return_value=mock_new_weather_service,
            ),
        ):

            # Create a mock WeatherApp
            mock_app = MagicMock()
            mock_app.weather_service = mock_weather_service
            mock_app.location_service = mock_location_service
            mock_app.notification_service = mock_notification_service
            mock_app.config = mock_config
            mock_app.forecast_fetcher = mock_forecast_fetcher
            mock_app.alerts_fetcher = mock_alerts_fetcher
            mock_app.discussion_fetcher = mock_discussion_fetcher
            mock_app.current_conditions_fetcher = mock_current_conditions_fetcher
            mock_app.hourly_forecast_fetcher = mock_hourly_forecast_fetcher
            mock_app.national_forecast_fetcher = mock_national_forecast_fetcher

            # Import the method here to avoid import issues
            from accessiweather.gui.weather_app import WeatherApp

            # Call the method
            WeatherApp._handle_data_source_change(mock_app)

            # Verify that the weather service was updated
            assert mock_app.weather_service == mock_new_weather_service

            # Verify that the location service data source was updated
            mock_location_service.update_data_source.assert_called_once_with(DATA_SOURCE_AUTO)

            # Verify that the fetchers were updated
            assert mock_forecast_fetcher.service == mock_new_weather_service
            assert mock_alerts_fetcher.service == mock_new_weather_service
            assert mock_discussion_fetcher.service == mock_new_weather_service
            assert mock_current_conditions_fetcher.service == mock_new_weather_service
            assert mock_hourly_forecast_fetcher.service == mock_new_weather_service
            assert mock_national_forecast_fetcher.service == mock_new_weather_service

            # Verify that weather data was refreshed
            mock_app.UpdateWeatherData.assert_called_once()
