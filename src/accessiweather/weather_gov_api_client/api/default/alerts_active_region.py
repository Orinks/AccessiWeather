from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.alert_collection_geo_json import AlertCollectionGeoJson
from ...models.marine_region_code import MarineRegionCode
from ...types import Response


def _get_kwargs(
    region: MarineRegionCode,
) -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/alerts/active/region/{region}",
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
    region: MarineRegionCode,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[AlertCollectionGeoJson]:
    """Returns active alerts for the given marine region

    Args:
        region (MarineRegionCode): Marine region code. These are groups of marine areas combined.
            * AL: Alaska waters (PK)
            * AT: Atlantic Ocean (AM, AN)
            * GL: Great Lakes (LC, LE, LH, LM, LO, LS, SL)
            * GM: Gulf of Mexico (GM)
            * PA: Eastern Pacific Ocean and U.S. West Coast (PZ)
            * PI: Central and Western Pacific (PH, PM, PS)

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AlertCollectionGeoJson]
    """

    kwargs = _get_kwargs(
        region=region,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    region: MarineRegionCode,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[AlertCollectionGeoJson]:
    """Returns active alerts for the given marine region

    Args:
        region (MarineRegionCode): Marine region code. These are groups of marine areas combined.
            * AL: Alaska waters (PK)
            * AT: Atlantic Ocean (AM, AN)
            * GL: Great Lakes (LC, LE, LH, LM, LO, LS, SL)
            * GM: Gulf of Mexico (GM)
            * PA: Eastern Pacific Ocean and U.S. West Coast (PZ)
            * PI: Central and Western Pacific (PH, PM, PS)

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AlertCollectionGeoJson
    """

    return sync_detailed(
        region=region,
        client=client,
    ).parsed


async def asyncio_detailed(
    region: MarineRegionCode,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[AlertCollectionGeoJson]:
    """Returns active alerts for the given marine region

    Args:
        region (MarineRegionCode): Marine region code. These are groups of marine areas combined.
            * AL: Alaska waters (PK)
            * AT: Atlantic Ocean (AM, AN)
            * GL: Great Lakes (LC, LE, LH, LM, LO, LS, SL)
            * GM: Gulf of Mexico (GM)
            * PA: Eastern Pacific Ocean and U.S. West Coast (PZ)
            * PI: Central and Western Pacific (PH, PM, PS)

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AlertCollectionGeoJson]
    """

    kwargs = _get_kwargs(
        region=region,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    region: MarineRegionCode,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[AlertCollectionGeoJson]:
    """Returns active alerts for the given marine region

    Args:
        region (MarineRegionCode): Marine region code. These are groups of marine areas combined.
            * AL: Alaska waters (PK)
            * AT: Atlantic Ocean (AM, AN)
            * GL: Great Lakes (LC, LE, LH, LM, LO, LS, SL)
            * GM: Gulf of Mexico (GM)
            * PA: Eastern Pacific Ocean and U.S. West Coast (PZ)
            * PI: Central and Western Pacific (PH, PM, PS)

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AlertCollectionGeoJson
    """

    return (
        await asyncio_detailed(
            region=region,
            client=client,
        )
    ).parsed
