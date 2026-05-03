"""Forecast and text-product helpers for the NWS weather client."""
# ruff: noqa: F403, F405

from __future__ import annotations

from typing import cast
from urllib.parse import urlencode

from .weather_client_nws_common import *  # noqa: F403
from .weather_client_nws_parsers import parse_nws_forecast


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_nws_forecast_and_discussion(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
    grid_data: dict[str, Any] | None = None,
) -> tuple[Forecast | None, str | None, datetime | None]:
    """
    Fetch forecast and discussion from the NWS API for the given location.

    Forecast and discussion fetches are independent: if the forecast fetch fails,
    the discussion is still returned (and vice versa).

    Returns:
        Tuple of (forecast, discussion_text, discussion_issuance_time)

    """
    try:
        headers = {"User-Agent": user_agent}
        feature_headers = headers.copy()
        feature_headers["Feature-Flags"] = "forecast_temperature_qv, forecast_wind_speed_qv"

        # Use provided client or create a new one
        if client is not None:
            # Fetch grid data if not provided (needed by both forecast and discussion)
            if grid_data is None:
                grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
                response = await _client_get(client, grid_url, headers=headers)
                response.raise_for_status()
                grid_data = response.json()

            # Fetch forecast independently so a failure doesn't kill the discussion
            parsed_forecast: Forecast | None = None
            try:
                forecast_url = grid_data["properties"]["forecast"]
                response = await _client_get(client, forecast_url, headers=feature_headers)
                response.raise_for_status()
                parsed_forecast = parse_nws_forecast(response.json())
            except Exception as forecast_exc:  # noqa: BLE001
                logger.warning(
                    "Forecast fetch failed (discussion will still be returned): %s", forecast_exc
                )

            discussion, discussion_issuance_time = await get_nws_discussion(
                client, headers, grid_data, nws_base_url
            )
            logger.debug(
                "get_nws_forecast_and_discussion: forecast=%s discussion_len=%s issuance=%s",
                "ok" if parsed_forecast else "None",
                len(discussion) if discussion else 0,
                discussion_issuance_time,
            )

            return parsed_forecast, discussion, discussion_issuance_time

        grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()

            # Fetch forecast independently so a failure doesn't kill the discussion
            parsed_forecast = None
            try:
                forecast_url = grid_data["properties"]["forecast"]
                response = await new_client.get(forecast_url, headers=feature_headers)
                response.raise_for_status()
                parsed_forecast = parse_nws_forecast(response.json())
            except Exception as forecast_exc:  # noqa: BLE001
                logger.warning(
                    "Forecast fetch failed (discussion will still be returned): %s", forecast_exc
                )

            discussion, discussion_issuance_time = await get_nws_discussion(
                new_client, headers, grid_data, nws_base_url
            )
            logger.debug(
                "get_nws_forecast_and_discussion: forecast=%s discussion_len=%s issuance=%s",
                "ok" if parsed_forecast else "None",
                len(discussion) if discussion else 0,
                discussion_issuance_time,
            )

            return parsed_forecast, discussion, discussion_issuance_time

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS forecast and discussion: {exc}")
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None, None, None


