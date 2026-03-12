"""Surgical coverage tests for PR #449 changed lines.

Targets uncovered lines identified by diff-cover:
- src/accessiweather/models/alerts.py line 37 (references=None branch)
- src/accessiweather/weather_client_nws.py lines 865-868 (client=None branch)
- src/accessiweather/weather_client_nws.py lines 1336-1338 (parse_nws_alerts references)
- src/accessiweather/weather_client_base.py lines 742-743 (_fetch_nws_cancel_references in auto path)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from accessiweather.models.alerts import WeatherAlert
from accessiweather.weather_client_nws import fetch_nws_cancel_references, parse_nws_alerts


# ---------------------------------------------------------------------------
# 1. models/alerts.py line 37: references=None → defaults to []
# ---------------------------------------------------------------------------
def test_weather_alert_references_none_defaults_to_list():
    alert = WeatherAlert(
        title="Test",
        description="desc",
        severity="Severe",
        urgency="Immediate",
        certainty="Observed",
        references=None,
    )
    assert alert.references == []


# ---------------------------------------------------------------------------
# 2. weather_client_nws.py lines 865-868: fetch without pre-existing client
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_nws_cancel_references_creates_own_client():
    """When client=None the function creates its own httpx.AsyncClient."""
    cancel_data = {
        "features": [
            {
                "properties": {
                    "references": [
                        {"identifier": "cancel-ref-1"},
                        {"@id": "cancel-ref-2"},
                    ],
                }
            }
        ]
    }

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=cancel_data)

    mock_new_client = AsyncMock()
    mock_new_client.get = AsyncMock(return_value=mock_response)

    with patch("accessiweather.weather_client_nws.httpx.AsyncClient") as MockAsyncClient:
        MockAsyncClient.return_value.__aenter__ = AsyncMock(return_value=mock_new_client)
        MockAsyncClient.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await fetch_nws_cancel_references(
            nws_base_url="https://api.weather.gov",
            user_agent="TestAgent/1.0",
            timeout=10.0,
            client=None,
        )

    assert "cancel-ref-1" in result
    assert "cancel-ref-2" in result


# ---------------------------------------------------------------------------
# 3. weather_client_nws.py lines 1336-1338: parse_nws_alerts with references
# ---------------------------------------------------------------------------
def test_parse_nws_alerts_extracts_references():
    """parse_nws_alerts should populate WeatherAlert.references from properties.references."""
    data = {
        "features": [
            {
                "properties": {
                    "id": "urn:oid:2.49.0.1.840.0.123",
                    "headline": "Tornado Warning",
                    "severity": "Extreme",
                    "urgency": "Immediate",
                    "certainty": "Observed",
                    "event": "Tornado Warning",
                    "description": "desc",
                    "references": [
                        {"identifier": "ref-A"},
                        {"@id": "ref-B"},
                        {"id": "ref-C"},
                    ],
                }
            }
        ]
    }
    alerts_obj = parse_nws_alerts(data)
    assert len(alerts_obj.alerts) == 1
    assert "ref-A" in alerts_obj.alerts[0].references
    assert "ref-B" in alerts_obj.alerts[0].references
    assert "ref-C" in alerts_obj.alerts[0].references
