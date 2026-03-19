"""
Coverage gap tests for Pirate Weather integration.

Covers lines missed in:
- pirate_weather_client.py
- weather_client_base.py
- weather_client_parallel.py
- config/settings.py
- models/config.py
- display/presentation/forecast.py (summary feature)
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.models import AppConfig, Location, WeatherAlerts
from accessiweather.pirate_weather_client import (
    PirateWeatherApiError,
    PirateWeatherClient,
)
from accessiweather.weather_client import WeatherClient
from accessiweather.weather_client_parallel import ParallelFetchCoordinator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return PirateWeatherClient(api_key="test-key", units="us")


@pytest.fixture
def ca_client():
    return PirateWeatherClient(api_key="test-key", units="ca")


@pytest.fixture
def si_client():
    return PirateWeatherClient(api_key="test-key", units="si")


@pytest.fixture
def uk2_client():
    return PirateWeatherClient(api_key="test-key", units="uk2")


@pytest.fixture
def location():
    return Location(name="Test City", latitude=40.0, longitude=-75.0)


@pytest.fixture
def intl_location():
    return Location(name="London", latitude=51.5, longitude=-0.12, country_code="GB")


# ---------------------------------------------------------------------------
# pirate_weather_client.py – HTTP layer
# ---------------------------------------------------------------------------


class TestPirateWeatherHttpErrors:
    @pytest.mark.asyncio
    async def test_http_400_raises_bad_request(self, client, location):
        """Line 119: HTTP 400 raises PirateWeatherApiError."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_http
            mock_http.get.return_value = mock_resp

            with pytest.raises(PirateWeatherApiError) as exc_info:
                await client.get_forecast_data(location)

        assert exc_info.value.status_code == 400
        assert "Bad request" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_unexpected_exception_raises_error(self, client, location):
        """Lines 143-145: Non-httpx exception is wrapped."""
        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_cls.return_value.__aenter__.return_value = mock_http
            mock_http.get.side_effect = ValueError("json parse failed")

            with pytest.raises(PirateWeatherApiError) as exc_info:
                await client.get_forecast_data(location)

        assert "Unexpected error" in str(exc_info.value)


# ---------------------------------------------------------------------------
# pirate_weather_client.py – None return paths
# ---------------------------------------------------------------------------


class TestNoneDataPaths:
    @pytest.mark.asyncio
    async def test_get_current_conditions_none_when_data_none(self, client, location):
        """Line 151: returns None when get_forecast_data returns None."""
        with patch.object(client, "get_forecast_data", return_value=None):
            result = await client.get_current_conditions(location)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_forecast_none_when_data_none(self, client, location):
        """Line 158: returns None when get_forecast_data returns None."""
        with patch.object(client, "get_forecast_data", return_value=None):
            result = await client.get_forecast(location)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_hourly_forecast_none_when_data_none(self, client, location):
        """Line 165: returns None when get_forecast_data returns None."""
        with patch.object(client, "get_forecast_data", return_value=None):
            result = await client.get_hourly_forecast(location)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_alerts_empty_when_data_none(self, client, location):
        """Line 173: returns empty WeatherAlerts when get_forecast_data returns None."""
        with patch.object(client, "get_forecast_data", return_value=None):
            result = await client.get_alerts(location)
        assert result.alerts == []


# ---------------------------------------------------------------------------
# pirate_weather_client.py – _parse_current_conditions edge cases
# ---------------------------------------------------------------------------


