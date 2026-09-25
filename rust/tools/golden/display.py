r"""
Golden files for ``aw_core::display`` (the presentation layer).

Run from the Python checkout:

    cd C:\\Users\\joshu\\accessiweather
    uv run python <worktree>\\rust\\tools\\golden\\display.py

Builds WeatherData from the recorded NWS / Open-Meteo / Pirate Weather
cassettes (parsed by the app's own parsers, no network) plus synthetic
cases, runs ``WeatherPresenter`` and ``TaskbarIconUpdater`` under a matrix of
settings with a frozen clock, and writes one JSON file per case to
``rust/testdata/golden/display/``. Each file holds the WeatherData
(``asdict`` shape), the frozen "now", the system timezone and, per settings
variant, the full ``WeatherPresentation`` plus tray tooltips.

The inputs are normalised before presenting so Python sees exactly what the
Rust model can hold: numeric fields take their declared type, numeric wind
directions become cardinal text (as the presenter would print them), naive
datetimes get the system offset, and every datetime is labelled with the
location's ZoneInfo when the offsets agree (a fixed offset otherwise) - the
rule ``aw_core::display::time::PyDateTime::aware`` applies.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import sys
import time
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

import accessiweather.alert_lifecycle as m_lifecycle
import accessiweather.display.presentation.forecast_time as m_forecast_time
import accessiweather.models.alerts as m_alerts
import accessiweather.models.weather_forecast as m_weather_forecast
import accessiweather.services.mobility_briefing as m_mobility
import accessiweather.weather_client_trends as m_trends
from accessiweather.alert_lifecycle import diff_alerts
from accessiweather.display import WeatherPresenter
from accessiweather.display.presentation.formatters import format_date, format_datetime
from accessiweather.forecast_confidence import ForecastConfidence, ForecastConfidenceLevel
from accessiweather.format_string_parser import FormatStringParser
from accessiweather.models import (
    AppSettings,
    AviationData,
    CurrentConditions,
    EnvironmentalConditions,
    Forecast,
    ForecastPeriod,
    HourlyAirQuality,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    MarineForecast,
    MarineForecastPeriod,
    MinutelyPrecipitationForecast,
    MinutelyPrecipitationPoint,
    SourceAttribution,
    TrendInsight,
    WeatherAlert,
    WeatherAlerts,
    WeatherData,
)
from accessiweather.notifications.minutely_precipitation import (
    parse_pirate_weather_minutely_block,
)
from accessiweather.pirate_weather_client import PirateWeatherClient
from accessiweather.taskbar_icon_updater import TaskbarIconUpdater
from accessiweather.utils import decode_taf_text
from accessiweather.utils.taf_decoder import (
    _decode_cloud,
    _decode_visibility,
    _decode_weather,
    _decode_wind,
)
from accessiweather.utils.unit_utils import convert_wind_direction_to_cardinal
from accessiweather.weather_anomaly import AnomalyCallout
from accessiweather.weather_client_nws_parsers import (
    parse_nws_alerts,
    parse_nws_current_conditions,
    parse_nws_forecast,
    parse_nws_hourly_forecast,
)
from accessiweather.weather_client_openmeteo import (
    parse_openmeteo_forecast,
    parse_openmeteo_hourly_forecast,
)
from accessiweather.weather_client_openmeteo_current import parse_openmeteo_current_conditions
from accessiweather.weather_client_trends import apply_trend_insights

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "testdata" / "golden" / "display"
CASSETTES = Path.cwd() / "tests" / "integration" / "cassettes"
LOCAL_TZ = "America/New_York"

if time.tzname != ("Eastern Standard Time", "Eastern Daylight Time"):
    sys.exit(
        "Generate these on a machine set to US Eastern time (the files record America/New_York)."
    )

# ---------------------------------------------------------------------------
# Frozen clock
# ---------------------------------------------------------------------------

_FROZEN: list[datetime] = [datetime(2026, 1, 1, tzinfo=UTC)]


class FrozenDatetime(datetime):
    """``datetime`` whose ``now()`` returns the frozen instant."""

    @classmethod
    def now(cls, tz=None):  # noqa: D102
        now = _FROZEN[0]
        if tz is None:
            return now.astimezone().replace(tzinfo=None)
        return now.astimezone(tz)


for _module in (m_alerts, m_weather_forecast, m_mobility, m_forecast_time, m_trends, m_lifecycle):
    _module.datetime = FrozenDatetime


def freeze(now: datetime) -> None:
    _FROZEN[0] = now


# ---------------------------------------------------------------------------
# Normalisation and serialisation
# ---------------------------------------------------------------------------


def location_zone(location: Location):
    if not location.timezone:
        return None
    try:
        return ZoneInfo(location.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def relabel(value: datetime, zone) -> datetime:
    if value.tzinfo is None:
        value = value.astimezone()
    offset = value.utcoffset()
    if zone is not None:
        zoned = value.astimezone(zone)
        if zoned.utcoffset() == offset:
            return zoned
    return value.astimezone(timezone(offset))


def normalise(obj, zone) -> None:
    """Coerce values in place to what the Rust model can represent."""
    if isinstance(obj, list):
        for item in obj:
            normalise(item, zone)
        return
    if not dataclasses.is_dataclass(obj) or isinstance(obj, type):
        return
    for f in dataclasses.fields(obj):
        value = getattr(obj, f.name)
        declared = f.type if isinstance(f.type, str) else str(f.type)
        if isinstance(value, bool) or value is None:
            continue
        if f.name == "wind_direction" and isinstance(value, int | float):
            setattr(obj, f.name, convert_wind_direction_to_cardinal(value))
        elif isinstance(value, int) and declared.startswith("float"):
            setattr(obj, f.name, float(value))
        elif isinstance(value, float) and declared.startswith("int"):
            setattr(obj, f.name, int(round(value)))
        elif isinstance(value, datetime):
            setattr(obj, f.name, relabel(value, zone))
        elif isinstance(value, set):
            continue
        else:
            normalise(value, zone)


def to_json(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: to_json(getattr(value, f.name))
            for f in dataclasses.fields(value)
            if f.name != "pending_enrichments"
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.astimezone()).isoformat()
    if isinstance(value, set | frozenset):
        return sorted(to_json(v) for v in value)
    if isinstance(value, list | tuple):
        return [to_json(v) for v in value]
    if isinstance(value, dict):
        return {str(k): to_json(v) for k, v in value.items()}
    return value


# ---------------------------------------------------------------------------
# Cassettes
# ---------------------------------------------------------------------------


def cassette(path: str, uri_part: str = "") -> dict:
    data = yaml.safe_load((CASSETTES / path).read_text(encoding="utf-8"))
    for interaction in data["interactions"]:
        if uri_part in interaction["request"]["uri"]:
            return json.loads(interaction["response"]["body"]["string"])
    raise KeyError(f"{uri_part!r} not in {path}")


def at(text: str) -> datetime:
    return datetime.fromisoformat(text)


NYC = Location("New York, NY", 40.7128, -74.006, timezone="America/New_York", country_code="US")
ANCHORAGE = Location(
    "Anchorage, AK", 61.2181, -149.9003, timezone="America/Anchorage", country_code="US"
)
LONDON = Location("London", 51.5074, -0.1278, timezone="Europe/London", country_code="GB")
TROMSO = Location("Tromsø", 69.6489, 18.9551, timezone="Europe/Oslo", country_code="NO")
TORONTO = Location("Toronto", 43.65, -79.38, timezone="America/Toronto", country_code="CA")
SEATTLE = Location("Seattle, WA", 47.61, -122.33, timezone="America/Los_Angeles")
MIAMI = Location("Miami, FL", 25.77, -80.19, timezone="America/New_York", country_code="US")
NOWHERE = Location("Somewhere", 10.0, 10.0)


def nws_nyc() -> tuple[WeatherData, datetime]:
    current = parse_nws_current_conditions(
        cassette("nws/current_nyc.yaml", "observations/latest"), NYC
    )
    forecast = parse_nws_forecast(cassette("nws/forecast_nyc.yaml", "/forecast"))
    forecast.generated_at = at("2026-01-20T12:45:00-05:00")
    hourly = parse_nws_hourly_forecast(cassette("nws/hourly_nyc.yaml", "forecast/hourly"), NYC)
    del hourly.periods[72:]  # three days is plenty for the 48-hour variant
    hourly.generated_at = at("2026-01-20T12:40:00-05:00")
    data = WeatherData(location=NYC, current=current, forecast=forecast, hourly_forecast=hourly)
    data.alerts = parse_nws_alerts(cassette("nws/alerts_nyc.yaml"))
    data.source_attribution = SourceAttribution(contributing_sources={"nws"})
    return data, at("2026-01-20T13:10:00-05:00")


def nws_alaska() -> tuple[WeatherData, datetime]:
    current = parse_nws_current_conditions(
        cassette("nws/current_alaska.yaml", "observations/latest"), ANCHORAGE
    )
    forecast = parse_nws_forecast(cassette("nws/forecast_alaska.yaml", "/forecast"))
    forecast.generated_at = at("2026-01-20T09:00:00-09:00")
    return WeatherData(location=ANCHORAGE, current=current, forecast=forecast), at(
        "2026-01-20T10:00:00-09:00"
    )


def openmeteo_nyc() -> tuple[WeatherData, datetime]:
    current = parse_openmeteo_current_conditions(cassette("openmeteo/current_weather_nyc.yaml"))
    forecast = parse_openmeteo_forecast(cassette("openmeteo/forecast_daily.yaml"))
    forecast.generated_at = at("2025-01-15T11:55:00-05:00")
    hourly = parse_openmeteo_hourly_forecast(cassette("openmeteo/hourly_forecast.yaml"))
    hourly.generated_at = at("2025-01-15T09:00:00-05:00")
    data = WeatherData(location=NYC, current=current, forecast=forecast, hourly_forecast=hourly)
    data.source_attribution = SourceAttribution(
        contributing_sources={"openmeteo"}, failed_sources={"nws"}
    )
    data.incomplete_sections = {"alerts"}
    now = at("2025-01-15T09:20:00-05:00")
    freeze(now.astimezone(UTC))
    apply_trend_insights(data, True, 24)
    return data, now


def openmeteo_london() -> tuple[WeatherData, datetime]:
    current = parse_openmeteo_current_conditions(cassette("openmeteo/current_weather_london.yaml"))
    return WeatherData(location=LONDON, current=current), at("2025-01-15T12:00:00+00:00")


def openmeteo_celsius_extended() -> tuple[WeatherData, datetime]:
    current = parse_openmeteo_current_conditions(cassette("openmeteo/current_weather_celsius.yaml"))
    forecast = parse_openmeteo_forecast(cassette("openmeteo/forecast_extended.yaml"))
    forecast.generated_at = None
    loc = dataclasses.replace(TORONTO, name="Toronto (metric)")
    return WeatherData(location=loc, current=current, forecast=forecast), at(
        "2025-01-15T12:00:00-05:00"
    )


def openmeteo_alaska() -> tuple[WeatherData, datetime]:
    current = parse_openmeteo_current_conditions(cassette("openmeteo/current_weather_alaska.yaml"))
    forecast = parse_openmeteo_forecast(cassette("openmeteo/forecast_alaska.yaml"))
    forecast.generated_at = at("2026-01-20T08:00:00-09:00")
    return WeatherData(location=ANCHORAGE, current=current, forecast=forecast), at(
        "2026-01-20T09:00:00-09:00"
    )


def pirate(name: str, location: Location, now: str) -> tuple[WeatherData, datetime]:
    payload = cassette(f"pirate_weather/{name}.yaml")
    client = PirateWeatherClient("golden", units="us")
    data = WeatherData(
        location=location,
        current=client._parse_current_conditions(payload),
        forecast=client._parse_forecast(payload),
        hourly_forecast=client._parse_hourly_forecast(payload),
        alerts=client._parse_alerts(payload),
        minutely_precipitation=parse_pirate_weather_minutely_block(payload, units="us"),
    )
    if data.hourly_forecast is not None:
        del data.hourly_forecast.periods[72:]
        data.hourly_forecast.generated_at = at(now) - timedelta(minutes=5)
    if data.forecast is not None:
        data.forecast.generated_at = at(now) - timedelta(minutes=5)
    data.source_attribution = SourceAttribution(
        contributing_sources={"pirateweather"},
        field_sources={"condition": "pirateweather", "hourly_source": "pirateweather"},
    )
    return data, at(now)


def nws_alert_payload(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": [{"properties": p} for p in features]}


def winter_storm() -> tuple[WeatherData, datetime]:
    now = at("2026-02-03T07:30:00-05:00")
    current = CurrentConditions(
        temperature_f=18.0,
        temperature_c=-7.8,
        condition="Heavy Snow and Fog",
        humidity=92,
        dewpoint_f=16.2,
        dewpoint_c=-8.8,
        wind_speed_mph=22.0,
        wind_speed_kph=35.4,
        wind_direction="NE",
        wind_gust_mph=41.0,
        wind_gust_kph=66.0,
        pressure_in=29.62,
        pressure_mb=1003.0,
        feels_like_f=2.0,
        visibility_miles=0.2,
        visibility_km=0.3,
        cloud_cover=100.0,
        precipitation_in=0.35,
        precipitation_mm=8.9,
        snow_depth_in=9.5,
        snow_depth_cm=24.1,
        wind_chill_f=2.0,
        wind_chill_c=-16.7,
        freezing_level_ft=0.0,
        frost_risk="High",
        precipitation_type=["snow", "ice pellets"],
        severe_weather_risk=65,
        sunrise_time=at("2026-02-03T06:58:00-05:00"),
        sunset_time=at("2026-02-03T17:14:00-05:00"),
        moon_phase="Waxing Gibbous",
        moonrise_time=at("2026-02-03T14:02:00-05:00"),
        moonset_time=at("2026-02-04T05:40:00-05:00"),
    )
    alerts = parse_nws_alert_samples(now)
    previous = WeatherAlerts(alerts=[alerts.alerts[1]])
    base = datetime(2026, 2, 3, 3, 0, tzinfo=ZoneInfo("America/New_York"))
    hourly = HourlyForecast(
        periods=[
            HourlyForecastPeriod(
                start_time=base + timedelta(hours=i),
                temperature=18.0 - i * 0.5,
                short_forecast="Heavy Snow" if i < 10 else "Snow Showers",
                wind_speed=f"{20 + i} mph",
                wind_speed_mph=float(20 + i),
                wind_direction="NE",
                wind_gust_mph=35.0 + i * 2,
                humidity=90 + (i % 3),
                pressure_mb=1003.0 - i * 0.4,
                pressure_in=29.62 - i * 0.012,
                precipitation_probability=95.0 - i,
                snowfall=0.8,
                precipitation_amount=0.12,
                uv_index=0.0,
                cloud_cover=100.0,
                visibility_miles=0.5,
                wind_chill_f=1.0,
            )
            for i in range(30)
        ],
        summary="Snow, heavy at times, through the evening.",
    )
    forecast = Forecast(
        periods=[
            ForecastPeriod(
                name=name,
                temperature=temp,
                temperature_unit="F",
                short_forecast=short,
                detailed_forecast=detail,
                wind_speed=wind,
                wind_direction="NE",
                wind_gust="45 mph" if i < 2 else None,
                precipitation_probability=pop,
                snowfall=snow,
                precipitation_amount=amount,
                precipitation_type=types,
                start_time=base + timedelta(hours=3 + 12 * i),
                uv_index=1.0,
                cloud_cover=100.0,
            )
            for i, (name, temp, short, detail, wind, pop, snow, amount, types) in enumerate(
                [
                    (
                        "Today",
                        22.0,
                        "Heavy Snow",
                        "Snow, heavy at times. Areas of blowing snow. High near 22. "
                        "Northeast wind 20 to 30 mph, with gusts as high as 45 mph. "
                        "Chance of precipitation is 100%. New snow accumulation of 8 to "
                        "12 inches possible.",
                        "20 to 30 mph",
                        100.0,
                        10.0,
                        0.9,
                        ["snow"],
                    ),
                    (
                        "Tonight",
                        12.0,
                        "Snow Showers",
                        "Snow showers, mainly before 11pm. Low around 12. North-northeast "
                        "wind 15 to 20 mph.",
                        "15 to 20 mph",
                        70.0,
                        2.0,
                        0.2,
                        ["snow"],
                    ),
                    (
                        "Wednesday",
                        20.0,
                        "Mostly Sunny",
                        "Mostly sunny.",
                        "10 mph",
                        5.0,
                        0.0,
                        0.0,
                        None,
                    ),
                    ("Wednesday Night", 5.0, "Clear", "Clear", "5 mph", None, None, None, None),
                    (
                        "Thursday",
                        27.0,
                        "Sunny",
                        "Sunny, with a high near 27.",
                        "5 to 10 mph",
                        0.0,
                        None,
                        None,
                        None,
                    ),
                    (
                        "Thursday Night",
                        15.0,
                        "Partly Cloudy",
                        None,
                        "5 mph",
                        None,
                        None,
                        None,
                        None,
                    ),
                    (
                        "Friday",
                        33.0,
                        "Chance Rain And Snow",
                        "A chance of rain and snow.",
                        "10 mph",
                        40.0,
                        0.5,
                        0.1,
                        ["rain", "snow"],
                    ),
                    (
                        "Friday Night",
                        25.0,
                        "Rain And Snow Likely",
                        None,
                        "10 mph",
                        60.0,
                        1.0,
                        0.25,
                        ["rain", "snow"],
                    ),
                ]
            )
        ],
        generated_at=at("2026-02-03T06:10:00-05:00"),
        summary="Major winter storm today, then a cold, dry stretch.",
    )
    data = WeatherData(
        location=NYC,
        current=current,
        forecast=forecast,
        hourly_forecast=hourly,
        alerts=alerts,
        trend_insights=[
            TrendInsight(
                "temperature",
                "falling",
                -6.4,
                "°F",
                24,
                "Temperature falling -6.4°F over 24h",
                "▇▆▅▃▂",
            ),
            TrendInsight("wind_speed", "rising", 12.25, "mph", 12),
            TrendInsight("daily_trend", "cooler", None, None, 24, "Colder than yesterday"),
        ],
    )
    data.alert_lifecycle_diff = diff_alerts(previous, alerts)
    data.stale = True
    data.stale_since = at("2026-02-03T06:45:00-05:00")
    data.stale_reason = "network unavailable"
    return data, now


def parse_nws_alert_samples(now: datetime) -> WeatherAlerts:
    long_description = (
        "* WHAT...Heavy snow expected. Total snow accumulations of 10 to 16 inches. "
        "Winds gusting as high as 45 mph.\n\n* WHERE...New York (Manhattan), Bronx and "
        "Kings (Brooklyn) Counties.\n\n* WHEN...Until 6 PM EST this evening.\n\n"
        "* IMPACTS...Travel could be very difficult to impossible. The hazardous "
        "conditions could impact the morning and evening commutes. Well-above-average "
        "snowfall-rates of 2-3 inches per hour are possible."
    )
    features = [
        {
            "id": "urn:oid:2.49.0.1.840.0.winter",
            "event": "Winter Storm Warning",
            "headline": "Winter Storm Warning issued February 3 at 4:05AM EST until February 3 at 6:00PM EST by NWS Upton NY",
            "description": long_description,
            "instruction": "If you must travel, keep an extra flashlight, food, and water in "
            "your vehicle in case of an emergency. The latest road conditions can be "
            "obtained by calling 5 1 1.",
            "severity": "Severe",
            "urgency": "Expected",
            "certainty": "Likely",
            "sent": "2026-02-03T04:05:00-05:00",
            "effective": "2026-02-03T04:05:00-05:00",
            "onset": "2026-02-03T04:05:00-05:00",
            "expires": "2026-02-03T18:00:00-05:00",
            "areaDesc": "New York (Manhattan); Bronx; Kings (Brooklyn); Queens; Richmond (Staten Island)",
            "messageType": "Alert",
        },
        {
            "id": "urn:oid:2.49.0.1.840.0.fog",
            "event": "Dense Fog Advisory",
            "headline": "Dense Fog Advisory until 10:00AM EST",
            "description": "Visibility one quarter mile or less in dense fog.",
            "severity": "Minor",
            "urgency": "Unknown",
            "certainty": "Likely",
            "sent": "2026-02-03T02:00:00-05:00",
            "expires": "2026-02-03T10:00:00-05:00",
            "areaDesc": "Kings (Brooklyn)",
            "messageType": "Alert",
        },
        {
            "id": "urn:oid:2.49.0.1.840.0.expired",
            "event": "Wind Advisory",
            "headline": "Wind Advisory has expired",
            "description": "Winds have diminished.",
            "severity": "Moderate",
            "urgency": "Past",
            "sent": "2026-02-02T20:00:00-05:00",
            "expires": "2026-02-03T01:00:00-05:00",
            "areaDesc": "Queens",
        },
    ]
    alerts = parse_nws_alerts(nws_alert_payload(features))
    alerts.alerts.append(
        WeatherAlert(
            title="Snow avalanche warning",
            description="",
            severity="Unknown",
            event=None,
            areas=["Region A", "Region B", "Region C", "Region D", "Region E"],
            source="PirateWeather",
            expires=None,
        )
    )
    return alerts


def summer_heat() -> tuple[WeatherData, datetime]:
    now = at("2026-07-18T14:05:00-04:00")
    tz = ZoneInfo("America/New_York")
    current = CurrentConditions(
        temperature_f=96.0,
        temperature_c=35.6,
        condition="Mostly Sunny",
        humidity=58,
        wind_speed_mph=7.0,
        wind_speed_kph=11.3,
        wind_direction="SW",
        pressure_in=29.92,
        pressure_mb=1013.2,
        feels_like_f=112.0,
        feels_like_c=44.4,
        heat_index_f=112.0,
        heat_index_c=44.4,
        visibility_miles=10.0,
        visibility_km=16.1,
        uv_index=9.2,
        cloud_cover=20.0,
        sunrise_time=at("2026-07-18T05:40:00-04:00"),
        sunset_time=at("2026-07-18T20:22:00-04:00"),
        precipitation_type=["rain"],
    )
    env = EnvironmentalConditions(
        air_quality_index=152.4,
        air_quality_category="Unhealthy",
        air_quality_pollutant="O3",
        air_quality_updated_at=at("2026-07-18T13:00:00-04:00"),
        pollen_index=8.6,
        pollen_category="Very High",
        pollen_tree_index=2.4,
        pollen_grass_index=9.5,
        pollen_weed_index=3.5,
        pollen_primary_allergen="Grass",
        uv_index=9.2,
        uv_category="Very High",
        updated_at=at("2026-07-18T13:05:00-04:00"),
        sources=["AirNow", "Open-Meteo", "AirNow", ""],
        hourly_air_quality=[
            HourlyAirQuality(
                timestamp=datetime(2026, 7, 18, 14 + i, tzinfo=tz),
                aqi=150 + i * 5,
                category="Unhealthy",
            )
            for i in range(3)
        ],
    )
    hourly = HourlyForecast(
        periods=[
            HourlyForecastPeriod(
                start_time=datetime(2026, 7, 18, 14, tzinfo=tz) + timedelta(hours=i),
                temperature=96.0 - i,
                short_forecast="Mostly Sunny" if i < 4 else "Chance Thunderstorms",
                wind_speed="7 mph",
                wind_direction="SW",
                wind_speed_mph=7.0,
                humidity=55 + i,
                precipitation_probability=10.0 + i * 5.5,
                uv_index=9.4 - i,
                cloud_cover=20.0 + i * 7,
                wind_gust_mph=15.0 + i * 4,
                heat_index_f=110.0,
                visibility_miles=10.0 - i,
            )
            for i in range(8)
        ]
    )
    forecast = Forecast(
        periods=[
            ForecastPeriod(
                name="This Afternoon",
                temperature=98.0,
                short_forecast="Hot and humid, chance of thunderstorms",
                detailed_forecast="Hot and humid, chance of thunderstorms",
                wind_speed="5 to 10 mph",
                wind_direction="SW",
                precipitation_probability=35.5,
                uv_index=9.4,
                uv_index_max=10.0,
                feels_like_high=110.0,
                pollen_forecast="High",
                cloud_cover=30.0,
                wind_gust="25 mph",
            ),
            ForecastPeriod(
                name="Tonight", temperature=78.0, short_forecast="Partly Cloudy", wind_speed="5 mph"
            ),
            ForecastPeriod(name="Saturday", temperature=94.0, short_forecast="Sunny"),
            ForecastPeriod(name="Saturday Night", temperature=76.0, short_forecast="Clear"),
        ],
        generated_at=at("2026-07-18T13:30:00-04:00"),
    )
    data = WeatherData(
        location=MIAMI,
        current=current,
        forecast=forecast,
        hourly_forecast=hourly,
        environmental=env,
        marine=MarineForecast(
            zone_id="AMZ651",
            zone_name="Coastal waters from Jupiter Inlet to Deerfield Beach FL out 20 NM",
            forecast_summary="Southeast winds 10 to 15 knots. Seas 2 to 3 feet.",
            issued_at=at("2026-07-18T10:00:00-04:00"),
            periods=[
                MarineForecastPeriod(
                    "Today",
                    "Southeast winds 10 to 15 knots. Seas 2 to 3 feet. Intracoastal waters a light chop. Isolated thunderstorms in the afternoon, which could produce gusty winds and locally higher seas.",
                ),
                MarineForecastPeriod("Tonight", "South winds around 10 knots."),
                MarineForecastPeriod("Saturday", ""),
                MarineForecastPeriod("Sunday", "Not shown"),
            ],
            highlights=[
                "SE 10-15 kt",
                "Seas 2-3 ft",
                "Isolated storms",
                "Rip current risk",
                "Fifth highlight",
            ],
        ),
        forecast_confidence=ForecastConfidence(
            level=ForecastConfidenceLevel.MEDIUM,
            rationale="NWS and Open-Meteo agree on temperature but differ on rain chances...",
            sources_compared=2,
            source_names=["NWS", "Open-Meteo"],
        ),
        anomaly_callout=AnomalyCallout(
            temp_anomaly=8.2,
            temp_anomaly_description="8°F warmer than the 30-year average for this date",
            precip_anomaly_description=None,
            severity="notable",
        ),
        alerts=WeatherAlerts(
            alerts=[
                WeatherAlert(
                    title="Excessive Heat Warning",
                    description="Dangerously hot conditions with heat index values up to 115.",
                    severity="Extreme",
                    urgency="Immediate",
                    event="Excessive Heat Warning",
                    expires=at("2026-07-18T20:00:00-04:00"),
                    areas=["Miami-Dade"],
                )
            ]
        ),
    )
    return data, now


def aviation_case() -> tuple[WeatherData, datetime]:
    now = at("2026-04-02T16:00:00+00:00")
    current = CurrentConditions(
        temperature_c=12.0, condition="Overcast", humidity=0, wind_speed_kph=0.4
    )
    aviation = AviationData(
        raw_taf="TAF AMD KSEA 021720Z 0218/0324 VRB03KT P6SM SCT015 BKN035 "
        "TEMPO 0218/0222 4SM -SHRA BR BKN012 "
        "FM030200 20012G22KT 3/4SM +RA FG VV005 "
        "BECMG 0306/0308 M1/4SM FZFG "
        "PROB40 TEMPO 0310/0314 1 1/2SM TSRA SCT020CB "
        "FM031200 00000KT 9999 NSC CAVOK NSW XYZ= RMK AO2",
        station_id="KSEA",
        airport_name="Seattle-Tacoma International Airport",
        active_sigmets=[
            {
                "name": "SIGMET NOVEMBER 3",
                "severity": "SEV",
                "fir": ["KZSE", "", "KZOA"],
                "startTime": "2026-04-02T15:00:00Z",
                "endTime": "2026-04-02T19:00:00Z",
                "description": "Severe turbulence between FL250 and FL380.",
            },
            {"hazard": "ICE", "area": "Cascades", "validUntil": "2026-04-02T20:00:00+00:00"},
            {"phenomenon": "MTN OBSCN", "issueTime": "not a time", "intensity": 2},
            {"text": "Only text"},
            "not a dict",
            {"name": "Sixth", "regions": []},
        ],
        active_cwas=[
            {
                "event": "IFR",
                "cwsu": "ZSE",
                "startTime": "2026-04-02T15:30:00Z",
                "endTime": "2026-04-02T17:30:00Z",
                "text": "IFR conditions in low clouds.",
            },
            {
                "phenomenon": "TS",
                "issuingOffice": "ZOA",
                "area": "ZOA",
                "issueTime": "2026-04-02T12:00:00",
            },
            {},
        ],
    )
    data = WeatherData(location=SEATTLE, current=current, aviation=aviation)
    return data, now


def aviation_decoded_only() -> tuple[WeatherData, datetime]:
    loc = Location("KJFK", 40.64, -73.78, timezone="America/New_York", country_code="US")
    aviation = AviationData(
        decoded_taf="Forecast for station KJFK.\nBase forecast: Calm winds.",
        station_id="kjfk",
    )
    return WeatherData(location=loc, aviation=aviation), at("2026-04-02T16:00:00+00:00")


def empty_case() -> tuple[WeatherData, datetime]:
    data = WeatherData(
        location=NOWHERE, current=CurrentConditions(), alerts=WeatherAlerts(alerts=[])
    )
    data.forecast = Forecast(periods=[])
    return data, at("2026-05-05T12:00:00+00:00")


def sparse_case() -> tuple[WeatherData, datetime]:
    now = at("2026-10-10T18:00:00-04:00")
    current = CurrentConditions(
        condition="Rain",
        wind_direction="",
        pressure_mb=1009.0,
        dewpoint_c=11.0,
        temperature_c=13.0,
        wind_speed=0.0,
    )
    hourly = HourlyForecast(
        periods=[
            HourlyForecastPeriod(
                start_time=datetime(2026, 10, 10, 20, 0) + timedelta(hours=i),
                temperature=13.0 - i * 0.25,
                temperature_unit="C",
                humidity=0 if i == 0 else 80,
                pressure_mb=1010.2 if i == 5 else None,
            )
            for i in range(6)
        ]
        + [HourlyForecastPeriod(start_time=datetime(2026, 10, 10, 19, 0))],
        summary="Clearing later.",
    )
    forecast = Forecast(
        periods=[
            ForecastPeriod(
                name=n, temperature=t, temperature_unit="C", temperature_low=lo, wind_speed=w
            )
            for n, t, lo, w in [
                ("Tonight", 10.0, None, ""),
                ("Sunday", 15.0, 8.0, "Light"),
                ("Sunday Night", 8.0, None, None),
                ("", None, None, None),
                ("Monday", 16.0, 9.0, None),
                ("Monday Night", 9.0, None, None),
                ("Tuesday", 14.0, None, None),
                ("Tuesday Night", 7.0, None, None),
                ("Wednesday", 12.0, None, None),
            ]
        ],
        summary="",
    )
    data = WeatherData(
        location=NOWHERE,
        current=current,
        hourly_forecast=hourly,
        forecast=forecast,
        minutely_precipitation=MinutelyPrecipitationForecast(summary="Clear for the hour."),
        source_attribution=SourceAttribution(
            field_sources={
                "condition": "openmeteo",
                "hourly_source": "customsource",
                "hourly_summary": "pirateweather",
            },
            contributing_sources={"openmeteo", "customsource"},
        ),
        incomplete_sections={"hourly"},
        stale=True,
    )
    data.hourly_forecast.periods[0].short_forecast = "Mostly Clear"
    return data, now


def mobility_case() -> tuple[WeatherData, datetime]:
    now = at("2026-06-01T12:00:00+00:00")
    start = at("2026-06-01T12:00:00+00:00")
    minutely = MinutelyPrecipitationForecast(
        summary="Rain starting in 20 min.",
        points=[
            MinutelyPrecipitationPoint(
                time=start + timedelta(minutes=m),
                precipitation_intensity=0.0 if m < 20 else 0.4,
                precipitation_probability=0.1 if m < 20 else 0.8,
            )
            for m in range(61)
        ],
    )
    hourly = HourlyForecast(
        periods=[
            HourlyForecastPeriod(
                start_time=start + timedelta(minutes=30 + 30 * i),
                temperature=60.0,
                short_forecast="Showers",
                wind_gust_mph=[10.0, 18.0, 31.0, 50.0][i],
                visibility_miles=[8.0, 4.4, 5.0, 1.0][i],
                precipitation_probability=70.0,
            )
            for i in range(4)
        ],
        generated_at=start + timedelta(minutes=5),
    )
    data = WeatherData(
        location=TORONTO,
        current=CurrentConditions(temperature_f=60.0, condition="Cloudy", visibility_miles=9.0),
        hourly_forecast=hourly,
        forecast=Forecast(periods=[ForecastPeriod(name="Today", temperature=64.0)]),
        minutely_precipitation=minutely,
        source_attribution=SourceAttribution(
            field_sources={"condition": "nws", "minutely_precipitation": "pirateweather"},
            contributing_sources={"nws", "pirateweather"},
            failed_sources={"openmeteo"},
        ),
    )
    return data, now


def fog_pressure_case() -> tuple[WeatherData, datetime]:
    now = at("2026-11-12T08:00:00-08:00")
    tz = ZoneInfo("America/Los_Angeles")
    current = CurrentConditions(
        temperature_f=48.4,
        temperature_c=9.1,
        condition="Fog",
        humidity=99,
        wind_speed_mph=0.3,
        wind_speed_kph=0.5,
        wind_direction="S",
        pressure_in=30.12,
        pressure_mb=1020.0,
        visibility_miles=0.12,
        visibility_km=0.2,
        uv_index=0.0,
        feels_like_f=48.0,
        snow_depth_in=0.0,
        frost_risk="none",
    )
    hourly = HourlyForecast(
        periods=[
            HourlyForecastPeriod(
                start_time=datetime(2026, 11, 12, 8, tzinfo=tz) + timedelta(hours=i),
                temperature=48.0 + i,
                short_forecast="Fog",
                pressure_in=30.12 - 0.011 * i,
                pressure_mb=1020.0 - 0.4 * i,
            )
            for i in range(8)
        ]
    )
    alerts = WeatherAlerts(
        alerts=[
            WeatherAlert(
                title="Dense Fog Advisory",
                description="Visibility a quarter mile or less.",
                event="Dense Fog Advisory",
                severity="Moderate",
                urgency="Expected",
                expires=at("2026-11-12T11:00:00-08:00"),
            )
        ]
    )
    data = WeatherData(location=SEATTLE, current=current, hourly_forecast=hourly, alerts=alerts)
    return data, now


def environment_partial() -> tuple[WeatherData, datetime]:
    """Pollen without air quality, then a pollutant-only reading."""
    current = CurrentConditions(
        temperature_f=55.0, condition="Partly Cloudy", humidity=35, wind_speed_mph=18.0
    )
    env = EnvironmentalConditions(
        pollen_index=6.4,
        pollen_primary_allergen="Ragweed",
        air_quality_pollutant="nh3_x",
        sources=["Open-Meteo"],
        uv_index=2.0,
    )
    data = WeatherData(location=TORONTO, current=current, environmental=env)
    return data, at("2026-09-01T12:00:00-04:00")


CASES = {
    "nws_nyc": nws_nyc,
    "nws_alaska": nws_alaska,
    "openmeteo_nyc": openmeteo_nyc,
    "openmeteo_london": openmeteo_london,
    "openmeteo_celsius_extended": openmeteo_celsius_extended,
    "openmeteo_alaska": openmeteo_alaska,
    "pirate_nyc": lambda: pirate("minutely_nyc", NYC, "2026-03-18T19:50:00-04:00"),
    "pirate_london": lambda: pirate("current_london", LONDON, "2026-03-18T23:50:00+00:00"),
    "pirate_tromso": lambda: pirate("alerts_tromso", TROMSO, "2026-03-19T12:00:00+01:00"),
    "winter_storm": winter_storm,
    "summer_heat": summer_heat,
    "aviation": aviation_case,
    "aviation_decoded_only": aviation_decoded_only,
    "empty": empty_case,
    "sparse": sparse_case,
    "mobility": mobility_case,
    "fog_pressure": fog_pressure_case,
    "environment_partial": environment_partial,
}

VARIANTS: list[dict] = [
    {},
    {"temperature_unit": "f"},
    {"temperature_unit": "c"},
    {"temperature_unit": "auto"},
    {"temperature_unit": "auto", "wind_speed_unit": "m/s"},
    {"temperature_unit": "both", "wind_speed_unit": "kph"},
    {
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "verbosity_level": "detailed",
        "show_impact_summaries": True,
    },
    {"verbosity_level": "minimal", "round_values": True},
    {"verbosity_level": "detailed", "time_format_12hour": False, "show_timezone_suffix": True},
    {"time_display_mode": "utc", "show_timezone_suffix": True},
    {"time_display_mode": "both", "show_timezone_suffix": True, "time_format_12hour": False},
    {"forecast_time_reference": "user_local", "show_timezone_suffix": True},
    {
        "show_dewpoint": False,
        "show_visibility": False,
        "show_uv_index": False,
        "show_pressure_trend": False,
        "show_seasonal_data": False,
    },
    {
        "severe_weather_override": True,
        "category_order": [
            "uv_index",
            "visibility_clouds",
            "humidity_pressure",
            "wind",
            "precipitation",
            "temperature",
        ],
    },
    {"severe_weather_override": True, "show_impact_summaries": True, "temperature_unit": "celsius"},
    {"forecast_duration_days": 3, "hourly_forecast_hours": 12, "round_values": True},
    {
        "forecast_duration_days": 16,
        "hourly_forecast_hours": 48,
        "date_format": "eu",
        "time_display_mode": "both",
    },
]

TRAY_FORMATS = [
    "{temp} {condition}",
    "{location}: {temp} (feels like {feels_like}) {wind} {humidity}",
    "{high}/{low} {precip} {precip_chance}% UV {uv} {visibility} {pressure} {alert}",
    "{temp_f} {temp_c} {wind_dir} {wind_speed} {unknown}",
    "Feels like: {feels_like} | {temp}",
    "{temp",
    "",
    "Error: {temp}",
    "{location} {condition} {wind} {location} {condition} {wind} {location} {condition} {wind} {location}",
]


def tray_outputs(settings: AppSettings, data: WeatherData) -> dict:
    updater = TaskbarIconUpdater(
        text_enabled=True,
        temperature_unit=settings.temperature_unit,
        wind_speed_unit=settings.wind_speed_unit,
        round_values=settings.round_values,
    )
    out = {}
    for fmt in TRAY_FORMATS:
        updater.format_string = fmt
        out[fmt] = {
            "tooltip": updater.format_tooltip(data, data.location.name),
            "preview": updater.build_preview(fmt, data, data.location.name),
            "sample_preview": updater.build_preview(fmt, None, None),
        }
    return out


def generate_cases() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, builder in CASES.items():
        # Parse under a plausible clock so parser-side "now" reads are stable too.
        freeze(datetime(2026, 1, 1, tzinfo=UTC))
        data, now = builder()
        freeze(now.astimezone(UTC))
        normalise(data, location_zone(data.location))
        doc = {
            "name": name,
            "now": now.astimezone(UTC).isoformat(),
            "local_tz": LOCAL_TZ,
            "weather_data": to_json(data),
            "variants": [],
        }
        for overrides in VARIANTS:
            settings = AppSettings(**overrides)
            presenter = WeatherPresenter(settings)
            variant = {
                "settings": overrides,
                "presentation": to_json(presenter.present(data)),
                "tray": tray_outputs(settings, data),
            }
            if not overrides:
                variant["present_current"] = to_json(
                    presenter.present_current(
                        data.current,
                        data.location,
                        environmental=data.environmental,
                        trends=data.trend_insights,
                        hourly_forecast=data.hourly_forecast,
                        alerts=data.alerts,
                    )
                )
                variant["present_forecast"] = to_json(
                    presenter.present_forecast(
                        data.forecast,
                        data.location,
                        hourly_forecast=data.hourly_forecast,
                        marine=data.marine,
                        confidence=data.forecast_confidence,
                        mobility_briefing="Stay dry.",
                    )
                )
                variant["present_alerts"] = to_json(
                    presenter.present_alerts(data.alerts, data.location)
                )
            doc["variants"].append(variant)
        path = OUT / f"{name}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
        print(f"wrote {path.name}")


def taf_test_inputs(function: str) -> list[str]:
    """Return the string literals the Python TAF tests pass to ``function`` (and ``raw = ...``)."""
    tree = ast.parse((Path.cwd() / "tests" / "test_taf_decoder.py").read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == function
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            found.append(node.args[0].value)
        if (
            function == "decode_taf_text"
            and isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "raw" for t in node.targets)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            found.append(node.value.value)
    return list(dict.fromkeys(found))


def generate_helpers() -> None:
    """Standalone helpers: TAF decoding, date formats, placeholder parsing."""
    tafs = [
        "",
        "TAF KJFK",
        "TAF KJFK NIL=",
        "TAF KORD 251130Z 2512/2618 27015G25KT P6SM FEW050 SCT250 "
        "FM251800 29012KT P6SM SKC "
        "FM260200 VRB03KT 5SM BR OVC008 TEMPO 2606/2610 1SM -DZ BR OVC004",
        "TAF EGLL 251100Z 2512/2618 24012KT 9999 SCT030 BECMG 2515/2518 27008KT "
        "PROB30 TEMPO 2600/2606 3000 SHRA BKN014 PROB40 2612/2615 0800 FG",
        "TAF LFPG 251100Z 2512/2618 36005MPS CAVOK TEMPO 2514/2518 VCTS FZUP BLSN +UP DRSA",
        "KSEA 021720Z 0218/0324 00000KT M1/4SM VV001 = RMK",
        "TAF CYYZ 251140Z 2512/2612 1 1/2SM 2 1/4SM OVC/// BKN020/// 3/0SM 1/2/3SM P",
        "TAF KXYZ 251140Z FM2 BECMG TEMPOX PROB3 2512/2612 18005KMH 1800 ==",
    ]
    date_values = [
        at("2026-01-05T00:05:00-05:00"),
        at("2026-07-14T13:45:00+02:00"),
        datetime(2026, 12, 31, 9, 7),
    ]
    dates = []
    for value in date_values:
        for style in ["iso", "us_short", "us_long", "eu", "bogus"]:
            for twelve in [True, False]:
                dates.append(
                    {
                        "value": value.isoformat(),
                        "style": style,
                        "time_12hour": twelve,
                        "date": format_date(value, style),
                        "datetime": format_datetime(value, style, twelve),
                    }
                )
    parser = FormatStringParser()
    formats = [
        "",
        "{temp} {condition}",
        "{temp",
        "{bogus} and {temp_f}",
        "{{temp}}",
        "{a b} {Temp}",
    ]
    placeholders = [
        {
            "format": fmt,
            "placeholders": parser.get_placeholders(fmt),
            "valid": list(parser.validate_format_string(fmt)),
            "formatted": parser.format_string(fmt, {"temp": "72F", "condition": "{temp}"}),
        }
        for fmt in formats
    ]
    tafs += taf_test_inputs("decode_taf_text")
    elements = {
        name: [{"token": t, "decoded": fn(t)} for t in taf_test_inputs(name)]
        for name, fn in [
            ("_decode_wind", _decode_wind),
            ("_decode_visibility", _decode_visibility),
            ("_decode_weather", _decode_weather),
            ("_decode_cloud", _decode_cloud),
        ]
    }
    doc = {
        "taf": [{"raw": raw, "decoded": decode_taf_text(raw)} for raw in dict.fromkeys(tafs)],
        "taf_elements": elements,
        "dates": dates,
        "placeholders": placeholders,
        "placeholder_help": FormatStringParser.get_supported_placeholders_help(),
    }
    (OUT / "_helpers.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=0) + "\n", encoding="utf-8"
    )
    print("wrote _helpers.json")


if __name__ == "__main__":
    generate_cases()
    generate_helpers()
