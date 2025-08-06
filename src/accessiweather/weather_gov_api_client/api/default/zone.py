import datetime
from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.nws_zone_type import NWSZoneType
from ...types import UNSET, Response, Unset


def _get_kwargs(
    type_: NWSZoneType,
    zone_id: str,
    *,
    effective: Union[Unset, datetime.datetime] = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_effective: Union[Unset, str] = UNSET
    if not isinstance(effective, Unset):
        json_effective = effective.isoformat()
    params["effective"] = json_effective

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/zones/{type_}/{zone_id}",
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
    type_: NWSZoneType,
    zone_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
    effective: Union[Unset, datetime.datetime] = UNSET,
) -> Response[Any]:
    """Returns metadata about a given zone

    Args:
        type_ (NWSZoneType):
        zone_id (str): UGC identifier for a NWS forecast zone or county.
            The first two letters will correspond to either a state code or marine area code (see
            #/components/schemas/StateTerritoryCode and #/components/schemas/MarineAreaCode for lists
            of valid letter combinations).
            The third letter will be Z for public/fire zone or C for county.
        effective (Union[Unset, datetime.datetime]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        type_=type_,
        zone_id=zone_id,
        effective=effective,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


async def asyncio_detailed(
    type_: NWSZoneType,
    zone_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
    effective: Union[Unset, datetime.datetime] = UNSET,
) -> Response[Any]:
    """Returns metadata about a given zone

    Args:
        type_ (NWSZoneType):
        zone_id (str): UGC identifier for a NWS forecast zone or county.
            The first two letters will correspond to either a state code or marine area code (see
            #/components/schemas/StateTerritoryCode and #/components/schemas/MarineAreaCode for lists
            of valid letter combinations).
            The third letter will be Z for public/fire zone or C for county.
        effective (Union[Unset, datetime.datetime]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        type_=type_,
        zone_id=zone_id,
        effective=effective,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)
