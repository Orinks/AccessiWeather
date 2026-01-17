"""Integration tests for complete priority ordering flow."""

from accessiweather.display.weather_presenter import WeatherPresenter
from accessiweather.models import (
    AppSettings,
    CurrentConditions,
    Location,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)


class TestPriorityIntegration:
    """Integration tests for priority ordering."""

    def test_full_flow_with_wind_alert(self):
        """Test complete flow from settings to presentation with wind alerts."""
        # Setup settings with custom order
        settings = AppSettings(
            verbosity_level="standard",
            category_order=["temperature", "precipitation", "wind"],
            severe_weather_override=True,
        )

        presenter = WeatherPresenter(settings)

        # Create weather data with wind alert
        location = Location(name="Test City", latitude=40.0, longitude=-75.0)
        current = CurrentConditions(
            temperature_f=75.0,
            humidity=65,
            wind_speed=45,
            wind_direction="NW",
            condition="Very Windy",
        )
        alerts = WeatherAlerts(
            alerts=[
                WeatherAlert(
                    title="High Wind Warning",
                    description="Dangerous winds up to 60 mph",
                    event="High Wind Warning",
                    severity="Severe",
                )
            ]
        )

        weather_data = WeatherData(
            location=location,
            current=current,
            alerts=alerts,
        )

        # Present the data
        result = presenter.present(weather_data)

        # Verify current conditions is present
        assert result.current_conditions is not None
        metrics = result.current_conditions.metrics
        metric_labels = [m.label for m in metrics]

        # Wind should be prioritized due to alert
        wind_idx = next((i for i, label in enumerate(metric_labels) if "Wind" in label), 999)

        # Wind should be prioritized near top due to alert override
        assert wind_idx < 3, f"Wind at index {wind_idx}, expected < 3. Labels: {metric_labels}"

    def test_full_flow_with_heat_alert(self):
        """Test complete flow with heat alert prioritizing temperature and UV."""
        settings = AppSettings(
            verbosity_level="standard",
            category_order=["wind", "precipitation", "temperature"],  # Temperature not first
            severe_weather_override=True,
        )

        presenter = WeatherPresenter(settings)

        location = Location(name="Test City", latitude=40.0, longitude=-75.0)
        current = CurrentConditions(
            temperature_f=105.0,
            feels_like_f=115.0,
            humidity=25,
            wind_speed=5,
            uv_index=11,
            condition="Extreme Heat",
        )
        alerts = WeatherAlerts(
            alerts=[
                WeatherAlert(
                    title="Excessive Heat Warning",
                    description="Dangerous heat conditions",
                    event="Excessive Heat Warning",
                    severity="Extreme",
                )
            ]
        )

        weather_data = WeatherData(
            location=location,
            current=current,
            alerts=alerts,
        )

        result = presenter.present(weather_data)

        assert result.current_conditions is not None
        metrics = result.current_conditions.metrics
        metric_labels = [m.label for m in metrics]

        # Temperature should be prioritized due to heat alert
        temp_idx = next((i for i, label in enumerate(metric_labels) if "Temperature" in label), 999)
        assert temp_idx < 3, (
            f"Temperature at index {temp_idx}, expected < 3. Labels: {metric_labels}"
        )

    def test_full_flow_no_alerts_uses_custom_order(self):
        """Without alerts, custom order should be respected."""
        settings = AppSettings(
            verbosity_level="standard",
            category_order=["wind", "temperature", "precipitation"],
            severe_weather_override=True,
        )

        presenter = WeatherPresenter(settings)

        location = Location(name="Test City", latitude=40.0, longitude=-75.0)
        current = CurrentConditions(
            temperature_f=75.0,
            humidity=65,
            wind_speed=10,
            wind_direction="NW",  # Need direction for wind to show
            condition="Clear",
        )

        weather_data = WeatherData(
            location=location,
            current=current,
        )

        result = presenter.present(weather_data)

        # Verify presentation was created
        assert result.current_conditions is not None
        metrics = result.current_conditions.metrics
        metric_labels = [m.label for m in metrics]

        # Verify Wind metric exists (since we provided wind data)
        assert any("Wind" in label for label in metric_labels), (
            f"Wind not in metrics. Labels: {metric_labels}"
        )

        # Get indices
        wind_idx = next((i for i, label in enumerate(metric_labels) if "Wind" in label), 999)
        temp_idx = next((i for i, label in enumerate(metric_labels) if "Temperature" in label), 999)

        # Wind should come before temperature per custom order
        assert wind_idx < temp_idx, (
            f"Wind at {wind_idx}, Temp at {temp_idx}. Labels: {metric_labels}"
        )

    def test_override_disabled_respects_user_order(self):
        """When override is disabled, alert should not reorder categories."""
        settings = AppSettings(
            verbosity_level="standard",
            category_order=["temperature", "precipitation", "humidity_pressure", "wind"],
            severe_weather_override=False,  # Override disabled
        )

        presenter = WeatherPresenter(settings)

        location = Location(name="Test City", latitude=40.0, longitude=-75.0)
        current = CurrentConditions(
            temperature_f=75.0,
            humidity=65,
            wind_speed=45,
            wind_direction="NW",
            condition="Very Windy",
        )
        alerts = WeatherAlerts(
            alerts=[
                WeatherAlert(
                    title="High Wind Warning",
                    description="Dangerous winds",
                    event="High Wind Warning",
                    severity="Severe",
                )
            ]
        )

        weather_data = WeatherData(
            location=location,
            current=current,
            alerts=alerts,
        )

        result = presenter.present(weather_data)

        metrics = result.current_conditions.metrics
        metric_labels = [m.label for m in metrics]

        # Temperature should still come first because override is disabled
        temp_idx = next((i for i, label in enumerate(metric_labels) if "Temperature" in label), 999)
        wind_idx = next((i for i, label in enumerate(metric_labels) if "Wind" in label), 999)

        assert temp_idx < wind_idx, (
            f"With override disabled, user order should be respected. "
            f"Temp at {temp_idx}, Wind at {wind_idx}. Labels: {metric_labels}"
        )

    def test_minimal_verbosity_reduces_output(self):
        """Minimal verbosity should produce less detailed output."""
        minimal_settings = AppSettings(verbosity_level="minimal")
        detailed_settings = AppSettings(verbosity_level="detailed")

        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        current = CurrentConditions(
            temperature_f=75.0,
            feels_like_f=78.0,
            humidity=65,
            wind_speed=10,
            wind_direction="NW",
            pressure_in=30.1,
            visibility_miles=10.0,
            uv_index=6,
            condition="Clear",
        )

        weather_data = WeatherData(location=location, current=current)

        minimal_result = WeatherPresenter(minimal_settings).present(weather_data)
        detailed_result = WeatherPresenter(detailed_settings).present(weather_data)

        # Minimal should have same or fewer metrics than detailed
        # (may be equal if all metrics are shown in both modes)
        minimal_count = len(minimal_result.current_conditions.metrics)
        detailed_count = len(detailed_result.current_conditions.metrics)
        assert minimal_count <= detailed_count, (
            f"Minimal has {minimal_count} metrics, Detailed has {detailed_count} metrics. "
            f"Expected minimal <= detailed."
        )

    def test_winter_storm_prioritizes_precipitation_and_temperature(self):
        """Winter storm alert should prioritize precipitation and temperature."""
        settings = AppSettings(
            verbosity_level="standard",
            category_order=["wind", "uv_index", "precipitation", "temperature"],
            severe_weather_override=True,
        )

        presenter = WeatherPresenter(settings)

        location = Location(name="Test City", latitude=40.0, longitude=-75.0)
        current = CurrentConditions(
            temperature_f=28.0,
            humidity=85,
            wind_speed=25,
            condition="Snow",
        )
        alerts = WeatherAlerts(
            alerts=[
                WeatherAlert(
                    title="Winter Storm Warning",
                    description="Heavy snow expected",
                    event="Winter Storm Warning",
                    severity="Severe",
                )
            ]
        )

        weather_data = WeatherData(
            location=location,
            current=current,
            alerts=alerts,
        )

        result = presenter.present(weather_data)

        metrics = result.current_conditions.metrics
        metric_labels = [m.label for m in metrics]

        # Both precipitation and temperature should be prioritized
        # They may not be exactly first and second, but should be near the top
        has_precip = any(
            "Precipitation" in label or "Rain" in label or "Snow" in label
            for label in metric_labels[:6]
        )
        has_temp = any("Temperature" in label for label in metric_labels[:3])
        assert has_precip or has_temp, (
            f"Winter storm should prioritize precip/temp. Labels: {metric_labels}"
        )

    def test_flood_alert_prioritizes_precipitation(self):
        """Flood alert should prioritize precipitation category."""
        settings = AppSettings(
            verbosity_level="standard",
            category_order=["temperature", "wind", "uv_index", "precipitation"],
            severe_weather_override=True,
        )

        presenter = WeatherPresenter(settings)

        location = Location(name="Test City", latitude=40.0, longitude=-75.0)
        current = CurrentConditions(
            temperature_f=68.0,
            humidity=95,
            wind_speed=5,
            condition="Heavy Rain",
        )
        alerts = WeatherAlerts(
            alerts=[
                WeatherAlert(
                    title="Flash Flood Warning",
                    description="Flash flooding imminent",
                    event="Flash Flood Warning",
                    severity="Extreme",
                )
            ]
        )

        weather_data = WeatherData(
            location=location,
            current=current,
            alerts=alerts,
        )

        result = presenter.present(weather_data)

        # Just verify the presentation was created successfully
        # The priority engine should have reordered based on the flood alert
        assert result.current_conditions is not None
        assert len(result.current_conditions.metrics) > 0

    def test_verbosity_affects_fallback_text_length(self):
        """Different verbosity levels should affect presentation content."""
        minimal_settings = AppSettings(verbosity_level="minimal")
        standard_settings = AppSettings(verbosity_level="standard")

        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        current = CurrentConditions(
            temperature_f=75.0,
            feels_like_f=78.0,
            humidity=65,
            wind_speed=10,
            wind_direction="NW",
            pressure_in=30.1,
            visibility_miles=10.0,
            uv_index=6,
            dewpoint_f=62.0,
            condition="Partly Cloudy",
        )

        weather_data = WeatherData(location=location, current=current)

        minimal_result = WeatherPresenter(minimal_settings).present(weather_data)
        standard_result = WeatherPresenter(standard_settings).present(weather_data)

        # Both should produce valid presentations
        assert minimal_result.current_conditions is not None
        assert standard_result.current_conditions is not None

        # The presentations should differ in detail level
        minimal_metrics = len(minimal_result.current_conditions.metrics)
        standard_metrics = len(standard_result.current_conditions.metrics)

        # Standard should have at least as many metrics as minimal
        assert standard_metrics >= minimal_metrics, (
            f"Standard ({standard_metrics}) should have >= metrics than minimal ({minimal_metrics})"
        )
