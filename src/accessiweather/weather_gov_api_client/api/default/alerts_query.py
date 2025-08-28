import datetime
from http import HTTPStatus
from typing import Any, Optional, Union, cast

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.alert_certainty import AlertCertainty
from ...models.alert_collection_geo_json import AlertCollectionGeoJson
from ...models.alert_severity import AlertSeverity
from ...models.alert_urgency import AlertUrgency
from ...models.alerts_query_message_type_item import AlertsQueryMessageTypeItem
from ...models.alerts_query_region_type import AlertsQueryRegionType
from ...models.alerts_query_status_item import AlertsQueryStatusItem
from ...models.marine_area_code import MarineAreaCode
from ...models.marine_region_code import MarineRegionCode
from ...models.state_territory_code import StateTerritoryCode
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    active: Union[Unset, bool] = UNSET,
    start: Union[Unset, datetime.datetime] = UNSET,
    end: Union[Unset, datetime.datetime] = UNSET,
    status: Union[Unset, list[AlertsQueryStatusItem]] = UNSET,
    message_type: Union[Unset, list[AlertsQueryMessageTypeItem]] = UNSET,
    event: Union[Unset, list[str]] = UNSET,
    code: Union[Unset, list[str]] = UNSET,
    area: Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]] = UNSET,
    point: Union[Unset, str] = UNSET,
    region: Union[Unset, list[MarineRegionCode]] = UNSET,
    region_type: Union[Unset, AlertsQueryRegionType] = UNSET,
    zone: Union[Unset, list[str]] = UNSET,
    urgency: Union[Unset, list[AlertUrgency]] = UNSET,
    severity: Union[Unset, list[AlertSeverity]] = UNSET,
    certainty: Union[Unset, list[AlertCertainty]] = UNSET,
    limit: Union[Unset, int] = 500,
    cursor: Union[Unset, str] = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    params["active"] = active

    json_start: Union[Unset, str] = UNSET
    if not isinstance(start, Unset):
        json_start = start.isoformat()
    params["start"] = json_start

    json_end: Union[Unset, str] = UNSET
    if not isinstance(end, Unset):
        json_end = end.isoformat()
    params["end"] = json_end

    json_status: Union[Unset, list[str]] = UNSET
    if not isinstance(status, Unset):
        json_status = []
        for status_item_data in status:
            status_item = status_item_data.value
            json_status.append(status_item)

    params["status"] = json_status

    json_message_type: Union[Unset, list[str]] = UNSET
    if not isinstance(message_type, Unset):
        json_message_type = []
        for message_type_item_data in message_type:
            message_type_item = message_type_item_data.value
            json_message_type.append(message_type_item)

    params["message_type"] = json_message_type

    json_event: Union[Unset, list[str]] = UNSET
    if not isinstance(event, Unset):
        json_event = event

    params["event"] = json_event

    json_code: Union[Unset, list[str]] = UNSET
    if not isinstance(code, Unset):
        json_code = code

    params["code"] = json_code

    json_area: Union[Unset, list[str]] = UNSET
    if not isinstance(area, Unset):
        json_area = []
        for area_item_data in area:
            area_item: str
            if isinstance(area_item_data, StateTerritoryCode):
                area_item = area_item_data.value
            else:
                area_item = area_item_data.value

            json_area.append(area_item)

    params["area"] = json_area

    params["point"] = point

    json_region: Union[Unset, list[str]] = UNSET
    if not isinstance(region, Unset):
        json_region = []
        for region_item_data in region:
            region_item = region_item_data.value
            json_region.append(region_item)

    params["region"] = json_region

    json_region_type: Union[Unset, str] = UNSET
    if not isinstance(region_type, Unset):
        json_region_type = region_type.value

    params["region_type"] = json_region_type

    json_zone: Union[Unset, list[str]] = UNSET
    if not isinstance(zone, Unset):
        json_zone = zone

    params["zone"] = json_zone

    json_urgency: Union[Unset, list[str]] = UNSET
    if not isinstance(urgency, Unset):
        json_urgency = []
        for urgency_item_data in urgency:
            urgency_item = urgency_item_data.value
            json_urgency.append(urgency_item)

    params["urgency"] = json_urgency

    json_severity: Union[Unset, list[str]] = UNSET
    if not isinstance(severity, Unset):
        json_severity = []
        for severity_item_data in severity:
            severity_item = severity_item_data.value
            json_severity.append(severity_item)

    params["severity"] = json_severity

    json_certainty: Union[Unset, list[str]] = UNSET
    if not isinstance(certainty, Unset):
        json_certainty = []
        for certainty_item_data in certainty:
            certainty_item = certainty_item_data.value
            json_certainty.append(certainty_item)

    params["certainty"] = json_certainty

    params["limit"] = limit

    params["cursor"] = cursor

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/alerts",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Union[AlertCollectionGeoJson, Any]]:
    if response.status_code == 200:
        response_200 = AlertCollectionGeoJson.from_dict(response.json())

        return response_200
    if response.status_code == 301:
        response_301 = cast(Any, None)
        return response_301
    if client.raise_on_unexpected_status:
        raise e from Nonerrors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[Union[AlertCollectionGeoJson, Any]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    active: Union[Unset, bool] = UNSET,
    start: Union[Unset, datetime.datetime] = UNSET,
    end: Union[Unset, datetime.datetime] = UNSET,
    status: Union[Unset, list[AlertsQueryStatusItem]] = UNSET,
    message_type: Union[Unset, list[AlertsQueryMessageTypeItem]] = UNSET,
    event: Union[Unset, list[str]] = UNSET,
    code: Union[Unset, list[str]] = UNSET,
    area: Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]] = UNSET,
    point: Union[Unset, str] = UNSET,
    region: Union[Unset, list[MarineRegionCode]] = UNSET,
    region_type: Union[Unset, AlertsQueryRegionType] = UNSET,
    zone: Union[Unset, list[str]] = UNSET,
    urgency: Union[Unset, list[AlertUrgency]] = UNSET,
    severity: Union[Unset, list[AlertSeverity]] = UNSET,
    certainty: Union[Unset, list[AlertCertainty]] = UNSET,
    limit: Union[Unset, int] = 500,
    cursor: Union[Unset, str] = UNSET,
) -> Response[Union[AlertCollectionGeoJson, Any]]:
    """Returns all alerts

    Args:
        active (Union[Unset, bool]):
        start (Union[Unset, datetime.datetime]):
        end (Union[Unset, datetime.datetime]):
        status (Union[Unset, list[AlertsQueryStatusItem]]):
        message_type (Union[Unset, list[AlertsQueryMessageTypeItem]]):
        event (Union[Unset, list[str]]):
        code (Union[Unset, list[str]]):
        area (Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]]):
        point (Union[Unset, str]):
        region (Union[Unset, list[MarineRegionCode]]):
        region_type (Union[Unset, AlertsQueryRegionType]):
        zone (Union[Unset, list[str]]):
        urgency (Union[Unset, list[AlertUrgency]]):
        severity (Union[Unset, list[AlertSeverity]]):
        certainty (Union[Unset, list[AlertCertainty]]):
        limit (Union[Unset, int]):  Default: 500.
        cursor (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[AlertCollectionGeoJson, Any]]
    """

    kwargs = _get_kwargs(
        active=active,
        start=start,
        end=end,
        status=status,
        message_type=message_type,
        event=event,
        code=code,
        area=area,
        point=point,
        region=region,
        region_type=region_type,
        zone=zone,
        urgency=urgency,
        severity=severity,
        certainty=certainty,
        limit=limit,
        cursor=cursor,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: Union[AuthenticatedClient, Client],
    active: Union[Unset, bool] = UNSET,
    start: Union[Unset, datetime.datetime] = UNSET,
    end: Union[Unset, datetime.datetime] = UNSET,
    status: Union[Unset, list[AlertsQueryStatusItem]] = UNSET,
    message_type: Union[Unset, list[AlertsQueryMessageTypeItem]] = UNSET,
    event: Union[Unset, list[str]] = UNSET,
    code: Union[Unset, list[str]] = UNSET,
    area: Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]] = UNSET,
    point: Union[Unset, str] = UNSET,
    region: Union[Unset, list[MarineRegionCode]] = UNSET,
    region_type: Union[Unset, AlertsQueryRegionType] = UNSET,
    zone: Union[Unset, list[str]] = UNSET,
    urgency: Union[Unset, list[AlertUrgency]] = UNSET,
    severity: Union[Unset, list[AlertSeverity]] = UNSET,
    certainty: Union[Unset, list[AlertCertainty]] = UNSET,
    limit: Union[Unset, int] = 500,
    cursor: Union[Unset, str] = UNSET,
) -> Optional[Union[AlertCollectionGeoJson, Any]]:
    """Returns all alerts

    Args:
        active (Union[Unset, bool]):
        start (Union[Unset, datetime.datetime]):
        end (Union[Unset, datetime.datetime]):
        status (Union[Unset, list[AlertsQueryStatusItem]]):
        message_type (Union[Unset, list[AlertsQueryMessageTypeItem]]):
        event (Union[Unset, list[str]]):
        code (Union[Unset, list[str]]):
        area (Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]]):
        point (Union[Unset, str]):
        region (Union[Unset, list[MarineRegionCode]]):
        region_type (Union[Unset, AlertsQueryRegionType]):
        zone (Union[Unset, list[str]]):
        urgency (Union[Unset, list[AlertUrgency]]):
        severity (Union[Unset, list[AlertSeverity]]):
        certainty (Union[Unset, list[AlertCertainty]]):
        limit (Union[Unset, int]):  Default: 500.
        cursor (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[AlertCollectionGeoJson, Any]
    """

    return sync_detailed(
        client=client,
        active=active,
        start=start,
        end=end,
        status=status,
        message_type=message_type,
        event=event,
        code=code,
        area=area,
        point=point,
        region=region,
        region_type=region_type,
        zone=zone,
        urgency=urgency,
        severity=severity,
        certainty=certainty,
        limit=limit,
        cursor=cursor,
    ).parsed


