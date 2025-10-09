"""Tests for data models in the simplified AccessiWeather application.

This module provides comprehensive tests for the data models in the simplified
AccessiWeather implementation, adapted from existing test logic while updating
imports and ensuring tests match the simplified model structure.
"""

from datetime import UTC, datetime, timedelta

# Import simplified app models
from accessiweather.models import (
    ApiError,
    AppConfig,
    AppSettings,
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)


class TestLocationModel:
    """Test the Location data model - adapted from existing test logic."""

    def test_location_creation(self):
        """Test basic location creation."""
        location = Location("Philadelphia, PA", 39.9526, -75.1652)

        assert location.name == "Philadelphia, PA"
        assert location.latitude == 39.9526
        assert location.longitude == -75.1652

    def test_location_string_representation(self):
        """Test location string representation."""
        location = Location("New York, NY", 40.7128, -74.0060)
        assert str(location) == "New York, NY"

    def test_location_with_special_characters(self):
        """Test location with special characters in name."""
        location = Location("São Paulo, Brazil", -23.5505, -46.6333)
        assert location.name == "São Paulo, Brazil"
        assert str(location) == "São Paulo, Brazil"

    def test_location_coordinate_validation(self):
        """Test location with edge case coordinates."""
        # Test extreme coordinates
        north_pole = Location("North Pole", 90.0, 0.0)
        assert north_pole.latitude == 90.0

        south_pole = Location("South Pole", -90.0, 0.0)
        assert south_pole.latitude == -90.0

        # Test longitude boundaries
        date_line = Location("Date Line", 0.0, 180.0)
        assert date_line.longitude == 180.0


class TestCurrentConditionsModel:
    """Test the CurrentConditions data model - adapted from existing test logic."""

    def test_current_conditions_creation(self):
        """Test basic current conditions creation."""
        conditions = CurrentConditions(
            temperature_f=75.0,
            temperature_c=23.9,
            condition="Partly Cloudy",
            humidity=65,
            wind_speed_mph=10.0,
            wind_direction="NW",
        )

        assert conditions.temperature_f == 75.0
        assert conditions.temperature_c == 23.9
        assert conditions.condition == "Partly Cloudy"
        assert conditions.humidity == 65
        assert conditions.wind_speed_mph == 10.0
        assert conditions.wind_direction == "NW"

    def test_current_conditions_has_data(self):
        """Test has_data method with various data states."""
        # Test with temperature data
        conditions_with_temp = CurrentConditions(temperature_f=75.0)
        assert conditions_with_temp.has_data() is True

        # Test with condition data
        conditions_with_condition = CurrentConditions(condition="Sunny")
        assert conditions_with_condition.has_data() is True

        # Test with Celsius temperature
        conditions_with_celsius = CurrentConditions(temperature_c=23.9)
        assert conditions_with_celsius.has_data() is True

        # Test empty conditions
        empty_conditions = CurrentConditions()
        assert empty_conditions.has_data() is False

    def test_current_conditions_optional_fields(self):
        """Test current conditions with optional fields."""
        conditions = CurrentConditions(
            temperature_f=75.0,
            feels_like_f=78.0,
            pressure_in=29.92,
            visibility_miles=10.0,
            uv_index=6.0,
            last_updated=datetime.now(),
        )

        assert conditions.feels_like_f == 78.0
        assert conditions.pressure_in == 29.92
        assert conditions.visibility_miles == 10.0
        assert conditions.uv_index == 6.0
        assert conditions.last_updated is not None

    def test_current_conditions_numeric_wind_direction(self):
        """Test current conditions with numeric wind direction."""
        # This tests the bug fix for numeric wind directions
        conditions = CurrentConditions(
            temperature_f=75.0,
            wind_direction=330,  # Numeric instead of string
        )

        assert conditions.wind_direction == 330
        assert conditions.has_data() is True

    def test_current_conditions_edge_cases(self):
        """Test current conditions with edge case values."""
        # Test with zero values
        conditions_zero = CurrentConditions(temperature_f=0.0, humidity=0, wind_speed_mph=0.0)
        assert conditions_zero.has_data() is True
        assert conditions_zero.temperature_f == 0.0

        # Test with negative temperature
        conditions_negative = CurrentConditions(temperature_f=-10.0)
        assert conditions_negative.has_data() is True
        assert conditions_negative.temperature_f == -10.0


