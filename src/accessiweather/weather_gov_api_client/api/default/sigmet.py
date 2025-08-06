import datetime
from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.sigmet_geo_json import SigmetGeoJson
from ...types import Response


def _get_kwargs(
    atsu: str,
    date: datetime.date,
    time: str,
) -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/aviation/sigmets/{atsu}/{date}/{time}",
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[SigmetGeoJson]:
    if response.status_code == 200:
        response_200 = SigmetGeoJson.from_dict(response.json())

        return response_200
    if client.raise_on_unexpected_status:
        raise e from Nonerrors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[SigmetGeoJson]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    atsu: str,
    date: datetime.date,
    time: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[SigmetGeoJson]:
    """Returns a specific SIGMET/AIRMET

    Args:
        atsu (str): ATSU Identifier
        date (datetime.date): Date (in YYYY-MM-DD format).
        time (str): A time (in HHMM format). This is always specified in UTC (Zulu) time.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[SigmetGeoJson]
    """

    kwargs = _get_kwargs(
        atsu=atsu,
        date=date,
        time=time,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    atsu: str,
    date: datetime.date,
    time: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[SigmetGeoJson]:
    """Returns a specific SIGMET/AIRMET

    Args:
        atsu (str): ATSU Identifier
        date (datetime.date): Date (in YYYY-MM-DD format).
        time (str): A time (in HHMM format). This is always specified in UTC (Zulu) time.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        SigmetGeoJson
    """

    return sync_detailed(
        atsu=atsu,
        date=date,
        time=time,
        client=client,
    ).parsed


async def asyncio_detailed(
    atsu: str,
    date: datetime.date,
    time: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Response[SigmetGeoJson]:
    """Returns a specific SIGMET/AIRMET

    Args:
        atsu (str): ATSU Identifier
        date (datetime.date): Date (in YYYY-MM-DD format).
        time (str): A time (in HHMM format). This is always specified in UTC (Zulu) time.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[SigmetGeoJson]
    """

    kwargs = _get_kwargs(
        atsu=atsu,
        date=date,
        time=time,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    atsu: str,
    date: datetime.date,
    time: str,
    *,
    client: Union[AuthenticatedClient, Client],
) -> Optional[SigmetGeoJson]:
    """Returns a specific SIGMET/AIRMET

    Args:
        atsu (str): ATSU Identifier
        date (datetime.date): Date (in YYYY-MM-DD format).
        time (str): A time (in HHMM format). This is always specified in UTC (Zulu) time.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        SigmetGeoJson
    """

    return (
        await asyncio_detailed(
            atsu=atsu,
            date=date,
            time=time,
            client=client,
        )
    ).parsed
