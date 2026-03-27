"""
Surgical coverage tests for PR #449 and PR #456 changed lines.

Targets uncovered lines identified by diff-cover:
- src/accessiweather/models/alerts.py line 37 (references=None branch)
- src/accessiweather/weather_client_nws.py lines 865-868 (client=None branch)
- src/accessiweather/weather_client_nws.py lines 1336-1338 (parse_nws_alerts references)
- src/accessiweather/weather_client_base.py lines 742-743 (_fetch_nws_cancel_references in auto path)
- src/accessiweather/weather_client_base.py lines 912-924 (_launch_enrichment_tasks auto-mode tasks)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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


# ---------------------------------------------------------------------------
# 4. weather_client_base.py lines 912-924: _launch_enrichment_tasks auto-mode
#    These lines are inside `if self.data_source == "auto":` and create tasks
#    for sunrise_sunset, nws_discussion, vc_alerts, vc_moon_data, and marine.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_launch_enrichment_tasks_auto_mode_creates_smart_tasks():
    """_launch_enrichment_tasks with data_source='auto' creates all smart enrichment tasks."""
    import asyncio

    import accessiweather.weather_client_enrichment as enrichment
    from accessiweather.models import Location, WeatherData
    from accessiweather.weather_client import WeatherClient

    client = WeatherClient(data_source="auto")
    location = Location(name="NYC", latitude=40.7128, longitude=-74.0060)
    weather_data = WeatherData(location=location)

    async def _noop(*args, **kwargs):
        pass

    with (
        patch.object(enrichment, "enrich_with_sunrise_sunset", side_effect=_noop),
        patch.object(enrichment, "enrich_with_nws_discussion", side_effect=_noop),
        patch.object(enrichment, "enrich_with_visual_crossing_alerts", side_effect=_noop),
        patch.object(enrichment, "enrich_with_visual_crossing_moon_data", side_effect=_noop),
        patch.object(enrichment, "populate_environmental_metrics", side_effect=_noop),
        patch.object(enrichment, "enrich_with_aviation_data", side_effect=_noop),
        patch.object(enrichment, "enrich_with_marine_data", side_effect=_noop),
    ):
        tasks = client._launch_enrichment_tasks(weather_data, location)
        # Cancel tasks to prevent ResourceWarning about pending coroutines
        for t in tasks.values():
            t.cancel()
        await asyncio.gather(*tasks.values(), return_exceptions=True)

    assert "sunrise_sunset" in tasks
    assert "nws_discussion" in tasks
    assert "vc_alerts" in tasks
    assert "vc_moon_data" in tasks
    assert "environmental" in tasks
    assert "aviation" in tasks
    assert "marine" in tasks


@pytest.mark.asyncio
async def test_launch_enrichment_tasks_non_auto_skips_smart_tasks():
    """_launch_enrichment_tasks with data_source != 'auto' does not create smart enrichment tasks."""
    import asyncio

    import accessiweather.weather_client_enrichment as enrichment
    from accessiweather.models import Location, WeatherData
    from accessiweather.weather_client import WeatherClient

    client = WeatherClient(data_source="nws")
    location = Location(name="NYC", latitude=40.7128, longitude=-74.0060)
    weather_data = WeatherData(location=location)

    async def _noop(*args, **kwargs):
        pass

    with (
        patch.object(enrichment, "populate_environmental_metrics", side_effect=_noop),
        patch.object(enrichment, "enrich_with_aviation_data", side_effect=_noop),
        patch.object(enrichment, "enrich_with_marine_data", side_effect=_noop),
    ):
        tasks = client._launch_enrichment_tasks(weather_data, location)
        for t in tasks.values():
            t.cancel()
        await asyncio.gather(*tasks.values(), return_exceptions=True)

    assert "sunrise_sunset" not in tasks
    assert "nws_discussion" not in tasks
    assert "vc_alerts" not in tasks
    assert "vc_moon_data" not in tasks
    assert "environmental" in tasks
    assert "aviation" in tasks
    assert "marine" in tasks
