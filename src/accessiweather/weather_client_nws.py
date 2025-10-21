"""NWS API client methods for fetching and parsing weather data from the National Weather Service."""

from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import datetime
from typing import Any

import httpx

from .models import (
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    WeatherAlert,
    WeatherAlerts,
)
from .weather_client_parsers import (
    convert_pa_to_inches,
    convert_pa_to_mb,
    convert_wind_speed_to_mph_and_kph,
)

logger = logging.getLogger(__name__)


def _extract_scalar(value: Any) -> Any:
    """Recursively extract a scalar value from nested NWS response objects."""
    if isinstance(value, dict):
        if "value" in value:
            return _extract_scalar(value["value"])
        if "values" in value and isinstance(value["values"], list):
            for item in value["values"]:
                extracted = _extract_scalar(item)
                if extracted is not None:
                    return extracted
        return None
    if isinstance(value, list):
        for item in value:
            extracted = _extract_scalar(item)
            if extracted is not None:
                return extracted
        return None
    return value


def _extract_float(value: Any) -> float | None:
    """Extract a float from an NWS response value."""
    scalar = _extract_scalar(value)
    if isinstance(scalar, (int, float)):
        return float(scalar)
    if isinstance(scalar, str):
        try:
            return float(scalar)
        except ValueError:
            return None
    return None


def _format_unit(unit_code: str | None) -> str | None:
    """Return a human-readable suffix for WMO unit codes."""
    if not unit_code:
        return None
    unit = unit_code.split(":")[-1]
    replacements = {
        "km_h-1": " km/h",
        "m_s-1": " m/s",
        "mi_h-1": " mph",
        "kn": " kn",
        "kt": " kt",
    }
    return replacements.get(unit, f" {unit}")


def _format_wind_speed(value: Any) -> str | None:
    """Format NWS wind speed objects into a readable string."""
    if value is None:
        return None
    if isinstance(value, dict):
        unit_code = value.get("unitCode")
        numeric = _extract_float(value.get("value"))
        if numeric is None:
            return None
        mph, kph = convert_wind_speed_to_mph_and_kph(numeric, unit_code)
        if mph is not None and kph is not None:
            return f"{round(mph)} mph ({round(kph)} km/h)"
        if mph is not None:
            return f"{round(mph)} mph"
        if kph is not None:
            return f"{round(kph)} km/h"
        suffix = _format_unit(unit_code)
        return f"{numeric}{suffix}" if suffix else str(numeric)
    scalar = _extract_scalar(value)
    if scalar is None:
        return None
    if isinstance(scalar, (int, float)):
        return f"{scalar}"
    return str(scalar)


async def _client_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    """Call AsyncClient.get allowing for mocked synchronous responses in tests."""
    response = client.get(url, headers=headers, params=params)
    if inspect.isawaitable(response):
        return await response
    return response


