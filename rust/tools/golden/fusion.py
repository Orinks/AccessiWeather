"""Golden outputs for data fusion, thermal comfort, alert aggregation/lifecycle,
forecast confidence and trend insights.

Writes rust/testdata/golden/{fusion,thermal,alerts,confidence,trends}/*.json.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from common import frozen_datetime, jsonable, write

import accessiweather.alert_lifecycle as alert_lifecycle
import accessiweather.models.alerts as alerts_module
import accessiweather.weather_client_trends as trends
from accessiweather.config.source_priority import SourcePriorityConfig
from accessiweather.forecast_confidence import calculate_forecast_confidence
from accessiweather.models.alerts import WeatherAlert, WeatherAlerts
from accessiweather.models.weather import (
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    SourceAttribution,
    SourceData,
    WeatherData,
)
from accessiweather.thermal_comfort import (
    calculate_heat_index_f,
    calculate_wind_chill_f,
    sanitize_thermal_comfort_readings,
)
from accessiweather.weather_client_alerts import AlertAggregator
from accessiweather.weather_client_fusion import DataFusionEngine

FETCH = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
NOW = datetime(2026, 7, 15, 16, 0, tzinfo=UTC)
EDT = timezone(timedelta(hours=-4))

US = Location(name="New York", latitude=40.7, longitude=-74.0, country_code="US")
INTL = Location(name="London", latitude=51.5, longitude=-0.1, country_code="GB")
US_NO_CC = Location(name="Chicago", latitude=41.8, longitude=-87.6)
INTL_NO_CC = Location(name="Tokyo", latitude=35.7, longitude=139.7)
VICTORIA = Location(name="Victoria", latitude=48.4284, longitude=-123.3656)


def src(name, current=None, forecast=None, hourly=None, success=True, error=None, alerts=None):
    return SourceData(
        source=name,
        current=current,
        forecast=forecast,
        hourly_forecast=hourly,
        alerts=alerts,
        fetch_time=FETCH,
        success=success,
        error=error,
    )


CC = CurrentConditions


# ---------------------------------------------------------------------------
# merge_current_conditions
# ---------------------------------------------------------------------------

rich_nws = CC(
    temperature_f=72.0,
    temperature_c=22.2,
    condition="Partly Cloudy",
    humidity=None,
    dewpoint_f=None,
    wind_speed_mph=10.0,
    wind_direction="NW",
    pressure_in=30.01,
    visibility_miles=10.0,
    uv_index=None,
    sunrise_time=datetime(2026, 7, 15, 5, 40, tzinfo=EDT),
    snow_depth_in=None,
    precipitation_type=["rain"],
)
rich_om = CC(
    temperature_f=71.0,
    temperature_c=21.7,
    condition="Mainly clear",
    humidity=55,
    dewpoint_c=12.5,
    wind_speed_kph=18.0,
    wind_gust_kph=35.0,
    wind_direction="WNW",
    pressure_mb=1016.2,
    feels_like_c=21.0,
    uv_index=6.5,
    cloud_cover=40.0,
    precipitation_mm=0.2,
    sunrise_time=datetime(2026, 7, 15, 5, 41, tzinfo=EDT),
    sunset_time=datetime(2026, 7, 15, 20, 25, tzinfo=EDT),
    snow_depth_cm=3.0,
    freezing_level_m=4200.0,
    moon_phase="Waxing Gibbous",
    frost_risk="None",
    severe_weather_risk=10,
)
rich_pw = CC(
    temperature_f=73.5,
    condition="Humid",
    humidity=60,
    wind_speed_mph=11.0,
    wind_gust_mph=19.0,
    visibility_km=16.0,
    feels_like_f=76.0,
    uv_index=7.0,
    precipitation_in=0.01,
    moonrise_time=datetime(2026, 7, 15, 14, 2, tzinfo=EDT),
    heat_index_f=74.0,
)

current_cases = [
    ("no_sources", US, None, []),
    ("all_failed", US, None, [src("nws", success=False, error="timeout")]),
    (
        "mix_failed_and_valid",
        US,
        None,
        [src("nws", current=CC(temperature_f=70.0)), src("openmeteo", success=False, error="t")],
    ),
    ("single_source", US, None, [src("nws", current=CC(temperature_f=72.0, condition="Clear"))]),
    (
        "priority_order_us",
        US,
        None,
        [
            src("openmeteo", current=CC(condition="Clear")),
            src("nws", current=CC(condition="Sunny")),
        ],
    ),
    (
        "priority_order_international",
        INTL,
        None,
        [
            src("pirateweather", current=CC(condition="Overcast")),
            src("openmeteo", current=CC(condition="Rainy")),
        ],
    ),
    (
        "fallback_when_primary_has_none",
        US,
        None,
        [
            src("nws", current=CC(temperature_f=70.0, humidity=None)),
            src("openmeteo", current=CC(temperature_f=68.0, humidity=55)),
        ],
    ),
    (
        "empty_condition_falls_back",
        US,
        None,
        [
            src("nws", current=CC(temperature_f=70.0, condition="")),
            src("openmeteo", current=CC(temperature_f=68.0, condition="Partly Cloudy")),
        ],
    ),
    (
        "placeholder_conditions_fall_back",
        US,
        None,
        [
            src("nws", current=CC(temperature_f=70.0, condition=" N/A ")),
            src("openmeteo", current=CC(temperature_f=68.0, condition="unknown")),
            src("pirateweather", current=CC(temperature_f=69.0, condition="Clear")),
        ],
    ),
    (
        "whitespace_wind_direction_skipped",
        US,
        None,
        [
            src("nws", current=CC(temperature_f=70.0, wind_direction="  ")),
            src("openmeteo", current=CC(temperature_f=68.0, wind_direction="SW")),
        ],
    ),
    (
        "unknown_source_sorted_last",
        US,
        None,
        [
            src("mystery_api", current=CC(condition="Unknown Provider")),
            src("nws", current=CC(condition="NWS Clear")),
        ],
    ),
    (
        "per_field_priority_override",
        US,
        {"field_priorities": {"humidity": ["openmeteo", "nws"]}},
        [src("nws", current=CC(humidity=40)), src("openmeteo", current=CC(humidity=55))],
    ),
    (
        "none_current_filtered",
        US,
        None,
        [src("nws", current=None), src("openmeteo", current=CC(temperature_f=65.0))],
    ),
    (
        "visibility_priority_source",
        US,
        None,
        [
            src("openmeteo", current=CC(visibility_miles=10.0, visibility_km=16.1)),
            src("nws", current=CC(visibility_miles=0.25, visibility_km=0.4)),
        ],
    ),
    (
        "visibility_units_from_winning_source",
        US,
        None,
        [
            src("openmeteo", current=CC(visibility_km=5.0)),
            src("nws", current=CC(visibility_miles=0.5)),
        ],
    ),
    (
        "visibility_km_only_winner",
        INTL,
        None,
        [
            src("openmeteo", current=CC(visibility_km=3.2)),
            src("pirateweather", current=CC(visibility_miles=2.0)),
        ],
    ),
    (
        "temperature_group_aligned",
        US,
        None,
        [
            src("openmeteo", current=CC(temperature_c=10.0)),
            src("nws", current=CC(temperature_f=72.0)),
        ],
    ),
    (
        "pressure_group_aligned",
        US,
        None,
        [src("openmeteo", current=CC(pressure_mb=990.0)), src("nws", current=CC(pressure_in=30.0))],
    ),
    (
        "wind_speed_group_override",
        US,
        {"field_priorities": {"wind_speed": ["openmeteo", "nws"]}},
        [
            src("nws", current=CC(wind_speed_mph=12.0)),
            src("openmeteo", current=CC(wind_speed_kph=20.0)),
        ],
    ),
    (
        "feels_like_falls_back",
        US,
        None,
        [
            src("nws", current=CC(temperature_f=72.0, temperature_c=22.2)),
            src("openmeteo", current=CC(temperature_f=70.0, temperature_c=21.1, feels_like_c=19.0)),
        ],
    ),
    (
        "us_strips_openmeteo_snow_depth",
        US,
        None,
        [
            src("nws", current=CC(temperature_f=32.0)),
            src(
                "openmeteo", current=CC(temperature_f=31.0, snow_depth_in=17.3, snow_depth_cm=44.0)
            ),
        ],
    ),
    (
        "us_strips_pirateweather_snow_depth",
        US,
        None,
        [
            src("nws", current=CC(temperature_f=32.0)),
            src(
                "pirateweather",
                current=CC(temperature_f=31.5, snow_depth_in=12.0, snow_depth_cm=30.5),
            ),
        ],
    ),
    (
        "us_keeps_nws_snow_depth",
        US,
        None,
        [src("nws", current=CC(temperature_f=28.0, snow_depth_in=5.0, snow_depth_cm=12.7))],
    ),
    (
        "international_keeps_snow_depth",
        INTL,
        None,
        [src("openmeteo", current=CC(temperature_f=25.0, snow_depth_in=8.0, snow_depth_cm=20.3))],
    ),
    (
        "conflict_detected",
        US,
        None,
        [
            src("nws", current=CC(temperature_f=70.0)),
            src("openmeteo", current=CC(temperature_f=80.0)),
        ],
    ),
    (
        "conflict_within_threshold",
        US,
        None,
        [
            src("nws", current=CC(temperature_f=70.0)),
            src("openmeteo", current=CC(temperature_f=73.0)),
        ],
    ),
    (
        "conflict_custom_threshold",
        US,
        {"temperature_conflict_threshold": 2.0},
        [
            src("nws", current=CC(temperature_f=70.0)),
            src("openmeteo", current=CC(temperature_f=73.0)),
        ],
    ),
    (
        "conflict_three_sources_celsius",
        INTL,
        None,
        [
            src("pirateweather", current=CC(temperature_c=30.0, temperature_f=86.0)),
            src("nws", current=CC(temperature_c=20.0)),
            src("openmeteo", current=CC(temperature_c=21.0, temperature_f=69.8)),
        ],
    ),
    (
        "gust_higher_than_speed_kept",
        INTL,
        None,
        [
            src("pirateweather", current=CC(wind_speed_mph=14.0, wind_speed_kph=22.5)),
            src("openmeteo", current=CC(wind_gust_mph=20.0, wind_gust_kph=32.2)),
        ],
    ),
    (
        "gust_equal_to_speed_kept",
        INTL,
        None,
        [
            src("pirateweather", current=CC(wind_speed_mph=14.0, wind_speed_kph=22.5)),
            src("openmeteo", current=CC(wind_gust_mph=14.0, wind_gust_kph=22.5)),
        ],
    ),
    (
        "gust_lower_than_speed_discarded",
        INTL,
        None,
        [
            src("pirateweather", current=CC(wind_speed_mph=14.0, wind_speed_kph=22.5)),
            src("openmeteo", current=CC(wind_gust_mph=11.0, wind_gust_kph=17.7)),
        ],
    ),
    (
        "gust_without_speed_kept",
        INTL,
        None,
        [src("pirateweather", current=CC(wind_gust_mph=20.0, wind_gust_kph=32.2))],
    ),
    (
        "thermal_incoherent_feels_like_dropped",
        US,
        None,
        [
            src("nws", current=CC(temperature_f=85.0, humidity=30)),
            src("openmeteo", current=CC(temperature_f=84.0, feels_like_f=99.0, heat_index_f=98.0)),
        ],
    ),
    (
        "thermal_cold_feels_like_becomes_wind_chill",
        US,
        None,
        [
            src("nws", current=CC(temperature_f=30.0, wind_speed_mph=15.0)),
            src("openmeteo", current=CC(temperature_f=31.0, feels_like_f=19.0)),
        ],
    ),
    (
        "thermal_heat_index_fills_feels_like",
        US,
        None,
        [
            src("nws", current=CC(temperature_f=92.0, humidity=60)),
            src("pirateweather", current=CC(temperature_f=91.0, heat_index_f=104.0)),
        ],
    ),
    (
        "thermal_wind_chill_above_temp_dropped",
        US,
        None,
        [src("nws", current=CC(temperature_f=40.0, wind_chill_f=45.0, feels_like_f=38.0))],
    ),
    (
        "rich_us_three_sources",
        US,
        None,
        [src("nws", rich_nws), src("openmeteo", rich_om), src("pirateweather", rich_pw)],
    ),
    (
        "rich_intl_three_sources",
        INTL,
        None,
        [src("pirateweather", rich_pw), src("openmeteo", rich_om), src("nws", rich_nws)],
    ),
    (
        "rich_us_no_country",
        US_NO_CC,
        None,
        [src("openmeteo", rich_om), src("pirateweather", rich_pw)],
    ),
    (
        "rich_intl_no_country",
        INTL_NO_CC,
        None,
        [src("openmeteo", rich_om), src("pirateweather", rich_pw)],
    ),
    (
        "victoria_is_international",
        VICTORIA,
        None,
        [src("nws", rich_nws), src("openmeteo", rich_om)],
    ),
    (
        "custom_defaults_order",
        US,
        {"us_default": ["pirateweather", "nws"], "international_default": ["pirateweather"]},
        [src("nws", rich_nws), src("openmeteo", rich_om), src("pirateweather", rich_pw)],
    ),
]


def make_config(overrides):
    return SourcePriorityConfig(**(overrides or {}))


def current_golden():
    out = []
    for name, location, config, sources in current_cases:
        engine = DataFusionEngine(make_config(config))
        inputs = jsonable(sources)
        merged, attribution = engine.merge_current_conditions(sources, location)
        out.append(
            {
                "name": name,
                "location": location,
                "config": make_config(config).to_dict(),
                "sources": inputs,
                "current": merged,
                "attribution": attribution,
            }
        )
    write("fusion", "merge_current", out)


# ---------------------------------------------------------------------------
# merge_forecasts / merge_hourly_forecasts
# ---------------------------------------------------------------------------

START = datetime(2026, 7, 15, 10, tzinfo=UTC)


def fc(label, temp=55.0, summary=None, periods=1):
    return Forecast(
        periods=[
            ForecastPeriod(
                name=f"{label} {i}",
                temperature=temp + i,
                start_time=START + timedelta(hours=12 * i),
                detailed_forecast=f"{label} details {i}",
            )
            for i in range(periods)
        ],
        generated_at=START,
        summary=summary,
    )


def hr(label, temp=65.0, summary=None, pressure_mb=None, pressure_in=None, offset_minutes=0, n=3):
    return HourlyForecast(
        periods=[
            HourlyForecastPeriod(
                start_time=START + timedelta(hours=i, minutes=offset_minutes),
                temperature=temp + i,
                short_forecast=label,
                pressure_mb=None if pressure_mb is None else pressure_mb + i,
                pressure_in=None if pressure_in is None else pressure_in + i / 100,
            )
            for i in range(n)
        ],
        generated_at=START,
        summary=summary,
    )


forecast_cases = [
    ("no_sources", US, 7, []),
    ("all_failed", US, 7, [src("nws", success=False)]),
    (
        "us_prefers_nws",
        US,
        7,
        [src("openmeteo", forecast=fc("OM")), src("nws", forecast=fc("NWS"))],
    ),
    (
        "us_requested_8_prefers_openmeteo",
        US,
        8,
        [src("nws", forecast=fc("NWS")), src("openmeteo", forecast=fc("OM"))],
    ),
    (
        "us_extended_falls_back_to_nws",
        US,
        15,
        [src("nws", forecast=fc("NWS")), src("pirateweather", forecast=fc("PW"))],
    ),
    (
        "intl_prefers_openmeteo",
        INTL,
        7,
        [src("pirateweather", forecast=fc("PW")), src("openmeteo", forecast=fc("OM"))],
    ),
    (
        "intl_ignores_nws",
        INTL,
        7,
        [src("nws", forecast=fc("NWS")), src("pirateweather", forecast=fc("PW"))],
    ),
    ("fallback_to_available", US, 7, [src("openmeteo", forecast=fc("OM"))]),
    (
        "fallback_unknown_source",
        US,
        7,
        [src("mystery_api", forecast=fc("MY")), src("other", forecast=fc("OT"))],
    ),
    (
        "none_forecast_filtered",
        US,
        7,
        [src("nws", forecast=None), src("openmeteo", forecast=fc("OM"))],
    ),
    (
        "extended_prefers_openmeteo_full_range",
        US,
        15,
        [
            src("nws", forecast=fc("NWS", periods=14)),
            src("openmeteo", forecast=fc("OM", periods=15)),
        ],
    ),
    (
        "pirate_summary_preserved",
        INTL,
        7,
        [
            src("openmeteo", forecast=fc("OM")),
            src("pirateweather", forecast=fc("PW", summary="Rain later this evening.")),
        ],
    ),
    (
        "own_summary_kept",
        INTL,
        7,
        [
            src("openmeteo", forecast=fc("OM", summary="Open-Meteo summary")),
            src("pirateweather", forecast=fc("PW", summary="Rain later this evening.")),
        ],
    ),
    (
        "pirate_selected_summary_attribution",
        US,
        7,
        [
            src("pirateweather", forecast=fc("PW", summary="Clear all week.")),
            src("nws", success=False),
        ],
    ),
    (
        "failed_pirate_summary_ignored",
        INTL,
        7,
        [
            src("openmeteo", forecast=fc("OM")),
            src("pirateweather", forecast=fc("PW", summary="x"), success=False),
        ],
    ),
]

hourly_cases = [
    ("no_sources", US, []),
    ("all_failed", US, [src("nws", success=False)]),
    ("us_prefers_nws", US, [src("openmeteo", hourly=hr("OM")), src("nws", hourly=hr("NWS"))]),
    (
        "intl_prefers_openmeteo",
        INTL,
        [src("pirateweather", hourly=hr("PW")), src("openmeteo", hourly=hr("OM"))],
    ),
    ("fallback_unknown_source", US, [src("mystery_api", hourly=hr("MY"))]),
    (
        "pirate_summary_preserved",
        INTL,
        [
            src("openmeteo", hourly=hr("OM", pressure_mb=1010.0)),
            src("pirateweather", hourly=hr("PW", summary="Light rain developing overnight.")),
        ],
    ),
    (
        "selected_keeps_own_pressure",
        US,
        [
            src("openmeteo", hourly=hr("OM", pressure_mb=1008.0)),
            src("nws", hourly=hr("NWS", pressure_mb=1012.0)),
        ],
    ),
    (
        "overlay_pressure_from_openmeteo",
        US,
        [
            src(
                "openmeteo",
                hourly=hr("OM", pressure_mb=1007.5, pressure_in=29.75, offset_minutes=30),
            ),
            src("nws", hourly=hr("NWS")),
        ],
    ),
    (
        "overlay_prefers_openmeteo_over_pirate",
        US,
        [
            src("pirateweather", hourly=hr("PW", pressure_mb=1001.0)),
            src("nws", hourly=hr("NWS")),
            src("openmeteo", hourly=hr("OM", pressure_mb=1005.0, offset_minutes=-45)),
        ],
    ),
    (
        "overlay_from_pirate_when_only_option",
        INTL,
        [
            src("openmeteo", hourly=hr("OM")),
            src("pirateweather", hourly=hr("PW", pressure_in=29.9, offset_minutes=90)),
        ],
    ),
    (
        "overlay_too_far_apart",
        US,
        [
            src("nws", hourly=hr("NWS")),
            src("openmeteo", hourly=hr("OM", pressure_mb=1003.0, offset_minutes=95, n=1)),
        ],
    ),
    (
        "overlay_partial_periods",
        US,
        [
            src(
                "nws",
                hourly=HourlyForecast(
                    periods=[
                        HourlyForecastPeriod(
                            start_time=START, temperature=60.0, pressure_mb=1011.0
                        ),
                        HourlyForecastPeriod(
                            start_time=START + timedelta(hours=1), temperature=61.0
                        ),
                        HourlyForecastPeriod(
                            start_time=START + timedelta(hours=6), temperature=62.0
                        ),
                    ]
                ),
            ),
            src("openmeteo", hourly=hr("OM", pressure_mb=1000.0, n=2)),
        ],
    ),
]


def forecast_golden():
    engine = DataFusionEngine()
    out = []
    for name, location, days, sources in forecast_cases:
        inputs = jsonable(sources)
        merged, field_sources = engine.merge_forecasts(sources, location, requested_days=days)
        out.append(
            {
                "name": name,
                "location": location,
                "requested_days": days,
                "sources": inputs,
                "forecast": merged,
                "field_sources": field_sources,
            }
        )
    write("fusion", "merge_forecasts", out)

    out = []
    for name, location, sources in hourly_cases:
        inputs = jsonable(sources)
        merged, field_sources = engine.merge_hourly_forecasts(sources, location)
        out.append(
            {
                "name": name,
                "location": location,
                "sources": inputs,
                "hourly": merged,
                "field_sources": field_sources,
            }
        )
    write("fusion", "merge_hourly", out)


# ---------------------------------------------------------------------------
# thermal comfort
# ---------------------------------------------------------------------------


def thermal_golden():
    sanitize = []
    temps = [None, 20.0, 45.0, 79.0, 85.0, 95.0]
    humidities = [None, 20, 50, 90]
    apparent = [None, 10.0, 44.0, 83.0, 88.0, 110.0]
    for temp in temps:
        for humidity in humidities:
            for feels in apparent:
                for heat in (None, 90.0, 120.0):
                    for chill in (None, 15.0, 50.0):
                        kwargs = {
                            "temperature_f": temp,
                            "humidity": humidity,
                            "feels_like_f": feels,
                            "heat_index_f": heat,
                            "wind_chill_f": chill,
                        }
                        sanitize.append(
                            {"input": kwargs, "output": sanitize_thermal_comfort_readings(**kwargs)}
                        )
    celsius = [
        {"temperature_f": None, "temperature_c": 30.0, "humidity": 70, "feels_like_c": 36.0},
        {"temperature_f": None, "temperature_c": -5.0, "humidity": 70, "wind_chill_c": -12.0},
        {"temperature_f": None, "temperature_c": 25.0, "humidity": None, "heat_index_c": 30.0},
    ]
    for kwargs in celsius:
        sanitize.append({"input": kwargs, "output": sanitize_thermal_comfort_readings(**kwargs)})

    heat_index = [
        {"temperature_f": t, "humidity": h, "output": calculate_heat_index_f(t, h)}
        for t in (79.9, 80.0, 84.0, 87.0, 88.0, 100.0)
        for h in (39, 40, 60, 86, 95)
    ]
    wind_chill = [
        {"temperature_f": t, "wind_speed_mph": w, "output": calculate_wind_chill_f(t, w)}
        for t in (-10.0, 20.0, 50.0, 50.1)
        for w in (3.0, 3.1, 15.0, 40.0)
    ]
    write(
        "thermal",
        "cases",
        {"sanitize": sanitize, "heat_index": heat_index, "wind_chill": wind_chill},
    )


# ---------------------------------------------------------------------------
# alert aggregation
# ---------------------------------------------------------------------------


def alert(title="Alert", event="Flood Warning", **kw):
    kw.setdefault("description", f"{title} description")
    return WeatherAlert(title=title, event=event, **kw)


def aggregate_golden():
    onset = datetime(2026, 7, 15, 14, 0, tzinfo=UTC)
    cases = [
        ("both_none", None, None, 60),
        ("empty_lists", WeatherAlerts(alerts=[]), WeatherAlerts(alerts=[]), 60),
        (
            "nws_only",
            WeatherAlerts(alerts=[alert("A"), alert("B", event="Heat Advisory")]),
            None,
            60,
        ),
        ("secondary_only", None, WeatherAlerts(alerts=[alert("P")]), 60),
        (
            "source_preserved",
            WeatherAlerts(alerts=[alert("A", source="NWS")]),
            WeatherAlerts(alerts=[alert("P", source="WMO", event="Heat")]),
            60,
        ),
        (
            "duplicates_merged",
            WeatherAlerts(
                alerts=[
                    alert(
                        "NWS Flood",
                        severity="Severe",
                        urgency="Unknown",
                        certainty="Likely",
                        headline="Flood warning",
                        instruction="Move up.",
                        onset=onset,
                        expires=onset + timedelta(hours=6),
                        sent=onset,
                        effective=onset,
                        areas=["Kings", "Queens"],
                        id="urn:nws:1",
                        message_type="Alert",
                        references=["r1"],
                        affected_zones=["NYZ075"],
                        same_codes=["036047"],
                        same_event_codes=["FFW"],
                    )
                ]
            ),
            WeatherAlerts(
                alerts=[
                    alert(
                        "PW Flood",
                        description="A much longer description from Pirate Weather about flooding.",
                        severity="Unknown",
                        urgency="Immediate",
                        certainty="Unknown",
                        headline="Flood warning for Kings County and nearby areas",
                        instruction="Move to higher ground now.",
                        onset=onset + timedelta(minutes=30),
                        areas=[" queens ", "Bronx"],
                    )
                ]
            ),
            60,
        ),
        (
            "secondary_listed_first_nws_still_base",
            WeatherAlerts(alerts=[]),
            WeatherAlerts(
                alerts=[
                    alert("PW", source="pirateweather", areas=["A"]),
                    alert("NWS", source="nws", areas=["a"], severity="Minor"),
                ]
            ),
            60,
        ),
        (
            "onset_outside_window",
            WeatherAlerts(alerts=[alert("A", onset=onset)]),
            WeatherAlerts(alerts=[alert("B", onset=onset + timedelta(minutes=61))]),
            60,
        ),
        (
            "onset_inside_custom_window",
            WeatherAlerts(alerts=[alert("A", onset=onset)]),
            WeatherAlerts(alerts=[alert("B", onset=onset + timedelta(minutes=61))]),
            90,
        ),
        (
            "one_onset_missing_still_matches",
            WeatherAlerts(alerts=[alert("A", onset=onset)]),
            WeatherAlerts(alerts=[alert("B")]),
            60,
        ),
        (
            "non_overlapping_areas",
            WeatherAlerts(alerts=[alert("A", areas=["X"])]),
            WeatherAlerts(alerts=[alert("B", areas=["Y"])]),
            60,
        ),
        (
            "different_events",
            WeatherAlerts(alerts=[alert("A", event="Flood Warning")]),
            WeatherAlerts(alerts=[alert("B", event="Flood Watch")]),
            60,
        ),
        (
            "three_way_group",
            WeatherAlerts(alerts=[alert("N1", description="short"), alert("N2", event="Other")]),
            WeatherAlerts(
                alerts=[
                    alert("P1", description="longer text here", headline="h"),
                    alert("P2", description="Ünïcødé descriptïon", headline="hh"),
                ]
            ),
            60,
        ),
    ]
    out = []
    for name, nws, secondary, window in cases:
        inputs = {"nws": jsonable(nws), "secondary": jsonable(secondary)}
        result = AlertAggregator(dedup_time_window_minutes=window).aggregate_alerts(nws, secondary)
        for a in result.alerts:
            a.areas = sorted(a.areas)  # Python unions areas through a set; order is arbitrary
        out.append({"name": name, "window_minutes": window, **inputs, "result": result})
    write("alerts", "aggregate", out)


# ---------------------------------------------------------------------------
# alert lifecycle
# ---------------------------------------------------------------------------


def lifecycle_golden():
    alert_lifecycle.datetime = frozen_datetime(NOW)
    alerts_module.datetime = frozen_datetime(NOW)

    def la(title="Test Alert", severity="Moderate", urgency="Expected", alert_id=None, **kw):
        return WeatherAlert(
            title=title,
            description=kw.pop("description", "A description."),
            severity=severity,
            urgency=urgency,
            id=alert_id,
            **kw,
        )

    def wa(*items):
        return WeatherAlerts(alerts=list(items))

    recent = NOW - timedelta(minutes=5)
    old = NOW - timedelta(hours=2)
    later = NOW + timedelta(hours=3)
    cases = [
        ("both_none", None, None, None),
        (
            "previous_none_recent_and_old",
            None,
            wa(
                la("R", alert_id="r", effective=recent),
                la("O", alert_id="o", effective=old),
                la("N", alert_id="n"),
            ),
            None,
        ),
        (
            "previous_none_onset_fallback",
            None,
            wa(la("On", alert_id="on", onset=old), la("On2", alert_id="on2", onset=recent)),
            None,
        ),
        ("new_alert", wa(), wa(la("New", alert_id="a1", effective=old)), None),
        (
            "cancelled_generic_source",
            wa(la("Gone", alert_id="g", source="VisualCrossing")),
            wa(),
            None,
        ),
        ("cancelled_no_source", wa(la("Gone", alert_id="g")), None, None),
        ("nws_cancel_unconfirmed_none", wa(la("N", alert_id="n1", source="NWS")), wa(), None),
        ("nws_cancel_confirmed", wa(la("N", alert_id="n1", source="nws")), wa(), ["n1", "other"]),
        ("nws_cancel_not_in_set", wa(la("N", alert_id="n1", source=" NWS ")), wa(), ["zzz"]),
        ("pirate_cancel_suppressed", wa(la("P", alert_id="p1", source="pirateweather")), wa(), []),
        (
            "content_change",
            wa(la("A", alert_id="x", description="old")),
            wa(la("A", alert_id="x", description="new")),
            None,
        ),
        (
            "severity_downgrade",
            wa(la("A", alert_id="x", severity="Severe")),
            wa(la("A", alert_id="x", severity="Minor")),
            None,
        ),
        (
            "urgency_change",
            wa(la("A", alert_id="x", urgency="Future")),
            wa(la("A", alert_id="x", urgency="Immediate")),
            None,
        ),
        ("identical", wa(la("A", alert_id="x")), wa(la("A", alert_id="x")), None),
        (
            "escalated",
            wa(la("A", alert_id="x", severity="Moderate")),
            wa(la("A", alert_id="x", severity="Extreme")),
            None,
        ),
        (
            "escalate_from_unrecognised",
            wa(la("A", alert_id="x", severity="Bogus")),
            wa(la("A", alert_id="x", severity="Unknown")),
            None,
        ),
        (
            "extended",
            wa(la("A", alert_id="x", expires=NOW + timedelta(hours=1))),
            wa(la("A", alert_id="x", expires=later)),
            None,
        ),
        (
            "expiry_earlier_not_extended",
            wa(la("A", alert_id="x", expires=later)),
            wa(la("A", alert_id="x", expires=NOW + timedelta(hours=1))),
            None,
        ),
        (
            "expired_alerts_ignored",
            wa(la("Old", alert_id="e1", expires=NOW - timedelta(minutes=1))),
            wa(la("Now", alert_id="e2", expires=NOW)),
            None,
        ),
        (
            "combined_summary",
            wa(
                la("Keep", alert_id="k"),
                la("Esc1", alert_id="e1", severity="Minor"),
                la("Esc2", alert_id="e2", severity="Minor"),
                la("Upd", alert_id="u", description="v1"),
                la("Ext", alert_id="x", expires=NOW + timedelta(hours=1)),
                la("Gone", alert_id="g", source="VisualCrossing"),
            ),
            wa(
                la("Keep", alert_id="k"),
                la("Esc1", alert_id="e1", severity="Severe"),
                la("Esc2", alert_id="e2", severity="Extreme"),
                la("Upd", alert_id="u", description="v2"),
                la("Ext", alert_id="x", expires=later),
                la("New1", alert_id="n1"),
                la("New2", alert_id="n2"),
            ),
            [],
        ),
        (
            "derived_ids",
            wa(
                la(
                    "T",
                    event="Wind Advisory",
                    source="NWS",
                    areas=["B", "A"],
                    headline="Wind Advisory issued",
                )
            ),
            wa(
                la(
                    "T",
                    event="Wind Advisory",
                    source="NWS",
                    areas=["A", "B"],
                    headline="Wind Advisory issued",
                    description="changed",
                ),
                la("T2", event="Heat", areas=["Z"]),
            ),
            None,
        ),
        (
            "duplicate_ids_last_wins",
            wa(la("A", alert_id="d", description="one")),
            wa(la("A", alert_id="d", description="one"), la("B", alert_id="d", description="two")),
            None,
        ),
    ]
    out = []
    for name, previous, current, cancel_ids in cases:
        inputs = {"previous": jsonable(previous), "current": jsonable(current)}
        diff = alert_lifecycle.diff_alerts(
            previous, current, confirmed_cancel_ids=None if cancel_ids is None else set(cancel_ids)
        )
        out.append(
            {
                "name": name,
                "now": NOW,
                **inputs,
                "confirmed_cancel_ids": cancel_ids,
                "diff": diff,
                "has_changes": diff.has_changes,
            }
        )
    write("alerts", "lifecycle", out)

    label_alerts = [
        la("A", alert_id="1", source="NWS", message_type="Alert"),
        la("B", alert_id="2", source="NWS", message_type="UPDATE"),
        la("C", alert_id="3", source="NWS", message_type="Cancel"),
        la("D", alert_id="4", source="NWS"),
        la("E", alert_id="5", source="nws", message_type="Alert"),
        la("F", alert_id="6", source="VisualCrossing", message_type="Alert"),
        la("G", source="NWS", message_type="alert", event="Heat", areas=["Z"]),
    ]
    write(
        "alerts",
        "labels",
        {"alerts": label_alerts, "labels": alert_lifecycle.compute_lifecycle_labels(label_alerts)},
    )


# ---------------------------------------------------------------------------
# forecast confidence
# ---------------------------------------------------------------------------


def confidence_golden():
    def s(name, temp=None, precip=None, pname="Today", success=True, periods=None):
        forecast = (
            Forecast(periods=periods)
            if periods is not None
            else Forecast(
                periods=[
                    ForecastPeriod(name=pname, temperature=temp, precipitation_probability=precip)
                ]
            )
        )
        return src(name, forecast=forecast, success=success)

    night_first = [
        ForecastPeriod(name="Tonight", temperature=50.0),
        ForecastPeriod(name="Wednesday", temperature=75.0, precipitation_probability=20.0),
    ]
    cases = [
        ("none", []),
        ("failed_only", [s("nws", 70.0, success=False)]),
        ("empty_forecast", [src("pirateweather", forecast=Forecast(periods=[]))]),
        ("single", [s("nws", 70.0)]),
        ("single_unknown_name", [s("visual_crossing", 70.0)]),
        ("two_high", [s("nws", 70.0, 20.0), s("openmeteo", 73.0, 30.0)]),
        ("two_medium_temp", [s("nws", 70.0, 20.0), s("openmeteo", 78.0, 60.0)]),
        ("two_medium_precip", [s("nws", 70.0, 20.0), s("openmeteo", 85.0, 40.0)]),
        ("two_low", [s("nws", 70.0, 0.0), s("openmeteo", 85.0, 50.0)]),
        ("temp_only_high", [s("nws", 70.0), s("openmeteo", 75.0)]),
        ("temp_only_medium", [s("nws", 70.0), s("openmeteo", 80.0)]),
        ("temp_only_low", [s("nws", 70.0), s("openmeteo", 80.5)]),
        ("one_precip_only", [s("nws", 70.0, 20.0), s("openmeteo", 90.0)]),
        (
            "three_sources",
            [s("nws", 70.0, 10.0), s("openmeteo", 71.0, 12.0), s("pirateweather", 72.0, 20.0)],
        ),
        (
            "night_period_skipped",
            [src("nws", forecast=Forecast(periods=night_first)), s("openmeteo", 76.0, 25.0)],
        ),
        (
            "all_night_periods",
            [s("nws", 50.0, pname="Tonight"), s("openmeteo", 70.0, pname="Overnight")],
        ),
        ("no_temperatures", [s("nws", None, 10.0), s("openmeteo", None, 40.0)]),
    ]
    out = []
    for name, sources in cases:
        out.append(
            {
                "name": name,
                "sources": jsonable(sources),
                "confidence": calculate_forecast_confidence(sources),
            }
        )
    write("confidence", "cases", out)


# ---------------------------------------------------------------------------
# trends
# ---------------------------------------------------------------------------


def trends_golden():
    trends.datetime = frozen_datetime(NOW)

    def hourly(temps, pressures_mb=None, pressures_in=None, step_hours=1, start=NOW):
        periods = []
        for i, temp in enumerate(temps):
            periods.append(
                HourlyForecastPeriod(
                    start_time=start + timedelta(hours=i * step_hours),
                    temperature=temp,
                    pressure_mb=None if pressures_mb is None else pressures_mb[i],
                    pressure_in=None if pressures_in is None else pressures_in[i],
                )
            )
        return HourlyForecast(periods=periods)

    def wd(current=None, hourly_fc=None, forecast=None, history=None, attribution=None):
        return WeatherData(
            location=US,
            current=current,
            hourly_forecast=hourly_fc,
            forecast=forecast,
            daily_history=history or [],
            source_attribution=attribution,
        )

    temps24 = [70.0 + i * 0.25 for i in range(30)]
    mb24 = [1015.0 - i * 0.2 for i in range(30)]
    in24 = [30.0 - i * 0.005 for i in range(30)]
    cases = [
        ("disabled", wd(CC(temperature_f=70.0), hourly(temps24)), False, 24, True),
        ("no_data", wd(), True, 24, True),
        ("temperature_rising", wd(CC(temperature_f=70.0), hourly(temps24)), True, 24, False),
        (
            "temperature_celsius",
            wd(CC(temperature_c=20.0), hourly([20.0, 20.4, 20.9, 21.0])),
            True,
            3,
            False,
        ),
        (
            "temperature_falling_strong",
            wd(CC(temperature_f=80.0), hourly([80.0, 76.0, 72.0])),
            True,
            2,
            False,
        ),
        (
            "temperature_steady",
            wd(CC(temperature_f=70.0), hourly([70.0, 70.5, 70.9])),
            True,
            2,
            False,
        ),
        (
            "pressure_mb_falling",
            wd(
                CC(temperature_f=70.0, pressure_mb=1015.0, pressure_in=29.97), hourly(temps24, mb24)
            ),
            True,
            24,
            True,
        ),
        (
            "pressure_in_rising",
            wd(
                CC(temperature_f=70.0, pressure_in=29.8),
                hourly(temps24, None, [29.8 + i * 0.004 for i in range(30)]),
            ),
            True,
            12,
            True,
        ),
        (
            "pressure_implausible",
            wd(
                CC(temperature_f=70.0, pressure_mb=1015.0),
                hourly([70.0] * 7, [1015.0 - i * 5 for i in range(7)]),
            ),
            True,
            6,
            True,
        ),
        (
            "pressure_steady",
            wd(
                CC(temperature_f=70.0, pressure_mb=1015.0),
                hourly([70.0] * 7, [1015.0 + i * 0.05 for i in range(7)]),
            ),
            True,
            6,
            True,
        ),
        (
            "pressure_target_too_far",
            wd(
                CC(temperature_f=70.0, pressure_mb=1015.0),
                hourly([70.0] * 3, [1015.0, 1014.0, 1013.0]),
            ),
            True,
            24,
            True,
        ),
        (
            "pressure_missing_current",
            wd(CC(temperature_f=70.0), hourly(temps24, mb24)),
            True,
            24,
            True,
        ),
        ("pressure_missing_hourly", wd(CC(temperature_f=70.0, pressure_mb=1015.0)), True, 24, True),
        (
            "pressure_hourly_without_pressure_named_source",
            wd(
                CC(temperature_f=70.0, pressure_mb=1015.0),
                hourly(temps24),
                attribution=SourceAttribution(field_sources={"hourly_source": "nws"}),
            ),
            True,
            24,
            True,
        ),
        (
            "pressure_hourly_without_pressure_unknown_source",
            wd(
                CC(temperature_f=70.0, pressure_mb=1015.0),
                hourly(temps24),
                attribution=SourceAttribution(field_sources={"hourly_source": "custom"}),
            ),
            True,
            24,
            True,
        ),
        (
            "pressure_no_attribution",
            wd(CC(temperature_f=70.0, pressure_mb=1015.0), hourly(temps24)),
            True,
            24,
            True,
        ),
        (
            "pressure_units_mismatch",
            wd(CC(temperature_f=70.0, pressure_mb=1015.0), hourly(temps24, None, in24)),
            True,
            24,
            True,
        ),
        ("pressure_current_empty", wd(CC(), hourly(temps24, mb24)), True, 24, True),
        (
            "daily_warmer",
            wd(
                CC(temperature_f=70.0),
                forecast=Forecast(periods=[ForecastPeriod(name="Today", temperature=80.0)]),
                history=[ForecastPeriod(name="Yesterday", temperature=74.4)],
            ),
            True,
            24,
            False,
        ),
        (
            "daily_cooler_celsius",
            wd(
                None,
                forecast=Forecast(
                    periods=[ForecastPeriod(name="Today", temperature=18.0, temperature_unit="C")]
                ),
                history=[ForecastPeriod(name="Yesterday", temperature=20.5, temperature_unit="C")],
            ),
            True,
            24,
            False,
        ),
        (
            "daily_similar",
            wd(
                None,
                forecast=Forecast(periods=[ForecastPeriod(name="Today", temperature=70.0)]),
                history=[ForecastPeriod(name="Yesterday", temperature=71.0)],
            ),
            True,
            24,
            False,
        ),
        (
            "daily_equal",
            wd(
                None,
                forecast=Forecast(periods=[ForecastPeriod(name="Today", temperature=70.0)]),
                history=[ForecastPeriod(name="Yesterday", temperature=70.0)],
            ),
            True,
            24,
            False,
        ),
        (
            "everything",
            wd(
                CC(temperature_f=60.0, pressure_mb=1010.0),
                hourly(
                    [60.0, 61.0, 62.0, 63.0, 64.0, 65.0, 66.0],
                    [1010.0, 1009.0, 1008.0, 1007.0, 1006.0, 1005.0, 1004.0],
                ),
                forecast=Forecast(periods=[ForecastPeriod(name="Today", temperature=66.0)]),
                history=[ForecastPeriod(name="Yesterday", temperature=60.0)],
            ),
            True,
            6,
            True,
        ),
        (
            "hourly_before_now",
            wd(CC(temperature_f=60.0), hourly([50.0, 55.0, 58.0], start=NOW - timedelta(hours=10))),
            True,
            6,
            True,
        ),
    ]
    out = []
    for name, weather, enabled, hours, include_pressure in cases:
        inputs = jsonable(weather)
        trends.apply_trend_insights(weather, enabled, hours, include_pressure=include_pressure)
        out.append(
            {
                "name": name,
                "now": NOW,
                "weather": inputs,
                "enabled": enabled,
                "trend_hours": hours,
                "include_pressure": include_pressure,
                "insights": weather.trend_insights,
            }
        )
    write("trends", "cases", out)


if __name__ == "__main__":
    current_golden()
    forecast_golden()
    thermal_golden()
    aggregate_golden()
    lifecycle_golden()
    confidence_golden()
    trends_golden()
