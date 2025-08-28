from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.alert_collection_geo_json import AlertCollectionGeoJson
from ...types import Response


def _get_kwargs(
    zone_id: str,
) -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/alerts/active/zone/{zone_id}",
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[AlertCollectionGeoJson]:
    if response.status_code == 200:
        response_200 = AlertCollectionGeoJson.from_dict(response.json())

        return response_200
    if client.raise_on_unexpected_status:
        raise e from Nonerrors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[AlertCollectionGeoJson]:
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
) -> Response[AlertCollectionGeoJson]:
    """Returns active alerts for the given NWS public zone or county

    Args:
        zone_id (str): UGC identifier for a NWS forecast zone or county.
            The first two letters will correspond to either a state code or marine area code (see
            #/components/schemas/StateTerritoryCode and #/components/schemas/MarineAreaCode for lists
            of valid letter combinations).
            The third letter will be Z for public/fire zone or C for county.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AlertCollectionGeoJson]
    """

    kwargs = _get_kwargs(
        zone_id=zone_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    zone_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[AlertCollectionGeoJson]:
    """Returns active alerts for the given NWS public zone or county

    Args:
        zone_id (str): UGC identifier for a NWS forecast zone or county.
            The first two letters will correspond to either a state code or marine area code (see
            #/components/schemas/StateTerritoryCode and #/components/schemas/MarineAreaCode for lists
            of valid letter combinations).
            The third letter will be Z for public/fire zone or C for county.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AlertCollectionGeoJson
    """

    return sync_detailed(
        zone_id=zone_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    zone_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[AlertCollectionGeoJson]:
    """Returns active alerts for the given NWS public zone or county

    Args:
        zone_id (str): UGC identifier for a NWS forecast zone or county.
            The first two letters will correspond to either a state code or marine area code (see
            #/components/schemas/StateTerritoryCode and #/components/schemas/MarineAreaCode for lists
            of valid letter combinations).
            The third letter will be Z for public/fire zone or C for county.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AlertCollectionGeoJson]
    """

    kwargs = _get_kwargs(
        zone_id=zone_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    zone_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[AlertCollectionGeoJson]:
    """Returns active alerts for the given NWS public zone or county

    Args:
        zone_id (str): UGC identifier for a NWS forecast zone or county.
            The first two letters will correspond to either a state code or marine area code (see
            #/components/schemas/StateTerritoryCode and #/components/schemas/MarineAreaCode for lists
            of valid letter combinations).
            The third letter will be Z for public/fire zone or C for county.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AlertCollectionGeoJson
    """

    return (
        await asyncio_detailed(
            zone_id=zone_id,
            client=client,
        )
    ).parsed