async def asyncio_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    active: Union[Unset, bool] = UNSET,
    start: Union[Unset, datetime.datetime] = UNSET,
    end: Union[Unset, datetime.datetime] = UNSET,
    status: Union[Unset, list[AlertsQueryStatusItem]] = UNSET,
    message_type: Union[Unset, list[AlertsQueryMessageTypeItem]] = UNSET,
    event: Union[Unset, list[str]] = UNSET,
    code: Union[Unset, list[str]] = UNSET,
    area: Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]] = UNSET,
    point: Union[Unset, str] = UNSET,
    region: Union[Unset, list[MarineRegionCode]] = UNSET,
    region_type: Union[Unset, AlertsQueryRegionType] = UNSET,
    zone: Union[Unset, list[str]] = UNSET,
    urgency: Union[Unset, list[AlertUrgency]] = UNSET,
    severity: Union[Unset, list[AlertSeverity]] = UNSET,
    certainty: Union[Unset, list[AlertCertainty]] = UNSET,
    limit: Union[Unset, int] = 500,
    cursor: Union[Unset, str] = UNSET,
) -> Response[Union[AlertCollectionGeoJson, Any]]:
    """Returns all alerts

    Args:
        active (Union[Unset, bool]):
        start (Union[Unset, datetime.datetime]):
        end (Union[Unset, datetime.datetime]):
        status (Union[Unset, list[AlertsQueryStatusItem]]):
        message_type (Union[Unset, list[AlertsQueryMessageTypeItem]]):
        event (Union[Unset, list[str]]):
        code (Union[Unset, list[str]]):
        area (Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]]):
        point (Union[Unset, str]):
        region (Union[Unset, list[MarineRegionCode]]):
        region_type (Union[Unset, AlertsQueryRegionType]):
        zone (Union[Unset, list[str]]):
        urgency (Union[Unset, list[AlertUrgency]]):
        severity (Union[Unset, list[AlertSeverity]]):
        certainty (Union[Unset, list[AlertCertainty]]):
        limit (Union[Unset, int]):  Default: 500.
        cursor (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[AlertCollectionGeoJson, Any]]
    """

    kwargs = _get_kwargs(
        active=active,
        start=start,
        end=end,
        status=status,
        message_type=message_type,
        event=event,
        code=code,
        area=area,
        point=point,
        region=region,
        region_type=region_type,
        zone=zone,
        urgency=urgency,
        severity=severity,
        certainty=certainty,
        limit=limit,
        cursor=cursor,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: Union[AuthenticatedClient, Client],
    active: Union[Unset, bool] = UNSET,
    start: Union[Unset, datetime.datetime] = UNSET,
    end: Union[Unset, datetime.datetime] = UNSET,
    status: Union[Unset, list[AlertsQueryStatusItem]] = UNSET,
    message_type: Union[Unset, list[AlertsQueryMessageTypeItem]] = UNSET,
    event: Union[Unset, list[str]] = UNSET,
    code: Union[Unset, list[str]] = UNSET,
    area: Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]] = UNSET,
    point: Union[Unset, str] = UNSET,
    region: Union[Unset, list[MarineRegionCode]] = UNSET,
    region_type: Union[Unset, AlertsQueryRegionType] = UNSET,
    zone: Union[Unset, list[str]] = UNSET,
    urgency: Union[Unset, list[AlertUrgency]] = UNSET,
    severity: Union[Unset, list[AlertSeverity]] = UNSET,
    certainty: Union[Unset, list[AlertCertainty]] = UNSET,
    limit: Union[Unset, int] = 500,
    cursor: Union[Unset, str] = UNSET,
) -> Optional[Union[AlertCollectionGeoJson, Any]]:
    """Returns all alerts

    Args:
        active (Union[Unset, bool]):
        start (Union[Unset, datetime.datetime]):
        end (Union[Unset, datetime.datetime]):
        status (Union[Unset, list[AlertsQueryStatusItem]]):
        message_type (Union[Unset, list[AlertsQueryMessageTypeItem]]):
        event (Union[Unset, list[str]]):
        code (Union[Unset, list[str]]):
        area (Union[Unset, list[Union[MarineAreaCode, StateTerritoryCode]]]):
        point (Union[Unset, str]):
        region (Union[Unset, list[MarineRegionCode]]):
        region_type (Union[Unset, AlertsQueryRegionType]):
        zone (Union[Unset, list[str]]):
        urgency (Union[Unset, list[AlertUrgency]]):
        severity (Union[Unset, list[AlertSeverity]]):
        certainty (Union[Unset, list[AlertCertainty]]):
        limit (Union[Unset, int]):  Default: 500.
        cursor (Union[Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[AlertCollectionGeoJson, Any]
    """

    return (
        await asyncio_detailed(
            client=client,
            active=active,
            start=start,
            end=end,
            status=status,
            message_type=message_type,
            event=event,
            code=code,
            area=area,
            point=point,
            region=region,
            region_type=region_type,
            zone=zone,
            urgency=urgency,
            severity=severity,
            certainty=certainty,
            limit=limit,
            cursor=cursor,
        )
    ).parsed
