import datetime
from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.get_timeline_unit_group import GetTimelineUnitGroup
from ...models.timeline_response import TimelineResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    location: str,
    *,
    key: str,
    unit_group: Union[Unset, GetTimelineUnitGroup] = UNSET,
    include: Union[Unset, str] = UNSET,
    elements: Union[Unset, str] = UNSET,
    start_date_time: Union[Unset, datetime.datetime] = UNSET,
    end_date_time: Union[Unset, datetime.datetime] = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    params["key"] = key

    json_unit_group: Union[Unset, str] = UNSET
    if not isinstance(unit_group, Unset):
        json_unit_group = unit_group.value

    params["unitGroup"] = json_unit_group

    params["include"] = include

    params["elements"] = elements

    json_start_date_time: Union[Unset, str] = UNSET
    if not isinstance(start_date_time, Unset):
        json_start_date_time = start_date_time.isoformat()
    params["startDateTime"] = json_start_date_time

    json_end_date_time: Union[Unset, str] = UNSET
    if not isinstance(end_date_time, Unset):
        json_end_date_time = end_date_time.isoformat()
    params["endDateTime"] = json_end_date_time

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/timeline/{location}",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Union[ErrorResponse, TimelineResponse]]:
    if response.status_code == 200:
        response_200 = TimelineResponse.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = ErrorResponse.from_dict(response.json())

        return response_400

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 429:
        response_429 = ErrorResponse.from_dict(response.json())

        return response_429

    if response.status_code == 500:
        response_500 = ErrorResponse.from_dict(response.json())

        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[Union[ErrorResponse, TimelineResponse]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    location: str,
    *,
    client: Union[AuthenticatedClient, Client],
    key: str,
    unit_group: Union[Unset, GetTimelineUnitGroup] = UNSET,
    include: Union[Unset, str] = UNSET,
    elements: Union[Unset, str] = UNSET,
    start_date_time: Union[Unset, datetime.datetime] = UNSET,
    end_date_time: Union[Unset, datetime.datetime] = UNSET,
) -> Response[Union[ErrorResponse, TimelineResponse]]:
    """Retrieve timeline weather data

     Fetches weather information for a location. The API supports coordinate pairs (`latitude,longitude`)
    or place names. Results include current conditions, multi-day forecasts, optional hourly data, and
    weather alerts.

    Args:
        location (str):
        key (str):
        unit_group (Union[Unset, GetTimelineUnitGroup]):
        include (Union[Unset, str]):
        elements (Union[Unset, str]):
        start_date_time (Union[Unset, datetime.datetime]):
        end_date_time (Union[Unset, datetime.datetime]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[ErrorResponse, TimelineResponse]]
    """

    kwargs = _get_kwargs(
        location=location,
        key=key,
        unit_group=unit_group,
        include=include,
        elements=elements,
        start_date_time=start_date_time,
        end_date_time=end_date_time,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    location: str,
    *,
    client: Union[AuthenticatedClient, Client],
    key: str,
    unit_group: Union[Unset, GetTimelineUnitGroup] = UNSET,
    include: Union[Unset, str] = UNSET,
    elements: Union[Unset, str] = UNSET,
    start_date_time: Union[Unset, datetime.datetime] = UNSET,
    end_date_time: Union[Unset, datetime.datetime] = UNSET,
) -> Optional[Union[ErrorResponse, TimelineResponse]]:
    """Retrieve timeline weather data

     Fetches weather information for a location. The API supports coordinate pairs (`latitude,longitude`)
    or place names. Results include current conditions, multi-day forecasts, optional hourly data, and
    weather alerts.

    Args:
        location (str):
        key (str):
        unit_group (Union[Unset, GetTimelineUnitGroup]):
        include (Union[Unset, str]):
        elements (Union[Unset, str]):
        start_date_time (Union[Unset, datetime.datetime]):
        end_date_time (Union[Unset, datetime.datetime]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[ErrorResponse, TimelineResponse]
    """

    return sync_detailed(
        location=location,
        client=client,
        key=key,
        unit_group=unit_group,
        include=include,
        elements=elements,
        start_date_time=start_date_time,
        end_date_time=end_date_time,
    ).parsed


async def asyncio_detailed(
    location: str,
    *,
    client: Union[AuthenticatedClient, Client],
    key: str,
    unit_group: Union[Unset, GetTimelineUnitGroup] = UNSET,
    include: Union[Unset, str] = UNSET,
    elements: Union[Unset, str] = UNSET,
    start_date_time: Union[Unset, datetime.datetime] = UNSET,
    end_date_time: Union[Unset, datetime.datetime] = UNSET,
) -> Response[Union[ErrorResponse, TimelineResponse]]:
    """Retrieve timeline weather data

     Fetches weather information for a location. The API supports coordinate pairs (`latitude,longitude`)
    or place names. Results include current conditions, multi-day forecasts, optional hourly data, and
    weather alerts.

    Args:
        location (str):
        key (str):
        unit_group (Union[Unset, GetTimelineUnitGroup]):
        include (Union[Unset, str]):
        elements (Union[Unset, str]):
        start_date_time (Union[Unset, datetime.datetime]):
        end_date_time (Union[Unset, datetime.datetime]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[ErrorResponse, TimelineResponse]]
    """

    kwargs = _get_kwargs(
        location=location,
        key=key,
        unit_group=unit_group,
        include=include,
        elements=elements,
        start_date_time=start_date_time,
        end_date_time=end_date_time,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    location: str,
    *,
    client: Union[AuthenticatedClient, Client],
    key: str,
    unit_group: Union[Unset, GetTimelineUnitGroup] = UNSET,
    include: Union[Unset, str] = UNSET,
    elements: Union[Unset, str] = UNSET,
    start_date_time: Union[Unset, datetime.datetime] = UNSET,
    end_date_time: Union[Unset, datetime.datetime] = UNSET,
) -> Optional[Union[ErrorResponse, TimelineResponse]]:
    """Retrieve timeline weather data

     Fetches weather information for a location. The API supports coordinate pairs (`latitude,longitude`)
    or place names. Results include current conditions, multi-day forecasts, optional hourly data, and
    weather alerts.

    Args:
        location (str):
        key (str):
        unit_group (Union[Unset, GetTimelineUnitGroup]):
        include (Union[Unset, str]):
        elements (Union[Unset, str]):
        start_date_time (Union[Unset, datetime.datetime]):
        end_date_time (Union[Unset, datetime.datetime]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[ErrorResponse, TimelineResponse]
    """

    return (
        await asyncio_detailed(
            location=location,
            client=client,
            key=key,
            unit_group=unit_group,
            include=include,
            elements=elements,
            start_date_time=start_date_time,
            end_date_time=end_date_time,
        )
    ).parsed
