from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.observation_geo_json import ObservationGeoJson
from ...types import UNSET, Response, Unset


def _get_kwargs(
    station_id: str,
    *,
    require_qc: Union[Unset, bool] = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    params["require_qc"] = require_qc

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/stations/{station_id}/observations/latest",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[ObservationGeoJson]:
    if response.status_code == 200:
        response_200 = ObservationGeoJson.from_dict(response.json())

        return response_200
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[ObservationGeoJson]:
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
    require_qc: Union[Unset, bool] = UNSET,
) -> Response[ObservationGeoJson]:
    """Returns the latest observation for a station

    Args:
        station_id (str):
        require_qc (Union[Unset, bool]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ObservationGeoJson]
    """

    kwargs = _get_kwargs(
        station_id=station_id,
        require_qc=require_qc,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    station_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
    require_qc: Union[Unset, bool] = UNSET,
) -> Optional[ObservationGeoJson]:
    """Returns the latest observation for a station

    Args:
        station_id (str):
        require_qc (Union[Unset, bool]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ObservationGeoJson
    """

    return sync_detailed(
        station_id=station_id,
        client=client,
        require_qc=require_qc,
    ).parsed


async def asyncio_detailed(
    station_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
    require_qc: Union[Unset, bool] = UNSET,
) -> Response[ObservationGeoJson]:
    """Returns the latest observation for a station

    Args:
        station_id (str):
        require_qc (Union[Unset, bool]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ObservationGeoJson]
    """

    kwargs = _get_kwargs(
        station_id=station_id,
        require_qc=require_qc,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    station_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
    require_qc: Union[Unset, bool] = UNSET,
) -> Optional[ObservationGeoJson]:
    """Returns the latest observation for a station

    Args:
        station_id (str):
        require_qc (Union[Unset, bool]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ObservationGeoJson
    """

    return (
        await asyncio_detailed(
            station_id=station_id,
            client=client,
            require_qc=require_qc,
        )
    ).parsed
