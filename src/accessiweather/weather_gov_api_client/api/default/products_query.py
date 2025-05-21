import datetime
from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    location: Union[Unset, list[str]] = UNSET,
    start: Union[Unset, datetime.datetime] = UNSET,
    end: Union[Unset, datetime.datetime] = UNSET,
    office: Union[Unset, list[str]] = UNSET,
    wmoid: Union[Unset, list[str]] = UNSET,
    type_: Union[Unset, list[str]] = UNSET,
    limit: Union[Unset, int] = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_location: Union[Unset, list[str]] = UNSET
    if not isinstance(location, Unset):
        json_location = location

    params["location"] = json_location

    json_start: Union[Unset, str] = UNSET
    if not isinstance(start, Unset):
        json_start = start.isoformat()
    params["start"] = json_start

    json_end: Union[Unset, str] = UNSET
    if not isinstance(end, Unset):
        json_end = end.isoformat()
    params["end"] = json_end

    json_office: Union[Unset, list[str]] = UNSET
    if not isinstance(office, Unset):
        json_office = office

    params["office"] = json_office

    json_wmoid: Union[Unset, list[str]] = UNSET
    if not isinstance(wmoid, Unset):
        json_wmoid = wmoid

    params["wmoid"] = json_wmoid

    json_type_: Union[Unset, list[str]] = UNSET
    if not isinstance(type_, Unset):
        json_type_ = type_

    params["type"] = json_type_

    params["limit"] = limit

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/products",
        "params": params,
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
    *,
    client: Union[AuthenticatedClient, Client],
    location: Union[Unset, list[str]] = UNSET,
    start: Union[Unset, datetime.datetime] = UNSET,
    end: Union[Unset, datetime.datetime] = UNSET,
    office: Union[Unset, list[str]] = UNSET,
    wmoid: Union[Unset, list[str]] = UNSET,
    type_: Union[Unset, list[str]] = UNSET,
    limit: Union[Unset, int] = UNSET,
) -> Response[Any]:
    """Returns a list of text products

    Args:
        location (Union[Unset, list[str]]):
        start (Union[Unset, datetime.datetime]):
        end (Union[Unset, datetime.datetime]):
        office (Union[Unset, list[str]]):
        wmoid (Union[Unset, list[str]]):
        type_ (Union[Unset, list[str]]):
        limit (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        location=location,
        start=start,
        end=end,
        office=office,
        wmoid=wmoid,
        type_=type_,
        limit=limit,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


async def asyncio_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    location: Union[Unset, list[str]] = UNSET,
    start: Union[Unset, datetime.datetime] = UNSET,
    end: Union[Unset, datetime.datetime] = UNSET,
    office: Union[Unset, list[str]] = UNSET,
    wmoid: Union[Unset, list[str]] = UNSET,
    type_: Union[Unset, list[str]] = UNSET,
    limit: Union[Unset, int] = UNSET,
) -> Response[Any]:
    """Returns a list of text products

    Args:
        location (Union[Unset, list[str]]):
        start (Union[Unset, datetime.datetime]):
        end (Union[Unset, datetime.datetime]):
        office (Union[Unset, list[str]]):
        wmoid (Union[Unset, list[str]]):
        type_ (Union[Unset, list[str]]):
        limit (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        location=location,
        start=start,
        end=end,
        office=office,
        wmoid=wmoid,
        type_=type_,
        limit=limit,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)
