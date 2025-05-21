from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.marine_area_code import MarineAreaCode
from ...models.observation_station_collection_geo_json import ObservationStationCollectionGeoJson
from ...models.state_territory_code import StateTerritoryCode
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    id: Union[Unset, list[str]] = UNSET,
    state: Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]] = UNSET,
    limit: Union[Unset, int] = 500,
    cursor: Union[Unset, str] = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_id: Union[Unset, list[str]] = UNSET
    if not isinstance(id, Unset):
        json_id = id

    params["id"] = json_id

    json_state: Union[Unset, list[str]] = UNSET
    if not isinstance(state, Unset):
        json_state = []
        for state_item_data in state:
            state_item: str
            if isinstance(state_item_data, StateTerritoryCode):
                state_item = state_item_data.value
            else:
                state_item = state_item_data.value

            json_state.append(state_item)

    params["state"] = json_state

    params["limit"] = limit

    params["cursor"] = cursor

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/stations",
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
    *,
    client: Union[AuthenticatedClient, Client],
    id: Union[Unset, list[str]] = UNSET,
    state: Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]] = UNSET,
    limit: Union[Unset, int] = 500,
    cursor: Union[Unset, str] = UNSET,
) -> Response[ObservationStationCollectionGeoJson]:
    """Returns a list of observation stations.

    Args:
        id (Union[Unset, list[str]]):
        state (Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]]):
        limit (Union[Unset, int]):  Default: 500.
        cursor (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ObservationStationCollectionGeoJson]
    """

    kwargs = _get_kwargs(
        id=id,
        state=state,
        limit=limit,
        cursor=cursor,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: Union[AuthenticatedClient, Client],
    id: Union[Unset, list[str]] = UNSET,
    state: Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]] = UNSET,
    limit: Union[Unset, int] = 500,
    cursor: Union[Unset, str] = UNSET,
) -> Optional[ObservationStationCollectionGeoJson]:
    """Returns a list of observation stations.

    Args:
        id (Union[Unset, list[str]]):
        state (Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]]):
        limit (Union[Unset, int]):  Default: 500.
        cursor (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ObservationStationCollectionGeoJson
    """

    return sync_detailed(
        client=client,
        id=id,
        state=state,
        limit=limit,
        cursor=cursor,
    ).parsed


async def asyncio_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    id: Union[Unset, list[str]] = UNSET,
    state: Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]] = UNSET,
    limit: Union[Unset, int] = 500,
    cursor: Union[Unset, str] = UNSET,
) -> Response[ObservationStationCollectionGeoJson]:
    """Returns a list of observation stations.

    Args:
        id (Union[Unset, list[str]]):
        state (Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]]):
        limit (Union[Unset, int]):  Default: 500.
        cursor (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ObservationStationCollectionGeoJson]
    """

    kwargs = _get_kwargs(
        id=id,
        state=state,
        limit=limit,
        cursor=cursor,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: Union[AuthenticatedClient, Client],
    id: Union[Unset, list[str]] = UNSET,
    state: Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]] = UNSET,
    limit: Union[Unset, int] = 500,
    cursor: Union[Unset, str] = UNSET,
) -> Optional[ObservationStationCollectionGeoJson]:
    """Returns a list of observation stations.

    Args:
        id (Union[Unset, list[str]]):
        state (Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]]):
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
            client=client,
            id=id,
            state=state,
            limit=limit,
            cursor=cursor,
        )
    ).parsed
