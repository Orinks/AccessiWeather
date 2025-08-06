import datetime
from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.land_region_code import LandRegionCode
from ...models.marine_area_code import MarineAreaCode
from ...models.marine_region_code import MarineRegionCode
from ...models.nws_zone_type import NWSZoneType
from ...models.state_territory_code import StateTerritoryCode
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    id: Union[Unset, list[str]] = UNSET,
    area: Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]] = UNSET,
    region: Union[Unset, list[Union[LandRegionCode, MarineRegionCode]]] = UNSET,
    type_: Union[Unset, list[NWSZoneType]] = UNSET,
    point: Union[Unset, str] = UNSET,
    include_geometry: Union[Unset, bool] = UNSET,
    limit: Union[Unset, int] = UNSET,
    effective: Union[Unset, datetime.datetime] = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_id: Union[Unset, list[str]] = UNSET
    if not isinstance(id, Unset):
        json_id = id

    params["id"] = json_id

    json_area: Union[Unset, list[str]] = UNSET
    if not isinstance(area, Unset):
        json_area = []
        for area_item_data in area:
            area_item: str
            if isinstance(area_item_data, StateTerritoryCode):
                area_item = area_item_data.value
            else:
                area_item = area_item_data.value

            json_area.append(area_item)

    params["area"] = json_area

    json_region: Union[Unset, list[str]] = UNSET
    if not isinstance(region, Unset):
        json_region = []
        for region_item_data in region:
            region_item: str
            if isinstance(region_item_data, LandRegionCode):
                region_item = region_item_data.value
            else:
                region_item = region_item_data.value

            json_region.append(region_item)

    params["region"] = json_region

    json_type_: Union[Unset, list[str]] = UNSET
    if not isinstance(type_, Unset):
        json_type_ = []
        for type_item_data in type_:
            type_item = type_item_data.value
            json_type_.append(type_item)

    params["type"] = json_type_

    params["point"] = point

    params["include_geometry"] = include_geometry

    params["limit"] = limit

    json_effective: Union[Unset, str] = UNSET
    if not isinstance(effective, Unset):
        json_effective = effective.isoformat()
    params["effective"] = json_effective

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/zones",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Any]:
    if client.raise_on_unexpected_status:
        raise e from Nonerrors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[Any]:
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
    area: Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]] = UNSET,
    region: Union[Unset, list[Union[LandRegionCode, MarineRegionCode]]] = UNSET,
    type_: Union[Unset, list[NWSZoneType]] = UNSET,
    point: Union[Unset, str] = UNSET,
    include_geometry: Union[Unset, bool] = UNSET,
    limit: Union[Unset, int] = UNSET,
    effective: Union[Unset, datetime.datetime] = UNSET,
) -> Response[Any]:
    """Returns a list of zones

    Args:
        id (Union[Unset, list[str]]):
        area (Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]]):
        region (Union[Unset, list[Union[LandRegionCode, MarineRegionCode]]]):
        type_ (Union[Unset, list[NWSZoneType]]):
        point (Union[Unset, str]):
        include_geometry (Union[Unset, bool]):
        limit (Union[Unset, int]):
        effective (Union[Unset, datetime.datetime]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        id=id,
        area=area,
        region=region,
        type_=type_,
        point=point,
        include_geometry=include_geometry,
        limit=limit,
        effective=effective,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


async def asyncio_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    id: Union[Unset, list[str]] = UNSET,
    area: Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]] = UNSET,
    region: Union[Unset, list[Union[LandRegionCode, MarineRegionCode]]] = UNSET,
    type_: Union[Unset, list[NWSZoneType]] = UNSET,
    point: Union[Unset, str] = UNSET,
    include_geometry: Union[Unset, bool] = UNSET,
    limit: Union[Unset, int] = UNSET,
    effective: Union[Unset, datetime.datetime] = UNSET,
) -> Response[Any]:
    """Returns a list of zones

    Args:
        id (Union[Unset, list[str]]):
        area (Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]]):
        region (Union[Unset, list[Union[LandRegionCode, MarineRegionCode]]]):
        type_ (Union[Unset, list[NWSZoneType]]):
        point (Union[Unset, str]):
        include_geometry (Union[Unset, bool]):
        limit (Union[Unset, int]):
        effective (Union[Unset, datetime.datetime]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        id=id,
        area=area,
        region=region,
        type_=type_,
        point=point,
        include_geometry=include_geometry,
        limit=limit,
        effective=effective,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)