class TestForecastModels:
    """Test the Forecast and ForecastPeriod data models - adapted from existing test logic."""

    def test_forecast_period_creation(self):
        """Test basic forecast period creation."""
        period = ForecastPeriod(
            name="Today",
            temperature=80.0,
            temperature_unit="F",
            short_forecast="Sunny",
            detailed_forecast="Sunny skies with light winds.",
        )

        assert period.name == "Today"
        assert period.temperature == 80.0
        assert period.temperature_unit == "F"
        assert period.short_forecast == "Sunny"
        assert period.detailed_forecast == "Sunny skies with light winds."

    def test_forecast_period_with_times(self):
        """Test forecast period with start and end times."""
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=12)

        period = ForecastPeriod(
            name="Tonight", temperature=65.0, start_time=start_time, end_time=end_time
        )

        assert period.start_time == start_time
        assert period.end_time == end_time

    def test_forecast_creation(self):
        """Test basic forecast creation."""
        periods = [
            ForecastPeriod(name="Today", temperature=80.0, short_forecast="Sunny"),
            ForecastPeriod(name="Tonight", temperature=65.0, short_forecast="Clear"),
        ]

        forecast = Forecast(periods=periods)

        assert len(forecast.periods) == 2
        assert forecast.periods[0].name == "Today"
        assert forecast.periods[1].name == "Tonight"

    def test_forecast_has_data(self):
        """Test forecast has_data method."""
        # Test with periods
        periods = [ForecastPeriod(name="Today", temperature=80.0)]
        forecast_with_data = Forecast(periods=periods)
        assert forecast_with_data.has_data() is True

        # Test empty forecast
        empty_forecast = Forecast(periods=[])
        assert empty_forecast.has_data() is False

    def test_forecast_with_generation_time(self):
        """Test forecast with generation timestamp."""
        generated_at = datetime.now()
        periods = [ForecastPeriod(name="Today", temperature=80.0)]

        forecast = Forecast(periods=periods, generated_at=generated_at)

        assert forecast.generated_at == generated_at


class TestWeatherAlertModels:
    """Test the WeatherAlert and WeatherAlerts data models - adapted from existing test logic."""

    def test_weather_alert_creation(self):
        """Test basic weather alert creation."""
        alert = WeatherAlert(
            title="Severe Thunderstorm Warning",
            description="A severe thunderstorm warning is in effect.",
            severity="Severe",
            urgency="Immediate",
            certainty="Observed",
            event="Severe Thunderstorm Warning",
            headline="Severe thunderstorms approaching",
        )

        assert alert.title == "Severe Thunderstorm Warning"
        assert alert.description == "A severe thunderstorm warning is in effect."
        assert alert.severity == "Severe"
        assert alert.urgency == "Immediate"
        assert alert.certainty == "Observed"
        assert alert.event == "Severe Thunderstorm Warning"
        assert alert.headline == "Severe thunderstorms approaching"

    def test_weather_alert_with_times(self):
        """Test weather alert with onset and expiration times."""
        onset = datetime.now()
        expires = onset + timedelta(hours=6)

        alert = WeatherAlert(
            title="Winter Storm Watch",
            description="Heavy snow expected.",
            onset=onset,
            expires=expires,
        )

        assert alert.onset == onset
        assert alert.expires == expires

    def test_weather_alert_areas_initialization(self):
        """Test weather alert areas list initialization."""
        # Test with areas provided
        alert_with_areas = WeatherAlert(
            title="Flood Warning", description="Flooding expected.", areas=["County A", "County B"]
        )
        assert alert_with_areas.areas == ["County A", "County B"]

        # Test with no areas (should initialize empty list)
        alert_no_areas = WeatherAlert(
            title="Heat Advisory", description="High temperatures expected."
        )
        assert alert_no_areas.areas == []

    def test_weather_alerts_collection(self):
        """Test WeatherAlerts collection functionality."""
        alert1 = WeatherAlert(title="Alert 1", description="Description 1")
        alert2 = WeatherAlert(title="Alert 2", description="Description 2")

        alerts = WeatherAlerts(alerts=[alert1, alert2])

        assert len(alerts.alerts) == 2
        assert alerts.has_alerts() is True

    def test_weather_alerts_empty(self):
        """Test empty WeatherAlerts collection."""
        empty_alerts = WeatherAlerts(alerts=[])

        assert len(empty_alerts.alerts) == 0
        assert empty_alerts.has_alerts() is False

    def test_weather_alerts_active_filtering(self):
        """Test active alerts filtering by expiration time."""
        now = datetime.now(UTC)

        # Create expired alert
        expired_alert = WeatherAlert(
            title="Expired Alert",
            description="This alert has expired.",
            expires=now - timedelta(hours=1),
        )

        # Create active alert
        active_alert = WeatherAlert(
            title="Active Alert",
            description="This alert is still active.",
            expires=now + timedelta(hours=1),
        )

        # Create alert with no expiration (should be considered active)
        no_expiry_alert = WeatherAlert(
            title="No Expiry Alert", description="This alert has no expiration."
        )

        alerts = WeatherAlerts(alerts=[expired_alert, active_alert, no_expiry_alert])
        active_alerts = alerts.get_active_alerts()

        assert len(active_alerts) == 2  # active_alert and no_expiry_alert
        assert active_alert in active_alerts
        assert no_expiry_alert in active_alerts
        assert expired_alert not in active_alerts


