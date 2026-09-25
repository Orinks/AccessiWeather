"""Golden outputs for the weather-client orchestration (automatic-mode budget
staging, single-source fetches, enrichment, alert lifecycle, offline cache
fallback and the notification poll).

Every data source is replaced by a scripted fake; the fake table, the steps
and the requests each step made are written with the resulting WeatherData
to rust/testdata/golden/client/<scenario>.json (compact, nulls dropped; each
step lists only the fakes it overrides).
"""

from __future__ import annotations

import asyncio
import copy
import tempfile
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from common import frozen_datetime, jsonable, write

import accessiweather.alert_lifecycle as alert_lifecycle
import accessiweather.cache as cache_module
import accessiweather.cache_serialization as cache_serialization
import accessiweather.models.alerts as alerts_module
import accessiweather.models.weather_forecast as forecast_module
import accessiweather.weather_client_aviation as aviation_module
import accessiweather.weather_client_base as base_module
import accessiweather.weather_client_nws as nws_module
import accessiweather.weather_client_parallel as parallel_module
import accessiweather.weather_client_trends as trends_module
from accessiweather.cache import WeatherDataCache
from accessiweather.models import AppSettings
from accessiweather.models.alerts import WeatherAlert, WeatherAlerts
from accessiweather.models.weather import (
    AviationData,
    CurrentConditions,
    EnvironmentalConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    MinutelyPrecipitationForecast,
    MinutelyPrecipitationPoint,
)
from accessiweather.pirate_weather_client import PirateWeatherApiError
from accessiweather.weather_client import WeatherClient

T0 = datetime(2026, 7, 15, 16, 0, tzinfo=UTC)
EDT = timezone(timedelta(hours=-4))

US = Location(name="New York", latitude=40.7128, longitude=-74.006, country_code="US")
US_MARINE = Location(
    name="Montauk", latitude=41.0359, longitude=-71.9545, country_code="US", marine_mode=True
)
INTL = Location(name="London", latitude=51.5074, longitude=-0.1278, country_code="GB")


class Err:
    def __init__(self, message: str):
        self.message = message


def freeze(now):
    frozen = frozen_datetime(now)
    for module in (
        alert_lifecycle,
        alerts_module,
        trends_module,
        base_module,
        forecast_module,
        parallel_module,
        cache_module,
        cache_serialization,
    ):
        module.datetime = frozen


# ---------------------------------------------------------------------------
# data builders
# ---------------------------------------------------------------------------


def current(temp_f, condition, **kw):
    return CurrentConditions(temperature_f=temp_f, condition=condition, **kw)


def forecast(label, temps, precip=None, summary=None):
    return Forecast(
        periods=[
            ForecastPeriod(
                name=f"{label} {i}" if i else "Today",
                temperature=t,
                precipitation_probability=None if precip is None else precip[i],
                start_time=T0 + timedelta(hours=12 * i),
                short_forecast=f"{label} sky",
            )
            for i, t in enumerate(temps)
        ],
        generated_at=T0,
        summary=summary,
    )


def hourly(label, temps, pressure=None, precip=None, start=T0):
    return HourlyForecast(
        periods=[
            HourlyForecastPeriod(
                start_time=start + timedelta(hours=i),
                temperature=t,
                short_forecast=label,
                pressure_mb=None if pressure is None else pressure - i * 0.5,
                precipitation_probability=None if precip is None else precip[i],
            )
            for i, t in enumerate(temps)
        ]
    )


def alert(alert_id, title, source=None, severity="Moderate", minutes_ago=5, **kw):
    issued = T0 - timedelta(minutes=minutes_ago)
    return WeatherAlert(
        title=title,
        description=kw.pop("description", f"{title} details."),
        severity=severity,
        urgency="Expected",
        certainty="Likely",
        event=kw.pop("event", title),
        id=alert_id,
        source=source,
        effective=issued,
        onset=issued,
        expires=kw.pop("expires", T0 + timedelta(hours=6)),
        **kw,
    )


TEMPS_24 = [70.0 + i * 0.25 for i in range(30)]

