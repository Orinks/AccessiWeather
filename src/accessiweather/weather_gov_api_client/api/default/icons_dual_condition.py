from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.icons_dual_condition_size_type_0 import IconsDualConditionSizeType0
from ...types import UNSET, Response, Unset


def _get_kwargs(
    set_: str,
    time_of_day: str,
    first: str,
    second: str,
    *,
    size: Union[IconsDualConditionSizeType0, Unset, int] = UNSET,
    fontsize: Union[Unset, int] = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_size: Union[Unset, int, str]
    if isinstance(size, Unset):
        json_size = UNSET
    elif isinstance(size, IconsDualConditionSizeType0):
        json_size = size.value
    else:
        json_size = size
    params["size"] = json_size

    params["fontsize"] = fontsize

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/icons/{set_}/{time_of_day}/{first}/{second}",
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
    set_: str,
    time_of_day: str,
    first: str,
    second: str,
    *,
    client: Union[AuthenticatedClient, Client],
    size: Union[IconsDualConditionSizeType0, Unset, int] = UNSET,
    fontsize: Union[Unset, int] = UNSET,
) -> Response[Any]:
    """Returns a forecast icon. Icon services in API are deprecated.

    Args:
        set_ (str):
        time_of_day (str):
        first (str):
        second (str):
        size (Union[IconsDualConditionSizeType0, Unset, int]):
        fontsize (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        set_=set_,
        time_of_day=time_of_day,
        first=first,
        second=second,
        size=size,
        fontsize=fontsize,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


async def asyncio_detailed(
    set_: str,
    time_of_day: str,
    first: str,
    second: str,
    *,
    client: Union[AuthenticatedClient, Client],
    size: Union[IconsDualConditionSizeType0, Unset, int] = UNSET,
    fontsize: Union[Unset, int] = UNSET,
) -> Response[Any]:
    """Returns a forecast icon. Icon services in API are deprecated.

    Args:
        set_ (str):
        time_of_day (str):
        first (str):
        second (str):
        size (Union[IconsDualConditionSizeType0, Unset, int]):
        fontsize (Union[Unset, int]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any]
    """

    kwargs = _get_kwargs(
        set_=set_,
        time_of_day=time_of_day,
        first=first,
        second=second,
        size=size,
        fontsize=fontsize,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)