class TestWeatherDataModel:
    """Test the WeatherData composite model - adapted from existing test logic."""

    def test_weather_data_creation(self):
        """Test basic weather data creation."""
        location = Location("Test City", 40.0, -75.0)
        current = CurrentConditions(temperature_f=75.0, condition="Sunny")
        periods = [ForecastPeriod(name="Today", temperature=80.0)]
        forecast = Forecast(periods=periods)
        alerts = WeatherAlerts(alerts=[])

        weather_data = WeatherData(
            location=location, current=current, forecast=forecast, alerts=alerts
        )

        assert weather_data.location == location
        assert weather_data.current == current
        assert weather_data.forecast == forecast
        assert weather_data.alerts == alerts

    def test_weather_data_has_any_data(self):
        """Test has_any_data method with various data combinations."""
        location = Location("Test City", 40.0, -75.0)

        # Test with current conditions only
        current = CurrentConditions(temperature_f=75.0)
        weather_data_current = WeatherData(location=location, current=current)
        assert weather_data_current.has_any_data() is True

        # Test with forecast only
        periods = [ForecastPeriod(name="Today", temperature=80.0)]
        forecast = Forecast(periods=periods)
        weather_data_forecast = WeatherData(location=location, forecast=forecast)
        assert weather_data_forecast.has_any_data() is True

        # Test with alerts only
        alert = WeatherAlert(title="Test Alert", description="Test description")
        alerts = WeatherAlerts(alerts=[alert])
        weather_data_alerts = WeatherData(location=location, alerts=alerts)
        assert weather_data_alerts.has_any_data() is True

        # Test with no data
        weather_data_empty = WeatherData(location=location)
        assert weather_data_empty.has_any_data() is False

    def test_weather_data_with_timestamp(self):
        """Test weather data with last updated timestamp."""
        location = Location("Test City", 40.0, -75.0)
        last_updated = datetime.now()

        weather_data = WeatherData(location=location, last_updated=last_updated)

        assert weather_data.last_updated == last_updated


class TestApiErrorModel:
    """Test the ApiError data model - adapted from existing test logic."""

    def test_api_error_creation(self):
        """Test basic API error creation."""
        error = ApiError(
            message="API request failed", code="HTTP_500", details="Internal server error occurred"
        )

        assert error.message == "API request failed"
        assert error.code == "HTTP_500"
        assert error.details == "Internal server error occurred"

    def test_api_error_timestamp_auto_generation(self):
        """Test that timestamp is automatically generated."""
        error = ApiError(message="Test error")

        assert error.timestamp is not None
        assert isinstance(error.timestamp, datetime)

    def test_api_error_with_custom_timestamp(self):
        """Test API error with custom timestamp."""
        custom_timestamp = datetime.now() - timedelta(minutes=5)
        error = ApiError(message="Test error", timestamp=custom_timestamp)

        assert error.timestamp == custom_timestamp