NWS_CURRENT = current(
    72.0, "Partly Cloudy", humidity=None, wind_speed_mph=8.0, pressure_in=30.01, uv_index=6.0
)
OM_CURRENT = current(
    71.0,
    "Mainly clear",
    humidity=55,
    wind_speed_mph=9.0,
    pressure_mb=1016.0,
    sunrise_time=datetime(2026, 7, 15, 5, 40, tzinfo=EDT),
    sunset_time=datetime(2026, 7, 15, 20, 25, tzinfo=EDT),
)
PW_CURRENT = current(73.0, "Humid", humidity=60, wind_gust_mph=15.0, visibility_miles=9.0)
NWS_ALERTS = WeatherAlerts(alerts=[alert("urn:nws:heat", "Heat Advisory", areas=["Kings"])])
PW_ALERTS = WeatherAlerts(
    alerts=[
        alert(
            "pw-1",
            "Heat Advisory",
            areas=["kings"],
            description="Longer heat advisory text from Pirate Weather.",
        )
    ]
)
MINUTELY = MinutelyPrecipitationForecast(
    summary="Rain starting in 20 min.",
    points=[
        MinutelyPrecipitationPoint(
            time=T0, precipitation_intensity=0.0, precipitation_probability=0.1
        )
    ],
)
AFD = ("Area Forecast Discussion text", datetime(2026, 7, 15, 14, 2, tzinfo=UTC))
NWS_ALL = [
    NWS_CURRENT,
    forecast("NWS", [80.0, 65.0, 82.0], precip=[20.0, 10.0, 30.0]),
    AFD[0],
    AFD[1],
    NWS_ALERTS,
    hourly("NWS", TEMPS_24),
]
OM_ALL = [
    OM_CURRENT,
    forecast("OM", [79.0, 64.0, 81.0], precip=[25.0, 15.0, 30.0]),
    hourly("OM", TEMPS_24, pressure=1016.0),
]
PW_FULL = {
    "current": PW_CURRENT,
    "forecast": forecast("PW", [83.0, 66.0], precip=[40.0, 20.0], summary="Humid all week."),
    "hourly": hourly("PW", TEMPS_24),
    "alerts": PW_ALERTS,
    "minutely": MINUTELY,
}
ENV = EnvironmentalConditions(
    air_quality_index=35.0, air_quality_category="Good", sources=["AirNow"]
)
AVIATION = {
    "station": ["KJFK", "John F. Kennedy International Airport"],
    "data": AviationData(
        raw_taf="TAF KJFK 151720Z",
        decoded_taf="Decoded TAF",
        station_id="KJFK",
        airport_name="KJFK",
    ),
}
MARINE_ZONES = {
    "features": [
        {
            "id": "https://api.weather.gov/zones/forecast/ANZ350",
            "properties": {"id": "ANZ350", "name": "Moriches Inlet to Montauk Point"},
        }
    ]
}
MARINE_FORECAST = {
    "properties": {
        "updateTime": "2026-07-15T14:30:00Z",
        "periods": [
            {
                "name": "Today",
                "detailedForecast": "SW winds 10 to 15 kt. Seas 3 to 4 ft. A chance of showers.",
            },
            {
                "name": "Tonight",
                "shortForecast": "Patchy fog",
                "detailedForecast": "S winds around 10 kt; seas 3 ft.",
            },
            {"name": "", "detailedForecast": "Swells subsiding. Winds light."},
            {"name": "Thursday", "detailedForecast": "Gusts to 25 kt. WAVES 5 FT."},
        ],
    }
}
MARINE_ALERTS = WeatherAlerts(
    alerts=[alert(None, "Small Craft Advisory", event="Small Craft Advisory", areas=["ANZ350"])]
)


def defaults():
    return {
        "nws": {
            "all": [None] * 6,
            "forecast_and_discussion": [None, None, None],
            "discussion_only": [None, None],
            "alerts": None,
            "cancel_refs": [],
        },
        "openmeteo": {"all": [None] * 3, "current": None},
        "pirateweather": {
            "current": None,
            "forecast": None,
            "hourly": None,
            "alerts": None,
            "minutely": None,
        },
        "environmental": ENV,
        "aviation": {"station": [None, None], "data": AviationData()},
        "marine": {"zones": {"features": []}, "forecast": None, "alerts": WeatherAlerts(alerts=[])},
    }


