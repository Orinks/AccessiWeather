import datetime
from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import Response


def _get_kwargs(
    station_id: str,
    date: datetime.date,
    time: str,
) -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/stations/{station_id}/tafs/{date}/{time}",
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
    station_id: str,
    date: datetime.date,
    time: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[Any]:
    """Returns a single Terminal Aerodrome Forecast.

    Args:
        station_id (str):
        date (datetime.date): Date (in YYYY-MM-DD format).
        time (str): A time (in HHMM format). This is always specified in UTC (Zulu) time.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        station_id=station_id,
        date=date,
        time=time,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


async def asyncio_detailed(
    station_id: str,
    date: datetime.date,
    time: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[Any]:
    """Returns a single Terminal Aerodrome Forecast.

    Args:
        station_id (str):
        date (datetime.date): Date (in YYYY-MM-DD format).
        time (str): A time (in HHMM format). This is always specified in UTC (Zulu) time.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        station_id=station_id,
        date=date,
        time=time,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)