@async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=20.0)
async def get_nws_discussion_only(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
) -> tuple[str | None, datetime | None]:
    """
    Fetch only the NWS Area Forecast Discussion for a location.

    Lighter-weight than get_nws_forecast_and_discussion — skips the forecast
    fetch entirely.  Used by the notification event path so that a transient
    forecast API error never silently suppresses AFD update notifications.

    Returns:
        Tuple of (discussion_text, discussion_issuance_time).
        Returns (None, None) on unrecoverable error.

    """
    try:
        headers = {"User-Agent": user_agent}
        logger.debug(
            "get_nws_discussion_only: fetching grid data for %s,%s",
            location.latitude,
            location.longitude,
        )

        if client is not None:
            grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
            response = await _client_get(client, grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()
            discussion, issuance_time = await get_nws_discussion(
                client, headers, grid_data, nws_base_url
            )
            logger.debug(
                "get_nws_discussion_only: discussion_len=%s issuance=%s",
                len(discussion) if discussion else 0,
                issuance_time,
            )
            return discussion, issuance_time

        grid_url = f"{nws_base_url}/points/{location.latitude},{location.longitude}"
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
            response = await new_client.get(grid_url, headers=headers)
            response.raise_for_status()
            grid_data = response.json()
            discussion, issuance_time = await get_nws_discussion(
                new_client, headers, grid_data, nws_base_url
            )
            logger.debug(
                "get_nws_discussion_only: discussion_len=%s issuance=%s",
                len(discussion) if discussion else 0,
                issuance_time,
            )
            return discussion, issuance_time

    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to fetch NWS discussion only: %s", exc)
        if isinstance(exc, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(exc):
            raise
        return None, None


class TextProductFetchError(Exception):
    """
    Network, timeout, or non-200 response from the NWS /products endpoint.

    Distinct from the "empty @graph" case, which returns ``None`` (AFD/HWO) or
    ``[]`` (SPS) rather than raising.
    """


async def _fetch_text_product_by_id(
    client: httpx.AsyncClient,
    nws_base_url: str,
    headers: dict[str, str],
    product_type: str,
    cwa_office: str,
    entry: dict[str, Any],
) -> TextProduct | None:
    """
    Fetch a single /products/{id} and return a TextProduct.

    Returns None for individual product fetches whose id is missing or whose
    response is missing productText — these are treated as best-effort skips
    rather than hard errors.
    """
    product_id = entry.get("id")
    if not product_id:
        logger.warning("No product ID in %s @graph entry for office %s", product_type, cwa_office)
        return None

    issuance_time = _parse_iso_datetime(entry.get("issuanceTime"))

    product_url = f"{nws_base_url}/products/{product_id}"
    response = await _client_get(client, product_url, headers=headers)
    if response.status_code != 200:
        logger.warning(
            "Failed to get %s product text (%s): HTTP %s",
            product_type,
            product_id,
            response.status_code,
        )
        raise TextProductFetchError(
            f"HTTP {response.status_code} fetching {product_type} product {product_id}"
        )

    product_data = response.json()
    product_text = product_data.get("productText")
    if not product_text:
        logger.warning("No productText in %s product %s", product_type, product_id)
        return None

    # Prefer product-level issuanceTime over @graph metadata when present.
    body_issuance = _parse_iso_datetime(product_data.get("issuanceTime"))
    if body_issuance is not None:
        issuance_time = body_issuance

    headline = product_data.get("headline") or entry.get("headline")
    if headline is not None and not isinstance(headline, str):
        headline = str(headline)

    return TextProduct(
        product_type=cast(Any, product_type),
        product_id=str(product_id),
        cwa_office=cwa_office,
        issuance_time=issuance_time,
        product_text=product_text,
        headline=headline,
    )


async def get_nws_text_product(
    product_type: Literal[AFD, HWO, SPS],
    cwa_office: str | None,
    *,
    nws_base_url: str = "https://api.weather.gov",
    client: httpx.AsyncClient | None = None,
    timeout: float = 10.0,
    user_agent: str = "AccessiWeather (github.com/orinks/accessiweather)",
) -> TextProduct | list[TextProduct] | None:
    """
    Fetch an NWS text product (AFD / HWO / SPS) for a CWA office.

    Endpoint: ``/products/types/{product_type}/locations/{cwa_office}`` returns
    an ``@graph`` of product stubs; each is fetched individually via
    ``/products/{id}`` to get ``productText`` and metadata.

    Return convention:
        - ``cwa_office`` falsy -> ``None`` (no HTTP call).
        - AFD or HWO, empty ``@graph`` -> ``None``.
        - AFD or HWO, products present -> single ``TextProduct`` (newest @graph entry).
        - SPS -> ``list[TextProduct]`` (possibly empty), sorted newest-first.

    Raises:
        TextProductFetchError on network failure, timeout, or non-200 response
        from the NWS /products endpoints. Empty @graph is NOT an error.

    """
    if not cwa_office:
        return None

    headers = {"User-Agent": user_agent}
    products_url = f"{nws_base_url}/products/types/{product_type}/locations/{cwa_office}"

    async def _run(http_client: httpx.AsyncClient) -> TextProduct | list[TextProduct] | None:
        try:
            listing_response = await _client_get(http_client, products_url, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError, httpx.RequestError) as exc:
            raise TextProductFetchError(
                f"Request failed fetching {product_type} listing for {cwa_office}: {exc}"
            ) from exc

        if listing_response.status_code != 200:
            raise TextProductFetchError(
                f"HTTP {listing_response.status_code} fetching {product_type} "
                f"listing for {cwa_office}"
            )

        graph = listing_response.json().get("@graph") or []

        if product_type == "SPS":
            products: list[TextProduct] = []
            try:
                for entry in graph:
                    if not isinstance(entry, dict):
                        continue
                    tp = await _fetch_text_product_by_id(
                        http_client, nws_base_url, headers, product_type, cwa_office, entry
                    )
                    if tp is not None:
                        products.append(tp)
            except (httpx.TimeoutException, httpx.TransportError, httpx.RequestError) as exc:
                raise TextProductFetchError(
                    f"Request failed fetching SPS product for {cwa_office}: {exc}"
                ) from exc

            products.sort(
                key=lambda p: p.issuance_time or datetime.min.replace(tzinfo=UTC),
                reverse=True,
            )
            return products

        # AFD or HWO: newest @graph entry only, or None if empty. The API is
        # usually newest-first, but live listings can contain out-of-order
        # entries, so select by issuanceTime defensively.
        if not graph:
            return None

        latest = max(
            (entry for entry in graph if isinstance(entry, dict)),
            key=lambda entry: (
                _parse_iso_datetime(entry.get("issuanceTime")) or datetime.min.replace(tzinfo=UTC)
            ),
            default=None,
        )
        if not isinstance(latest, dict):
            return None

        try:
            return await _fetch_text_product_by_id(
                http_client, nws_base_url, headers, product_type, cwa_office, latest
            )
        except (httpx.TimeoutException, httpx.TransportError, httpx.RequestError) as exc:
            raise TextProductFetchError(
                f"Request failed fetching {product_type} product for {cwa_office}: {exc}"
            ) from exc

    if client is not None:
        return await _run(client)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
        return await _run(new_client)


async def get_nws_text_product_history(
    product_type: str,
    cwa_office: str | None,
    *,
    nws_base_url: str = "https://api.weather.gov",
    client: httpx.AsyncClient | None = None,
    timeout: float = 10.0,
    user_agent: str = "AccessiWeather (github.com/orinks/accessiweather)",
    limit: int = 10,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[TextProduct]:
    """
    Fetch NWS text-product history from the official ``/products`` endpoint.

    Endpoint: ``/products?location={cwa_office}&type={product_type}&limit={limit}``
    with optional ``start`` and ``end`` ISO timestamp filters. Listing entries are
    fetched individually via ``/products/{id}`` so callers receive product bodies.

    Returns a newest-first list. Empty listings are not errors.
    """
    if not cwa_office:
        return []

    headers = {"User-Agent": user_agent}
    query: dict[str, str | int] = {
        "location": cwa_office,
        "type": product_type,
        "limit": limit,
    }
    if start is not None:
        query["start"] = start.isoformat()
    if end is not None:
        query["end"] = end.isoformat()

    products_url = f"{nws_base_url}/products?{urlencode(query)}"

    async def _run(http_client: httpx.AsyncClient) -> list[TextProduct]:
        try:
            listing_response = await _client_get(http_client, products_url, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError, httpx.RequestError) as exc:
            raise TextProductFetchError(
                f"Request failed fetching {product_type} history for {cwa_office}: {exc}"
            ) from exc

        if listing_response.status_code != 200:
            raise TextProductFetchError(
                f"HTTP {listing_response.status_code} fetching {product_type} "
                f"history for {cwa_office}"
            )

        products: list[TextProduct] = []
        graph = listing_response.json().get("@graph") or []
        try:
            for entry in graph:
                if not isinstance(entry, dict):
                    continue
                product = await _fetch_text_product_by_id(
                    http_client, nws_base_url, headers, product_type, cwa_office, entry
                )
                if product is not None:
                    products.append(product)
        except (httpx.TimeoutException, httpx.TransportError, httpx.RequestError) as exc:
            raise TextProductFetchError(
                f"Request failed fetching {product_type} history product for {cwa_office}: {exc}"
            ) from exc

        products.sort(
            key=lambda p: p.issuance_time or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return products

    if client is not None:
        return await _run(client)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as new_client:
        return await _run(new_client)


async def get_nws_discussion(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    grid_data: dict[str, Any],
    nws_base_url: str,
) -> tuple[str, datetime | None]:
    """
    Fetch the NWS Area Forecast Discussion (AFD) for the given grid data.

    Thin backward-compat wrapper around :func:`get_nws_text_product` for the AFD
    product type. Preserves the pre-existing ``(discussion_text, issuance_time)``
    tuple contract so existing internal callers continue to work unchanged.

    Returns:
        Tuple of (discussion_text, issuance_time). The issuance_time is parsed from
        the NWS API's issuanceTime field and can be used to detect when the AFD
        has been updated without comparing content.

    """
    try:
        forecast_url = grid_data.get("properties", {}).get("forecast")
        if not forecast_url:
            logger.warning("No forecast URL found in grid data")
            return "Forecast discussion not available.", None

        parts = forecast_url.split("/")
        if len(parts) < 6:
            logger.warning(f"Unexpected forecast URL format: {forecast_url}")
            return "Forecast discussion not available.", None

        office_id = parts[-3]
        logger.info(f"Fetching AFD for office: {office_id}")

        # Preserve existing User-Agent behavior by reusing caller-supplied headers.
        user_agent = headers.get("User-Agent", "AccessiWeather")

        try:
            product = await get_nws_text_product(
                "AFD",
                office_id,
                nws_base_url=nws_base_url,
                client=client,
                user_agent=user_agent,
            )
        except TextProductFetchError as exc:
            logger.warning("Failed to fetch AFD via text-product path: %s", exc)
            return "Forecast discussion not available.", None

        if product is None:
            logger.warning(f"No AFD products found for office {office_id}")
            return "Forecast discussion not available for this location.", None

        assert isinstance(product, TextProduct)  # AFD path never returns a list
        logger.info(f"Successfully fetched AFD for office {office_id}")
        return product.product_text, product.issuance_time

    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to get NWS discussion: {exc}")
        return "Forecast discussion not available due to error.", None