class TestParseCurrentConditionsEdgeCases:
    def test_dewpoint_calculated_from_temp_humidity(self, client):
        """Lines 208-209: dewpoint derived from temp+humidity when not in payload."""
        data = {
            "currently": {
                "temperature": 72.0,
                "humidity": 0.70,
                # intentionally no "dewPoint"
            },
            "offset": 0,
            "daily": {"data": []},
        }
        result = client._parse_current_conditions(data)
        assert result.dewpoint_f is not None
        assert result.dewpoint_c is not None

    def test_ca_units_wind_speed(self, ca_client):
        """Lines 220-221: ca units converts km/h → mph."""
        data = {
            "currently": {"temperature": 20.0, "windSpeed": 36.0},
            "offset": 0,
            "daily": {"data": []},
        }
        result = ca_client._parse_current_conditions(data)
        assert result.wind_speed_kph == 36.0
        assert result.wind_speed_mph is not None
        assert abs(result.wind_speed_mph - 36.0 / 1.60934) < 0.1

    def test_ca_units_wind_gust(self, ca_client):
        """Lines 257-258: ca units wind gust km/h → mph."""
        data = {
            "currently": {"temperature": 20.0, "windGust": 50.0},
            "offset": 0,
            "daily": {"data": []},
        }
        result = ca_client._parse_current_conditions(data)
        assert result.wind_gust_kph == 50.0
        assert result.wind_gust_mph is not None

    def test_si_units_visibility_km(self, si_client):
        """Non-us path for visibility: km → miles (lines 239-240)."""
        data = {
            "currently": {"temperature": 20.0, "visibility": 15.0},
            "offset": 0,
            "daily": {"data": []},
        }
        result = si_client._parse_current_conditions(data)
        assert result.visibility_km == 15.0
        assert result.visibility_miles is not None


# ---------------------------------------------------------------------------
# pirate_weather_client.py – _parse_forecast edge cases
# ---------------------------------------------------------------------------


class TestParseForecastEdgeCases:
    def test_no_time_val_gets_day_n_name(self, client):
        """Line 340: daily entry without 'time' gets 'Day N' name."""
        data = {
            "daily": {"data": [{"temperatureHigh": 75.0}]},  # no "time"
            "offset": 0,
        }
        result = client._parse_forecast(data)
        assert result.periods[0].name == "Day 1"

    def test_ca_units_wind_string_kmh(self, ca_client):
        """Line 351: ca units produce 'km/h' wind string."""
        data = {
            "daily": {"data": [{"time": 1700000000, "windSpeed": 25.0}]},
            "offset": 0,
        }
        result = ca_client._parse_forecast(data)
        assert result.periods[0].wind_speed is not None
        assert "km/h" in result.periods[0].wind_speed

    def test_null_wind_speed_gives_none(self, client):
        """Line 355: missing windSpeed produces None wind_str."""
        data = {
            "daily": {"data": [{"time": 1700000000}]},
            "offset": 0,
        }
        result = client._parse_forecast(data)
        assert result.periods[0].wind_speed is None

    def test_ca_units_wind_gust_kmh(self, ca_client):
        """Line 362: ca units produce 'km/h' wind gust string."""
        data = {
            "daily": {"data": [{"time": 1700000000, "windGust": 35.0}]},
            "offset": 0,
        }
        result = ca_client._parse_forecast(data)
        assert result.periods[0].wind_gust is not None
        assert "km/h" in result.periods[0].wind_gust

    def test_si_units_wind_gust_ms(self):
        """Line 364: si units produce 'm/s' wind gust string."""
        si_client = PirateWeatherClient(api_key="key", units="si")
        data = {
            "daily": {"data": [{"time": 1700000000, "windGust": 8.0}]},
            "offset": 0,
        }
        result = si_client._parse_forecast(data)
        assert result.periods[0].wind_gust is not None
        assert "m/s" in result.periods[0].wind_gust

    def test_null_wind_gust_gives_none(self, client):
        """Line 366: missing windGust produces None."""
        data = {
            "daily": {"data": [{"time": 1700000000}]},
            "offset": 0,
        }
        result = client._parse_forecast(data)
        assert result.periods[0].wind_gust is None

    def test_null_precip_intensity_gives_none(self, client):
        """Line 375: missing precipIntensity produces None."""
        data = {
            "daily": {"data": [{"time": 1700000000}]},
            "offset": 0,
        }
        result = client._parse_forecast(data)
        assert result.periods[0].precipitation_amount is None


# ---------------------------------------------------------------------------
# pirate_weather_client.py – _parse_hourly_forecast edge cases
# ---------------------------------------------------------------------------


