#!/usr/bin/env python3
"""
Find active NWS alert zones with representative coordinates.

This developer utility fetches active NWS alerts and prints locations that can be
used for AccessiWeather notification testing.

Usage:
    python tools/find_alert_zones.py
    python tools/find_alert_zones.py --state TX
    python tools/find_alert_zones.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from typing import Any

ALERTS_URL = "https://api.weather.gov/alerts/active?status=actual&message_type=alert"
ZONE_URL_TEMPLATE = "https://api.weather.gov/zones/forecast/{zone}"
USER_AGENT = "AccessiWeather (dev-tools/find_alert_zones.py)"

STATE_NAMES = {
    "AL": "ALABAMA",
    "AK": "ALASKA",
    "AZ": "ARIZONA",
    "AR": "ARKANSAS",
    "CA": "CALIFORNIA",
    "CO": "COLORADO",
    "CT": "CONNECTICUT",
    "DE": "DELAWARE",
    "FL": "FLORIDA",
    "GA": "GEORGIA",
    "HI": "HAWAII",
    "ID": "IDAHO",
    "IL": "ILLINOIS",
    "IN": "INDIANA",
    "IA": "IOWA",
    "KS": "KANSAS",
    "KY": "KENTUCKY",
    "LA": "LOUISIANA",
    "ME": "MAINE",
    "MD": "MARYLAND",
    "MA": "MASSACHUSETTS",
    "MI": "MICHIGAN",
    "MN": "MINNESOTA",
    "MS": "MISSISSIPPI",
    "MO": "MISSOURI",
    "MT": "MONTANA",
    "NE": "NEBRASKA",
    "NV": "NEVADA",
    "NH": "NEW HAMPSHIRE",
    "NJ": "NEW JERSEY",
    "NM": "NEW MEXICO",
    "NY": "NEW YORK",
    "NC": "NORTH CAROLINA",
    "ND": "NORTH DAKOTA",
    "OH": "OHIO",
    "OK": "OKLAHOMA",
    "OR": "OREGON",
    "PA": "PENNSYLVANIA",
    "RI": "RHODE ISLAND",
    "SC": "SOUTH CAROLINA",
    "SD": "SOUTH DAKOTA",
    "TN": "TENNESSEE",
    "TX": "TEXAS",
    "UT": "UTAH",
    "VT": "VERMONT",
    "VA": "VIRGINIA",
    "WA": "WASHINGTON",
    "WV": "WEST VIRGINIA",
    "WI": "WISCONSIN",
    "WY": "WYOMING",
    "DC": "DISTRICT OF COLUMBIA",
    "PR": "PUERTO RICO",
    "VI": "U.S. VIRGIN ISLANDS",
    "GU": "GUAM",
    "AS": "AMERICAN SAMOA",
    "MP": "NORTHERN MARIANA ISLANDS",
}


def _get_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/geo+json, application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
        return json.load(resp)


def _extract_points(coords: Any) -> list[tuple[float, float]]:
    """Recursively extract [lon, lat] points from nested coordinate arrays."""
    points: list[tuple[float, float]] = []
    if not isinstance(coords, list):
        return points

    if len(coords) >= 2 and all(isinstance(v, (int, float)) for v in coords[:2]):
        lon = float(coords[0])
        lat = float(coords[1])
        points.append((lat, lon))
        return points

    for item in coords:
        points.extend(_extract_points(item))

    return points


def _centroid_from_geometry(geometry: Any) -> tuple[float, float] | None:
    if not isinstance(geometry, dict):
        return None

    coords = geometry.get("coordinates")
    points = _extract_points(coords)
    if not points:
        return None

    lat = sum(p[0] for p in points) / len(points)
    lon = sum(p[1] for p in points) / len(points)
    return (lat, lon)


def _first_ugc(properties: dict[str, Any]) -> str | None:
    geocode = properties.get("geocode")
    if not isinstance(geocode, dict):
        return None

    ugc = geocode.get("UGC")
    if isinstance(ugc, list) and ugc:
        first = ugc[0]
        if isinstance(first, str) and first.strip():
            return first.strip().upper()
    return None


def _zone_centroid(
    zone_code: str, cache: dict[str, tuple[float, float] | None]
) -> tuple[float, float] | None:
    if zone_code in cache:
        return cache[zone_code]

    try:
        zone_data = _get_json(ZONE_URL_TEMPLATE.format(zone=zone_code))
        centroid = _centroid_from_geometry(zone_data.get("geometry"))
        if centroid is None:
            props = zone_data.get("properties", {})
            if isinstance(props, dict):
                point = props.get("centroid")
                centroid = _centroid_from_geometry(point)
        cache[zone_code] = centroid
        time.sleep(0.1)
        return centroid
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        cache[zone_code] = None
        return None


def _state_from_alert(properties: dict[str, Any]) -> str:
    ugc = _first_ugc(properties)
    if ugc and len(ugc) >= 2:
        return ugc[:2]

    area = properties.get("areaDesc")
    if isinstance(area, str) and area:
        parts = [p.strip() for p in area.split(",") if p.strip()]
        if parts and len(parts[-1]) == 2 and parts[-1].isalpha():
            return parts[-1].upper()

    return "??"


def collect_alerts(state_filter: str | None = None) -> list[dict[str, Any]]:
    payload = _get_json(ALERTS_URL)
    features = payload.get("features", [])
    if not isinstance(features, list):
        raise ValueError("Unexpected alerts payload: features is not a list")

    zone_cache: dict[str, tuple[float, float] | None] = {}
    rows: list[dict[str, Any]] = []

    for feature in features:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties", {})
        if not isinstance(properties, dict):
            continue

        state = _state_from_alert(properties)
        if state_filter and state != state_filter:
            continue

        event = properties.get("event") if isinstance(properties.get("event"), str) else "Unknown"
        severity = (
            properties.get("severity") if isinstance(properties.get("severity"), str) else "Unknown"
        )
        area_desc = (
            properties.get("areaDesc")
            if isinstance(properties.get("areaDesc"), str)
            else "Unknown area"
        )

        centroid = _centroid_from_geometry(feature.get("geometry"))
        source = "geometry"

        if centroid is None:
            ugc = _first_ugc(properties)
            if ugc:
                centroid = _zone_centroid(ugc, zone_cache)
                source = f"zone:{ugc}"
            else:
                source = "none"

        if centroid is None:
            continue

        rows.append(
            {
                "state": state,
                "state_name": STATE_NAMES.get(state, state),
                "event": event,
                "severity": severity,
                "area": area_desc,
                "latitude": round(centroid[0], 4),
                "longitude": round(centroid[1], 4),
                "coordinate_source": source,
            }
        )

    return rows


def print_table(rows: list[dict[str, Any]]) -> None:
    print("=== Active NWS Alerts ===")
    if not rows:
        print("\nNo matching alerts found.")
        return

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["state"])].append(row)

    for state in sorted(grouped.keys()):
        items = grouped[state]
        label = str(items[0].get("state_name") or state)
        print(f"\n{label} ({len(items)} alerts)")
        for item in items:
            event = str(item.get("event", "Unknown"))
            area = str(item.get("area", "Unknown area"))
            lat = float(item.get("latitude"))
            lon = float(item.get("longitude"))
            print(f"  [{event}] {area}  →  {lat:.4f}, {lon:.4f}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find active NWS alert zones and coordinates")
    parser.add_argument("--state", help="Optional 2-letter state/territory code filter (e.g. TX)")
    parser.add_argument(
        "--json", action="store_true", help="Output structured JSON instead of table"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state_filter = args.state.upper() if args.state else None
    if state_filter and (len(state_filter) != 2 or not state_filter.isalpha()):
        print("Error: --state must be a 2-letter code (e.g. TX)", file=sys.stderr)
        return 2

    try:
        rows = collect_alerts(state_filter=state_filter)
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        json.JSONDecodeError,
    ) as exc:
        print(f"Failed to fetch alert data: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print_table(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
