"""Observation station selection helpers for NWS weather data."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

STATION_SELECTION_STRATEGIES = {
    "nearest",
    "major_airport_preferred",
    "freshest_observation",
    "hybrid_default",
}

FetchStationObservation = Callable[[str, bool], dict[str, Any]]


def select_station(
    lat: float,
    lon: float,
    stations_data: dict[str, Any],
    strategy: str,
    force_refresh: bool,
    fetch_station_observation: FetchStationObservation,
) -> dict[str, Any]:
    """Select station according to configured strategy with resilient fallbacks."""
    features = stations_data.get("features", [])
    if not features:
        raise ValueError("No observation stations found")

    if strategy not in STATION_SELECTION_STRATEGIES:
        logger.warning("Unknown station strategy '%s', falling back to hybrid_default", strategy)
        strategy = "hybrid_default"

    if strategy == "nearest":
        return features[0]

    top_n = features[:5]
    nearest_station = features[0]
    nearest_distance = distance_km(lat, lon, nearest_station)

    if strategy == "major_airport_preferred":
        preferred_radius_km = max(25.0, min(80.0, nearest_distance + 35.0))
        major_candidates = [
            st
            for st in top_n
            if is_major_station(st) and distance_km(lat, lon, st) <= preferred_radius_km
        ]
        if major_candidates:
            return min(major_candidates, key=lambda st: distance_km(lat, lon, st))
        return nearest_station

    observations = collect_candidate_observations(
        lat, lon, top_n, force_refresh, fetch_station_observation
    )

    if strategy == "freshest_observation":
        freshest = pick_freshest(observations)
        if freshest:
            return freshest["station"]
        usable = pick_nearest_usable(observations)
        return usable["station"] if usable else nearest_station

    # hybrid_default: favor reliable major stations and fresh observations,
    # but keep a distance guardrail to avoid stations that are too far away.
    guardrail_km = max(20.0, min(100.0, nearest_distance + 30.0))
    guarded = [o for o in observations if o["distance_km"] <= guardrail_km and o["usable"]]

    major_fresh = [
        o
        for o in guarded
        if o["is_major"] and o["age_minutes"] is not None and o["age_minutes"] <= 90
    ]
    if major_fresh:
        return min(major_fresh, key=lambda o: (o["age_minutes"], o["distance_km"]))["station"]

    freshest_guarded = pick_freshest(guarded)
    if freshest_guarded:
        return freshest_guarded["station"]

    nearest_usable = pick_nearest_usable(observations)
    return nearest_usable["station"] if nearest_usable else nearest_station


def collect_candidate_observations(
    lat: float,
    lon: float,
    stations: list[dict[str, Any]],
    force_refresh: bool,
    fetch_station_observation: FetchStationObservation,
) -> list[dict[str, Any]]:
    """Fetch and score candidate station observations."""
    candidates: list[dict[str, Any]] = []
    for station in stations:
        station_id = station.get("properties", {}).get("stationIdentifier")
        if not station_id:
            continue
        try:
            obs = fetch_station_observation(station_id, force_refresh)
        except Exception as exc:
            logger.warning("Failed fetching observation for station %s: %s", station_id, exc)
            obs = {}

        candidates.append(
            {
                "station": station,
                "observation": obs,
                "distance_km": distance_km(lat, lon, station),
                "is_major": is_major_station(station),
                "usable": observation_has_usable_data(obs),
                "age_minutes": observation_age_minutes(obs),
            }
        )
    return candidates


def pick_freshest(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the freshest usable candidate, breaking ties by distance."""
    valid = [c for c in candidates if c.get("usable") and c.get("age_minutes") is not None]
    if not valid:
        return None
    return min(valid, key=lambda c: (c["age_minutes"], c["distance_km"]))


def pick_nearest_usable(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the nearest candidate with usable observation data."""
    usable = [c for c in candidates if c.get("usable")]
    if not usable:
        return None
    return min(usable, key=lambda c: c["distance_km"])


def distance_km(lat: float, lon: float, station: dict[str, Any]) -> float:
    """Calculate the distance from coordinates to a station."""
    geometry = station.get("geometry", {})
    coords = geometry.get("coordinates") or []
    if len(coords) < 2:
        return float("inf")
    station_lon, station_lat = coords[0], coords[1]

    r = 6371.0
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    lat2 = math.radians(station_lat)
    lon2 = math.radians(station_lon)

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def is_major_station(station: dict[str, Any]) -> bool:
    """Return whether a station looks like a major airport or reliable ASOS/AWOS source."""
    props = station.get("properties", {})
    station_id = str(props.get("stationIdentifier", "")).upper()
    name = str(props.get("name", "")).lower()

    major_name_markers = (
        "international",
        "intl",
        "regional airport",
        "air force base",
        "afb",
        "asos",
        "awos",
    )
    if any(marker in name for marker in major_name_markers):
        return True

    return len(station_id) == 4 and station_id.isalpha() and station_id[:1] in {"K", "C", "P"}


def observation_has_usable_data(observation: dict[str, Any]) -> bool:
    """Return whether an observation has enough data to support current conditions."""
    props = observation.get("properties", {}) if isinstance(observation, dict) else {}
    if not props:
        return False

    temp = props.get("temperature", {}).get("value")
    dewpoint = props.get("dewpoint", {}).get("value")
    wind_speed = props.get("windSpeed", {}).get("value")
    text_desc = props.get("textDescription")
    return any(v is not None for v in (temp, dewpoint, wind_speed, text_desc))


def observation_age_minutes(observation: dict[str, Any]) -> float | None:
    """Return observation age in minutes, or ``None`` when no timestamp is available."""
    props = observation.get("properties", {}) if isinstance(observation, dict) else {}
    timestamp = props.get("timestamp")
    if not timestamp:
        return None
    try:
        dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return max(0.0, (datetime.now(UTC) - dt.astimezone(UTC)).total_seconds() / 60.0)
    except Exception:
        return None