class TestParseHourlyForecastEdgeCases:
    def test_no_time_val_uses_now(self, client):
        """Line 419: hourly entry without 'time' uses datetime.now()."""
        data = {
            "hourly": {"data": [{"temperature": 68.0}]},  # no "time"
            "offset": 0,
        }
        result = client._parse_hourly_forecast(data)
        assert result.periods[0].start_time is not None

    def test_si_units_temp_converted_to_f(self, si_client):
        """Lines 425-426: si units convert °C → °F for temperature."""
        data = {
            "hourly": {"data": [{"time": 1700000000, "temperature": 20.0}]},
            "offset": 0,
        }
        result = si_client._parse_hourly_forecast(data)
        assert result.periods[0].temperature is not None
        assert abs(result.periods[0].temperature - (20.0 * 9 / 5 + 32)) < 0.1

    def test_ca_units_wind_string_kmh(self, ca_client):
        """Lines 436-437: ca units wind string uses km/h."""
        data = {
            "hourly": {"data": [{"time": 1700000000, "windSpeed": 25.0}]},
            "offset": 0,
        }
        result = ca_client._parse_hourly_forecast(data)
        assert "km/h" in result.periods[0].wind_speed

    def test_si_units_wind_string_ms(self, si_client):
        """Line 439: si units wind string uses m/s."""
        data = {
            "hourly": {"data": [{"time": 1700000000, "windSpeed": 8.0}]},
            "offset": 0,
        }
        result = si_client._parse_hourly_forecast(data)
        assert "m/s" in result.periods[0].wind_speed

    def test_null_wind_speed_gives_none(self, client):
        """Line 441: missing windSpeed gives None."""
        data = {
            "hourly": {"data": [{"time": 1700000000}]},
            "offset": 0,
        }
        result = client._parse_hourly_forecast(data)
        assert result.periods[0].wind_speed is None

    def test_ca_units_wind_gust_converts(self, ca_client):
        """Lines 448-449: ca units wind gust km/h → mph."""
        data = {
            "hourly": {"data": [{"time": 1700000000, "windGust": 40.0}]},
            "offset": 0,
        }
        result = ca_client._parse_hourly_forecast(data)
        assert result.periods[0].wind_gust_mph is not None
        assert abs(result.periods[0].wind_gust_mph - 40.0 / 1.60934) < 0.1

    def test_si_units_wind_gust_converts(self, si_client):
        """Line 451: si units wind gust m/s → mph."""
        data = {
            "hourly": {"data": [{"time": 1700000000, "windGust": 5.0}]},
            "offset": 0,
        }
        result = si_client._parse_hourly_forecast(data)
        assert result.periods[0].wind_gust_mph is not None
        assert abs(result.periods[0].wind_gust_mph - 5.0 * 2.23694) < 0.1

    def test_null_precip_intensity_gives_none(self, client):
        """Line 460: missing precipIntensity gives None."""
        data = {
            "hourly": {"data": [{"time": 1700000000}]},
            "offset": 0,
        }
        result = client._parse_hourly_forecast(data)
        assert result.periods[0].precipitation_amount is None

    def test_si_units_visibility_km_to_miles(self, si_client):
        """Lines 473-474: non-us visibility in km → miles."""
        data = {
            "hourly": {"data": [{"time": 1700000000, "visibility": 15.0}]},
            "offset": 0,
        }
        result = si_client._parse_hourly_forecast(data)
        assert result.periods[0].visibility_km == 15.0
        assert result.periods[0].visibility_miles is not None

    def test_null_visibility_gives_none(self, client):
        """Lines 476-477: missing visibility gives None for both fields."""
        data = {
            "hourly": {"data": [{"time": 1700000000}]},
            "offset": 0,
        }
        result = client._parse_hourly_forecast(data)
        assert result.periods[0].visibility_miles is None
        assert result.periods[0].visibility_km is None

    def test_si_units_feels_like_converted(self, si_client):
        """Lines 483-484: non-us apparentTemperature °C → °F."""
        data = {
            "hourly": {"data": [{"time": 1700000000, "apparentTemperature": 18.0}]},
            "offset": 0,
        }
        result = si_client._parse_hourly_forecast(data)
        assert result.periods[0].feels_like is not None
        assert abs(result.periods[0].feels_like - (18.0 * 9 / 5 + 32)) < 0.1


# ---------------------------------------------------------------------------
# weather_client_parallel.py – pirateweather task
# ---------------------------------------------------------------------------