def merged(table, overrides):
    table = dict(table)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(table.get(key), dict):
            table[key] = {**table[key], **value}
        else:
            table[key] = value
    return table


def fakes(**overrides):
    return merged(defaults(), overrides)


def full_sources(**extra):
    base = fakes(
        nws={
            "all": NWS_ALL,
            "forecast_and_discussion": [None, *AFD],
            "discussion_only": list(AFD),
            "alerts": NWS_ALERTS,
        },
        openmeteo={"all": OM_ALL, "current": OM_CURRENT},
        pirateweather=PW_FULL,
        aviation=AVIATION,
    )
    return merged(base, extra)


# ---------------------------------------------------------------------------
# harness
# ---------------------------------------------------------------------------


def resolve(value, error=RuntimeError):
    if isinstance(value, Err):
        raise error(value.message)
    return copy.deepcopy(value)


def build_client(scenario, log, cache, state):
    settings = AppSettings(**scenario.get("settings", {}))
    env_value = state["table"]["environmental"]

    class FakeEnvironmental:
        async def fetch(self, location, **kwargs):
            log.append("environmental")
            return resolve(state["table"]["environmental"])

    client = WeatherClient(
        data_source=scenario["data_source"],
        settings=settings,
        pirate_weather_api_key="test-key" if scenario.get("pirate") else "",
        environmental_client=None if env_value == "absent" else FakeEnvironmental(),
        offline_cache=cache,
    )
    if env_value == "absent":
        client.environmental_client = None

    def recorder(name, source, key, shape=None):
        async def fake(*_args, **_kwargs):
            log.append(name)
            # The real Pirate Weather client raises PirateWeatherApiError.
            error = PirateWeatherApiError if source == "pirateweather" else RuntimeError
            result = resolve(state["table"][source][key], error)
            if shape == "tuple":
                return tuple(result)
            if shape == "set":
                return set(result)
            return result

        return fake

    client._fetch_nws_data = recorder("nws.all", "nws", "all", "tuple")
    client._get_nws_forecast_and_discussion = recorder(
        "nws.forecast_and_discussion", "nws", "forecast_and_discussion", "tuple"
    )
    client._get_nws_discussion_only = recorder(
        "nws.discussion_only", "nws", "discussion_only", "tuple"
    )
    client._get_nws_alerts = recorder("nws.alerts", "nws", "alerts")
    client._fetch_nws_cancel_references = recorder("nws.cancel_refs", "nws", "cancel_refs", "set")
    client._fetch_openmeteo_data = recorder("openmeteo.all", "openmeteo", "all", "tuple")
    client._get_openmeteo_current_conditions = recorder("openmeteo.current", "openmeteo", "current")

    class FakePirate:
        units = "us"
        get_current_conditions = staticmethod(
            recorder("pirateweather.current", "pirateweather", "current")
        )
        get_forecast = staticmethod(recorder("pirateweather.forecast", "pirateweather", "forecast"))
        get_hourly_forecast = staticmethod(
            recorder("pirateweather.hourly", "pirateweather", "hourly")
        )
        get_alerts = staticmethod(recorder("pirateweather.alerts", "pirateweather", "alerts"))

    pirate = FakePirate() if scenario.get("pirate") else None
    client._pirate_weather_client_for_location = lambda _location: pirate
    client._get_pirate_weather_minutely = recorder(
        "pirateweather.minutely", "pirateweather", "minutely"
    )
    return client


class FakeResponse:
    def __init__(self, value):
        self.value = value

    def raise_for_status(self):
        resolve(self.value)

    def json(self):
        return resolve(self.value)


