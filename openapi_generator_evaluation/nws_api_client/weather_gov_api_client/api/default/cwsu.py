from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.nws_center_weather_service_unit_id import NWSCenterWeatherServiceUnitId
from ...types import Response


def _get_kwargs(
    cwsu_id: NWSCenterWeatherServiceUnitId,
) -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/aviation/cwsus/{cwsu_id}",
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Any]:
    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
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
    cwsu_id: NWSCenterWeatherServiceUnitId,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[Any]:
    """Returns metadata about a Center Weather Service Unit

    Args:
        cwsu_id (NWSCenterWeatherServiceUnitId): Three-letter identifier for a Center Weather
            Service Unit (CWSU).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        cwsu_id=cwsu_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


async def asyncio_detailed(
    cwsu_id: NWSCenterWeatherServiceUnitId,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[Any]:
    """Returns metadata about a Center Weather Service Unit

    Args:
        cwsu_id (NWSCenterWeatherServiceUnitId): Three-letter identifier for a Center Weather
            Service Unit (CWSU).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        cwsu_id=cwsu_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)