class TestParallelFetchPirateWeather:
    @pytest.mark.asyncio
    async def test_fetch_pirateweather_source(self, location):
        """Lines 120, 123: pirateweather task is created and appended."""
        coordinator = ParallelFetchCoordinator(timeout=2.0)
        mock_current = MagicMock()
        mock_forecast = MagicMock()
        mock_hourly = MagicMock()
        mock_alerts = MagicMock()

        async def fake_pw():
            return (mock_current, mock_forecast, mock_hourly, mock_alerts)

        results = await coordinator.fetch_all(location, fetch_pirateweather=fake_pw())
        assert len(results) == 1
        assert results[0].source == "pirateweather"
        assert results[0].success is True
        assert results[0].current is mock_current
        assert results[0].forecast is mock_forecast
        assert results[0].hourly_forecast is mock_hourly
        assert results[0].alerts is mock_alerts

    @pytest.mark.asyncio
    async def test_all_four_sources_including_pirateweather(self, location):
        """All four sources fetched including pirateweather."""
        coordinator = ParallelFetchCoordinator(timeout=2.0)
        mock_data = MagicMock()

        async def fake_nws():
            return (mock_data, mock_data, mock_data, None)

        async def fake_om():
            return (mock_data, mock_data, mock_data)

        async def fake_vc():
            return (mock_data, mock_data, mock_data, None)

        async def fake_pw():
            return (mock_data, mock_data, mock_data, None)

        results = await coordinator.fetch_all(
            location,
            fetch_nws=fake_nws(),
            fetch_openmeteo=fake_om(),
            fetch_visualcrossing=fake_vc(),
            fetch_pirateweather=fake_pw(),
        )
        assert len(results) == 4
        sources = {r.source for r in results}
        assert sources == {"nws", "openmeteo", "visualcrossing", "pirateweather"}
        assert all(r.success for r in results)


# ---------------------------------------------------------------------------
# config/settings.py – pirateweather validation
# ---------------------------------------------------------------------------


class TestSettingsPirateWeatherValidation:
    @pytest.fixture
    def mock_manager(self, tmp_path):
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        manager.save_config.return_value = True

        config = AppConfig.default()
        config.settings.data_source = "pirateweather"
        config.settings.pirate_weather_api_key = ""  # no key
        manager._config = config
        manager.get_config.return_value = config

        return manager

    def test_pirateweather_without_api_key_falls_back_to_auto(self, mock_manager):
        """Lines 60, 63-64: pirateweather selected but no key → switch to auto."""
        from accessiweather.config.settings import SettingsOperations

        ops = SettingsOperations(mock_manager)
        ops._validate_and_fix_config()

        config = mock_manager.get_config()
        assert config.settings.data_source == "auto"
        mock_manager.save_config.assert_called()


# ---------------------------------------------------------------------------
# models/config.py – source priority validation
# ---------------------------------------------------------------------------


class TestSourcePriorityValidation:
    def test_source_priority_us_invalid_type_resets_to_default(self):
        """Lines 353-356: non-list value for source_priority_us resets to default."""
        from accessiweather.models.config import AppSettings

        settings = AppSettings()
        settings.source_priority_us = "not-a-list"
        settings.validate_on_access("source_priority_us")
        assert settings.source_priority_us == [
            "nws",
            "openmeteo",
            "visualcrossing",
            "pirateweather",
        ]

    def test_source_priority_international_invalid_type_resets_to_default(self):
        """Lines 351, 357-358: non-list value for source_priority_international resets."""
        from accessiweather.models.config import AppSettings

        settings = AppSettings()
        settings.source_priority_international = 42
        settings.validate_on_access("source_priority_international")
        assert settings.source_priority_international == [
            "openmeteo",
            "pirateweather",
            "visualcrossing",
        ]

    def test_source_priority_us_all_invalid_resets_to_default(self):
        """Lines 362-368: all-invalid filtered list for US resets to default."""
        from accessiweather.models.config import AppSettings

        settings = AppSettings()
        settings.source_priority_us = ["invalid_source"]
        settings.validate_on_access("source_priority_us")
        assert "nws" in settings.source_priority_us
        assert "pirateweather" in settings.source_priority_us

    def test_source_priority_international_all_invalid_resets_to_default(self):
        """Lines 369-372: all-invalid filtered list for international resets to default."""
        from accessiweather.models.config import AppSettings

        settings = AppSettings()
        settings.source_priority_international = ["bogus"]
        settings.validate_on_access("source_priority_international")
        assert "openmeteo" in settings.source_priority_international
        assert "pirateweather" in settings.source_priority_international

    def test_source_priority_us_filters_invalid_sources(self):
        """Lines 373-374: filtered != value triggers setattr."""
        from accessiweather.models.config import AppSettings

        settings = AppSettings()
        settings.source_priority_us = ["nws", "invalid_source"]
        settings.validate_on_access("source_priority_us")
        # "invalid_source" should be filtered out
        assert "nws" in settings.source_priority_us
        assert "invalid_source" not in settings.source_priority_us