def run_scenario(scenario):
    state = {"table": scenario["fakes"]}
    log: list[str] = []
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        freeze(scenario["steps"][0]["now"])
        cache = WeatherDataCache(Path(tmp)) if scenario.get("cache") else None
        client = build_client(scenario, log, cache, state)

        async def station_info(*_args, **_kwargs):
            log.append("aviation.station")
            return tuple(resolve(state["table"]["aviation"]["station"]))

        async def aviation_weather(_client, station_id, **_kwargs):
            log.append("aviation.weather")
            return resolve(state["table"]["aviation"]["data"])

        async def client_get(_http, url, headers=None, params=None):
            if url.endswith("/zones"):
                log.append("marine.zones")
                return FakeResponse(state["table"]["marine"]["zones"])
            log.append("marine.alerts")
            return FakeResponse({"alerts": True})

        async def marine_forecast(*_args, **_kwargs):
            log.append("marine.forecast")
            return resolve(state["table"]["marine"]["forecast"])

        def parse_alerts(_payload):
            return resolve(state["table"]["marine"]["alerts"])

        with (
            patch.object(nws_module, "get_nws_primary_station_info", station_info),
            patch.object(aviation_module, "get_aviation_weather", aviation_weather),
            patch.object(nws_module, "_client_get", client_get),
            patch.object(nws_module, "get_nws_marine_forecast", marine_forecast),
            patch.object(nws_module, "parse_nws_alerts", parse_alerts),
        ):
            for step in scenario["steps"]:
                state["table"] = merged(scenario["fakes"], step.get("fakes", {}))
                freeze(step["now"])
                log.clear()
                if step["call"] == "weather":
                    data = asyncio.run(
                        client.get_weather_data(
                            scenario["location"], force_refresh=step.get("force", False)
                        )
                    )
                else:
                    data = asyncio.run(client.get_notification_event_data(scenario["location"]))
                results.append(
                    {
                        "fakes": encode_fakes(step.get("fakes", {})),
                        "requests": sorted(log),
                        "weather": data,
                    }
                )
    return results


def encode_fakes(table):
    def enc(value):
        if isinstance(value, Err):
            return {"error": value.message}
        return {"value": jsonable(value)}

    out = {}
    for source, entries in table.items():
        if source == "environmental":
            out[source] = None if entries == "absent" else enc(entries)
        else:
            out[source] = {key: enc(value) for key, value in entries.items()}
    return out


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------


def weather(now=T0, force=False, **fakes):
    return {"call": "weather", "now": now, "force": force, "fakes": fakes}


def notify(now=T0, **fakes):
    return {"call": "notification", "now": now, "fakes": fakes}