class TestAppSettingsModel:
    """Test the AppSettings data model - adapted from existing test logic."""

    def test_app_settings_defaults(self):
        """Test AppSettings default values."""
        settings = AppSettings()

        assert settings.temperature_unit == "both"
        assert settings.update_interval_minutes == 10
        assert settings.show_detailed_forecast is True
        assert settings.enable_alerts is True
        assert settings.minimize_to_tray is False
        assert settings.data_source == "auto"

    def test_app_settings_custom_values(self):
        """Test AppSettings with custom values."""
        settings = AppSettings(
            temperature_unit="f",
            update_interval_minutes=15,
            show_detailed_forecast=False,
            enable_alerts=False,
            minimize_to_tray=False,
            data_source="nws",
        )

        assert settings.temperature_unit == "f"
        assert settings.update_interval_minutes == 15
        assert settings.show_detailed_forecast is False
        assert settings.enable_alerts is False
        assert settings.minimize_to_tray is False
        assert settings.data_source == "nws"

    def test_app_settings_serialization(self):
        """Test AppSettings to_dict serialization."""
        settings = AppSettings(
            temperature_unit="c", update_interval_minutes=20, data_source="openmeteo"
        )

        settings_dict = settings.to_dict()

        assert settings_dict["temperature_unit"] == "c"
        assert settings_dict["update_interval_minutes"] == 20
        assert settings_dict["show_detailed_forecast"] is True  # Default value
        assert settings_dict["data_source"] == "openmeteo"

    def test_app_settings_deserialization(self):
        """Test AppSettings from_dict deserialization."""
        settings_dict = {
            "temperature_unit": "f",
            "update_interval_minutes": 30,
            "show_detailed_forecast": False,
            "enable_alerts": True,
            "minimize_to_tray": False,
            "data_source": "nws",
        }

        settings = AppSettings.from_dict(settings_dict)

        assert settings.temperature_unit == "f"
        assert settings.update_interval_minutes == 30
        assert settings.show_detailed_forecast is False
        assert settings.enable_alerts is True
        assert settings.minimize_to_tray is False
        assert settings.data_source == "nws"

    def test_app_settings_partial_deserialization(self):
        """Test AppSettings deserialization with missing fields (should use defaults)."""
        partial_dict = {"temperature_unit": "c", "update_interval_minutes": 25}

        settings = AppSettings.from_dict(partial_dict)

        assert settings.temperature_unit == "c"
        assert settings.update_interval_minutes == 25
        # Should use defaults for missing fields
        assert settings.show_detailed_forecast is True
        assert settings.enable_alerts is True
        assert settings.data_source == "auto"

    def test_app_settings_roundtrip_serialization(self):
        """Test roundtrip serialization (to_dict -> from_dict)."""
        original_settings = AppSettings(
            temperature_unit="both", update_interval_minutes=12, show_detailed_forecast=False
        )

        # Serialize and deserialize
        settings_dict = original_settings.to_dict()
        restored_settings = AppSettings.from_dict(settings_dict)

        # Should be identical
        assert restored_settings.temperature_unit == original_settings.temperature_unit
        assert (
            restored_settings.update_interval_minutes == original_settings.update_interval_minutes
        )
        assert restored_settings.show_detailed_forecast == original_settings.show_detailed_forecast
        assert restored_settings.enable_alerts == original_settings.enable_alerts

    def test_app_settings_roundtrip_preserves_startup_enabled_true(self):
        """Ensure startup_enabled stays True after serialization and deserialization."""
        original_settings = AppSettings(startup_enabled=True)

        restored_settings = AppSettings.from_dict(original_settings.to_dict())

        assert restored_settings.startup_enabled is True

    def test_app_settings_missing_startup_enabled_defaults_to_false(self):
        """Ensure missing startup_enabled falls back to the default False value."""
        settings = AppSettings.from_dict({"temperature_unit": "f"})

        assert settings.startup_enabled is False

    def test_app_settings_from_dict_normalizes_boolean_inputs(self):
        """AppSettings.from_dict should coerce diverse truthy/falsey values."""
        settings = AppSettings.from_dict(
            {
                "show_detailed_forecast": "false",
                "enable_alerts": "true",
                "minimize_to_tray": 1,
                "startup_enabled": "True",
                "auto_update_enabled": 0,
                "debug_mode": "no",
                "sound_enabled": "YES",
                "alert_notifications_enabled": "off",
                "alert_notify_extreme": "false",
                "alert_notify_severe": "TRUE",
                "alert_notify_moderate": "0",
                "alert_notify_minor": "1",
                "alert_notify_unknown": "On",
                "alert_tts_enabled": "off",
                "international_alerts_enabled": "OFF",
                "trend_insights_enabled": 1,
                "air_quality_enabled": 0,
                "pollen_enabled": "true",
                "offline_cache_enabled": "False",
            }
        )

        assert settings.show_detailed_forecast is False
        assert settings.enable_alerts is True
        assert settings.minimize_to_tray is True
        assert settings.startup_enabled is True
        assert settings.auto_update_enabled is False
        assert settings.debug_mode is False
        assert settings.sound_enabled is True
        assert settings.alert_notifications_enabled is False
        assert settings.alert_notify_extreme is False
        assert settings.alert_notify_severe is True
        assert settings.alert_notify_moderate is False
        assert settings.alert_notify_minor is True
        assert settings.alert_notify_unknown is True
        assert settings.international_alerts_enabled is False
        assert settings.trend_insights_enabled is True
        assert settings.air_quality_enabled is False
        assert settings.pollen_enabled is True
        assert settings.offline_cache_enabled is False