# ---------------------------------------------------------------------------
# weather_client_base.py – pirate_weather_client branch in notification data
# ---------------------------------------------------------------------------


class TestGetNotificationEventDataPirateWeatherBranch:
    @pytest.mark.asyncio
    async def test_pirate_weather_used_when_no_vc_client_intl_location(self, intl_location):
        """Lines 475, 478-480: pw client used for notification data when no VC and intl location."""
        wc = WeatherClient(data_source="openmeteo")

        mock_pw = MagicMock()
        mock_pw.get_current_conditions = AsyncMock(return_value=MagicMock())
        mock_pw.get_alerts = AsyncMock(return_value=WeatherAlerts(alerts=[]))
        wc._pirate_weather_client = mock_pw
        wc._visual_crossing_client = None

        wc._fetch_nws_cancel_references = AsyncMock(return_value=set())

        with patch.object(wc, "_is_us_location", return_value=False):
            result = await wc.get_notification_event_data(intl_location)

        assert result is not None
        mock_pw.get_current_conditions.assert_called_once_with(intl_location)
        mock_pw.get_alerts.assert_called_once_with(intl_location)


# ---------------------------------------------------------------------------
# weather_client_base.py – pirateweather data source path
# ---------------------------------------------------------------------------


class TestPirateWeatherDataSourcePath:
    @pytest.mark.asyncio
    async def test_pirateweather_data_source_successful_fetch(self, intl_location):
        """Lines 561, 571-576, 579-583, 586, 590: successful PW fetch."""
        wc = WeatherClient(data_source="pirateweather", pirate_weather_api_key="test-key")

        mock_pw = MagicMock()
        mock_pw.get_current_conditions = AsyncMock(return_value=MagicMock())
        mock_pw.get_forecast = AsyncMock(return_value=MagicMock())
        mock_pw.get_hourly_forecast = AsyncMock(return_value=MagicMock())
        mock_pw.get_alerts = AsyncMock(return_value=WeatherAlerts(alerts=[]))
        wc._pirate_weather_client = mock_pw
        wc._pirate_weather_client_for_location = lambda loc: mock_pw

        result = await wc._do_fetch_weather_data(intl_location)

        assert result is not None
        assert result.source_attribution is not None
        assert "pirateweather" in result.source_attribution.contributing_sources

    @pytest.mark.asyncio
    async def test_pirateweather_data_source_no_client_sets_empty_data(self, intl_location):
        """Lines 556-558, 592-594: no PW client raises error, sets empty data."""
        wc = WeatherClient(data_source="pirateweather", pirate_weather_api_key="test-key")
        wc._pirate_weather_client = None  # force None despite key existing

        # Force _determine_api_choice to return "pirateweather" even without a working client
        with patch.object(wc, "_determine_api_choice", return_value="pirateweather"):
            result = await wc._do_fetch_weather_data(intl_location)

        # _set_empty_weather_data is called: current is empty CurrentConditions, not None
        assert result is not None
        assert result.discussion == "Weather data not available."

    @pytest.mark.asyncio
    async def test_pirateweather_api_error_handled_gracefully(self, intl_location):
        """Lines 592-594: PirateWeatherApiError caught and empty data returned."""
        wc = WeatherClient(data_source="pirateweather", pirate_weather_api_key="test-key")

        mock_pw = MagicMock()
        mock_pw.get_current_conditions = AsyncMock(
            side_effect=PirateWeatherApiError("API failed", 503)
        )
        mock_pw.get_forecast = AsyncMock(side_effect=PirateWeatherApiError("API failed", 503))
        mock_pw.get_hourly_forecast = AsyncMock(
            side_effect=PirateWeatherApiError("API failed", 503)
        )
        mock_pw.get_alerts = AsyncMock(side_effect=PirateWeatherApiError("API failed", 503))
        wc._pirate_weather_client = mock_pw

        result = await wc._do_fetch_weather_data(intl_location)

        # _set_empty_weather_data is called: returns empty weather data
        assert result is not None
        assert result.discussion == "Weather data not available."

    @pytest.mark.asyncio
    async def test_pirateweather_alert_disappearance_does_not_emit_cancel(self, intl_location):
        """Pirate Weather lifecycle stays conservative when an alert disappears."""
        from accessiweather.models.alerts import WeatherAlert

        wc = WeatherClient(data_source="pirateweather", pirate_weather_api_key="test-key")

        first_alerts = WeatherAlerts(
            alerts=[
                WeatherAlert(
                    title="Avalanche Warning",
                    description="Heavy avalanche risk.",
                    id="pw-wmo-1",
                    source="PirateWeather",
                )
            ]
        )
        second_alerts = WeatherAlerts(alerts=[])

        mock_pw = MagicMock()
        mock_pw.get_current_conditions = AsyncMock(return_value=MagicMock())
        mock_pw.get_forecast = AsyncMock(return_value=MagicMock())
        mock_pw.get_hourly_forecast = AsyncMock(return_value=MagicMock())
        mock_pw.get_alerts = AsyncMock(side_effect=[first_alerts, second_alerts])
        wc._pirate_weather_client = mock_pw
        wc._pirate_weather_client_for_location = lambda loc: mock_pw

        first = await wc._do_fetch_weather_data(intl_location)
        second = await wc._do_fetch_weather_data(intl_location)

        assert first.alert_lifecycle_diff is not None
        assert len(first.alert_lifecycle_diff.new_alerts) == 1
        assert second.alert_lifecycle_diff is not None
        assert len(second.alert_lifecycle_diff.cancelled_alerts) == 0


