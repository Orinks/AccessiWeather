"""Tests for weather data formatter functions in ai_tools."""

from __future__ import annotations

from accessiweather.ai_tools import format_alerts, format_current_weather, format_forecast


class TestFormatCurrentWeather:
    """Tests for format_current_weather."""

    def test_all_fields(self):
        data = {
            "temperature": "72°F",
            "feels_like": "75°F",
            "description": "Partly Cloudy",
            "humidity": "55%",
            "wind": "5 mph NW",
            "pressure": "30.12 inHg",
        }
        result = format_current_weather(data, "New York, NY")
        assert "Current weather for New York, NY:" in result
        assert "Temperature: 72°F" in result
        assert "Feels Like: 75°F" in result
        assert "Conditions: Partly Cloudy" in result
        assert "Humidity: 55%" in result
        assert "Wind: 5 mph NW" in result
        assert "Pressure: 30.12 inHg" in result

    def test_text_description_field(self):
        data = {"textDescription": "Sunny"}
        result = format_current_weather(data, "Boston")
        assert "Conditions: Sunny" in result

    def test_feels_like_camel_case(self):
        data = {"feelsLike": "80°F"}
        result = format_current_weather(data, "Miami")
        assert "Feels Like: 80°F" in result

    def test_wind_speed_field(self):
        data = {"windSpeed": "10 mph"}
        result = format_current_weather(data, "Chicago")
        assert "Wind: 10 mph" in result

    def test_barometric_pressure_field(self):
        data = {"barometricPressure": "1013 hPa"}
        result = format_current_weather(data, "Denver")
        assert "Pressure: 1013 hPa" in result

    def test_missing_fields_graceful(self):
        data = {}
        result = format_current_weather(data, "Nowhere")
        assert "Current weather for Nowhere:" in result

    def test_none_values_skipped(self):
        data = {"temperature": None, "humidity": None, "wind": "5 mph"}
        result = format_current_weather(data, "Test")
        assert "Temperature" not in result
        assert "Humidity" not in result
        assert "Wind: 5 mph" in result

    def test_fallback_scalar_dump(self):
        data = {"status": "ok", "code": 200}
        result = format_current_weather(data, "Test")
        assert "status: ok" in result
        assert "code: 200" in result

    def test_no_display_name(self):
        data = {"temperature": "70°F"}
        result = format_current_weather(data)
        assert result.startswith("Current weather:")

    def test_empty_string_values_skipped(self):
        data = {"temperature": "", "humidity": "50%"}
        result = format_current_weather(data, "Test")
        assert "Temperature" not in result
        assert "Humidity: 50%" in result


class TestFormatForecast:
    """Tests for format_forecast."""

    def test_basic_periods(self):
        data = {
            "periods": [
                {
                    "name": "Tonight",
                    "temperature": 60,
                    "temperatureUnit": "F",
                    "shortForecast": "Clear",
                },
                {
                    "name": "Tomorrow",
                    "temperature": 85,
                    "temperatureUnit": "F",
                    "shortForecast": "Sunny",
                },
            ]
        }
        result = format_forecast(data, "New York, NY")
        assert "Forecast for New York, NY:" in result
        assert "Tonight - 60°F - Clear" in result
        assert "Tomorrow - 85°F - Sunny" in result

    def test_up_to_seven_periods(self):
        data = {
            "periods": [
                {
                    "name": f"Period {i}",
                    "temperature": 70 + i,
                    "temperatureUnit": "F",
                    "shortForecast": "Fair",
                }
                for i in range(10)
            ]
        }
        result = format_forecast(data, "Test")
        assert "Period 6" in result
        assert "Period 7" not in result  # 0-indexed, so Period 7 would be the 8th

    def test_nested_properties_periods(self):
        data = {
            "properties": {
                "periods": [
                    {
                        "name": "Today",
                        "temperature": 80,
                        "temperatureUnit": "F",
                        "shortForecast": "Sunny",
                    }
                ]
            }
        }
        result = format_forecast(data, "Test")
        assert "Today" in result

    def test_detailed_forecast_fallback(self):
        data = {
            "periods": [
                {
                    "name": "Tonight",
                    "temperature": 60,
                    "temperatureUnit": "F",
                    "detailedForecast": "Clear skies with a low of 60.",
                }
            ]
        }
        result = format_forecast(data, "Test")
        assert "Clear skies" in result

    def test_missing_temperature(self):
        data = {"periods": [{"name": "Tonight", "shortForecast": "Cloudy"}]}
        result = format_forecast(data, "Test")
        assert "Tonight - Cloudy" in result

    def test_missing_forecast_text(self):
        data = {"periods": [{"name": "Tonight", "temperature": 55, "temperatureUnit": "F"}]}
        result = format_forecast(data, "Test")
        assert "Tonight - 55°F" in result

    def test_empty_periods(self):
        data = {"periods": []}
        result = format_forecast(data, "Test")
        # Falls back to JSON dump
        assert "Forecast for Test:" in result

    def test_no_periods_key(self):
        data = {"something": "else"}
        result = format_forecast(data, "Test")
        assert "Forecast for Test:" in result

    def test_none_name_defaults(self):
        data = {"periods": [{"name": None, "temperature": 70, "temperatureUnit": "F"}]}
        result = format_forecast(data, "Test")
        assert "Unknown" in result

    def test_no_display_name(self):
        data = {"periods": [{"name": "Today", "shortForecast": "Nice"}]}
        result = format_forecast(data)
        assert result.startswith("Forecast:")


