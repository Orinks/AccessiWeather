from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset


def _get_kwargs(
    host: str,
    *,
    limit: Union[Unset, int] = UNSET,
    arrived: Union[Unset, str] = UNSET,
    created: Union[Unset, str] = UNSET,
    published: Union[Unset, str] = UNSET,
    station: Union[Unset, str] = UNSET,
    type_: Union[Unset, str] = UNSET,
    feed: Union[Unset, str] = UNSET,
    resolution: Union[Unset, int] = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    params["limit"] = limit

    json_arrived: Union[Unset, str]
    if isinstance(arrived, Unset):
        json_arrived = UNSET
    else:
        json_arrived = arrived
    params["arrived"] = json_arrived

    json_created: Union[Unset, str]
    if isinstance(created, Unset):
        json_created = UNSET
    else:
        json_created = created
    params["created"] = json_created

    json_published: Union[Unset, str]
    if isinstance(published, Unset):
        json_published = UNSET
    else:
        json_published = published
    params["published"] = json_published

    params["station"] = station

    params["type"] = type_

    params["feed"] = feed

    params["resolution"] = resolution

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/radar/queues/{host}",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Any]:
    if response.status_code == 200:
        return None
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
    host: str,
    *,
    client: Union[AuthenticatedClient, Client],
    limit: Union[Unset, int] = UNSET,
    arrived: Union[Unset, str] = UNSET,
    created: Union[Unset, str] = UNSET,
    published: Union[Unset, str] = UNSET,
    station: Union[Unset, str] = UNSET,
    type_: Union[Unset, str] = UNSET,
    feed: Union[Unset, str] = UNSET,
    resolution: Union[Unset, int] = UNSET,
) -> Response[Any]:
    """Returns metadata about a given radar queue

    Args:
        host (str):
        limit (Union[Unset, int]):
        arrived (Union[Unset, str]): A time interval in ISO 8601 format. This can be one of:

                1. Start and end time
                2. Start time and duration
                3. Duration and end time
            The string "NOW" can also be used in place of a start/end time.
        created (Union[Unset, str]): A time interval in ISO 8601 format. This can be one of:

                1. Start and end time
                2. Start time and duration
                3. Duration and end time
            The string "NOW" can also be used in place of a start/end time.
        published (Union[Unset, str]): A time interval in ISO 8601 format. This can be one of:

                1. Start and end time
                2. Start time and duration
                3. Duration and end time
            The string "NOW" can also be used in place of a start/end time.
        station (Union[Unset, str]):
        type_ (Union[Unset, str]):
        feed (Union[Unset, str]):
        resolution (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        host=host,
        limit=limit,
        arrived=arrived,
        created=created,
        published=published,
        station=station,
        type_=type_,
        feed=feed,
        resolution=resolution,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


async def asyncio_detailed(
    host: str,
    *,
    client: Union[AuthenticatedClient, Client],
    limit: Union[Unset, int] = UNSET,
    arrived: Union[Unset, str] = UNSET,
    created: Union[Unset, str] = UNSET,
    published: Union[Unset, str] = UNSET,
    station: Union[Unset, str] = UNSET,
    type_: Union[Unset, str] = UNSET,
    feed: Union[Unset, str] = UNSET,
    resolution: Union[Unset, int] = UNSET,
) -> Response[Any]:
    """Returns metadata about a given radar queue

    Args:
        host (str):
        limit (Union[Unset, int]):
        arrived (Union[Unset, str]): A time interval in ISO 8601 format. This can be one of:

                1. Start and end time
                2. Start time and duration
                3. Duration and end time
            The string "NOW" can also be used in place of a start/end time.
        created (Union[Unset, str]): A time interval in ISO 8601 format. This can be one of:

                1. Start and end time
                2. Start time and duration
                3. Duration and end time
            The string "NOW" can also be used in place of a start/end time.
        published (Union[Unset, str]): A time interval in ISO 8601 format. This can be one of:

                1. Start and end time
                2. Start time and duration
                3. Duration and end time
            The string "NOW" can also be used in place of a start/end time.
        station (Union[Unset, str]):
        type_ (Union[Unset, str]):
        feed (Union[Unset, str]):
        resolution (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        host=host,
        limit=limit,
        arrived=arrived,
        created=created,
        published=published,
        station=station,
        type_=type_,
        feed=feed,
        resolution=resolution,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)
