from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.forecast_response import ForecastResponse
from ...models.get_forecast_precipitation_unit import GetForecastPrecipitationUnit
from ...models.get_forecast_temperature_unit import GetForecastTemperatureUnit
from ...models.get_forecast_wind_speed_unit import GetForecastWindSpeedUnit
from ...models.open_meteo_error import OpenMeteoError
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    latitude: float,
    longitude: float,
    current: Union[Unset, str] = UNSET,
    hourly: Union[Unset, str] = UNSET,
    daily: Union[Unset, str] = UNSET,
    temperature_unit: Union[Unset, GetForecastTemperatureUnit] = UNSET,
    wind_speed_unit: Union[Unset, GetForecastWindSpeedUnit] = UNSET,
    precipitation_unit: Union[Unset, GetForecastPrecipitationUnit] = UNSET,
    timezone: Union[Unset, str] = UNSET,
    forecast_days: Union[Unset, int] = UNSET,
    forecast_hours: Union[Unset, int] = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    params["latitude"] = latitude

    params["longitude"] = longitude

    params["current"] = current

    params["hourly"] = hourly

    params["daily"] = daily

    json_temperature_unit: Union[Unset, str] = UNSET
    if not isinstance(temperature_unit, Unset):
        json_temperature_unit = temperature_unit.value

    params["temperature_unit"] = json_temperature_unit

    json_wind_speed_unit: Union[Unset, str] = UNSET
    if not isinstance(wind_speed_unit, Unset):
        json_wind_speed_unit = wind_speed_unit.value

    params["wind_speed_unit"] = json_wind_speed_unit

    json_precipitation_unit: Union[Unset, str] = UNSET
    if not isinstance(precipitation_unit, Unset):
        json_precipitation_unit = precipitation_unit.value

    params["precipitation_unit"] = json_precipitation_unit

    params["timezone"] = timezone

    params["forecast_days"] = forecast_days

    params["forecast_hours"] = forecast_hours

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/forecast",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Union[ForecastResponse, OpenMeteoError]]:
    if response.status_code == 200:
        response_200 = ForecastResponse.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = OpenMeteoError.from_dict(response.json())

        return response_400

    if response.status_code == 500:
        response_500 = OpenMeteoError.from_dict(response.json())

        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[Union[ForecastResponse, OpenMeteoError]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    latitude: float,
    longitude: float,
    current: Union[Unset, str] = UNSET,
    hourly: Union[Unset, str] = UNSET,
    daily: Union[Unset, str] = UNSET,
    temperature_unit: Union[Unset, GetForecastTemperatureUnit] = UNSET,
    wind_speed_unit: Union[Unset, GetForecastWindSpeedUnit] = UNSET,
    precipitation_unit: Union[Unset, GetForecastPrecipitationUnit] = UNSET,
    timezone: Union[Unset, str] = UNSET,
    forecast_days: Union[Unset, int] = UNSET,
    forecast_hours: Union[Unset, int] = UNSET,
) -> Response[Union[ForecastResponse, OpenMeteoError]]:
    """Retrieve forecast and current conditions

     Fetches current, hourly, and daily forecast data for a given location. The specific data returned
    depends on the `current`, `hourly`, and `daily` parameters supplied.

    Args:
        latitude (float):
        longitude (float):
        current (Union[Unset, str]):
        hourly (Union[Unset, str]):
        daily (Union[Unset, str]):
        temperature_unit (Union[Unset, GetForecastTemperatureUnit]):
        wind_speed_unit (Union[Unset, GetForecastWindSpeedUnit]):
        precipitation_unit (Union[Unset, GetForecastPrecipitationUnit]):
        timezone (Union[Unset, str]):
        forecast_days (Union[Unset, int]):
        forecast_hours (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[ForecastResponse, OpenMeteoError]]
    """

    kwargs = _get_kwargs(
        latitude=latitude,
        longitude=longitude,
        current=current,
        hourly=hourly,
        daily=daily,
        temperature_unit=temperature_unit,
        wind_speed_unit=wind_speed_unit,
        precipitation_unit=precipitation_unit,
        timezone=timezone,
        forecast_days=forecast_days,
        forecast_hours=forecast_hours,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: Union[AuthenticatedClient, Client],
    latitude: float,
    longitude: float,
    current: Union[Unset, str] = UNSET,
    hourly: Union[Unset, str] = UNSET,
    daily: Union[Unset, str] = UNSET,
    temperature_unit: Union[Unset, GetForecastTemperatureUnit] = UNSET,
    wind_speed_unit: Union[Unset, GetForecastWindSpeedUnit] = UNSET,
    precipitation_unit: Union[Unset, GetForecastPrecipitationUnit] = UNSET,
    timezone: Union[Unset, str] = UNSET,
    forecast_days: Union[Unset, int] = UNSET,
    forecast_hours: Union[Unset, int] = UNSET,
) -> Optional[Union[ForecastResponse, OpenMeteoError]]:
    """Retrieve forecast and current conditions

     Fetches current, hourly, and daily forecast data for a given location. The specific data returned
    depends on the `current`, `hourly`, and `daily` parameters supplied.

    Args:
        latitude (float):
        longitude (float):
        current (Union[Unset, str]):
        hourly (Union[Unset, str]):
        daily (Union[Unset, str]):
        temperature_unit (Union[Unset, GetForecastTemperatureUnit]):
        wind_speed_unit (Union[Unset, GetForecastWindSpeedUnit]):
        precipitation_unit (Union[Unset, GetForecastPrecipitationUnit]):
        timezone (Union[Unset, str]):
        forecast_days (Union[Unset, int]):
        forecast_hours (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[ForecastResponse, OpenMeteoError]
    """

    return sync_detailed(
        client=client,
        latitude=latitude,
        longitude=longitude,
        current=current,
        hourly=hourly,
        daily=daily,
        temperature_unit=temperature_unit,
        wind_speed_unit=wind_speed_unit,
        precipitation_unit=precipitation_unit,
        timezone=timezone,
        forecast_days=forecast_days,
        forecast_hours=forecast_hours,
    ).parsed