class TestFormatAlerts:
    """Tests for format_alerts."""

    def test_alert_with_all_fields(self):
        data = {
            "alerts": [
                {
                    "properties": {
                        "event": "Heat Advisory",
                        "severity": "Moderate",
                        "headline": "Heat advisory until 8 PM",
                        "description": "Dangerously hot conditions expected.",
                    }
                }
            ]
        }
        result = format_alerts(data, "Phoenix")
        assert "Weather alerts for Phoenix:" in result
        assert "- Heat Advisory (Severity: Moderate)" in result
        assert "Heat advisory until 8 PM" in result
        assert "Dangerously hot conditions" in result

    def test_no_active_alerts(self):
        data = {"alerts": []}
        result = format_alerts(data, "Test")
        assert "No active alerts." in result

    def test_no_alerts_key(self):
        data = {}
        result = format_alerts(data, "Test")
        assert "No active alerts." in result

    def test_geojson_features_format(self):
        data = {
            "features": [
                {
                    "properties": {
                        "event": "Tornado Warning",
                        "severity": "Extreme",
                        "headline": "Tornado warning for the area",
                    }
                }
            ]
        }
        result = format_alerts(data, "Oklahoma City")
        assert "Tornado Warning" in result
        assert "Severity: Extreme" in result

    def test_alert_missing_severity(self):
        data = {
            "alerts": [{"properties": {"event": "Flood Watch", "headline": "Flooding possible"}}]
        }
        result = format_alerts(data, "Test")
        assert "- Flood Watch" in result
        assert "Severity" not in result

    def test_alert_missing_headline(self):
        data = {
            "alerts": [
                {"properties": {"event": "Wind Advisory", "description": "Strong winds expected."}}
            ]
        }
        result = format_alerts(data, "Test")
        assert "Wind Advisory" in result
        assert "Strong winds expected." in result

    def test_alert_flat_dict_format(self):
        """Test alerts that are flat dicts (no nested properties)."""
        data = {
            "alerts": [
                {"event": "Frost Advisory", "severity": "Minor", "headline": "Frost tonight"}
            ]
        }
        result = format_alerts(data, "Test")
        assert "Frost Advisory" in result
        assert "Severity: Minor" in result

    def test_description_truncated(self):
        data = {"alerts": [{"properties": {"event": "Test", "description": "x" * 500}}]}
        result = format_alerts(data, "Test")
        # Description should be truncated to 300 chars
        desc_line = [line for line in result.split("\n") if line.startswith("  x")][0]
        assert len(desc_line.strip()) == 300

    def test_none_fields_graceful(self):
        data = {"alerts": [{"properties": {"event": None, "severity": None, "headline": None}}]}
        result = format_alerts(data, "Test")
        assert "Unknown Alert" in result

    def test_no_display_name(self):
        data = {"alerts": []}
        result = format_alerts(data)
        assert result.startswith("Weather alerts:")

    def test_multiple_alerts(self):
        data = {
            "alerts": [
                {"properties": {"event": "Heat Advisory", "headline": "Hot"}},
                {"properties": {"event": "Air Quality Alert", "headline": "Poor air"}},
            ]
        }
        result = format_alerts(data, "LA")
        assert "Heat Advisory" in result
        assert "Air Quality Alert" in result
