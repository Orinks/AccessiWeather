"""
Tests for data models.

Tests the core data models used throughout the application.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from accessiweather.models import (
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


class TestLocation:
    """Tests for Location model."""

    def test_create_location(self):
        """Test creating a location."""
        loc = Location(name="Test City", latitude=40.0, longitude=-74.0)
        assert loc.name == "Test City"
        assert loc.latitude == 40.0
        assert loc.longitude == -74.0

    def test_location_with_country_code(self):
        """Test location with country code."""
        loc = Location(name="New York", latitude=40.7128, longitude=-74.0060, country_code="US")
        assert loc.country_code == "US"

    def test_location_equality(self):
        """Test location equality."""
        loc1 = Location(name="Test", latitude=40.0, longitude=-74.0)
        loc2 = Location(name="Test", latitude=40.0, longitude=-74.0)
        loc3 = Location(name="Other", latitude=40.0, longitude=-74.0)

        assert loc1 == loc2
        assert loc1 != loc3


class TestCurrentConditions:
    """Tests for CurrentConditions model."""

    def test_create_current_conditions(self):
        """Test creating current conditions."""
        current = CurrentConditions(
            temperature_f=72.0,
            temperature_c=22.2,
            condition="Sunny",
        )
        assert current.temperature_f == 72.0
        assert current.condition == "Sunny"

    def test_has_data(self):
        """Test has_data method."""
        empty = CurrentConditions()
        assert empty.has_data() is False

        with_temp = CurrentConditions(temperature_f=72.0)
        assert with_temp.has_data() is True

        with_condition = CurrentConditions(condition="Sunny")
        assert with_condition.has_data() is True

    def test_all_fields(self):
        """Test all current condition fields."""
        current = CurrentConditions(
            temperature_f=72.0,
            temperature_c=22.2,
            condition="Partly Cloudy",
            humidity=65,
            dewpoint_f=58.0,
            dewpoint_c=14.4,
            wind_speed_mph=10.0,
            wind_speed_kph=16.1,
            wind_direction="NW",
            pressure_in=30.05,
            pressure_mb=1017.0,
            feels_like_f=74.0,
            feels_like_c=23.3,
            visibility_miles=10.0,
            visibility_km=16.1,
            uv_index=5,
        )
        assert current.humidity == 65
        assert current.wind_direction == "NW"
        assert current.uv_index == 5


class TestForecast:
    """Tests for Forecast model."""

    def test_create_forecast(self):
        """Test creating a forecast."""
        periods = [
            ForecastPeriod(
                name="Today",
                temperature=75,
                temperature_unit="F",
                short_forecast="Sunny",
            )
        ]
        forecast = Forecast(periods=periods)
        assert len(forecast.periods) == 1
        assert forecast.periods[0].name == "Today"

    def test_has_data(self):
        """Test has_data method."""
        empty = Forecast(periods=[])
        assert empty.has_data() is False

        with_periods = Forecast(periods=[ForecastPeriod(name="Today", temperature=75)])
        assert with_periods.has_data() is True

    def test_forecast_period_fields(self):
        """Test forecast period fields."""
        period = ForecastPeriod(
            name="Today",
            temperature=75,
            temperature_unit="F",
            short_forecast="Sunny",
            detailed_forecast="Sunny with highs near 75.",
            wind_speed="10 mph",
            wind_direction="NW",
            icon="sunny",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC) + timedelta(hours=12),
        )
        assert period.detailed_forecast is not None
        assert period.wind_speed == "10 mph"


class TestHourlyForecast:
    """Tests for HourlyForecast model."""

    def test_create_hourly_forecast(self):
        """Test creating an hourly forecast."""
        now = datetime.now(UTC)
        periods = [
            HourlyForecastPeriod(
                start_time=now + timedelta(hours=i),
                temperature=70 + i,
                temperature_unit="F",
            )
            for i in range(24)
        ]
        hourly = HourlyForecast(periods=periods)
        assert len(hourly.periods) == 24

    def test_has_data(self):
        """Test has_data method."""
        empty = HourlyForecast(periods=[])
        assert empty.has_data() is False

        with_periods = HourlyForecast(
            periods=[
                HourlyForecastPeriod(
                    start_time=datetime.now(UTC),
                    temperature=70,
                )
            ]
        )
        assert with_periods.has_data() is True


class TestWeatherAlert:
    """Tests for WeatherAlert model."""

    def test_create_alert(self):
        """Test creating an alert."""
        alert = WeatherAlert(
            title="Heat Advisory",
            description="High temperatures expected.",
            severity="Moderate",
            urgency="Expected",
            certainty="Likely",
            event="Heat Advisory",
        )
        assert alert.title == "Heat Advisory"
        assert alert.severity == "Moderate"

    def test_is_expired(self):
        """Test expiration checking."""
        # Expired alert
        expired = WeatherAlert(
            title="Test",
            description="Test",
            severity="Minor",
            urgency="Past",
            certainty="Observed",
            expires=datetime.now(UTC) - timedelta(hours=1),
        )
        assert expired.is_expired() is True

        # Active alert
        active = WeatherAlert(
            title="Test",
            description="Test",
            severity="Minor",
            urgency="Immediate",
            certainty="Observed",
            expires=datetime.now(UTC) + timedelta(hours=1),
        )
        assert active.is_expired() is False

        # No expiration
        no_expiry = WeatherAlert(
            title="Test",
            description="Test",
            severity="Minor",
            urgency="Immediate",
            certainty="Observed",
        )
        assert no_expiry.is_expired() is False

    def test_get_unique_id(self):
        """Test unique ID generation."""
        alert = WeatherAlert(
            id="NWS-123",
            title="Test",
            description="Test",
            severity="Minor",
            urgency="Immediate",
            certainty="Observed",
        )
        unique_id = alert.get_unique_id()
        assert unique_id is not None
        assert len(unique_id) > 0

    def test_get_severity_priority(self):
        """Test severity priority mapping."""
        extreme = WeatherAlert(
            title="T", description="T", severity="Extreme", urgency="I", certainty="O"
        )
        assert extreme.get_severity_priority() == 5

        severe = WeatherAlert(
            title="T", description="T", severity="Severe", urgency="I", certainty="O"
        )
        assert severe.get_severity_priority() == 4

        moderate = WeatherAlert(
            title="T", description="T", severity="Moderate", urgency="I", certainty="O"
        )
        assert moderate.get_severity_priority() == 3

        minor = WeatherAlert(
            title="T", description="T", severity="Minor", urgency="I", certainty="O"
        )
        assert minor.get_severity_priority() == 2


class TestWeatherAlerts:
    """Tests for WeatherAlerts collection."""

    def test_has_alerts(self):
        """Test has_alerts method."""
        empty = WeatherAlerts(alerts=[])
        assert empty.has_alerts() is False

        with_alerts = WeatherAlerts(
            alerts=[
                WeatherAlert(
                    title="T", description="T", severity="Minor", urgency="I", certainty="O"
                )
            ]
        )
        assert with_alerts.has_alerts() is True

    def test_get_active_alerts(self):
        """Test filtering active alerts."""
        expired = WeatherAlert(
            title="Expired",
            description="T",
            severity="Minor",
            urgency="Past",
            certainty="O",
            expires=datetime.now(UTC) - timedelta(hours=1),
        )
        active = WeatherAlert(
            title="Active",
            description="T",
            severity="Minor",
            urgency="Immediate",
            certainty="O",
            expires=datetime.now(UTC) + timedelta(hours=1),
        )

        alerts = WeatherAlerts(alerts=[expired, active])
        active_alerts = alerts.get_active_alerts()

        assert len(active_alerts) == 1
        assert active_alerts[0].title == "Active"


class TestWeatherData:
    """Tests for WeatherData model."""

    def test_create_weather_data(self):
        """Test creating weather data."""
        loc = Location(name="Test", latitude=40.0, longitude=-74.0)
        data = WeatherData(location=loc)
        assert data.location.name == "Test"

    def test_has_any_data(self):
        """Test has_any_data method."""
        loc = Location(name="Test", latitude=40.0, longitude=-74.0)

        empty = WeatherData(location=loc)
        assert empty.has_any_data() is False

        with_current = WeatherData(
            location=loc,
            current=CurrentConditions(temperature_f=72.0),
        )
        assert with_current.has_any_data() is True

        with_forecast = WeatherData(
            location=loc,
            forecast=Forecast(periods=[ForecastPeriod(name="Today", temperature=75)]),
        )
        assert with_forecast.has_any_data() is True


class TestAppSettings:
    """Tests for AppSettings model."""

    def test_default_settings(self):
        """Test default settings."""
        settings = AppSettings()
        assert settings.update_interval_minutes == 10
        assert settings.enable_alerts is True

    def test_custom_settings(self):
        """Test custom settings."""
        settings = AppSettings(
            update_interval_minutes=30,
            enable_alerts=False,
            data_source="openmeteo",
        )
        assert settings.update_interval_minutes == 30
        assert settings.enable_alerts is False
        assert settings.data_source == "openmeteo"


class TestAppConfig:
    """Tests for AppConfig model."""

    def test_default_config(self):
        """Test default config."""
        config = AppConfig.default()
        assert config.settings is not None
        assert config.locations == []

    def test_serialization_roundtrip(self):
        """Test to_dict and from_dict."""
        config = AppConfig.default()
        test_location = Location(name="Test", latitude=40.0, longitude=-74.0)
        config.locations = [test_location]
        config.current_location = test_location

        data = config.to_dict()
        restored = AppConfig.from_dict(data)

        assert restored.current_location is not None
        assert restored.current_location.name == "Test"
        assert len(restored.locations) == 1
        assert restored.locations[0].name == "Test"
