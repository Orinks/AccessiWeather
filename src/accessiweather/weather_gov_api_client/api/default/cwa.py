import datetime
from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.center_weather_advisory_geo_json import CenterWeatherAdvisoryGeoJson
from ...models.nws_center_weather_service_unit_id import NWSCenterWeatherServiceUnitId
from ...types import Response


def _get_kwargs(
    cwsu_id: NWSCenterWeatherServiceUnitId,
    date: datetime.date,
    sequence: int,
) -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/aviation/cwsus/{cwsu_id}/cwas/{date}/{sequence}",
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[CenterWeatherAdvisoryGeoJson]:
    if response.status_code == 200:
        response_200 = CenterWeatherAdvisoryGeoJson.from_dict(response.json())

        return response_200
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[CenterWeatherAdvisoryGeoJson]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    cwsu_id: NWSCenterWeatherServiceUnitId,
    date: datetime.date,
    sequence: int,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[CenterWeatherAdvisoryGeoJson]:
    """Returns a list of Center Weather Advisories from a CWSU

    Args:
        cwsu_id (NWSCenterWeatherServiceUnitId): Three-letter identifier for a Center Weather
            Service Unit (CWSU).
        date (datetime.date): Date (in YYYY-MM-DD format).
        sequence (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CenterWeatherAdvisoryGeoJson]
    """

    kwargs = _get_kwargs(
        cwsu_id=cwsu_id,
        date=date,
        sequence=sequence,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    cwsu_id: NWSCenterWeatherServiceUnitId,
    date: datetime.date,
    sequence: int,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[CenterWeatherAdvisoryGeoJson]:
    """Returns a list of Center Weather Advisories from a CWSU

    Args:
        cwsu_id (NWSCenterWeatherServiceUnitId): Three-letter identifier for a Center Weather
            Service Unit (CWSU).
        date (datetime.date): Date (in YYYY-MM-DD format).
        sequence (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CenterWeatherAdvisoryGeoJson
    """

    return sync_detailed(
        cwsu_id=cwsu_id,
        date=date,
        sequence=sequence,
        client=client,
    ).parsed


async def asyncio_detailed(
    cwsu_id: NWSCenterWeatherServiceUnitId,
    date: datetime.date,
    sequence: int,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[CenterWeatherAdvisoryGeoJson]:
    """Returns a list of Center Weather Advisories from a CWSU

    Args:
        cwsu_id (NWSCenterWeatherServiceUnitId): Three-letter identifier for a Center Weather
            Service Unit (CWSU).
        date (datetime.date): Date (in YYYY-MM-DD format).
        sequence (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CenterWeatherAdvisoryGeoJson]
    """

    kwargs = _get_kwargs(
        cwsu_id=cwsu_id,
        date=date,
        sequence=sequence,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    cwsu_id: NWSCenterWeatherServiceUnitId,
    date: datetime.date,
    sequence: int,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[CenterWeatherAdvisoryGeoJson]:
    """Returns a list of Center Weather Advisories from a CWSU

    Args:
        cwsu_id (NWSCenterWeatherServiceUnitId): Three-letter identifier for a Center Weather
            Service Unit (CWSU).
        date (datetime.date): Date (in YYYY-MM-DD format).
        sequence (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CenterWeatherAdvisoryGeoJson
    """

    return (
        await asyncio_detailed(
            cwsu_id=cwsu_id,
            date=date,
            sequence=sequence,
            client=client,
        )
    ).parsed
