from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.center_weather_advisory_collection_geo_json import (
    CenterWeatherAdvisoryCollectionGeoJson,
)
from ...models.nws_center_weather_service_unit_id import NWSCenterWeatherServiceUnitId
from ...types import Response


def _get_kwargs(
    cwsu_id: NWSCenterWeatherServiceUnitId,
) -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/aviation/cwsus/{cwsu_id}/cwas",
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[CenterWeatherAdvisoryCollectionGeoJson]:
    if response.status_code == 200:
        response_200 = CenterWeatherAdvisoryCollectionGeoJson.from_dict(response.json())

        return response_200
    if client.raise_on_unexpected_status:
        raise e from Nonerrors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[CenterWeatherAdvisoryCollectionGeoJson]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    cwsu_id: NWSCenterWeatherServiceUnitId,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[CenterWeatherAdvisoryCollectionGeoJson]:
    """Returns a list of Center Weather Advisories from a CWSU

    Args:
        cwsu_id (NWSCenterWeatherServiceUnitId): Three-letter identifier for a Center Weather
            Service Unit (CWSU).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CenterWeatherAdvisoryCollectionGeoJson]
    """

    kwargs = _get_kwargs(
        cwsu_id=cwsu_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    cwsu_id: NWSCenterWeatherServiceUnitId,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[CenterWeatherAdvisoryCollectionGeoJson]:
    """Returns a list of Center Weather Advisories from a CWSU

    Args:
        cwsu_id (NWSCenterWeatherServiceUnitId): Three-letter identifier for a Center Weather
            Service Unit (CWSU).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CenterWeatherAdvisoryCollectionGeoJson
    """

    return sync_detailed(
        cwsu_id=cwsu_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    cwsu_id: NWSCenterWeatherServiceUnitId,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[CenterWeatherAdvisoryCollectionGeoJson]:
    """Returns a list of Center Weather Advisories from a CWSU

    Args:
        cwsu_id (NWSCenterWeatherServiceUnitId): Three-letter identifier for a Center Weather
            Service Unit (CWSU).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CenterWeatherAdvisoryCollectionGeoJson]
    """

    kwargs = _get_kwargs(
        cwsu_id=cwsu_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    cwsu_id: NWSCenterWeatherServiceUnitId,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[CenterWeatherAdvisoryCollectionGeoJson]:
    """Returns a list of Center Weather Advisories from a CWSU

    Args:
        cwsu_id (NWSCenterWeatherServiceUnitId): Three-letter identifier for a Center Weather
            Service Unit (CWSU).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CenterWeatherAdvisoryCollectionGeoJson
    """

    return (
        await asyncio_detailed(
            cwsu_id=cwsu_id,
            client=client,
        )
    ).parsed