class TestAppConfigModel:
    """Test the AppConfig data model - adapted from existing test logic."""

    def test_app_config_creation(self):
        """Test basic AppConfig creation."""
        settings = AppSettings(temperature_unit="f")
        locations = [
            Location("Philadelphia, PA", 39.9526, -75.1652),
            Location("New York, NY", 40.7128, -74.0060),
        ]
        current_location = locations[0]

        config = AppConfig(
            settings=settings, locations=locations, current_location=current_location
        )

        assert config.settings == settings
        assert config.locations == locations
        assert config.current_location == current_location

    def test_app_config_default(self):
        """Test AppConfig default factory method."""
        config = AppConfig.default()

        assert isinstance(config.settings, AppSettings)
        assert config.locations == []
        assert config.current_location is None

    def test_app_config_serialization(self):
        """Test AppConfig to_dict serialization."""
        settings = AppSettings(temperature_unit="c")
        locations = [Location("Test City", 40.0, -75.0)]
        current_location = locations[0]

        config = AppConfig(
            settings=settings, locations=locations, current_location=current_location
        )

        config_dict = config.to_dict()

        assert "settings" in config_dict
        assert "locations" in config_dict
        assert "current_location" in config_dict
        assert config_dict["settings"]["temperature_unit"] == "c"
        assert len(config_dict["locations"]) == 1
        assert config_dict["locations"][0]["name"] == "Test City"
        assert config_dict["current_location"]["name"] == "Test City"

    def test_app_config_serialization_no_current_location(self):
        """Test AppConfig serialization with no current location."""
        settings = AppSettings()
        locations = [Location("Test City", 40.0, -75.0)]

        config = AppConfig(settings=settings, locations=locations)
        config_dict = config.to_dict()

        assert config_dict["current_location"] is None

    def test_app_config_deserialization(self):
        """Test AppConfig from_dict deserialization."""
        config_dict = {
            "settings": {
                "temperature_unit": "both",
                "update_interval_minutes": 15,
                "data_source": "nws",
            },
            "locations": [
                {"name": "Philadelphia, PA", "latitude": 39.9526, "longitude": -75.1652},
                {"name": "New York, NY", "latitude": 40.7128, "longitude": -74.0060},
            ],
            "current_location": {
                "name": "Philadelphia, PA",
                "latitude": 39.9526,
                "longitude": -75.1652,
            },
        }

        config = AppConfig.from_dict(config_dict)

        assert config.settings.temperature_unit == "both"
        assert config.settings.update_interval_minutes == 15
        assert config.settings.data_source == "nws"
        assert len(config.locations) == 2
        assert config.locations[0].name == "Philadelphia, PA"
        assert config.current_location.name == "Philadelphia, PA"

    def test_app_config_deserialization_no_current_location(self):
        """Test AppConfig deserialization with no current location."""
        config_dict = {
            "settings": {"temperature_unit": "f"},
            "locations": [{"name": "Test City", "latitude": 40.0, "longitude": -75.0}],
            "current_location": None,
        }

        config = AppConfig.from_dict(config_dict)

        assert config.current_location is None
        assert len(config.locations) == 1

    def test_app_config_roundtrip_serialization(self):
        """Test roundtrip serialization for AppConfig."""
        original_settings = AppSettings(temperature_unit="both", data_source="openmeteo")
        original_locations = [
            Location("City 1", 40.0, -75.0),
            Location("City 2", 41.0, -76.0),
        ]
        original_current = original_locations[1]

        original_config = AppConfig(
            settings=original_settings,
            locations=original_locations,
            current_location=original_current,
        )

        # Serialize and deserialize
        config_dict = original_config.to_dict()
        restored_config = AppConfig.from_dict(config_dict)

        # Verify settings
        assert (
            restored_config.settings.temperature_unit == original_config.settings.temperature_unit
        )
        assert restored_config.settings.data_source == original_config.settings.data_source

        # Verify locations
        assert len(restored_config.locations) == len(original_config.locations)
        assert restored_config.locations[0].name == original_config.locations[0].name
        assert restored_config.locations[1].name == original_config.locations[1].name

        # Verify current location
        assert restored_config.current_location.name == original_config.current_location.name