# ---------------------------------------------------------------------------
# weather_client_base.py – fetch_pw in _fetch_smart_auto_source
# ---------------------------------------------------------------------------


class TestFetchPirateWeatherInAutoMode:
    @pytest.mark.asyncio
    async def test_auto_mode_includes_pw_alerts_for_intl(self, intl_location):
        """Lines 796-806, 855, 861-862, 869-870: PW fetched in auto mode for intl locations."""
        from accessiweather.models.weather import (
            MinutelyPrecipitationForecast,
            MinutelyPrecipitationPoint,
            SourceAttribution,
        )
        from accessiweather.weather_client_fusion import DataFusionEngine
        from accessiweather.weather_client_parallel import ParallelFetchCoordinator, SourceData

        wc = WeatherClient(data_source="auto", pirate_weather_api_key="test-key")

        # Use MagicMock() without spec to avoid dataclass instance-attr limitations
        mock_current = MagicMock()
        mock_current.has_data.return_value = True
        mock_forecast = MagicMock()
        mock_forecast.has_data.return_value = True
        mock_hourly = MagicMock()
        mock_hourly.has_data.return_value = True
        mock_alerts = WeatherAlerts(alerts=[])

        mock_pw = MagicMock()
        mock_pw.get_current_conditions = AsyncMock(return_value=mock_current)
        mock_pw.get_forecast = AsyncMock(return_value=mock_forecast)
        mock_pw.get_hourly_forecast = AsyncMock(return_value=mock_hourly)
        mock_pw.get_alerts = AsyncMock(return_value=mock_alerts)
        wc._pirate_weather_client = mock_pw
        mock_minutely = MinutelyPrecipitationForecast(
            summary="Rain starting in 12 minutes.",
            points=[MinutelyPrecipitationPoint(time=datetime.now(UTC))],
        )
        wc._get_pirate_weather_minutely = AsyncMock(return_value=mock_minutely)

        pw_source = SourceData(
            source="pirateweather",
            current=mock_current,
            forecast=mock_forecast,
            hourly_forecast=mock_hourly,
            alerts=mock_alerts,
            fetch_time=datetime.now(UTC),
            success=True,
        )

        mock_current_attribution = SourceAttribution(
            field_sources={},
            conflicts=[],
            contributing_sources={"pirateweather"},
            failed_sources=set(),
        )
        mock_forecast_attribution = {"summary": "pirateweather"}
        mock_hourly_attribution = {"temperature": "pirateweather"}

        with (
            patch.object(
                ParallelFetchCoordinator,
                "fetch_all",
                return_value=[pw_source],
            ),
            patch.object(wc, "_fetch_nws_cancel_references", return_value=set()),
            patch.object(
                DataFusionEngine,
                "merge_current_conditions",
                return_value=(mock_current, mock_current_attribution),
            ),
            patch.object(
                DataFusionEngine,
                "merge_forecasts",
                return_value=(mock_forecast, mock_forecast_attribution),
            ),
            patch.object(
                DataFusionEngine,
                "merge_hourly_forecasts",
                return_value=(mock_hourly, mock_hourly_attribution),
            ),
        ):
            result = await wc._fetch_smart_auto_source(intl_location)

        assert result is not None
        assert result.minutely_precipitation is mock_minutely


