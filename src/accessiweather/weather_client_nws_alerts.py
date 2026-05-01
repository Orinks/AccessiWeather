"""Alert helpers for the NWS weather client."""
# ruff: noqa: F403, F405

from __future__ import annotations

from .weather_client_nws_common import *  # noqa: F403
from .weather_client_nws_parsers import parse_nws_alerts


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_nws_alerts(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
    alert_radius_type: str = "county",
) -> WeatherAlerts | None:
    """
    Fetch weather alerts from the NWS API.

    Args:
        location: The location to fetch alerts for
        nws_base_url: Base URL for NWS API
        user_agent: User agent string
        timeout: Request timeout
        client: Optional HTTP client to reuse
        alert_radius_type: "county", "point" (exact location), "zone" (forecast zone), or "state"

    """
    try:
        alerts_url = f"{nws_base_url}/alerts/active"
        headers = {"User-Agent": user_agent}

        # Build params based on alert_radius_type
        if alert_radius_type == "county":
            # Prefer the stored county_zone_id (populated by zone enrichment and
            # kept fresh by drift correction). This skips a redundant /points
            # round-trip on each refresh. Fall back to /points resolution when
            # the stored field is absent.
            if location.county_zone_id:
                params = {"zone": location.county_zone_id, "status": "actual"}
            else:
                # Get county zone from point data
                point_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
                if client is not None:
                    point_response = await _client_get(client, point_url, headers=headers)
                else:
                    async with httpx.AsyncClient(
                        timeout=timeout, follow_redirects=True
                    ) as new_client:
                        point_response = await new_client.get(point_url, headers=headers)
                point_response.raise_for_status()
                point_data = point_response.json()

                county_url = point_data.get("properties", {}).get("county")
                if county_url and "/county/" in county_url:
                    zone_id = county_url.split("/county/")[1]
                    params = {"zone": zone_id, "status": "actual"}
                else:
                    logger.warning("Could not determine county zone, falling back to point query")
                    params = {
                        "point": f"{location.latitude},{location.longitude}",
                        "status": "actual",
                    }

        elif alert_radius_type == "state":
            # Get state from location - need to fetch point data first
            point_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
            if client is not None:
                point_response = await _client_get(client, point_url, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
                    point_response = await new_client.get(point_url, headers=headers)
            point_response.raise_for_status()
            point_data = point_response.json()
            state = (
                point_data.get("properties", {})
                .get("relativeLocation", {})
                .get("properties", {})
                .get("state")
            )
            if state:
                params = {"area": state, "status": "actual"}
            else:
                # Fall back to point query if state not found
                logger.warning("Could not determine state, falling back to point query")
                params = {"point": f"{location.latitude},{location.longitude}", "status": "actual"}

        elif alert_radius_type == "zone":
            # Prefer the stored forecast_zone_id (populated by zone enrichment
            # and kept fresh by drift correction). This skips a redundant
            # /points round-trip on each refresh. Fall back to /points
            # resolution when the stored field is absent.
            if location.forecast_zone_id:
                params = {"zone": location.forecast_zone_id, "status": "actual"}
            else:
                # Get zone from point data
                point_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
                if client is not None:
                    point_response = await _client_get(client, point_url, headers=headers)
                else:
                    async with httpx.AsyncClient(
                        timeout=timeout, follow_redirects=True
                    ) as new_client:
                        point_response = await new_client.get(point_url, headers=headers)
                point_response.raise_for_status()
                point_data = point_response.json()

                # Try to get zone ID (prefer county, then forecast zone)
                zone_id = None
                county_url = point_data.get("properties", {}).get("county")
                if county_url and "/county/" in county_url:
                    zone_id = county_url.split("/county/")[1]
                if not zone_id:
                    forecast_zone_url = point_data.get("properties", {}).get("forecastZone")
                    if forecast_zone_url and "/forecast/" in forecast_zone_url:
                        zone_id = forecast_zone_url.split("/forecast/")[1]

                if zone_id:
                    params = {"zone": zone_id, "status": "actual"}
                else:
                    # Fall back to point query if zone not found
                    logger.warning("Could not determine zone, falling back to point query")
                    params = {
                        "point": f"{location.latitude},{location.longitude}",
                        "status": "actual",
                    }

        else:  # "point" (default) - most precise
            params = {
                "point": f"{location.latitude},{location.longitude}",
                "status": "actual",
            }

        # Note: Don't filter by message_type - we want Alert, Update, and Cancel
        # message_type=alert would exclude updated warnings (messageType: "Update")

        # Use provided client or create a new one
        if client is not None:
            response = await _client_get(client, alerts_url, headers=headers, params=params)
            response.raise_for_status()
            alerts_data = response.json()
            return parse_nws_alerts(alerts_data)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(alerts_url, params=params, headers=headers)
            response.raise_for_status()
            alerts_data = response.json()
            return parse_nws_alerts(alerts_data)

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS alerts: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return WeatherAlerts(alerts=[])


async def fetch_nws_cancel_references(
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    lookback_minutes: int = 15,
    client: httpx.AsyncClient | None = None,
) -> set[str]:
    """
    Fetch recent NWS Cancel messages and return the set of alert IDs they reference.

    Queries GET /alerts?message_type=cancel&start=<lookback ago>&end=<now>.
    Returns set of all referenced alert IDs (from properties.references[].identifier or @id).
    On any failure, returns empty set (safe default: caller suppresses ambiguous cancels).
    """
    try:
        now = datetime.now(UTC)
        start = now - timedelta(minutes=lookback_minutes)
        start_str = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{nws_base_url}/alerts"
        params = {"message_type": "cancel", "start": start_str, "end": end_str}
        headers = {"User-Agent": user_agent}
        if client is not None:
            response = await _client_get(client, url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
        else:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
                response = await new_client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
        referenced_ids: set[str] = set()
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            for ref in props.get("references", []):
                ref_id = ref.get("identifier") or ref.get("@id") or ref.get("id")
                if ref_id:
                    referenced_ids.add(ref_id)
        logger.debug(f"Fetched {len(referenced_ids)} NWS cancel references")
        return referenced_ids
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to fetch NWS cancel references: {exc}")
        return set()