async def get_nws_all_data_parallel(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient,
) -> tuple[
    CurrentConditions | None,
    Forecast | None,
    str | None,
    WeatherAlerts | None,
    HourlyForecast | None,
]:
    """
    Fetch all NWS data in parallel with optimized grid data caching.

    Returns: (current, forecast, discussion, alerts, hourly_forecast)
    """
    try:
        # First, fetch grid data once
        grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
        headers = {"User-Agent": user_agent}
        feature_headers = headers.copy()
        feature_headers["Feature-Flags"] = "forecast_temperature_qv, forecast_wind_speed_qv"

        response = await _client_get(client, grid_url, headers=headers)
        response.raise_for_status()
        grid_data = response.json()

        # Now fetch all other data in parallel, reusing grid_data
        current_task = asyncio.create_task(
            get_nws_current_conditions(location, nws_base_url, user_agent, timeout, client)
        )
        forecast_task = asyncio.create_task(
            get_nws_forecast_and_discussion(
                location, nws_base_url, user_agent, timeout, client, grid_data
            )
        )
        alerts_task = asyncio.create_task(
            get_nws_alerts(location, nws_base_url, user_agent, timeout, client)
        )
        hourly_task = asyncio.create_task(
            get_nws_hourly_forecast(location, nws_base_url, user_agent, timeout, client, grid_data)
        )

        # Gather all results
        current = await current_task
        forecast, discussion = await forecast_task
        alerts = await alerts_task
        hourly_forecast = await hourly_task

        return current, forecast, discussion, alerts, hourly_forecast

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS data in parallel: {exc}")
        return None, None, None, None, None


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

        # Use provided client or create a new one
        if client is not None:
            response = await _client_get(client, grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()

            stations_url = grid_data["properties"]["observationStations"]
            response = await _client_get(client, stations_url, headers=headers)
            response.raise_for_status()
            stations_data = response.json()

            if not stations_data["features"]:
                logger.warning("No observation stations found")
                return None

            station_id = stations_data["features"][0]["properties"]["stationIdentifier"]
            obs_url = f"{nws_base_url}/stations/{station_id}/observations/latest"

            response = await _client_get(client, obs_url, headers=headers)
            response.raise_for_status()
            obs_data = response.json()

            return parse_nws_current_conditions(obs_data)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()

            stations_url = grid_data["properties"]["observationStations"]
            response = await new_client.get(stations_url, headers=headers)
            response.raise_for_status()
            stations_data = response.json()

            if not stations_data["features"]:
                logger.warning("No observation stations found")
                return None

            station_id = stations_data["features"][0]["properties"]["stationIdentifier"]
            obs_url = f"{nws_base_url}/stations/{station_id}/observations/latest"

            response = await new_client.get(obs_url, headers=headers)
            response.raise_for_status()
            obs_data = response.json()

            return parse_nws_current_conditions(obs_data)

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS current conditions: {exc}")
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


async def get_nws_forecast_and_discussion(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
    grid_data: dict[str, Any] | None = None,
) -> tuple[Forecast | None, str | None]:
    """Fetch forecast and discussion from the NWS API for the given location."""
    try:
        headers = {"User-Agent": user_agent}
        feature_headers = headers.copy()
        feature_headers["Feature-Flags"] = "forecast_temperature_qv, forecast_wind_speed_qv"

        # Use provided client or create a new one
        if client is not None:
            # Fetch grid data if not provided
            if grid_data is None:
                grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
                response = await _client_get(client, grid_url, headers=headers)
                response.raise_for_status()
                grid_data = response.json()

            forecast_url = grid_data["properties"]["forecast"]
            response = await _client_get(client, forecast_url, headers=feature_headers)
            response.raise_for_status()
            forecast_data = response.json()

            discussion = await get_nws_discussion(client, headers, grid_data, nws_base_url)

            return parse_nws_forecast(forecast_data), discussion
        grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()

            forecast_url = grid_data["properties"]["forecast"]
            response = await new_client.get(forecast_url, headers=feature_headers)
            response.raise_for_status()
            forecast_data = response.json()

            discussion = await get_nws_discussion(new_client, headers, grid_data, nws_base_url)

            return parse_nws_forecast(forecast_data), discussion

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS forecast and discussion: {exc}")
        return None, None


async def get_nws_discussion(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    grid_data: dict[str, Any],
    nws_base_url: str,
) -> str:
    """Fetch the NWS Area Forecast Discussion (AFD) for the given grid data."""
    try:
        forecast_url = grid_data.get("properties", {}).get("forecast")
        if not forecast_url:
            logger.warning("No forecast URL found in grid data")
            return "Forecast discussion not available."

        parts = forecast_url.split("/")
        if len(parts) < 6:
            logger.warning(f"Unexpected forecast URL format: {forecast_url}")
            return "Forecast discussion not available."

        office_id = parts[-3]
        logger.info(f"Fetching AFD for office: {office_id}")

        products_url = f"{nws_base_url}/products/types/AFD/locations/{office_id}"
        response = await _client_get(client, products_url, headers=headers)

        if response.status_code != 200:
            logger.warning(f"Failed to get AFD products: HTTP {response.status_code}")
            return "Forecast discussion not available."

        products_data = response.json()

        if not products_data.get("@graph"):
            logger.warning(f"No AFD products found for office {office_id}")
            return "Forecast discussion not available for this location."

        latest_product = products_data["@graph"][0]
        latest_product_id = latest_product.get("id")
        if not latest_product_id:
            logger.warning("No product ID found in latest AFD product")
            return "Forecast discussion not available."

        product_url = f"{nws_base_url}/products/{latest_product_id}"
        response = await _client_get(client, product_url, headers=headers)

        if response.status_code != 200:
            logger.warning(f"Failed to get AFD product text: HTTP {response.status_code}")
            return "Forecast discussion not available."

        product_data = response.json()
        product_text = product_data.get("productText")

        if not product_text:
            logger.warning("No product text found in AFD product")
            return "Forecast discussion not available."

        logger.info(f"Successfully fetched AFD for office {office_id}")
        return product_text

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS discussion: {exc}")
        return "Forecast discussion not available due to error."


async def get_nws_alerts(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
) -> WeatherAlerts | None:
    """Fetch weather alerts from the NWS API."""
    try:
        alerts_url = f"{nws_base_url}/alerts/active"
        params = {
            "point": f"{location.latitude},{location.longitude}",
            "status": "actual",
            "message_type": "alert",
        }
        headers = {"User-Agent": user_agent}

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
        return WeatherAlerts(alerts=[])


async def get_nws_hourly_forecast(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
    grid_data: dict[str, Any] | None = None,
) -> HourlyForecast | None:
    """Fetch hourly forecast from the NWS API."""
    try:
        headers = {"User-Agent": user_agent}
        feature_headers = headers.copy()
        feature_headers["Feature-Flags"] = "forecast_temperature_qv, forecast_wind_speed_qv"

        # Use provided client or create a new one
        if client is not None:
            # Fetch grid data if not provided
            if grid_data is None:
                grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
                response = await _client_get(client, grid_url, headers=headers)
                response.raise_for_status()
                grid_data = response.json()

            hourly_forecast_url = grid_data.get("properties", {}).get("forecastHourly")
            if not hourly_forecast_url:
                logger.warning("No hourly forecast URL found in grid data")
                return None

            response = await _client_get(client, hourly_forecast_url, headers=feature_headers)
            response.raise_for_status()
            hourly_data = response.json()

            return parse_nws_hourly_forecast(hourly_data)
        grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()

            hourly_forecast_url = grid_data.get("properties", {}).get("forecastHourly")
            if not hourly_forecast_url:
                logger.warning("No hourly forecast URL found in grid data")
                return None

            response = await new_client.get(hourly_forecast_url, headers=feature_headers)
            response.raise_for_status()
            hourly_data = response.json()

            return parse_nws_hourly_forecast(hourly_data)

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS hourly forecast: {exc}")
        return None


async def get_nws_tafs(
    station_id: str,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient,
) -> str | None:
    """Fetch the most recent Terminal Aerodrome Forecast for a station."""
    del timeout  # The caller manages the async client lifecycle.

    taf_url = f"{nws_base_url}/stations/{station_id}/tafs"
    headers = {"User-Agent": user_agent}

    try:
        response = await _client_get(client, taf_url, headers=headers)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to fetch TAF for {station_id}: {exc}")
        return None

    data = response.json()
    features = data.get("features", [])
    for feature in features:
        properties = feature.get("properties", {})
        raw_message = properties.get("rawMessage")
        if raw_message:
            return raw_message.strip()

    logger.debug(f"No TAF message returned for station {station_id}")
    return None


async def get_nws_sigmets(
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient,
    *,
    atsu: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch active SIGMET or AIRMET advisories."""
    del timeout

    sigmet_url = f"{nws_base_url}/aviation/sigmets"
    headers = {"User-Agent": user_agent}
    params: dict[str, Any] | None = {"atsu": atsu} if atsu else None

    try:
        response = await _client_get(client, sigmet_url, headers=headers, params=params)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to fetch SIGMET data: {exc}")
        return []

    data = response.json()
    features = data.get("features", [])
    return [feature.get("properties", feature) for feature in features]


async def get_nws_cwas(
    cwsu_id: str,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    """Fetch Center Weather Advisories for a CWSU identifier."""
    del timeout

    cwa_url = f"{nws_base_url}/aviation/cwsus/{cwsu_id}/cwas"
    headers = {"User-Agent": user_agent}

    try:
        response = await _client_get(client, cwa_url, headers=headers)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to fetch CWA data for {cwsu_id}: {exc}")
        return []

    data = response.json()
    features = data.get("features", [])
    return [feature.get("properties", feature) for feature in features]


async def get_nws_radar_profiler(
    station_id: str,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient,
) -> dict[str, Any] | None:
    """Fetch metadata for a radar wind profiler station."""
    del timeout

    profiler_url = f"{nws_base_url}/radar/profilers/{station_id}"
    headers = {"User-Agent": user_agent}

    try:
        response = await _client_get(client, profiler_url, headers=headers)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to fetch radar profiler {station_id}: {exc}")
        return None

    return response.json()


async def get_nws_marine_forecast(
    zone_type: str,
    zone_id: str,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient,
) -> dict[str, Any] | None:
    """Fetch a marine zone forecast."""
    del timeout

    marine_url = f"{nws_base_url}/zones/{zone_type}/{zone_id}/forecast"
    headers = {"User-Agent": user_agent}

    try:
        response = await _client_get(client, marine_url, headers=headers)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to fetch marine forecast for {zone_type}/{zone_id}: {exc}")
        return None

    return response.json()


def parse_nws_current_conditions(data: dict) -> CurrentConditions:
    """Parse NWS current conditions payload into a CurrentConditions model."""
    props = data.get("properties", {})

    temp_c = props.get("temperature", {}).get("value")
    temp_f = (temp_c * 9 / 5) + 32 if temp_c is not None else None

    humidity = props.get("relativeHumidity", {}).get("value")
    humidity = round(humidity) if humidity is not None else None

    dewpoint_c = props.get("dewpoint", {}).get("value")
    dewpoint_f = (dewpoint_c * 9 / 5) + 32 if dewpoint_c is not None else None

    visibility_m = props.get("visibility", {}).get("value")
    visibility_miles = visibility_m / 1609.344 if visibility_m is not None else None
    visibility_km = visibility_m / 1000 if visibility_m is not None else None

    uv_index_value = props.get("uvIndex", {}).get("value")
    uv_index = None
    if uv_index_value is not None:
        try:
            uv_index = float(uv_index_value)
        except (TypeError, ValueError):
            uv_index = None

    wind_speed = props.get("windSpeed", {})
    wind_speed_value = wind_speed.get("value")
    wind_speed_unit = wind_speed.get("unitCode")
    wind_speed_mph, wind_speed_kph = convert_wind_speed_to_mph_and_kph(
        wind_speed_value, wind_speed_unit
    )

    wind_direction = props.get("windDirection", {}).get("value")

    pressure_pa = props.get("barometricPressure", {}).get("value")
    pressure_in = convert_pa_to_inches(pressure_pa)

    timestamp = props.get("timestamp")
    last_updated = None
    if isinstance(timestamp, str) and timestamp:
        try:
            last_updated = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            logger.debug(f"Failed to parse observation timestamp: {timestamp}")

    return CurrentConditions(
        temperature_f=temp_f,
        temperature_c=temp_c,
        condition=props.get("textDescription"),
        humidity=humidity,
        dewpoint_f=dewpoint_f,
        dewpoint_c=dewpoint_c,
        wind_speed_mph=wind_speed_mph,
        wind_speed_kph=wind_speed_kph,
        wind_direction=wind_direction,
        pressure_in=pressure_in,
        pressure_mb=convert_pa_to_mb(pressure_pa),
        feels_like_f=None,
        feels_like_c=None,
        visibility_miles=visibility_miles,
        visibility_km=visibility_km,
        uv_index=uv_index,
        last_updated=last_updated or datetime.now(),
    )


def parse_nws_forecast(data: dict) -> Forecast:
    """Parse NWS forecast payload into a Forecast model."""
    periods = []

    for period_data in data.get("properties", {}).get("periods", []):
        temperature = _extract_float(period_data.get("temperature"))
        temperature_unit = _extract_scalar(period_data.get("temperatureUnit")) or "F"

        wind_direction_value = _extract_scalar(period_data.get("windDirection"))
        wind_direction = str(wind_direction_value) if wind_direction_value is not None else None

        period = ForecastPeriod(
            name=period_data.get("name", ""),
            temperature=temperature,
            temperature_unit=str(temperature_unit),
            short_forecast=period_data.get("shortForecast"),
            detailed_forecast=period_data.get("detailedForecast"),
            wind_speed=_format_wind_speed(period_data.get("windSpeed")),
            wind_direction=wind_direction,
            icon=period_data.get("icon"),
        )
        periods.append(period)

    return Forecast(periods=periods, generated_at=datetime.now())


def parse_nws_alerts(data: dict) -> WeatherAlerts:
    """Parse NWS alerts payload into a WeatherAlerts collection."""
    alerts: list[WeatherAlert] = []

    for alert_data in data.get("features", []):
        props = alert_data.get("properties", {})

        alert_id = None
        if "id" in alert_data:
            alert_id = alert_data["id"]
        elif "identifier" in props:
            alert_id = props["identifier"]
        elif "@id" in props:
            alert_id = props["@id"]

        onset = None
        expires = None

        if props.get("onset"):
            try:
                onset = datetime.fromisoformat(props["onset"].replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Failed to parse onset time: {props['onset']}")

        if props.get("expires"):
            try:
                expires = datetime.fromisoformat(props["expires"].replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Failed to parse expires time: {props['expires']}")

        alert = WeatherAlert(
            title=props.get("headline", "Weather Alert"),
            description=props.get("description", ""),
            severity=props.get("severity", "Unknown"),
            urgency=props.get("urgency", "Unknown"),
            certainty=props.get("certainty", "Unknown"),
            event=props.get("event"),
            headline=props.get("headline"),
            instruction=props.get("instruction"),
            onset=onset,
            expires=expires,
            areas=props.get("areaDesc", "").split("; ") if props.get("areaDesc") else [],
            id=alert_id,
        )
        alerts.append(alert)

        if alert_id:
            logger.debug(f"Parsed alert with ID: {alert_id}")
        else:
            logger.debug("Parsed alert without ID, will generate unique ID")

    logger.info(f"Parsed {len(alerts)} alerts from NWS API")
    return WeatherAlerts(alerts=alerts)


def parse_nws_hourly_forecast(data: dict) -> HourlyForecast:
    """Parse NWS hourly forecast payload into an HourlyForecast model."""
    periods = []

    for period_data in data.get("properties", {}).get("periods", []):
        start_time_str = period_data.get("startTime")
        start_time = None
        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Failed to parse start time: {start_time_str}")

        end_time_str = period_data.get("endTime")
        end_time = None
        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Failed to parse end time: {end_time_str}")

        temperature = _extract_float(period_data.get("temperature"))
        temperature_unit = _extract_scalar(period_data.get("temperatureUnit")) or "F"

        wind_direction_value = _extract_scalar(period_data.get("windDirection"))
        wind_direction = str(wind_direction_value) if wind_direction_value is not None else None

        period = HourlyForecastPeriod(
            start_time=start_time or datetime.now(),
            end_time=end_time,
            temperature=temperature,
            temperature_unit=str(temperature_unit),
            short_forecast=period_data.get("shortForecast"),
            wind_speed=_format_wind_speed(period_data.get("windSpeed")),
            wind_direction=wind_direction,
            icon=period_data.get("icon"),
        )
        periods.append(period)

    return HourlyForecast(periods=periods, generated_at=datetime.now())
