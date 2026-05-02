from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import httpx
import pytest

from accessiweather.iem_client import (
    IemProductFetchError,
    fetch_iem_afos_text,
    fetch_iem_spc_mcds,
    fetch_iem_spc_outlook,
    fetch_iem_spc_watches,
    fetch_iem_wpc_mpds,
    fetch_iem_wpc_outlook,
)

IEM_BASE = "https://mesonet.example.test"


def _resp(json_data=None, text: str = "", status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = text
    return resp


def _client(response: MagicMock) -> MagicMock:
    client = MagicMock(spec=httpx.AsyncClient)
    client.get.return_value = response
    return client


@pytest.mark.asyncio
async def test_afos_retrieve_builds_current_text_query():
    client = _client(_resp(text="SWODY1 raw text"))

    result = await fetch_iem_afos_text("swody1", client=client, iem_base_url=IEM_BASE)

    assert result.product_type == "SWODY1"
    assert result.product_id == "SWODY1"
    assert result.cwa_office == "IEM"
    assert result.product_text == "SWODY1 raw text"
    client.get.assert_called_once_with(
        f"{IEM_BASE}/cgi-bin/afos/retrieve.py",
        params={"pil": "SWODY1", "fmt": "text", "limit": 1, "order": "desc"},
        headers={"User-Agent": "AccessiWeather (github.com/orinks/accessiweather)"},
    )


@pytest.mark.asyncio
async def test_afos_retrieve_accepts_history_filters():
    client = _client(_resp(text="historical text"))
    start = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    end = datetime(2026, 4, 2, 0, 0, tzinfo=UTC)

    await fetch_iem_afos_text(
        "AFDDMX",
        client=client,
        iem_base_url=IEM_BASE,
        limit=5,
        start=start,
        end=end,
        order="asc",
        center="KDMX",
        wmo_id="FXUS63",
        matches="AVIATION",
    )

    params = client.get.call_args.kwargs["params"]
    assert params == {
        "pil": "AFDDMX",
        "fmt": "text",
        "limit": 5,
        "order": "asc",
        "sdate": "2026-04-01T00:00:00Z",
        "edate": "2026-04-02T00:00:00Z",
        "center": "KDMX",
        "ttaaii": "FXUS63",
        "matches": "AVIATION",
    }


@pytest.mark.asyncio
async def test_afos_retrieve_strips_iem_control_characters():
    client = _client(_resp(text="\x01 627\r\nAFDRAH text\x03\n"))

    result = await fetch_iem_afos_text("AFDRAH", client=client, iem_base_url=IEM_BASE)

    assert result.product_text == "627\r\nAFDRAH text"


@pytest.mark.asyncio
async def test_afos_retrieve_raises_on_http_error():
    client = _client(_resp(status_code=503, text="slow query"))

    with pytest.raises(IemProductFetchError):
        await fetch_iem_afos_text("SWODY1", client=client, iem_base_url=IEM_BASE)


@pytest.mark.asyncio
async def test_spc_outlook_returns_accessible_summary():
    client = _client(
        _resp(
            {
                "generated_at": "2026-05-01T12:00:00Z",
                "outlooks": [
                    {
                        "category": "ENH",
                        "threshold": "CATEGORICAL",
                        "valid": "2026-05-01T13:00:00Z",
                    }
                ],
            }
        )
    )

    result = await fetch_iem_spc_outlook(
        38.907,
        -77.037,
        day=1,
        current=True,
        client=client,
        iem_base_url=IEM_BASE,
    )

    assert result.product_id == "SPC_OUTLOOK_DAY1"
    assert "SPC Day 1 Convective Outlook" in result.headline
    assert "ENH" in result.product_text
    client.get.assert_called_once()
    assert client.get.call_args.kwargs["params"] == {
        "lat": 38.907,
        "lon": -77.037,
        "day": 1,
        "fmt": "json",
        "current": 1,
    }


@pytest.mark.asyncio
async def test_spc_mcd_returns_accessible_summary():
    client = _client(
        _resp(
            {
                "mcds": [
                    {
                        "mdnum": 123,
                        "product_issue": "2026-05-01T18:00:00Z",
                        "concerning": "Severe potential",
                        "watch_prob": 60,
                    }
                ]
            }
        )
    )

    result = await fetch_iem_spc_mcds(42.0, -95.0, client=client, iem_base_url=IEM_BASE)

    assert result.product_id == "SPC_MCD"
    assert "Mesoscale Discussions" in result.headline
    assert "123" in result.product_text
    assert "Severe potential" in result.product_text
    assert "60" in result.product_text


@pytest.mark.asyncio
async def test_spc_watches_returns_accessible_summary():
    client = _client(
        _resp(
            {
                "features": [
                    {
                        "properties": {
                            "sel": "SEL7",
                            "type": "TOR",
                            "number": 67,
                            "issue": "2026-03-16T14:50:00Z",
                            "expire": "2026-03-16T23:13:00Z",
                            "is_pds": False,
                        }
                    }
                ]
            }
        )
    )

    result = await fetch_iem_spc_watches(38.0, -77.0, client=client, iem_base_url=IEM_BASE)

    assert result.product_id == "SPC_WATCHES"
    assert "SPC Watches" in result.product_text
    assert "SEL7" in result.product_text
    assert "TOR" in result.product_text
    client.get.assert_called_once()
    assert client.get.call_args.kwargs["params"] == {"lat": 38.0, "lon": -77.0}


@pytest.mark.asyncio
async def test_wpc_outlook_returns_accessible_summary():
    client = _client(
        _resp(
            {
                "generated_at": "2026-05-01T12:00:00Z",
                "outlooks": [
                    {
                        "day": 1,
                        "utc_product_issue": "2026-03-16T07:22:00Z",
                        "utc_issue": "2026-03-16T12:00:00Z",
                        "utc_expire": "2026-03-17T12:00:00Z",
                        "threshold": "MRGL",
                        "category": "CATEGORICAL",
                    }
                ],
            }
        )
    )

    result = await fetch_iem_wpc_outlook(
        38.907,
        -77.037,
        day=1,
        client=client,
        iem_base_url=IEM_BASE,
    )

    assert result.product_id == "WPC_ERO_DAY1"
    assert "WPC Day 1 Excessive Rainfall Outlook" in result.product_text
    assert "MRGL" in result.product_text
    assert client.get.call_args.kwargs["params"] == {
        "lat": 38.907,
        "lon": -77.037,
        "day": 1,
        "fmt": "json",
        "last": 1,
    }


@pytest.mark.asyncio
async def test_wpc_mpd_returns_accessible_summary():
    client = _client(
        _resp(
            {
                "mpds": [
                    {
                        "product_num": 934,
                        "product_id": "202508141928-KWNH-AWUS01-FFGMPD",
                        "utc_issue": "2025-08-14T19:27:00Z",
                        "utc_expire": "2025-08-14T22:27:00Z",
                        "concerning": "HEAVY RAINFALL...FLASH FLOODING POSSIBLE",
                    }
                ]
            }
        )
    )

    result = await fetch_iem_wpc_mpds(38.907, -77.037, client=client, iem_base_url=IEM_BASE)

    assert result.product_id == "WPC_MPD"
    assert "WPC Mesoscale Precipitation Discussions" in result.product_text
    assert "934" in result.product_text
    assert "FLASH FLOODING POSSIBLE" in result.product_text
