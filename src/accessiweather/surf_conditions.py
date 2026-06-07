"""Surf and beach-condition helpers for official and derived sources."""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from .models import Location, TextProduct
from .weather_client_parsers import degrees_to_cardinal

logger = logging.getLogger(__name__)

OPENMETEO_MARINE_BASE_URL = "https://marine-api.open-meteo.com/v1"
_OPENMETEO_CURRENT_VARIABLES = (
    "wave_height",
    "wave_direction",
    "wave_period",
    "swell_wave_height",
    "swell_wave_direction",
    "swell_wave_period",
    "sea_surface_temperature",
)


@dataclass(frozen=True)
class SurfConditionReport:
    """A source-labelled surf/beach conditions summary."""

    source_name: str
    product_id: str
    text: str
    issued_at: datetime | None = None
    official: bool = False

    def to_text_product(self) -> TextProduct:
        """Convert the report to the TextProduct shape used by Forecaster Notes."""
        return TextProduct(
            product_type="SURF_CONDITIONS",
            product_id=self.product_id,
            cwa_office=self.source_name,
            issuance_time=self.issued_at,
            product_text=self.text,
            headline=(
                f"Surf conditions from {self.source_name}"
                if not self.official
                else f"Official surf forecast from {self.source_name}"
            ),
        )


async def _client_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Call AsyncClient.get while tolerating synchronous test doubles."""
    response = client.get(url, params=params, headers=headers)
    if inspect.isawaitable(response):
        return await response
    return response


def _first_present(data: dict[str, Any], key: str) -> Any:
    value = data.get(key)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _format_value(value: Any, unit: str | None, *, precision: int = 1) -> str | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        text = f"{float(value):.{precision}f}".rstrip("0").rstrip(".")
    else:
        text = str(value).strip()
    if not text:
        return None
    return f"{text} {unit}".strip() if unit else text


def _format_direction(value: Any) -> str | None:
    if value is None:
        return None
    try:
        degrees = float(value)
    except (TypeError, ValueError):
        return str(value).strip() or None
    cardinal = degrees_to_cardinal(degrees)
    return f"{cardinal} ({degrees:.0f} degrees)"


def format_openmeteo_marine_report(
    data: dict[str, Any], location: Location
) -> SurfConditionReport | None:
    """Format Open-Meteo Marine API current data as accessible plain text."""
    current = data.get("current")
    if not isinstance(current, dict) or not current:
        return None
    units = data.get("current_units") if isinstance(data.get("current_units"), dict) else {}

    lines = [
        f"Surf conditions from Open-Meteo Marine for {location.name}.",
        "Marine/surf conditions from Open-Meteo Marine; not an official NWS Surf Zone Forecast.",
    ]

    fields = (
        (
            "Wave height",
            _format_value(_first_present(current, "wave_height"), units.get("wave_height")),
        ),
        ("Wave direction", _format_direction(_first_present(current, "wave_direction"))),
        (
            "Wave period",
            _format_value(_first_present(current, "wave_period"), units.get("wave_period")),
        ),
        (
            "Swell height",
            _format_value(
                _first_present(current, "swell_wave_height"), units.get("swell_wave_height")
            ),
        ),
        ("Swell direction", _format_direction(_first_present(current, "swell_wave_direction"))),
        (
            "Swell period",
            _format_value(
                _first_present(current, "swell_wave_period"), units.get("swell_wave_period")
            ),
        ),
        (
            "Sea surface temperature",
            _format_value(
                _first_present(current, "sea_surface_temperature"),
                units.get("sea_surface_temperature"),
            ),
        ),
    )
    for label, value in fields:
        if value:
            lines.append(f"{label}: {value}.")

    if len(lines) == 2:
        return None

    issued_at = None
    current_time = current.get("time")
    if isinstance(current_time, str) and current_time:
        try:
            issued_at = datetime.fromisoformat(current_time.replace("Z", "+00:00"))
        except ValueError:
            issued_at = None
    return SurfConditionReport(
        source_name="Open-Meteo Marine",
        product_id="openmeteo-marine-surf-conditions",
        issued_at=issued_at or datetime.now(UTC),
        text="\n".join(lines),
    )


async def fetch_openmeteo_marine_surf_conditions(
    location: Location,
    *,
    marine_base_url: str = OPENMETEO_MARINE_BASE_URL,
    client: httpx.AsyncClient | None = None,
    timeout: float = 10.0,
    user_agent: str = "AccessiWeather (github.com/orinks/accessiweather)",
) -> TextProduct | None:
    """Fetch a small Open-Meteo Marine surf/beach conditions summary."""
    if location.latitude is None or location.longitude is None:
        return None

    url = f"{marine_base_url}/marine"
    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "current": ",".join(_OPENMETEO_CURRENT_VARIABLES),
        "timezone": "auto",
    }
    headers = {"User-Agent": user_agent}

    async def _run(http_client: httpx.AsyncClient) -> TextProduct | None:
        try:
            response = await _client_get(http_client, url, params=params, headers=headers)
            if response.status_code != 200:
                logger.debug("Open-Meteo Marine returned HTTP %s", response.status_code)
                return None
            report = format_openmeteo_marine_report(response.json(), location)
            return report.to_text_product() if report is not None else None
        except (httpx.TimeoutException, httpx.TransportError, httpx.RequestError, ValueError):
            logger.debug("Open-Meteo Marine surf conditions unavailable", exc_info=True)
            return None

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
        return await _run(new_client)


async def fetch_pirate_weather_beach_conditions(
    location: Location,
    weather_client: object | None = None,
) -> TextProduct | None:
    """Build beach-weather context from an existing Pirate Weather client when available."""
    if weather_client is None:
        return None

    client_getter = getattr(weather_client, "_pirate_weather_client_for_location", None)
    pirate_client = client_getter(location) if callable(client_getter) else None
    if pirate_client is None:
        pirate_client = getattr(weather_client, "pirate_weather_client", None)
    if pirate_client is None:
        return None

    try:
        payload = await pirate_client.get_forecast_data(location)
    except Exception:  # noqa: BLE001
        logger.debug("Pirate Weather beach conditions unavailable", exc_info=True)
        return None
    if not isinstance(payload, dict):
        return None

    current = payload.get("currently")
    if not isinstance(current, dict):
        return None

    lines = [
        f"Surf conditions from Pirate Weather for {location.name}.",
        (
            "Beach-weather context from Pirate Weather; not an official NWS Surf Zone "
            "Forecast and wave data is not available from this source in AccessiWeather."
        ),
    ]
    for label, key, unit in (
        ("Conditions", "summary", ""),
        ("Temperature", "temperature", "degrees"),
        ("Feels like", "apparentTemperature", "degrees"),
        ("Wind speed", "windSpeed", "mph"),
        ("Wind gust", "windGust", "mph"),
        ("Wind direction", "windBearing", ""),
        ("UV index", "uvIndex", ""),
        ("Visibility", "visibility", "miles"),
    ):
        value = current.get(key)
        formatted = _format_direction(value) if key == "windBearing" else _format_value(value, unit)
        if formatted:
            lines.append(f"{label}: {formatted}.")

    precip_probability = current.get("precipProbability")
    if isinstance(precip_probability, int | float):
        lines.append(f"Precipitation chance: {precip_probability * 100:.0f} percent.")

    if len(lines) == 2:
        return None

    return TextProduct(
        product_type="SURF_CONDITIONS",
        product_id="pirate-weather-beach-conditions",
        cwa_office="Pirate Weather",
        issuance_time=datetime.now(UTC),
        product_text="\n".join(lines),
        headline="Surf conditions from Pirate Weather",
    )