class TestModelIntegration:
    """Test integration scenarios between models - adapted from existing test logic."""

    def test_complete_weather_data_scenario(self):
        """Test a complete weather data scenario with all models."""
        # Create location
        location = Location("Philadelphia, PA", 39.9526, -75.1652)

        # Create current conditions
        current = CurrentConditions(
            temperature_f=75.0,
            temperature_c=23.9,
            condition="Partly Cloudy",
            humidity=65,
            wind_speed_mph=10.0,
            wind_direction="NW",
            last_updated=datetime.now(),
        )

        # Create forecast
        periods = [
            ForecastPeriod(name="Today", temperature=80.0, short_forecast="Sunny"),
            ForecastPeriod(name="Tonight", temperature=65.0, short_forecast="Clear"),
        ]
        forecast = Forecast(periods=periods, generated_at=datetime.now())

        # Create alerts
        alert = WeatherAlert(
            title="Heat Advisory",
            description="High temperatures expected.",
            severity="Minor",
            event="Heat Advisory",
        )
        alerts = WeatherAlerts(alerts=[alert])

        # Create complete weather data
        weather_data = WeatherData(
            location=location,
            current=current,
            forecast=forecast,
            alerts=alerts,
            last_updated=datetime.now(),
        )

        # Verify all data is present and accessible
        assert weather_data.has_any_data() is True
        assert weather_data.current.has_data() is True
        assert weather_data.forecast.has_data() is True
        assert weather_data.alerts.has_alerts() is True
        assert weather_data.location.name == "Philadelphia, PA"

    def test_model_edge_cases_integration(self):
        """Test edge cases across multiple models."""
        # Test with minimal data
        location = Location("Minimal City", 0.0, 0.0)
        weather_data = WeatherData(location=location)

        assert weather_data.has_any_data() is False
        assert weather_data.location.name == "Minimal City"

        # Test with only temperature data
        current_minimal = CurrentConditions(temperature_f=32.0)
        weather_data_minimal = WeatherData(location=location, current=current_minimal)

        assert weather_data_minimal.has_any_data() is True
        assert weather_data_minimal.current.has_data() is True

    def test_weather_data_with_hourly_forecast(self):
        """Test WeatherData with hourly forecast integration."""
        location = Location("Test City", 40.0, -75.0)

        # Create hourly forecast
        hourly_periods = [
            HourlyForecastPeriod(
                start_time=datetime.now(), temperature=75.0, short_forecast="Sunny"
            ),
            HourlyForecastPeriod(
                start_time=datetime.now() + timedelta(hours=1),
                temperature=73.0,
                short_forecast="Partly Cloudy",
            ),
        ]
        hourly_forecast = HourlyForecast(periods=hourly_periods)

        # Create weather data with hourly forecast
        weather_data = WeatherData(
            location=location, hourly_forecast=hourly_forecast, last_updated=datetime.now()
        )

        assert weather_data.hourly_forecast is not None
        assert weather_data.hourly_forecast.has_data() is True
        assert len(weather_data.hourly_forecast.periods) == 2
        assert weather_data.has_any_data() is True

    def test_weather_data_complete_with_hourly(self):
        """Test complete WeatherData including hourly forecast."""
        location = Location("Complete City", 40.0, -75.0)
        current = CurrentConditions(temperature_f=75.0, condition="Sunny")

        # Regular forecast
        forecast_periods = [ForecastPeriod(name="Today", temperature=80.0)]
        forecast = Forecast(periods=forecast_periods)

        # Hourly forecast
        hourly_periods = [
            HourlyForecastPeriod(
                start_time=datetime.now(), temperature=75.0, short_forecast="Sunny"
            )
        ]
        hourly_forecast = HourlyForecast(periods=hourly_periods)

        # Alerts
        alert = WeatherAlert(title="Test Alert", description="Test description")
        alerts = WeatherAlerts(alerts=[alert])

        # Complete weather data
        weather_data = WeatherData(
            location=location,
            current=current,
            forecast=forecast,
            hourly_forecast=hourly_forecast,
            alerts=alerts,
            last_updated=datetime.now(),
        )

        # Verify all components
        assert weather_data.has_any_data() is True
        assert weather_data.current.has_data() is True
        assert weather_data.forecast.has_data() is True
        assert weather_data.hourly_forecast.has_data() is True
        assert weather_data.alerts.has_alerts() is True


