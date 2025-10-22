import datetime

import pytest

from accessiweather.models import CurrentConditions
from accessiweather.open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.models.archive_daily_data import (
    ArchiveDailyData,
)
from accessiweather.open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.models.archive_daily_units import (
    ArchiveDailyUnits,
)
from accessiweather.open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.models.archive_response import (
    ArchiveResponse,
)
from accessiweather.open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.models.current_data import (
    CurrentData,
)
from accessiweather.open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.models.current_units import (
    CurrentUnits,
)
from accessiweather.open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.models.daily_data import (
    DailyData,
)
from accessiweather.open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.models.daily_units import (
    DailyUnits,
)
from accessiweather.open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.models.forecast_response import (
    ForecastResponse,
)
from accessiweather.open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.models.hourly_data import (
    HourlyData,
)
from accessiweather.open_meteo_api_client.open_meteo_forecast_archive_api_accessi_weather_sketch_client.models.hourly_units import (
    HourlyUnits,
)
from accessiweather.openmeteo_client import OpenMeteoApiClient
from accessiweather.weather_client_openmeteo import (
    parse_openmeteo_current_conditions,
    parse_openmeteo_forecast,
    parse_openmeteo_hourly_forecast,
)
from accessiweather.weather_history import WeatherComparison, WeatherHistoryService


def _build_forecast_payload(
    *,
    temp_value: float,
    temp_unit: str,
) -> dict:
    """Create a ForecastResponse payload tailored for unit conversion checks."""
    now = datetime.datetime(2024, 5, 1, 12, tzinfo=datetime.UTC)

    current_units = CurrentUnits(
        time="iso8601",
        interval="seconds",
        temperature_2m=temp_unit,
        relative_humidity_2m="%",
        apparent_temperature=temp_unit,
        precipitation="in",
        weather_code="wmo",
        cloud_cover="%",
        pressure_msl="hPa",
        surface_pressure="hPa",
        wind_speed_10m="mph",
        wind_direction_10m="°",
        wind_gusts_10m="mph",
    )

    current = CurrentData(
        time=now,
        interval=900,
        temperature_2m=temp_value,
        relative_humidity_2m=55.0,
        apparent_temperature=temp_value - 2.0,
        precipitation=0.1,
        weather_code=2,
        cloud_cover=40.0,
        pressure_msl=1015.0,
        surface_pressure=1012.0,
        wind_speed_10m=12.0,
        wind_direction_10m=180.0,
        wind_gusts_10m=20.0,
    )

    daily_units = DailyUnits(
        time="iso8601",
        temperature_2m_max=temp_unit,
        temperature_2m_min=temp_unit,
        temperature_2m_mean=temp_unit,
        uv_index_max="index",
        sunrise="iso8601",
        sunset="iso8601",
        wind_speed_10m_max="mph",
        wind_direction_10m_dominant="°",
        weather_code="wmo",
    )

    forecast_date = datetime.date(2024, 5, 1)
    daily = DailyData(
        time=[forecast_date],
        weather_code=[2],
        temperature_2m_max=[temp_value + 5],
        temperature_2m_min=[temp_value - 5],
        temperature_2m_mean=[temp_value],
        uv_index_max=[5.0],
        sunrise=[datetime.datetime(2024, 5, 1, 7, 0, tzinfo=datetime.UTC)],
        sunset=[datetime.datetime(2024, 5, 1, 19, 30, tzinfo=datetime.UTC)],
        wind_speed_10m_max=[18.0],
        wind_direction_10m_dominant=[190.0],
    )

    hourly_units = HourlyUnits(
        time="iso8601",
        temperature_2m=temp_unit,
        weather_code="wmo",
        wind_speed_10m="mph",
        wind_direction_10m="°",
        pressure_msl="hPa",
        relative_humidity_2m="%",
        apparent_temperature=temp_unit,
    )

    hourly = HourlyData(
        time=[datetime.datetime(2024, 5, 1, 13, 0, tzinfo=datetime.UTC)],
        temperature_2m=[temp_value - 1],
        weather_code=[2],
        wind_speed_10m=[10.0],
        wind_direction_10m=[200.0],
        pressure_msl=[1010.0],
        relative_humidity_2m=[60.0],
        apparent_temperature=[temp_value - 1.5],
    )

    response = ForecastResponse(
        latitude=40.0,
        longitude=-74.0,
        timezone="America/New_York",
        timezone_abbreviation="EDT",
        current_units=current_units,
        current=current,
        daily_units=daily_units,
        daily=daily,
        hourly_units=hourly_units,
        hourly=hourly,
    )
    return response.to_dict()


