import datetime
from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.archive_response import ArchiveResponse
from ...models.get_archive_temperature_unit import GetArchiveTemperatureUnit
from ...models.open_meteo_error import OpenMeteoError
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    latitude: float,
    longitude: float,
    start_date: datetime.date,
    end_date: datetime.date,
    daily: Union[Unset, str] = UNSET,
    temperature_unit: Union[Unset, GetArchiveTemperatureUnit] = UNSET,
    timezone: Union[Unset, str] = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    params["latitude"] = latitude

    params["longitude"] = longitude

    json_start_date = start_date.isoformat()
    params["start_date"] = json_start_date

    json_end_date = end_date.isoformat()
    params["end_date"] = json_end_date

    params["daily"] = daily

    json_temperature_unit: Union[Unset, str] = UNSET
    if not isinstance(temperature_unit, Unset):
        json_temperature_unit = temperature_unit.value

    params["temperature_unit"] = json_temperature_unit

    params["timezone"] = timezone

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/archive",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Union[ArchiveResponse, OpenMeteoError]]:
    if response.status_code == 200:
        response_200 = ArchiveResponse.from_dict(response.json())

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
) -> Response[Union[ArchiveResponse, OpenMeteoError]]:
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
    start_date: datetime.date,
    end_date: datetime.date,
    daily: Union[Unset, str] = UNSET,
    temperature_unit: Union[Unset, GetArchiveTemperatureUnit] = UNSET,
    timezone: Union[Unset, str] = UNSET,
) -> Response[Union[ArchiveResponse, OpenMeteoError]]:
    """Retrieve historical weather data

     Provides historical daily weather statistics for the specified period. Used to compare current
    conditions against past weather.

    Args:
        latitude (float):
        longitude (float):
        start_date (datetime.date):
        end_date (datetime.date):
        daily (Union[Unset, str]):
        temperature_unit (Union[Unset, GetArchiveTemperatureUnit]):
        timezone (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[ArchiveResponse, OpenMeteoError]]
    """

    kwargs = _get_kwargs(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        daily=daily,
        temperature_unit=temperature_unit,
        timezone=timezone,
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
    start_date: datetime.date,
    end_date: datetime.date,
    daily: Union[Unset, str] = UNSET,
    temperature_unit: Union[Unset, GetArchiveTemperatureUnit] = UNSET,
    timezone: Union[Unset, str] = UNSET,
) -> Optional[Union[ArchiveResponse, OpenMeteoError]]:
    """Retrieve historical weather data

     Provides historical daily weather statistics for the specified period. Used to compare current
    conditions against past weather.

    Args:
        latitude (float):
        longitude (float):
        start_date (datetime.date):
        end_date (datetime.date):
        daily (Union[Unset, str]):
        temperature_unit (Union[Unset, GetArchiveTemperatureUnit]):
        timezone (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[ArchiveResponse, OpenMeteoError]
    """

    return sync_detailed(
        client=client,
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        daily=daily,
        temperature_unit=temperature_unit,
        timezone=timezone,
    ).parsed


async def asyncio_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    latitude: float,
    longitude: float,
    start_date: datetime.date,
    end_date: datetime.date,
    daily: Union[Unset, str] = UNSET,
    temperature_unit: Union[Unset, GetArchiveTemperatureUnit] = UNSET,
    timezone: Union[Unset, str] = UNSET,
) -> Response[Union[ArchiveResponse, OpenMeteoError]]:
    """Retrieve historical weather data

     Provides historical daily weather statistics for the specified period. Used to compare current
    conditions against past weather.

    Args:
        latitude (float):
        longitude (float):
        start_date (datetime.date):
        end_date (datetime.date):
        daily (Union[Unset, str]):
        temperature_unit (Union[Unset, GetArchiveTemperatureUnit]):
        timezone (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[ArchiveResponse, OpenMeteoError]]
    """

    kwargs = _get_kwargs(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        daily=daily,
        temperature_unit=temperature_unit,
        timezone=timezone,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: Union[AuthenticatedClient, Client],
    latitude: float,
    longitude: float,
    start_date: datetime.date,
    end_date: datetime.date,
    daily: Union[Unset, str] = UNSET,
    temperature_unit: Union[Unset, GetArchiveTemperatureUnit] = UNSET,
    timezone: Union[Unset, str] = UNSET,
) -> Optional[Union[ArchiveResponse, OpenMeteoError]]:
    """Retrieve historical weather data

     Provides historical daily weather statistics for the specified period. Used to compare current
    conditions against past weather.

    Args:
        latitude (float):
        longitude (float):
        start_date (datetime.date):
        end_date (datetime.date):
        daily (Union[Unset, str]):
        temperature_unit (Union[Unset, GetArchiveTemperatureUnit]):
        timezone (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[ArchiveResponse, OpenMeteoError]
    """

    return (
        await asyncio_detailed(
            client=client,
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
            daily=daily,
            temperature_unit=temperature_unit,
            timezone=timezone,
        )
    ).parsed