# Smoke test functions that can be run with briefcase dev --test
def test_models_can_be_imported():
    """Test that all simplified models can be imported successfully."""
    # This test verifies that all models are available for import
    from accessiweather.models import (
        AppSettings,
        HourlyForecast,
        HourlyForecastPeriod,
        Location,
    )

    # Basic instantiation test
    location = Location("Test", 0.0, 0.0)
    assert location.name == "Test"

    settings = AppSettings()
    assert settings.temperature_unit == "both"

    # Test hourly forecast models
    hourly_period = HourlyForecastPeriod(start_time=datetime.now())
    assert hourly_period.temperature_unit == "F"

    hourly_forecast = HourlyForecast(periods=[])
    assert hourly_forecast.has_data() is False


def test_models_basic_functionality():
    """Test basic model functionality without complex scenarios."""
    # Test basic model creation and methods
    location = Location("Test City", 40.0, -75.0)
    assert str(location) == "Test City"


class TestHourlyForecastPeriod:
    """Test HourlyForecastPeriod model."""

    def test_hourly_forecast_period_creation(self):
        """Test creating an hourly forecast period."""
        start_time = datetime.now()
        period = HourlyForecastPeriod(
            start_time=start_time,
            temperature=75.0,
            temperature_unit="F",
            short_forecast="Sunny",
            wind_speed="10 mph",
            wind_direction="NW",
        )

        assert period.start_time == start_time
        assert period.temperature == 75.0
        assert period.temperature_unit == "F"
        assert period.short_forecast == "Sunny"
        assert period.wind_speed == "10 mph"
        assert period.wind_direction == "NW"

    def test_hourly_forecast_period_defaults(self):
        """Test hourly forecast period with default values."""
        start_time = datetime.now()
        period = HourlyForecastPeriod(start_time=start_time)

        assert period.start_time == start_time
        assert period.temperature is None
        assert period.temperature_unit == "F"
        assert period.short_forecast is None
        assert period.wind_speed is None
        assert period.wind_direction is None

    def test_hourly_forecast_period_has_data(self):
        """Test has_data method for hourly forecast period."""
        # Period with no data
        period_empty = HourlyForecastPeriod(start_time=datetime.now())
        assert period_empty.has_data() is False

        # Period with temperature only
        period_temp = HourlyForecastPeriod(start_time=datetime.now(), temperature=75.0)
        assert period_temp.has_data() is True

        # Period with forecast only
        period_forecast = HourlyForecastPeriod(start_time=datetime.now(), short_forecast="Sunny")
        assert period_forecast.has_data() is True


