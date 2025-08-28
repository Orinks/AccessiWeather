from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.point_geo_json import PointGeoJson
from ...types import Response


def _get_kwargs(
    point: str,
) -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/points/{point}",
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[PointGeoJson]:
    if response.status_code == 200:
        response_200 = PointGeoJson.from_dict(response.json())

        return response_200
    if client.raise_on_unexpected_status:
        raise e from Nonerrors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[PointGeoJson]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    point: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[PointGeoJson]:
    """Returns metadata about a given latitude/longitude point

    Args:
        point (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PointGeoJson]
    """

    kwargs = _get_kwargs(
        point=point,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    point: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[PointGeoJson]:
    """Returns metadata about a given latitude/longitude point

    Args:
        point (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PointGeoJson
    """

    return sync_detailed(
        point=point,
        client=client,
    ).parsed


async def asyncio_detailed(
    point: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[PointGeoJson]:
    """Returns metadata about a given latitude/longitude point

    Args:
        point (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[PointGeoJson]
    """

    kwargs = _get_kwargs(
        point=point,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    point: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[PointGeoJson]:
    """Returns metadata about a given latitude/longitude point

    Args:
        point (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        PointGeoJson
    """

    return (
        await asyncio_detailed(
            point=point,
            client=client,
        )
    ).parsed