@pytest.mark.parametrize(
    ("value", "unit", "expected_f"),
    [
        (72.0, "°F", 72.0),
        (22.0, "°C", 71.6),
    ],
)
def test_parse_openmeteo_current_conditions_handles_units(
    value: float, unit: str, expected_f: float
):
    payload = _build_forecast_payload(temp_value=value, temp_unit=unit)

    conditions = parse_openmeteo_current_conditions(payload)

    assert isinstance(conditions, CurrentConditions)
    assert conditions.temperature_f == pytest.approx(expected_f, rel=1e-3)
    assert conditions.temperature_c is not None
    assert conditions.wind_speed_mph == pytest.approx(12.0)
    assert conditions.wind_speed_kph == pytest.approx(19.31208, rel=1e-3)
    assert conditions.pressure_mb == pytest.approx(1015.0)
    assert conditions.pressure_in == pytest.approx(29.973, rel=1e-3)
    assert conditions.sunrise_time is not None
    assert conditions.sunset_time is not None


def test_parse_openmeteo_forecast_periods_from_generated_payload():
    payload = _build_forecast_payload(temp_value=75.0, temp_unit="°F")

    forecast = parse_openmeteo_forecast(payload)

    assert len(forecast.periods) == 1
    period = forecast.periods[0]
    assert period.temperature == pytest.approx(80.0)
    assert period.short_forecast == "Partly cloudy"


def test_parse_openmeteo_hourly_forecast_uses_pressure_conversions():
    payload = _build_forecast_payload(temp_value=70.0, temp_unit="°F")

    hourly = parse_openmeteo_hourly_forecast(payload)

    assert len(hourly.periods) == 1
    period = hourly.periods[0]
    assert period.pressure_mb == pytest.approx(1010.0)
    assert period.pressure_in == pytest.approx(29.831, rel=1e-3)
    assert period.wind_speed == "10.0 mph"
    assert period.wind_direction == "SSW"


def test_archive_response_supports_weather_history_comparisons():
    daily_units = ArchiveDailyUnits(
        time="iso8601",
        weather_code="wmo",
        temperature_2m_max="°F",
        temperature_2m_min="°F",
        temperature_2m_mean="°F",
        wind_speed_10m_max="mph",
        wind_direction_10m_dominant="°",
    )

    archive_date = datetime.date(2024, 4, 30)
    daily_data = ArchiveDailyData(
        time=[archive_date],
        weather_code=[2],
        temperature_2m_max=[70.0],
        temperature_2m_min=[55.0],
        temperature_2m_mean=[62.0],
        wind_speed_10m_max=[15.0],
        wind_direction_10m_dominant=[210.0],
    )

    archive_payload = ArchiveResponse(
        daily_units=daily_units,
        daily=daily_data,
    ).to_dict()

    # Stub OpenMeteo client to return the generated payload
    class StubClient:
        def _make_request(self, endpoint: str, params: dict) -> dict:
            assert endpoint == "archive"
            return archive_payload

        @staticmethod
        def get_weather_description(code: int | str) -> str:
            return "Partly cloudy"

    service = WeatherHistoryService(openmeteo_client=StubClient())
    historical = service.get_historical_weather(40.0, -74.0, archive_date)

    assert historical is not None
    assert historical.temperature_mean == pytest.approx(62.0)
    assert historical.wind_speed == pytest.approx(15.0)
    assert historical.wind_direction == 210.0

    comparison = WeatherComparison.compare(
        CurrentConditions(temperature=70.0, condition="Partly cloudy"),
        historical,
        1,
    )
    assert comparison.temperature_difference == pytest.approx(8.0)


def test_openmeteo_client_optionally_normalises_payload():
    client = OpenMeteoApiClient(use_generated_models=True)
    payload = _build_forecast_payload(temp_value=68.0, temp_unit="°F")

    normalised = client._coerce_with_generated_model("forecast", payload)

    assert "current" in normalised
    assert normalised["current"]["temperature_2m"] == pytest.approx(68.0)
