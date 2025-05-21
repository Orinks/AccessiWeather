from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.sigmet_collection_geo_json import SigmetCollectionGeoJson
from ...types import Response


def _get_kwargs(
    atsu: str,
) -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/aviation/sigmets/{atsu}",
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[SigmetCollectionGeoJson]:
    if response.status_code == 200:
        response_200 = SigmetCollectionGeoJson.from_dict(response.json())

        return response_200
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[SigmetCollectionGeoJson]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    atsu: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[SigmetCollectionGeoJson]:
    """Returns a list of SIGMET/AIRMETs for the specified ATSU

    Args:
        atsu (str): ATSU Identifier

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[SigmetCollectionGeoJson]
    """

    kwargs = _get_kwargs(
        atsu=atsu,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    atsu: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[SigmetCollectionGeoJson]:
    """Returns a list of SIGMET/AIRMETs for the specified ATSU

    Args:
        atsu (str): ATSU Identifier

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        SigmetCollectionGeoJson
    """

    return sync_detailed(
        atsu=atsu,
        client=client,
    ).parsed


async def asyncio_detailed(
    atsu: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[SigmetCollectionGeoJson]:
    """Returns a list of SIGMET/AIRMETs for the specified ATSU

    Args:
        atsu (str): ATSU Identifier

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[SigmetCollectionGeoJson]
    """

    kwargs = _get_kwargs(
        atsu=atsu,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    atsu: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[SigmetCollectionGeoJson]:
    """Returns a list of SIGMET/AIRMETs for the specified ATSU

    Args:
        atsu (str): ATSU Identifier

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        SigmetCollectionGeoJson
    """

    return (
        await asyncio_detailed(
            atsu=atsu,
            client=client,
        )
    ).parsed