SCENARIOS = [
    dict(
        name="max_coverage_us_all_sources",
        data_source="auto",
        location=US,
        pirate=True,
        fakes=full_sources(),
        steps=[weather()],
    ),
    dict(
        name="max_coverage_intl",
        data_source="auto",
        location=INTL,
        pirate=True,
        fakes=full_sources(),
        steps=[weather()],
    ),
    dict(
        name="max_coverage_us_without_key",
        data_source="auto",
        location=US,
        fakes=full_sources(),
        steps=[weather()],
    ),
    dict(
        name="economy_us_extended_forecast",
        data_source="auto",
        location=US,
        pirate=True,
        settings={
            "auto_mode_api_budget": "economy",
            "forecast_duration_days": 10,
            "auto_sources_us": ["nws", "pirateweather", "openmeteo"],
        },
        fakes=full_sources(),
        steps=[weather()],
    ),
    dict(
        name="economy_us_sufficient",
        data_source="auto",
        location=US,
        pirate=True,
        settings={"auto_mode_api_budget": "economy"},
        fakes=full_sources(),
        steps=[weather()],
    ),
    dict(
        name="balanced_us_pirate_secondary",
        data_source="auto",
        location=US,
        pirate=True,
        settings={"auto_mode_api_budget": "balanced", "auto_sources_us": ["nws", "pirateweather"]},
        fakes=full_sources(
            nws={"all": [None, NWS_ALL[1], None, None, WeatherAlerts(alerts=[]), None]}
        ),
        steps=[weather()],
    ),
    dict(
        name="balanced_intl_pirate_primary",
        data_source="auto",
        location=INTL,
        pirate=True,
        settings={
            "auto_mode_api_budget": "balanced",
            "auto_sources_international": ["pirateweather", "openmeteo"],
        },
        fakes=full_sources(),
        steps=[weather()],
    ),
    dict(
        name="economy_intl_openmeteo_no_key",
        data_source="auto",
        location=INTL,
        settings={"auto_mode_api_budget": "economy"},
        fakes=full_sources(openmeteo={"all": [OM_CURRENT, OM_ALL[1], None]}),
        steps=[weather()],
    ),
    dict(
        name="economy_intl_openmeteo_then_pirate",
        data_source="auto",
        location=INTL,
        pirate=True,
        settings={"auto_mode_api_budget": "economy"},
        fakes=full_sources(),
        steps=[weather()],
    ),
    dict(
        name="nws_error_discussion_enriched",
        data_source="auto",
        location=US,
        fakes=full_sources(nws={"all": Err("NWS 503")}),
        steps=[weather()],
    ),
    dict(
        name="nws_empty_tuple",
        data_source="auto",
        location=US,
        settings={"trend_insights_enabled": False},
        fakes=full_sources(nws={"all": [None] * 6, "forecast_and_discussion": Err("no AFD")}),
        steps=[weather()],
    ),
    dict(
        name="us_without_nws_configured",
        data_source="auto",
        location=US,
        settings={"auto_sources_us": ["openmeteo", "bogus"]},
        fakes=full_sources(),
        steps=[weather()],
    ),
    dict(
        name="all_failed_no_cache",
        data_source="auto",
        location=US,
        pirate=True,
        fakes=fakes(
            nws={"all": Err("down")},
            openmeteo={"all": Err("down")},
            pirateweather={"current": Err("down")},
        ),
        steps=[weather()],
    ),
    dict(
        name="all_failed_uses_stale_cache",
        data_source="auto",
        location=US,
        cache=True,
        fakes=full_sources(),
        steps=[
            weather(),
            weather(
                T0 + timedelta(minutes=30), nws={"all": Err("down")}, openmeteo={"all": Err("down")}
            ),
        ],
    ),
    dict(
        name="empty_sources_all_failed",
        data_source="auto",
        location=INTL,
        cache=True,
        fakes=full_sources(openmeteo={"all": [None] * 3}),
        steps=[weather()],
    ),
    dict(
        name="lifecycle_across_refreshes",
        data_source="auto",
        location=US,
        fakes=full_sources(
            nws={
                "all": [
                    NWS_CURRENT,
                    NWS_ALL[1],
                    AFD[0],
                    AFD[1],
                    WeatherAlerts(
                        alerts=[
                            alert("a", "Heat Advisory"),
                            alert("b", "Flood Watch", minutes_ago=120),
                        ]
                    ),
                    NWS_ALL[5],
                ],
                "cancel_refs": ["b"],
            }
        ),
        steps=[
            weather(),
            weather(
                T0 + timedelta(minutes=10),
                nws={
                    "all": [
                        NWS_CURRENT,
                        NWS_ALL[1],
                        AFD[0],
                        AFD[1],
                        WeatherAlerts(
                            alerts=[
                                alert("a", "Heat Advisory", description="Heat index up to 105."),
                                alert("c", "Air Quality Alert"),
                            ]
                        ),
                        NWS_ALL[5],
                    ],
                    "cancel_refs": ["b"],
                },
            ),
        ],
    ),
    dict(
        name="marine_and_environment",
        data_source="auto",
        location=US_MARINE,
        settings={"pollen_enabled": False},
        fakes=full_sources(
            marine={"zones": MARINE_ZONES, "forecast": MARINE_FORECAST, "alerts": MARINE_ALERTS}
        ),
        steps=[weather()],
    ),
    dict(
        name="marine_alerts_fail_keeps_forecast",
        data_source="nws",
        location=US_MARINE,
        fakes=full_sources(
            environmental="absent",
            marine={
                "zones": MARINE_ZONES,
                "forecast": MARINE_FORECAST,
                "alerts": Err("alerts down"),
            },
        ),
        steps=[weather()],
    ),
    dict(
        name="nws_only",
        data_source="nws",
        location=US,
        fakes=full_sources(nws={"cancel_refs": ["urn:nws:heat"]}),
        steps=[weather(), weather(T0 + timedelta(minutes=10))],
    ),
    dict(
        name="nws_only_failure",
        data_source="nws",
        location=US,
        fakes=full_sources(nws={"all": Err("boom")}),
        steps=[weather()],
    ),
    dict(
        name="openmeteo_only",
        data_source="openmeteo",
        location=US,
        fakes=full_sources(),
        steps=[weather()],
    ),
    dict(
        name="pirate_only",
        data_source="pirateweather",
        location=INTL,
        pirate=True,
        fakes=full_sources(),
        steps=[weather(), weather(T0 + timedelta(minutes=5))],
    ),
    dict(
        name="pirate_only_without_key",
        data_source="pirateweather",
        location=US,
        fakes=full_sources(),
        steps=[weather()],
    ),
    dict(
        name="pirate_only_failure",
        data_source="pirateweather",
        location=INTL,
        pirate=True,
        cache=True,
        fakes=full_sources(pirateweather={"forecast": Err("quota")}),
        steps=[weather()],
    ),
    dict(
        name="notification_auto_us",
        data_source="auto",
        location=US,
        pirate=True,
        settings={"notify_minutely_precipitation_start": True},
        fakes=full_sources(
            nws={"alerts": WeatherAlerts(alerts=[alert("x", "Wind Advisory", areas=["Kings"])])}
        ),
        steps=[notify(), notify(T0 + timedelta(minutes=10)), notify(T0 + timedelta(minutes=15))],
    ),
    dict(
        name="notification_fast_minutely_polling",
        data_source="auto",
        location=INTL,
        pirate=True,
        settings={
            "notify_precipitation_likelihood": True,
            "minutely_precipitation_fast_polling": True,
            "update_interval_minutes": 3,
        },
        fakes=full_sources(
            openmeteo={
                "all": [
                    OM_CURRENT,
                    OM_ALL[1],
                    hourly("OM", [60.0] * 8, precip=[0, 10, 20, 50, 0, 0, 0, 0]),
                ]
            }
        ),
        steps=[
            notify(),
            notify(T0 + timedelta(minutes=2)),
            notify(T0 + timedelta(minutes=3)),
            weather(T0 + timedelta(minutes=4)),
            notify(T0 + timedelta(minutes=5)),
            notify(T0 + timedelta(minutes=8)),
        ],
    ),
    dict(
        name="notification_nws_error",
        data_source="nws",
        location=US,
        fakes=full_sources(nws={"alerts": Err("alerts down")}),
        steps=[notify()],
    ),
    dict(
        name="notification_openmeteo",
        data_source="openmeteo",
        location=US,
        fakes=full_sources(),
        steps=[notify()],
    ),
    dict(
        name="notification_pirate_intl",
        data_source="pirateweather",
        location=INTL,
        pirate=True,
        fakes=full_sources(),
        steps=[notify()],
    ),
    dict(
        name="force_refresh",
        data_source="openmeteo",
        location=US,
        cache=True,
        fakes=full_sources(),
        steps=[weather(), weather(T0 + timedelta(minutes=1), force=True)],
    ),
]


def main():
    for scenario in SCENARIOS:
        results = run_scenario(scenario)
        write(
            "client",
            scenario["name"],
            {
                "name": scenario["name"],
                "data_source": scenario["data_source"],
                "settings": scenario.get("settings", {}),
                "location": scenario["location"],
                "pirate": bool(scenario.get("pirate")),
                "cache": bool(scenario.get("cache")),
                "fakes": encode_fakes(scenario["fakes"]),
                "steps": [
                    {
                        "call": step["call"],
                        "now": step["now"],
                        "force": step.get("force", False),
                        **result,
                    }
                    for step, result in zip(scenario["steps"], results, strict=True)
                ],
            },
            compact=True,
        )


if __name__ == "__main__":
    main()
