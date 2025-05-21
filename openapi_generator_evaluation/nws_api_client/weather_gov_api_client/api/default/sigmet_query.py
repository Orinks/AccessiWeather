import datetime
from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.sigmet_collection_geo_json import SigmetCollectionGeoJson
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    start: Union[Unset, datetime.datetime] = UNSET,
    end: Union[Unset, datetime.datetime] = UNSET,
    date: Union[Unset, datetime.date] = UNSET,
    atsu: Union[Unset, str] = UNSET,
    sequence: Union[Unset, str] = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_start: Union[Unset, str] = UNSET
    if not isinstance(start, Unset):
        json_start = start.isoformat()
    params["start"] = json_start

    json_end: Union[Unset, str] = UNSET
    if not isinstance(end, Unset):
        json_end = end.isoformat()
    params["end"] = json_end

    json_date: Union[Unset, str] = UNSET
    if not isinstance(date, Unset):
        json_date = date.isoformat()
    params["date"] = json_date

    params["atsu"] = atsu

    params["sequence"] = sequence

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/aviation/sigmets",
        "params": params,
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
    *,
    client: Union[AuthenticatedClient, Client],
    start: Union[Unset, datetime.datetime] = UNSET,
    end: Union[Unset, datetime.datetime] = UNSET,
    date: Union[Unset, datetime.date] = UNSET,
    atsu: Union[Unset, str] = UNSET,
    sequence: Union[Unset, str] = UNSET,
) -> Response[SigmetCollectionGeoJson]:
    """Returns a list of SIGMET/AIRMETs

    Args:
        start (Union[Unset, datetime.datetime]):
        end (Union[Unset, datetime.datetime]):
        date (Union[Unset, datetime.date]): Date (in YYYY-MM-DD format).
        atsu (Union[Unset, str]): ATSU Identifier
        sequence (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[SigmetCollectionGeoJson]
    """

    kwargs = _get_kwargs(
        start=start,
        end=end,
        date=date,
        atsu=atsu,
        sequence=sequence,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: Union[AuthenticatedClient, Client],
    start: Union[Unset, datetime.datetime] = UNSET,
    end: Union[Unset, datetime.datetime] = UNSET,
    date: Union[Unset, datetime.date] = UNSET,
    atsu: Union[Unset, str] = UNSET,
    sequence: Union[Unset, str] = UNSET,
) -> Optional[SigmetCollectionGeoJson]:
    """Returns a list of SIGMET/AIRMETs

    Args:
        start (Union[Unset, datetime.datetime]):
        end (Union[Unset, datetime.datetime]):
        date (Union[Unset, datetime.date]): Date (in YYYY-MM-DD format).
        atsu (Union[Unset, str]): ATSU Identifier
        sequence (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        SigmetCollectionGeoJson
    """

    return sync_detailed(
        client=client,
        start=start,
        end=end,
        date=date,
        atsu=atsu,
        sequence=sequence,
    ).parsed


async def asyncio_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    start: Union[Unset, datetime.datetime] = UNSET,
    end: Union[Unset, datetime.datetime] = UNSET,
    date: Union[Unset, datetime.date] = UNSET,
    atsu: Union[Unset, str] = UNSET,
    sequence: Union[Unset, str] = UNSET,
) -> Response[SigmetCollectionGeoJson]:
    """Returns a list of SIGMET/AIRMETs

    Args:
        start (Union[Unset, datetime.datetime]):
        end (Union[Unset, datetime.datetime]):
        date (Union[Unset, datetime.date]): Date (in YYYY-MM-DD format).
        atsu (Union[Unset, str]): ATSU Identifier
        sequence (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[SigmetCollectionGeoJson]
    """

    kwargs = _get_kwargs(
        start=start,
        end=end,
        date=date,
        atsu=atsu,
        sequence=sequence,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: Union[AuthenticatedClient, Client],
    start: Union[Unset, datetime.datetime] = UNSET,
    end: Union[Unset, datetime.datetime] = UNSET,
    date: Union[Unset, datetime.date] = UNSET,
    atsu: Union[Unset, str] = UNSET,
    sequence: Union[Unset, str] = UNSET,
) -> Optional[SigmetCollectionGeoJson]:
    """Returns a list of SIGMET/AIRMETs

    Args:
        start (Union[Unset, datetime.datetime]):
        end (Union[Unset, datetime.datetime]):
        date (Union[Unset, datetime.date]): Date (in YYYY-MM-DD format).
        atsu (Union[Unset, str]): ATSU Identifier
        sequence (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        SigmetCollectionGeoJson
    """

    return (
        await asyncio_detailed(
            client=client,
            start=start,
            end=end,
            date=date,
            atsu=atsu,
            sequence=sequence,
        )
    ).parsed
