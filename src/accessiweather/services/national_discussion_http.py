"""HTTP request helpers for national discussion services."""

from __future__ import annotations

import logging
from typing import Any

HTML_HEADERS = {"User-Agent": "AccessiWeather/1.0 (AccessiWeather)"}


def rate_limit(owner: Any, *, time_module: Any, logger: logging.Logger) -> None:
    """Enforce the owner's delay between requests."""
    now = time_module.time()
    wait = owner.request_delay - (now - owner._last_request_time)
    if wait > 0:
        logger.debug(f"Rate limiting: sleeping {wait:.2f}s")
        time_module.sleep(wait)
    owner._last_request_time = time_module.time()


def make_json_request(
    owner: Any,
    url: str,
    *,
    httpx_module: Any,
    client_factory: Any,
    time_module: Any,
    logger: logging.Logger,
) -> dict[str, Any]:
    """Make a JSON GET request using the owner's retry settings."""
    return _make_request(
        owner,
        url,
        response_key="data",
        response_reader=lambda response: response.json(),
        headers=owner.headers,
        httpx_module=httpx_module,
        client_factory=client_factory,
        time_module=time_module,
        logger=logger,
    )


def make_html_request(
    owner: Any,
    url: str,
    *,
    httpx_module: Any,
    client_factory: Any,
    time_module: Any,
    logger: logging.Logger,
) -> dict[str, Any]:
    """Make an HTML GET request using the owner's retry settings."""
    return _make_request(
        owner,
        url,
        response_key="html",
        response_reader=lambda response: response.text,
        headers=HTML_HEADERS,
        httpx_module=httpx_module,
        client_factory=client_factory,
        time_module=time_module,
        logger=logger,
        log_label="HTML ",
    )


def _make_request(
    owner: Any,
    url: str,
    *,
    response_key: str,
    response_reader: Any,
    headers: dict[str, str],
    httpx_module: Any,
    client_factory: Any,
    time_module: Any,
    logger: logging.Logger,
    log_label: str = "",
) -> dict[str, Any]:
    last_error = ""
    for attempt in range(owner.max_retries + 1):
        owner._rate_limit()
        try:
            logger.debug(f"Requesting {log_label}{url} (attempt {attempt + 1})")
            with client_factory() as client:
                response = client.get(url, headers=headers, timeout=owner.timeout)
                response.raise_for_status()
            return {"success": True, response_key: response_reader(response)}
        except httpx_module.TimeoutException:
            last_error = "Request timed out"
        except httpx_module.ConnectError:
            last_error = "Connection error"
        except httpx_module.HTTPStatusError as e:
            last_error = f"HTTP error: {e.response.status_code}"
        except httpx_module.RequestError as e:
            last_error = f"Request error: {e}"
        except Exception as e:
            last_error = f"Unexpected error: {e}"

        if attempt < owner.max_retries:
            delay = owner.request_delay * (owner.retry_backoff**attempt)
            logger.info(f"Retrying in {delay:.1f}s after: {last_error}")
            time_module.sleep(delay)

    logger.error(f"All attempts failed for {url}: {last_error}")
    return {"success": False, "error": last_error}