# ---------------------------------------------------------------------------
# display/presentation/forecast.py – summary field from Forecast
# ---------------------------------------------------------------------------


class TestForecastSummaryPresentation:
    """Tests for the Pirate Weather daily summary wired into ForecastPresentation."""

    def _make_location(self):
        from accessiweather.models.weather import Location

        return Location(name="Test City", latitude=40.0, longitude=-75.0)

    def _make_forecast(self, summary=None):
        from accessiweather.models.weather import Forecast, ForecastPeriod

        period = ForecastPeriod(name="Today", temperature=72.0, short_forecast="Sunny")
        return Forecast(periods=[period], summary=summary)

    def test_summary_appears_in_presentation(self):
        """When Forecast.summary is set, ForecastPresentation.summary is populated."""
        from accessiweather.display.presentation.forecast import build_forecast
        from accessiweather.utils import TemperatureUnit

        forecast = self._make_forecast(summary="Light rain throughout the week.")
        result = build_forecast(forecast, None, self._make_location(), TemperatureUnit.FAHRENHEIT)
        assert result.summary == "Overall: Light rain throughout the week."

    def test_summary_appears_in_fallback_text(self):
        """When Forecast.summary is set, it appears in the screen-reader fallback text."""
        from accessiweather.display.presentation.forecast import build_forecast
        from accessiweather.utils import TemperatureUnit

        forecast = self._make_forecast(summary="Mostly cloudy with a chance of rain.")
        result = build_forecast(forecast, None, self._make_location(), TemperatureUnit.FAHRENHEIT)
        assert "Overall: Mostly cloudy with a chance of rain." in result.fallback_text

    def test_no_summary_leaves_presentation_summary_none(self):
        """When Forecast.summary is None, ForecastPresentation.summary is also None."""
        from accessiweather.display.presentation.forecast import build_forecast
        from accessiweather.utils import TemperatureUnit

        forecast = self._make_forecast(summary=None)
        result = build_forecast(forecast, None, self._make_location(), TemperatureUnit.FAHRENHEIT)
        assert result.summary is None

    def test_no_summary_omitted_from_fallback_text(self):
        """When Forecast.summary is None, 'Overall:' does not appear in fallback text."""
        from accessiweather.display.presentation.forecast import build_forecast
        from accessiweather.utils import TemperatureUnit

        forecast = self._make_forecast(summary=None)
        result = build_forecast(forecast, None, self._make_location(), TemperatureUnit.FAHRENHEIT)
        assert "Overall:" not in result.fallback_text

    def test_hourly_summary_appears_in_presentation_and_fallback_text(self):
        """Pirate Weather hourly block summaries surface above the hourly section."""
        from accessiweather.display.presentation.forecast import build_forecast
        from accessiweather.models.weather import HourlyForecast, HourlyForecastPeriod
        from accessiweather.utils import TemperatureUnit

        forecast = self._make_forecast()
        hourly = HourlyForecast(
            periods=[
                HourlyForecastPeriod(
                    start_time=datetime(2026, 2, 1, 12, tzinfo=UTC),
                    temperature=70.0,
                    short_forecast="Partly Cloudy",
                )
            ],
            summary="Partly cloudy until this afternoon.",
        )

        result = build_forecast(forecast, hourly, self._make_location(), TemperatureUnit.FAHRENHEIT)

        assert result.hourly_summary == "Hourly outlook: Partly cloudy until this afternoon."
        assert result.hourly_section_text.startswith("Hourly forecast:")
        assert "Hourly outlook: Partly cloudy until this afternoon." in result.fallback_text
