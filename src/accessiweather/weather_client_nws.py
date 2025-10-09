"""NWS API client methods for fetching and parsing weather data from the National Weather Service."""

from __future__ import annotations

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


async def get_nws_current_conditions(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
) -> CurrentConditions | None:
    """Fetch current conditions from the NWS API for the given location."""
    try:
        grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            headers = {"User-Agent": user_agent}

            response = await client.get(grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()

            stations_url = grid_data["properties"]["observationStations"]
            response = await client.get(stations_url, headers=headers)
            response.raise_for_status()
            stations_data = response.json()

            if not stations_data["features"]:
                logger.warning("No observation stations found")
                return None

            station_id = stations_data["features"][0]["properties"]["stationIdentifier"]
            obs_url = f"{nws_base_url}/stations/{station_id}/observations/latest"

            response = await client.get(obs_url, headers=headers)
            response.raise_for_status()
            obs_data = response.json()

            return parse_nws_current_conditions(obs_data)

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS current conditions: {exc}")
        return None


async def get_nws_forecast_and_discussion(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
) -> tuple[Forecast | None, str | None]:
    """Fetch forecast and discussion from the NWS API for the given location."""
    try:
        grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            headers = {"User-Agent": user_agent}

            response = await client.get(grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()

            forecast_url = grid_data["properties"]["forecast"]
            response = await client.get(forecast_url, headers=headers)
            response.raise_for_status()
            forecast_data = response.json()

            discussion = await get_nws_discussion(client, headers, grid_data, nws_base_url)

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
        response = await client.get(products_url, headers=headers)

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
        response = await client.get(product_url, headers=headers)

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
) -> WeatherAlerts | None:
    """Fetch weather alerts from the NWS API."""
    try:
        alerts_url = f"{nws_base_url}/alerts/active"
        params = {
            "point": f"{location.latitude},{location.longitude}",
            "status": "actual",
            "message_type": "alert",
        }

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            headers = {"User-Agent": user_agent}
            response = await client.get(alerts_url, params=params, headers=headers)
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
) -> HourlyForecast | None:
    """Fetch hourly forecast from the NWS API."""
    try:
        grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            headers = {"User-Agent": user_agent}
            response = await client.get(grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()

            hourly_forecast_url = grid_data.get("properties", {}).get("forecastHourly")
            if not hourly_forecast_url:
                logger.warning("No hourly forecast URL found in grid data")
                return None

            response = await client.get(hourly_forecast_url, headers=headers)
            response.raise_for_status()
            hourly_data = response.json()

            return parse_nws_hourly_forecast(hourly_data)

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS hourly forecast: {exc}")
        return None


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
    if timestamp:
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
        last_updated=last_updated or datetime.now(),
    )


def parse_nws_forecast(data: dict) -> Forecast:
    """Parse NWS forecast payload into a Forecast model."""
    periods = []

    for period_data in data.get("properties", {}).get("periods", []):
        period = ForecastPeriod(
            name=period_data.get("name", ""),
            temperature=period_data.get("temperature"),
            temperature_unit=period_data.get("temperatureUnit", "F"),
            short_forecast=period_data.get("shortForecast"),
            detailed_forecast=period_data.get("detailedForecast"),
            wind_speed=period_data.get("windSpeed"),
            wind_direction=period_data.get("windDirection"),
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

        period = HourlyForecastPeriod(
            start_time=start_time or datetime.now(),
            end_time=end_time,
            temperature=period_data.get("temperature"),
            temperature_unit=period_data.get("temperatureUnit", "F"),
            short_forecast=period_data.get("shortForecast"),
            wind_speed=period_data.get("windSpeed"),
            wind_direction=period_data.get("windDirection"),
            icon=period_data.get("icon"),
        )
        periods.append(period)

    return HourlyForecast(periods=periods, generated_at=datetime.now())
