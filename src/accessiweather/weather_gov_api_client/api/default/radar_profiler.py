from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset


def _get_kwargs(
    station_id: str,
    *,
    time: Union[Unset, str] = UNSET,
    interval: Union[Unset, str] = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_time: Union[Unset, str]
    if isinstance(time, Unset):
        json_time = UNSET
    else:
        json_time = time
    params["time"] = json_time

    params["interval"] = interval

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/radar/profilers/{station_id}",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Any]:
    if response.status_code == 200:
        return None
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
    station_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
    time: Union[Unset, str] = UNSET,
    interval: Union[Unset, str] = UNSET,
) -> Response[Any]:
    """Returns metadata about a given radar wind profiler

    Args:
        station_id (str):
        time (Union[Unset, str]): A time interval in ISO 8601 format. This can be one of:

                1. Start and end time
                2. Start time and duration
                3. Duration and end time
            The string "NOW" can also be used in place of a start/end time.
        interval (Union[Unset, str]): A time duration in ISO 8601 format. Example: P2DT12H.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        station_id=station_id,
        time=time,
        interval=interval,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


async def asyncio_detailed(
    station_id: str,
    *,
    client: Union[AuthenticatedClient, Client],
    time: Union[Unset, str] = UNSET,
    interval: Union[Unset, str] = UNSET,
) -> Response[Any]:
    """Returns metadata about a given radar wind profiler

    Args:
        station_id (str):
        time (Union[Unset, str]): A time interval in ISO 8601 format. This can be one of:

                1. Start and end time
                2. Start time and duration
                3. Duration and end time
            The string "NOW" can also be used in place of a start/end time.
        interval (Union[Unset, str]): A time duration in ISO 8601 format. Example: P2DT12H.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        station_id=station_id,
        time=time,
        interval=interval,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)