async def asyncio_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    latitude: float,
    longitude: float,
    current: Union[Unset, str] = UNSET,
    hourly: Union[Unset, str] = UNSET,
    daily: Union[Unset, str] = UNSET,
    temperature_unit: Union[Unset, GetForecastTemperatureUnit] = UNSET,
    wind_speed_unit: Union[Unset, GetForecastWindSpeedUnit] = UNSET,
    precipitation_unit: Union[Unset, GetForecastPrecipitationUnit] = UNSET,
    timezone: Union[Unset, str] = UNSET,
    forecast_days: Union[Unset, int] = UNSET,
    forecast_hours: Union[Unset, int] = UNSET,
) -> Response[Union[ForecastResponse, OpenMeteoError]]:
    """Retrieve forecast and current conditions

     Fetches current, hourly, and daily forecast data for a given location. The specific data returned
    depends on the `current`, `hourly`, and `daily` parameters supplied.

    Args:
        latitude (float):
        longitude (float):
        current (Union[Unset, str]):
        hourly (Union[Unset, str]):
        daily (Union[Unset, str]):
        temperature_unit (Union[Unset, GetForecastTemperatureUnit]):
        wind_speed_unit (Union[Unset, GetForecastWindSpeedUnit]):
        precipitation_unit (Union[Unset, GetForecastPrecipitationUnit]):
        timezone (Union[Unset, str]):
        forecast_days (Union[Unset, int]):
        forecast_hours (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[ForecastResponse, OpenMeteoError]]
    """

    kwargs = _get_kwargs(
        latitude=latitude,
        longitude=longitude,
        current=current,
        hourly=hourly,
        daily=daily,
        temperature_unit=temperature_unit,
        wind_speed_unit=wind_speed_unit,
        precipitation_unit=precipitation_unit,
        timezone=timezone,
        forecast_days=forecast_days,
        forecast_hours=forecast_hours,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: Union[AuthenticatedClient, Client],
    latitude: float,
    longitude: float,
    current: Union[Unset, str] = UNSET,
    hourly: Union[Unset, str] = UNSET,
    daily: Union[Unset, str] = UNSET,
    temperature_unit: Union[Unset, GetForecastTemperatureUnit] = UNSET,
    wind_speed_unit: Union[Unset, GetForecastWindSpeedUnit] = UNSET,
    precipitation_unit: Union[Unset, GetForecastPrecipitationUnit] = UNSET,
    timezone: Union[Unset, str] = UNSET,
    forecast_days: Union[Unset, int] = UNSET,
    forecast_hours: Union[Unset, int] = UNSET,
) -> Optional[Union[ForecastResponse, OpenMeteoError]]:
    """Retrieve forecast and current conditions

     Fetches current, hourly, and daily forecast data for a given location. The specific data returned
    depends on the `current`, `hourly`, and `daily` parameters supplied.

    Args:
        latitude (float):
        longitude (float):
        current (Union[Unset, str]):
        hourly (Union[Unset, str]):
        daily (Union[Unset, str]):
        temperature_unit (Union[Unset, GetForecastTemperatureUnit]):
        wind_speed_unit (Union[Unset, GetForecastWindSpeedUnit]):
        precipitation_unit (Union[Unset, GetForecastPrecipitationUnit]):
        timezone (Union[Unset, str]):
        forecast_days (Union[Unset, int]):
        forecast_hours (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[ForecastResponse, OpenMeteoError]
    """

    return (
        await asyncio_detailed(
            client=client,
            latitude=latitude,
            longitude=longitude,
            current=current,
            hourly=hourly,
            daily=daily,
            temperature_unit=temperature_unit,
            wind_speed_unit=wind_speed_unit,
            precipitation_unit=precipitation_unit,
            timezone=timezone,
            forecast_days=forecast_days,
            forecast_hours=forecast_hours,
        )
    ).parsed
