from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.gridpoint_geo_json import GridpointGeoJson
from ...models.nws_forecast_office_id import NWSForecastOfficeId
from ...types import Response


def _get_kwargs(
    wfo: NWSForecastOfficeId,
    x: int,
    y: int,
) -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/gridpoints/{wfo}/{x},{y}",
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[GridpointGeoJson]:
    if response.status_code == 200:
        response_200 = GridpointGeoJson.from_dict(response.json())

        return response_200
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[GridpointGeoJson]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    wfo: NWSForecastOfficeId,
    x: int,
    y: int,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[GridpointGeoJson]:
    """Returns raw numerical forecast data for a 2.5km grid area

    Args:
        wfo (NWSForecastOfficeId): Three-letter identifier for a NWS office.
        x (int):
        y (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GridpointGeoJson]
    """

    kwargs = _get_kwargs(
        wfo=wfo,
        x=x,
        y=y,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    wfo: NWSForecastOfficeId,
    x: int,
    y: int,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[GridpointGeoJson]:
    """Returns raw numerical forecast data for a 2.5km grid area

    Args:
        wfo (NWSForecastOfficeId): Three-letter identifier for a NWS office.
        x (int):
        y (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GridpointGeoJson
    """

    return sync_detailed(
        wfo=wfo,
        x=x,
        y=y,
        client=client,
    ).parsed


async def asyncio_detailed(
    wfo: NWSForecastOfficeId,
    x: int,
    y: int,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[GridpointGeoJson]:
    """Returns raw numerical forecast data for a 2.5km grid area

    Args:
        wfo (NWSForecastOfficeId): Three-letter identifier for a NWS office.
        x (int):
        y (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GridpointGeoJson]
    """

    kwargs = _get_kwargs(
        wfo=wfo,
        x=x,
        y=y,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    wfo: NWSForecastOfficeId,
    x: int,
    y: int,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[GridpointGeoJson]:
    """Returns raw numerical forecast data for a 2.5km grid area

    Args:
        wfo (NWSForecastOfficeId): Three-letter identifier for a NWS office.
        x (int):
        y (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GridpointGeoJson
    """

    return (
        await asyncio_detailed(
            wfo=wfo,
            x=x,
            y=y,
            client=client,
        )
    ).parsed
