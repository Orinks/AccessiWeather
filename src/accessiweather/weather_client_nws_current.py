"""Current-condition helpers for the NWS weather client."""
# ruff: noqa: F403, F405

from __future__ import annotations

from .weather_client_nws_common import *  # noqa: F403
from .weather_client_nws_parsers import parse_nws_current_conditions


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_nws_current_conditions(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
) -> CurrentConditions | None:
    """Fetch current conditions from the NWS API for the given location."""
    try:
        grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
        headers = {"User-Agent": user_agent}

        async def _select_best_observation(
            features: list[dict[str, Any]],
            http_client: httpx.AsyncClient,
        ) -> CurrentConditions | None:
            """Return the first observation with meaningful data, keeping a fallback."""
            if not features:
                return None

            fallback: CurrentConditions | None = None
            fallback_rank: tuple[int, int, int] | None = None
            attempts = 0

            sorted_features = sorted(features, key=_station_sort_key)

            for feature in sorted_features:
                if attempts >= MAX_STATION_OBSERVATION_ATTEMPTS:
                    break

                props = feature.get("properties", {}) or {}
                station_id = props.get("stationIdentifier")
                if not station_id:
                    continue

                obs_url = f"{nws_base_url}/stations/{station_id}/observations/latest"
                attempts += 1

                try:
                    response = await _client_get(http_client, obs_url, headers=headers)
                    response.raise_for_status()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed to fetch observation for %s: %s", station_id, exc)
                    continue

                try:
                    obs_data = response.json()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Invalid observation payload for %s: %s", station_id, exc)
                    continue

                obs_props = obs_data.get("properties", {}) or {}
                timestamp = _parse_iso_datetime(obs_props.get("timestamp"))
                stale = False
                if timestamp is not None:
                    if timestamp.tzinfo is None:
                        timestamp_utc = timestamp.replace(tzinfo=UTC)
                    else:
                        timestamp_utc = timestamp.astimezone(UTC)
                    age = datetime.now(UTC) - timestamp_utc
                    if age > MAX_OBSERVATION_AGE:
                        stale = True
                else:
                    stale = True

                try:
                    _scrub_measurements(obs_props)
                    current = parse_nws_current_conditions(obs_data, location=location)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Failed to parse observation for %s: %s", station_id, exc)
                    continue

                has_temperature = (
                    current.temperature_f is not None or current.temperature_c is not None
                )
                has_description = bool(current.condition and current.condition.strip())
                score = _current_data_score(current)

                if not stale and (has_temperature or has_description):
                    return current

                if score == 0:
                    continue

                rank = (1 if stale else 0, -score, attempts)
                if fallback_rank is None or rank < fallback_rank:
                    fallback = current
                    fallback_rank = rank

            return fallback

        # Use provided client or create a new one
        if client is not None:
            response = await _client_get(client, grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()

            # Extract timezone from grid data and update location
            if "properties" in grid_data and "timeZone" in grid_data["properties"]:
                location.timezone = grid_data["properties"]["timeZone"]

            stations_url = grid_data["properties"]["observationStations"]
            response = await _client_get(client, stations_url, headers=headers)
            response.raise_for_status()
            stations_data = response.json()

            if not stations_data["features"]:
                logger.warning("No observation stations found")
                return None

            current = await _select_best_observation(stations_data["features"], client)
            if current is None:
                logger.warning(
                    "No usable observations found for %s (lat=%s, lon=%s)",
                    location.name,
                    location.latitude,
                    location.longitude,
                )
            return current
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()

            # Extract timezone from grid data and update location
            if "properties" in grid_data and "timeZone" in grid_data["properties"]:
                location.timezone = grid_data["properties"]["timeZone"]

            stations_url = grid_data["properties"]["observationStations"]
            response = await new_client.get(stations_url, headers=headers)
            response.raise_for_status()
            stations_data = response.json()

            if not stations_data["features"]:
                logger.warning("No observation stations found")
                return None

            current = await _select_best_observation(stations_data["features"], new_client)
            if current is None:
                logger.warning(
                    "No usable observations found for %s (lat=%s, lon=%s)",
                    location.name,
                    location.latitude,
                    location.longitude,
                )
            return current

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS current conditions: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None


async def get_nws_primary_station_info(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
) -> tuple[str | None, str | None]:
    """Return the primary observation station identifier and name for a location."""
    try:
        headers = {"User-Agent": user_agent}
        grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"

        if client is not None:
            response = await _client_get(client, grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()
            stations_url = grid_data.get("properties", {}).get("observationStations")
            if not stations_url:
                logger.debug("No observationStations URL in NWS grid data")
                return None, None

            response = await _client_get(client, stations_url, headers=headers)
            response.raise_for_status()
            stations_data = response.json()
        else:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
                response = await new_client.get(grid_url, headers=headers)
                response.raise_for_status()
                grid_data = response.json()
                stations_url = grid_data.get("properties", {}).get("observationStations")
                if not stations_url:
                    logger.debug("No observationStations URL in NWS grid data")
                    return None, None

                response = await new_client.get(stations_url, headers=headers)
                response.raise_for_status()
                stations_data = response.json()

        features = stations_data.get("features", [])
        if not features:
            logger.debug("No observation station features returned")
            return None, None

        station_props = features[0].get("properties", {})
        station_id = station_props.get("stationIdentifier")
        station_name = station_props.get("name")
        return station_id, station_name
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to look up primary station info: {exc}")
        return None, None


async def get_nws_station_metadata(
    station_id: str,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any] | None:
    """Fetch metadata for a specific station."""
    if not station_id:
        return None

    headers = {"User-Agent": user_agent}
    station_url = f"{nws_base_url}/stations/{station_id}"

    try:
        if client is not None:
            response = await _client_get(client, station_url, headers=headers)
            response.raise_for_status()
            return response.json()

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(station_url, headers=headers)
            response.raise_for_status()
            return response.json()
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"Failed to fetch station metadata for {station_id}: {exc}")
        return None
