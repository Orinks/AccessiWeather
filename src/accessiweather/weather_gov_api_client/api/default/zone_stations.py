from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.observation_station_collection_geo_json import ObservationStationCollectionGeoJson
from ...types import UNSET, Response, Unset


def _get_kwargs(
    zone_id: str,
    *,
    limit: Union[Unset, int] = 500,
    cursor: Union[Unset, str] = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    params["limit"] = limit

    params["cursor"] = cursor

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/zones/forecast/{zone_id}/stations",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[ObservationStationCollectionGeoJson]:
    if response.status_code == 200:
        response_200 = ObservationStationCollectionGeoJson.from_dict(response.json())

        return response_200
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[ObservationStationCollectionGeoJson]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    zone_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
    limit: Union[Unset, int] = 500,
    cursor: Union[Unset, str] = UNSET,
) -> Response[ObservationStationCollectionGeoJson]:
    """Returns a list of observation stations for a given zone

    Args:
        zone_id (str): UGC identifier for a NWS forecast zone or county.
            The first two letters will correspond to either a state code or marine area code (see
            #/components/schemas/StateTerritoryCode and #/components/schemas/MarineAreaCode for lists
            of valid letter combinations).
            The third letter will be Z for public/fire zone or C for county.
        limit (Union[Unset, int]):  Default: 500.
        cursor (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ObservationStationCollectionGeoJson]
    """

    kwargs = _get_kwargs(
        zone_id=zone_id,
        limit=limit,
        cursor=cursor,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    zone_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
    limit: Union[Unset, int] = 500,
    cursor: Union[Unset, str] = UNSET,
) -> Optional[ObservationStationCollectionGeoJson]:
    """Returns a list of observation stations for a given zone

    Args:
        zone_id (str): UGC identifier for a NWS forecast zone or county.
            The first two letters will correspond to either a state code or marine area code (see
            #/components/schemas/StateTerritoryCode and #/components/schemas/MarineAreaCode for lists
            of valid letter combinations).
            The third letter will be Z for public/fire zone or C for county.
        limit (Union[Unset, int]):  Default: 500.
        cursor (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ObservationStationCollectionGeoJson
    """

    return sync_detailed(
        zone_id=zone_id,
        client=client,
        limit=limit,
        cursor=cursor,
    ).parsed


async def asyncio_detailed(
    zone_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
    limit: Union[Unset, int] = 500,
    cursor: Union[Unset, str] = UNSET,
) -> Response[ObservationStationCollectionGeoJson]:
    """Returns a list of observation stations for a given zone

    Args:
        zone_id (str): UGC identifier for a NWS forecast zone or county.
            The first two letters will correspond to either a state code or marine area code (see
            #/components/schemas/StateTerritoryCode and #/components/schemas/MarineAreaCode for lists
            of valid letter combinations).
            The third letter will be Z for public/fire zone or C for county.
        limit (Union[Unset, int]):  Default: 500.
        cursor (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ObservationStationCollectionGeoJson]
    """

    kwargs = _get_kwargs(
        zone_id=zone_id,
        limit=limit,
        cursor=cursor,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    zone_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
    limit: Union[Unset, int] = 500,
    cursor: Union[Unset, str] = UNSET,
) -> Optional[ObservationStationCollectionGeoJson]:
    """Returns a list of observation stations for a given zone

    Args:
        zone_id (str): UGC identifier for a NWS forecast zone or county.
            The first two letters will correspond to either a state code or marine area code (see
            #/components/schemas/StateTerritoryCode and #/components/schemas/MarineAreaCode for lists
            of valid letter combinations).
            The third letter will be Z for public/fire zone or C for county.
        limit (Union[Unset, int]):  Default: 500.
        cursor (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ObservationStationCollectionGeoJson
    """

    return (
        await asyncio_detailed(
            zone_id=zone_id,
            client=client,
            limit=limit,
            cursor=cursor,
        )
    ).parsed
