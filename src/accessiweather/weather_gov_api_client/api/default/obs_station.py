from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.observation_station_geo_json import ObservationStationGeoJson
from ...types import Response


def _get_kwargs(
    station_id: str,
) -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/stations/{station_id}",
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[ObservationStationGeoJson]:
    if response.status_code == 200:
        response_200 = ObservationStationGeoJson.from_dict(response.json())

        return response_200
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[ObservationStationGeoJson]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    station_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[ObservationStationGeoJson]:
    """Returns metadata about a given observation station

    Args:
        station_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ObservationStationGeoJson]
    """

    kwargs = _get_kwargs(
        station_id=station_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    station_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[ObservationStationGeoJson]:
    """Returns metadata about a given observation station

    Args:
        station_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ObservationStationGeoJson
    """

    return sync_detailed(
        station_id=station_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    station_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[ObservationStationGeoJson]:
    """Returns metadata about a given observation station

    Args:
        station_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ObservationStationGeoJson]
    """

    kwargs = _get_kwargs(
        station_id=station_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    station_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[ObservationStationGeoJson]:
    """Returns metadata about a given observation station

    Args:
        station_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ObservationStationGeoJson
    """

    return (
        await asyncio_detailed(
            station_id=station_id,
            client=client,
        )
    ).parsed