class TestHourlyForecast:
    """Test HourlyForecast model."""

    def test_hourly_forecast_creation(self):
        """Test creating an hourly forecast."""
        periods = [
            HourlyForecastPeriod(
                start_time=datetime.now(), temperature=75.0, short_forecast="Sunny"
            ),
            HourlyForecastPeriod(
                start_time=datetime.now() + timedelta(hours=1),
                temperature=73.0,
                short_forecast="Partly Cloudy",
            ),
        ]

        forecast = HourlyForecast(periods=periods)
        assert len(forecast.periods) == 2
        assert forecast.generated_at is None

    def test_hourly_forecast_with_generated_at(self):
        """Test hourly forecast with generation timestamp."""
        generated_at = datetime.now()
        forecast = HourlyForecast(periods=[], generated_at=generated_at)

        assert forecast.generated_at == generated_at
        assert len(forecast.periods) == 0

    def test_hourly_forecast_has_data(self):
        """Test has_data method for hourly forecast."""
        # Empty forecast
        forecast_empty = HourlyForecast(periods=[])
        assert forecast_empty.has_data() is False

        # Forecast with periods
        periods = [HourlyForecastPeriod(start_time=datetime.now(), temperature=75.0)]
        forecast_with_data = HourlyForecast(periods=periods)
        assert forecast_with_data.has_data() is True

    def test_hourly_forecast_get_next_hours_filters_past(self):
        """get_next_hours should skip past periods and return upcoming hours."""
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        periods = []

        # Create 4 periods in the past, 1 current, and 6 future
        for offset in range(-4, 6):
            periods.append(
                HourlyForecastPeriod(
                    start_time=now + timedelta(hours=offset),
                    temperature=70 + offset,
                    short_forecast=f"Hour {offset}",
                )
            )

        forecast = HourlyForecast(periods=periods)

        next_hours = forecast.get_next_hours()
        assert len(next_hours) == 6
        # First result should be the current hour (offset 0)
        assert next_hours[0].short_forecast == "Hour 0"
        # Last result should be offset 5
        assert next_hours[-1].short_forecast == "Hour 5"

    def test_hourly_forecast_get_next_hours_handles_naive_times(self):
        """Naive datetimes should be treated as UTC when filtering."""
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        periods = []
        for offset in range(-2, 4):
            periods.append(
                HourlyForecastPeriod(
                    start_time=now + timedelta(hours=offset),
                    short_forecast=f"Naive {offset}",
                )
            )

        forecast = HourlyForecast(periods=periods)
        next_hours = forecast.get_next_hours(3)
        assert [p.short_forecast for p in next_hours] == [
            "Naive 0",
            "Naive 1",
            "Naive 2",
        ]


class TestModelsPackageStructure:
    """Verify the models package exports and layout remain compatible."""

    def test_models_can_be_imported_from_package_modules(self):
        """Ensure models import paths remain available after refactor."""
        from accessiweather.models import Location as ReExportedLocation
        from accessiweather.models.alerts import WeatherAlert, WeatherAlerts
        from accessiweather.models.config import AppConfig, AppSettings
        from accessiweather.models.errors import ApiError
        from accessiweather.models.weather import CurrentConditions, Location, WeatherData

        assert Location is ReExportedLocation
        assert CurrentConditions is not None
        assert WeatherAlert is not None
        assert WeatherAlerts is not None
        assert AppSettings is not None
        assert AppConfig is not None
        assert ApiError is not None
        assert WeatherData is not None

    def test_backward_compatibility_imports(self):
        """Ensure legacy import paths still resolve after refactor."""
        from accessiweather.models import (
            ApiError,
            AppConfig,
            AppSettings,
            CurrentConditions,
            Location,
            WeatherAlert,
            WeatherAlerts,
            WeatherData,
        )

        location = Location("Test City", 1.0, 2.0)

        assert isinstance(location, Location)
        assert ApiError is not None
        assert AppConfig is not None
        assert AppSettings is not None
        assert CurrentConditions is not None
        assert WeatherAlert is not None
        assert WeatherAlerts is not None
        assert WeatherData is not None
