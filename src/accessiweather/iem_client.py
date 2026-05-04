"""IEM-backed NWS text product helpers."""

from __future__ import annotations

import inspect
import logging
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from .models import TextProduct

logger = logging.getLogger(__name__)

DEFAULT_IEM_BASE_URL = "https://mesonet.agron.iastate.edu"
DEFAULT_USER_AGENT = "AccessiWeather (github.com/orinks/accessiweather)"


class IemProductFetchError(Exception):
    """IEM request failed or returned an unusable response."""


async def _client_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Call AsyncClient.get while allowing synchronous mocks in tests."""
    response = client.get(url, params=params, headers=headers)
    if inspect.isawaitable(response):
        return await response
    return response


def _format_iem_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _clean_iem_text(value: str) -> str:
    """Remove non-printing transport markers while preserving product line breaks."""
    return "".join(char for char in value if char in "\n\r\t" or ord(char) >= 32).strip()


def _describe_request_error(exc: Exception) -> str:
    return str(exc) or exc.__class__.__name__


def _format_iem_compact_datetime(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%d%H%M")


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _item_datetime(item: dict[str, Any], keys: tuple[str, ...]) -> datetime | None:
    for key in keys:
        parsed = _parse_datetime(item.get(key))
        if parsed is not None:
            return _coerce_utc(parsed)
    return None


def _is_active_at(
    item: dict[str, Any],
    valid_at: datetime,
    *,
    start_keys: tuple[str, ...],
    end_keys: tuple[str, ...],
) -> bool:
    valid_at = _coerce_utc(valid_at)
    starts = _item_datetime(item, start_keys)
    ends = _item_datetime(item, end_keys)
    if starts is not None and starts > valid_at:
        return False
    return not (ends is not None and ends <= valid_at)


def _active_items(
    items: list[Any],
    valid_at: datetime,
    *,
    start_keys: tuple[str, ...],
    end_keys: tuple[str, ...],
) -> list[Any]:
    active: list[Any] = []
    for item in items:
        if not isinstance(item, dict):
            active.append(item)
            continue
        properties = item.get("properties")
        item_data = properties if isinstance(properties, dict) else item
        if _is_active_at(item_data, valid_at, start_keys=start_keys, end_keys=end_keys):
            active.append(item)
    return active


def _items_in_time_window(
    items: list[Any],
    *,
    start: datetime | None,
    end: datetime | None,
    time_keys: tuple[str, ...],
) -> list[Any]:
    if start is None and end is None:
        return items
    start_utc = _coerce_utc(start) if start is not None else None
    end_utc = _coerce_utc(end) if end is not None else None
    filtered: list[Any] = []
    for item in items:
        if not isinstance(item, dict):
            filtered.append(item)
            continue
        properties = item.get("properties")
        item_data = properties if isinstance(properties, dict) else item
        item_time = _item_datetime(item_data, time_keys)
        if item_time is None:
            continue
        if start_utc is not None and item_time < start_utc:
            continue
        if end_utc is not None and item_time >= end_utc:
            continue
        filtered.append(item)
    return filtered


def _payload_items(payload: dict[str, Any], item_keys: tuple[str, ...]) -> list[Any]:
    for key in item_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict) and value:
            return [value]
    return []


async def fetch_iem_afos_text(
    pil: str,
    *,
    client: httpx.AsyncClient | None = None,
    iem_base_url: str = DEFAULT_IEM_BASE_URL,
    timeout: float = 10.0,
    user_agent: str = DEFAULT_USER_AGENT,
    limit: int = 1,
    start: datetime | None = None,
    end: datetime | None = None,
    order: Literal["asc", "desc"] = "desc",
    center: str | None = None,
    wmo_id: str | None = None,
    matches: str | None = None,
) -> TextProduct:
    """Fetch raw NWS text from IEM AFOS retrieve by AWIPS/PIL."""
    product_id = pil.strip().upper()
    if not product_id:
        raise IemProductFetchError("A product ID is required.")

    params: dict[str, Any] = {
        "pil": product_id,
        "fmt": "text",
        "limit": max(1, int(limit)),
        "order": order,
    }
    if start is not None:
        params["sdate"] = _format_iem_datetime(start)
    if end is not None:
        params["edate"] = _format_iem_datetime(end)
    if center:
        params["center"] = center.strip().upper()
    if wmo_id:
        params["ttaaii"] = wmo_id.strip().upper()
    if matches:
        params["matches"] = matches.strip()

    url = f"{iem_base_url}/cgi-bin/afos/retrieve.py"
    headers = {"User-Agent": user_agent}

    async def _run(http_client: httpx.AsyncClient) -> TextProduct:
        try:
            response = await _client_get(http_client, url, params=params, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError, httpx.RequestError) as exc:
            raise IemProductFetchError(f"IEM AFOS request failed for {product_id}: {exc}") from exc
        if response.status_code != 200:
            raise IemProductFetchError(
                f"IEM AFOS returned HTTP {response.status_code} for {product_id}"
            )
        text = _clean_iem_text(response.text)
        if not text:
            raise IemProductFetchError(f"IEM AFOS returned no text for {product_id}")
        return TextProduct(
            product_type=product_id,
            product_id=product_id,
            cwa_office=(center or "IEM").strip().upper(),
            issuance_time=None,
            product_text=text,
            headline=f"IEM AFOS {product_id}",
        )

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
        return await _run(new_client)


def _limited_items(items: list[Any], max_items: int | None) -> tuple[list[Any], int]:
    if max_items is None or max_items <= 0:
        return items, 0
    return items[:max_items], max(0, len(items) - max_items)


def _append_omitted_count(lines: list[str], omitted: int) -> None:
    if omitted > 0:
        lines.append(f"{omitted} older matches omitted. Use Advanced Lookup for broader history.")


def _spc_summary_lines(
    title: str,
    payload: Any,
    *,
    item_keys: tuple[str, ...],
    active_at: datetime | None = None,
    start_keys: tuple[str, ...] = (),
    end_keys: tuple[str, ...] = (),
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    window_keys: tuple[str, ...] = (),
    max_items: int | None = None,
) -> list[str]:
    lines = [title, ""]
    if not isinstance(payload, dict):
        return [title, "", "No structured data returned."]

    generated = payload.get("generated_at") or payload.get("generated")
    if generated:
        lines.extend([f"Generated: {generated}", ""])

    items = _payload_items(payload, item_keys)
    if window_keys:
        items = _items_in_time_window(
            items,
            start=window_start,
            end=window_end,
            time_keys=window_keys,
        )
    if active_at is not None and (start_keys or end_keys):
        items = _active_items(items, active_at, start_keys=start_keys, end_keys=end_keys)
    if not items:
        if active_at is not None and (start_keys or end_keys):
            lines.append("No active point-based products were returned for this location.")
        else:
            lines.append("No matching point-based products were returned for this location.")
        return lines

    visible_items, omitted = _limited_items(items, max_items)
    for index, item in enumerate(visible_items, start=1):
        if not isinstance(item, dict):
            continue
        lines.append(f"Product {index}:")
        for label, key in (
            ("Number", "mdnum"),
            ("Category", "category"),
            ("Threshold", "threshold"),
            ("Valid", "valid"),
            ("Issued", "product_issue"),
            ("Concerning", "concerning"),
            ("Watch probability", "watch_prob"),
        ):
            value = item.get(key)
            if value not in (None, ""):
                lines.append(f"{label}: {value}")
        lines.append("")
    _append_omitted_count(lines, omitted)
    return lines


async def fetch_iem_spc_outlook(
    latitude: float,
    longitude: float,
    *,
    day: int = 1,
    current: bool = True,
    valid_at: datetime | None = None,
    max_items: int | None = 5,
    client: httpx.AsyncClient | None = None,
    iem_base_url: str = DEFAULT_IEM_BASE_URL,
    timeout: float = 10.0,
    user_agent: str = DEFAULT_USER_AGENT,
) -> TextProduct:
    """Fetch and summarize the structured IEM SPC convective outlook response."""
    day = min(8, max(1, int(day)))
    params = {
        "lat": latitude,
        "lon": longitude,
        "day": day,
        "fmt": "json",
        "current": 1 if current else 0,
    }
    if valid_at is not None and not current:
        params["time"] = _format_iem_datetime(valid_at)
    url = f"{iem_base_url}/json/spcoutlook.py"
    headers = {"User-Agent": user_agent}

    async def _run(http_client: httpx.AsyncClient) -> TextProduct:
        try:
            response = await _client_get(http_client, url, params=params, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError, httpx.RequestError) as exc:
            raise IemProductFetchError(
                f"IEM SPC outlook request failed: {_describe_request_error(exc)}"
            ) from exc
        if response.status_code != 200:
            raise IemProductFetchError(f"IEM SPC outlook returned HTTP {response.status_code}")
        data = response.json()
        title = f"SPC Day {day} Convective Outlook"
        issued = data.get("generated_at") if isinstance(data, dict) else None
        return TextProduct(
            product_type="SPC_OUTLOOK",
            product_id=f"SPC_OUTLOOK_DAY{day}",
            cwa_office="SPC",
            issuance_time=_parse_datetime(issued),
            product_text="\n".join(
                _spc_summary_lines(
                    title,
                    data,
                    item_keys=("outlooks", "outlook", "features"),
                    max_items=max_items,
                )
            ),
            headline=title,
        )

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
        return await _run(new_client)


async def fetch_iem_spc_mcds(
    latitude: float,
    longitude: float,
    *,
    active_at: datetime | None = None,
    active_only: bool = True,
    start: datetime | None = None,
    end: datetime | None = None,
    max_items: int | None = 5,
    client: httpx.AsyncClient | None = None,
    iem_base_url: str = DEFAULT_IEM_BASE_URL,
    timeout: float = 10.0,
    user_agent: str = DEFAULT_USER_AGENT,
) -> TextProduct:
    """Fetch and summarize IEM SPC mesoscale discussions near a point."""
    active_at = active_at or _now_utc()
    params = {"lat": latitude, "lon": longitude, "fmt": "json"}
    url = f"{iem_base_url}/json/spcmcd.py"
    headers = {"User-Agent": user_agent}

    async def _run(http_client: httpx.AsyncClient) -> TextProduct:
        try:
            response = await _client_get(http_client, url, params=params, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError, httpx.RequestError) as exc:
            raise IemProductFetchError(
                f"IEM SPC MCD request failed: {_describe_request_error(exc)}"
            ) from exc
        if response.status_code != 200:
            raise IemProductFetchError(f"IEM SPC MCD returned HTTP {response.status_code}")
        data = response.json()
        title = "SPC Mesoscale Discussions"
        item_filter_time = active_at if active_only else None
        return TextProduct(
            product_type="SPC_MCD",
            product_id="SPC_MCD",
            cwa_office="SPC",
            issuance_time=None,
            product_text="\n".join(
                _spc_summary_lines(
                    title,
                    data,
                    item_keys=("mcds", "features"),
                    active_at=item_filter_time,
                    start_keys=("utc_issue", "product_issue", "issue", "valid"),
                    end_keys=("utc_expire", "product_expire", "expire", "expires"),
                    window_start=start,
                    window_end=end,
                    window_keys=("utc_issue", "product_issue", "issue", "valid"),
                    max_items=max_items,
                )
            ),
            headline=title,
        )

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
        return await _run(new_client)


async def fetch_iem_spc_watches(
    latitude: float,
    longitude: float,
    *,
    valid_at: datetime | None = None,
    max_items: int | None = 5,
    client: httpx.AsyncClient | None = None,
    iem_base_url: str = DEFAULT_IEM_BASE_URL,
    timeout: float = 10.0,
    user_agent: str = DEFAULT_USER_AGENT,
) -> TextProduct:
    """Fetch and summarize IEM SPC watches for a point."""
    active_at = valid_at or _now_utc()
    params: dict[str, Any] = {"lat": latitude, "lon": longitude}
    params["ts"] = _format_iem_compact_datetime(active_at)
    url = f"{iem_base_url}/json/spcwatch.py"
    headers = {"User-Agent": user_agent}

    async def _run(http_client: httpx.AsyncClient) -> TextProduct:
        try:
            response = await _client_get(http_client, url, params=params, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError, httpx.RequestError) as exc:
            raise IemProductFetchError(
                f"IEM SPC watches request failed: {_describe_request_error(exc)}"
            ) from exc
        if response.status_code != 200:
            raise IemProductFetchError(f"IEM SPC watches returned HTTP {response.status_code}")
        title = "SPC Watches"
        return TextProduct(
            product_type="SPC_WATCHES",
            product_id="SPC_WATCHES",
            cwa_office="SPC",
            issuance_time=None,
            product_text="\n".join(
                _spc_watch_summary_lines(
                    title,
                    response.json(),
                    active_at=active_at,
                    max_items=max_items,
                )
            ),
            headline=title,
        )

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
        return await _run(new_client)


def _spc_watch_summary_lines(
    title: str,
    payload: Any,
    *,
    active_at: datetime | None = None,
    max_items: int | None = None,
) -> list[str]:
    lines = [title, ""]
    if not isinstance(payload, dict):
        return [title, "", "No structured data returned."]

    features = payload.get("features")
    if not isinstance(features, list) or not features:
        return [title, "", "No matching watches were returned."]
    if active_at is not None:
        features = _active_items(
            features,
            active_at,
            start_keys=("issue", "utc_issue", "product_issue", "valid"),
            end_keys=("expire", "utc_expire", "product_expire", "expires"),
        )
        if not features:
            return [title, "", "No active watches were returned."]

    visible_features, omitted = _limited_items(features, max_items)
    for index, feature in enumerate(visible_features, start=1):
        props = feature.get("properties") if isinstance(feature, dict) else None
        if not isinstance(props, dict):
            continue
        lines.append(f"Watch {index}:")
        for label, key in (
            ("SEL", "sel"),
            ("Type", "type"),
            ("Number", "number"),
            ("Issued", "issue"),
            ("Expires", "expire"),
            ("PDS", "is_pds"),
            ("Max hail size", "max_hail_size"),
            ("Max wind gust knots", "max_wind_gust_knots"),
        ):
            value = props.get(key)
            if value not in (None, ""):
                lines.append(f"{label}: {value}")
        lines.append("")
    _append_omitted_count(lines, omitted)
    return lines


async def fetch_iem_wpc_outlook(
    latitude: float,
    longitude: float,
    *,
    day: int = 1,
    valid_at: datetime | None = None,
    limit: int = 1,
    max_items: int | None = 5,
    client: httpx.AsyncClient | None = None,
    iem_base_url: str = DEFAULT_IEM_BASE_URL,
    timeout: float = 10.0,
    user_agent: str = DEFAULT_USER_AGENT,
) -> TextProduct:
    """Fetch and summarize IEM WPC excessive rainfall outlooks for a point."""
    active_at = valid_at or _now_utc()
    day = min(8, max(1, int(day)))
    params: dict[str, Any] = {
        "lat": latitude,
        "lon": longitude,
        "day": day,
        "fmt": "json",
        "last": max(1, int(limit)),
    }
    params["time"] = "current" if valid_at is None else _format_iem_datetime(active_at)
    url = f"{iem_base_url}/json/wpcoutlook.py"
    headers = {"User-Agent": user_agent}

    async def _run(http_client: httpx.AsyncClient) -> TextProduct:
        try:
            response = await _client_get(http_client, url, params=params, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError, httpx.RequestError) as exc:
            raise IemProductFetchError(
                f"IEM WPC outlook request failed: {_describe_request_error(exc)}"
            ) from exc
        if response.status_code != 200:
            raise IemProductFetchError(f"IEM WPC outlook returned HTTP {response.status_code}")
        data = response.json()
        title = f"WPC Day {day} Excessive Rainfall Outlook"
        issued = data.get("generated_at") if isinstance(data, dict) else None
        return TextProduct(
            product_type="WPC_ERO",
            product_id=f"WPC_ERO_DAY{day}",
            cwa_office="WPC",
            issuance_time=_parse_datetime(issued),
            product_text="\n".join(
                _wpc_outlook_summary_lines(
                    title,
                    data,
                    active_at=active_at,
                    max_items=max_items,
                )
            ),
            headline=title,
        )

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
        return await _run(new_client)


def _wpc_outlook_summary_lines(
    title: str,
    payload: Any,
    *,
    active_at: datetime | None = None,
    max_items: int | None = None,
) -> list[str]:
    lines = [title, ""]
    if not isinstance(payload, dict):
        return [title, "", "No structured data returned."]
    generated = payload.get("generated_at") or payload.get("generated")
    if generated:
        lines.extend([f"Generated: {generated}", ""])

    outlooks = _payload_items(payload, ("outlooks", "outlook"))
    if not outlooks:
        return [title, "", "No matching outlooks were returned."]
    if active_at is not None:
        outlooks = _active_items(
            outlooks,
            active_at,
            start_keys=("utc_issue", "issue", "valid", "valid_begin"),
            end_keys=("utc_expire", "expire", "expires", "valid_end"),
        )
        if not outlooks:
            return [title, "", "No active outlooks were returned."]

    visible_outlooks, omitted = _limited_items(outlooks, max_items)
    for index, outlook in enumerate(visible_outlooks, start=1):
        if not isinstance(outlook, dict):
            continue
        lines.append(f"Outlook {index}:")
        for label, key in (
            ("Day", "day"),
            ("Category", "category"),
            ("Threshold", "threshold"),
            ("Product issued", "utc_product_issue"),
            ("Valid begins", "utc_issue"),
            ("Valid expires", "utc_expire"),
        ):
            value = outlook.get(key)
            if value not in (None, ""):
                lines.append(f"{label}: {value}")
        lines.append("")
    _append_omitted_count(lines, omitted)
    return lines


async def fetch_iem_wpc_mpds(
    latitude: float,
    longitude: float,
    *,
    active_at: datetime | None = None,
    active_only: bool = True,
    start: datetime | None = None,
    end: datetime | None = None,
    max_items: int | None = 5,
    client: httpx.AsyncClient | None = None,
    iem_base_url: str = DEFAULT_IEM_BASE_URL,
    timeout: float = 10.0,
    user_agent: str = DEFAULT_USER_AGENT,
) -> TextProduct:
    """Fetch and summarize IEM WPC mesoscale precipitation discussions for a point."""
    active_at = active_at or _now_utc()
    params = {"lat": latitude, "lon": longitude, "fmt": "json"}
    url = f"{iem_base_url}/json/wpcmpd.py"
    headers = {"User-Agent": user_agent}

    async def _run(http_client: httpx.AsyncClient) -> TextProduct:
        try:
            response = await _client_get(http_client, url, params=params, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError, httpx.RequestError) as exc:
            raise IemProductFetchError(
                f"IEM WPC MPD request failed: {_describe_request_error(exc)}"
            ) from exc
        if response.status_code != 200:
            raise IemProductFetchError(f"IEM WPC MPD returned HTTP {response.status_code}")
        title = "WPC Mesoscale Precipitation Discussions"
        item_filter_time = active_at if active_only else None
        return TextProduct(
            product_type="WPC_MPD",
            product_id="WPC_MPD",
            cwa_office="WPC",
            issuance_time=None,
            product_text="\n".join(
                _wpc_mpd_summary_lines(
                    title,
                    response.json(),
                    active_at=item_filter_time,
                    window_start=start,
                    window_end=end,
                    max_items=max_items,
                )
            ),
            headline=title,
        )

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
        return await _run(new_client)


def _wpc_mpd_summary_lines(
    title: str,
    payload: Any,
    *,
    active_at: datetime | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    max_items: int | None = None,
) -> list[str]:
    lines = [title, ""]
    if not isinstance(payload, dict):
        return [title, "", "No structured data returned."]

    mpds = payload.get("mpds")
    if not isinstance(mpds, list) or not mpds:
        return [title, "", "No matching discussions were returned."]
    mpds = _items_in_time_window(
        mpds,
        start=window_start,
        end=window_end,
        time_keys=("utc_issue", "issue", "product_issue"),
    )
    if not mpds:
        return [title, "", "No matching discussions were returned."]
    if active_at is not None:
        mpds = _active_items(
            mpds,
            active_at,
            start_keys=("utc_issue", "issue", "product_issue"),
            end_keys=("utc_expire", "expire", "product_expire", "expires"),
        )
        if not mpds:
            return [title, "", "No active discussions were returned."]

    visible_mpds, omitted = _limited_items(mpds, max_items)
    for index, mpd in enumerate(visible_mpds, start=1):
        if not isinstance(mpd, dict):
            continue
        lines.append(f"Discussion {index}:")
        for label, key in (
            ("Number", "product_num"),
            ("Product ID", "product_id"),
            ("Issued", "utc_issue"),
            ("Expires", "utc_expire"),
            ("Concerning", "concerning"),
            ("Link", "product_href"),
        ):
            value = mpd.get(key)
            if value not in (None, ""):
                lines.append(f"{label}: {value}")
        lines.append("")
    _append_omitted_count(lines, omitted)
    return lines
