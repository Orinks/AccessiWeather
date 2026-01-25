"""
Tests for NWS alerts functionality.

Tests NWS alert parsing, including handling of different messageType values
(Alert, Update, Cancel) and regression tests for issue where updated warnings
were being filtered out.

Regression test for: 7862708 - Fix: NWS alerts not showing updated warnings
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.models import Location
from accessiweather.weather_client_nws import get_nws_alerts, parse_nws_alerts


class TestParseNwsAlerts:
    """Tests for parse_nws_alerts function."""

    def test_parse_alert_message_type_alert(self):
        """Test parsing alert with messageType 'Alert'."""
        data = {
            "features": [
                {
                    "id": "urn:oid:2.49.0.1.840.0.test1",
                    "properties": {
                        "messageType": "Alert",
                        "headline": "Tornado Warning issued",
                        "description": "A tornado has been spotted.",
                        "severity": "Extreme",
                        "urgency": "Immediate",
                        "certainty": "Observed",
                        "event": "Tornado Warning",
                        "expires": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                    },
                }
            ]
        }
        alerts = parse_nws_alerts(data)
        assert len(alerts.alerts) == 1
        assert alerts.alerts[0].event == "Tornado Warning"
        assert alerts.alerts[0].severity == "Extreme"

    def test_parse_alert_message_type_update(self):
        """
        Test parsing alert with messageType 'Update'.

        This is a regression test for issue where updated warnings
        were being filtered out (commit 7862708).
        """
        data = {
            "features": [
                {
                    "id": "urn:oid:2.49.0.1.840.0.test2",
                    "properties": {
                        "messageType": "Update",
                        "headline": "Winter Storm Warning now in effect",
                        "description": "Heavy snow expected. Warning extended.",
                        "severity": "Severe",
                        "urgency": "Expected",
                        "certainty": "Likely",
                        "event": "Winter Storm Warning",
                        "expires": (datetime.now(UTC) + timedelta(hours=6)).isoformat(),
                    },
                }
            ]
        }
        alerts = parse_nws_alerts(data)
        assert len(alerts.alerts) == 1
        assert alerts.alerts[0].event == "Winter Storm Warning"
        # The parser should successfully parse Update type alerts
        assert alerts.alerts[0].headline == "Winter Storm Warning now in effect"

    def test_parse_alert_message_type_cancel(self):
        """Test parsing alert with messageType 'Cancel'."""
        data = {
            "features": [
                {
                    "id": "urn:oid:2.49.0.1.840.0.test3",
                    "properties": {
                        "messageType": "Cancel",
                        "headline": "Tornado Warning cancelled",
                        "description": "The tornado warning has been cancelled.",
                        "severity": "Minor",
                        "urgency": "Past",
                        "certainty": "Observed",
                        "event": "Tornado Warning",
                        "expires": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
                    },
                }
            ]
        }
        alerts = parse_nws_alerts(data)
        assert len(alerts.alerts) == 1
        # Cancel alerts should still be parsed

    def test_parse_mixed_message_types(self):
        """Test parsing multiple alerts with different messageTypes."""
        now = datetime.now(UTC)
        data = {
            "features": [
                {
                    "id": "urn:oid:2.49.0.1.840.0.alert1",
                    "properties": {
                        "messageType": "Alert",
                        "headline": "Flash Flood Warning",
                        "event": "Flash Flood Warning",
                        "severity": "Severe",
                        "urgency": "Immediate",
                        "certainty": "Observed",
                        "expires": (now + timedelta(hours=2)).isoformat(),
                    },
                },
                {
                    "id": "urn:oid:2.49.0.1.840.0.update1",
                    "properties": {
                        "messageType": "Update",
                        "headline": "Severe Thunderstorm Warning updated",
                        "event": "Severe Thunderstorm Warning",
                        "severity": "Severe",
                        "urgency": "Immediate",
                        "certainty": "Observed",
                        "expires": (now + timedelta(hours=1)).isoformat(),
                    },
                },
                {
                    "id": "urn:oid:2.49.0.1.840.0.cancel1",
                    "properties": {
                        "messageType": "Cancel",
                        "headline": "Heat Advisory cancelled",
                        "event": "Heat Advisory",
                        "severity": "Minor",
                        "urgency": "Past",
                        "certainty": "Observed",
                        "expires": (now - timedelta(minutes=10)).isoformat(),
                    },
                },
            ]
        }
        alerts = parse_nws_alerts(data)
        # All three should be parsed
        assert len(alerts.alerts) == 3

        # Verify each type was included
        events = {a.event for a in alerts.alerts}
        assert "Flash Flood Warning" in events
        assert "Severe Thunderstorm Warning" in events
        assert "Heat Advisory" in events

    def test_parse_empty_features(self):
        """Test parsing response with no alerts."""
        data = {"features": []}
        alerts = parse_nws_alerts(data)
        assert len(alerts.alerts) == 0

    def test_parse_missing_features_key(self):
        """Test parsing response with missing features key."""
        data = {}
        alerts = parse_nws_alerts(data)
        assert len(alerts.alerts) == 0

    def test_parse_alert_id_extraction(self):
        """Test that alert IDs are correctly extracted."""
        data = {
            "features": [
                {
                    "id": "urn:oid:2.49.0.1.840.0.explicit-id",
                    "properties": {
                        "headline": "Test Alert",
                        "severity": "Moderate",
                    },
                }
            ]
        }
        alerts = parse_nws_alerts(data)
        assert alerts.alerts[0].id == "urn:oid:2.49.0.1.840.0.explicit-id"

    def test_parse_alert_id_from_identifier(self):
        """Test alert ID extraction from identifier property."""
        data = {
            "features": [
                {
                    "properties": {
                        "identifier": "identifier-based-id",
                        "headline": "Test Alert",
                        "severity": "Moderate",
                    },
                }
            ]
        }
        alerts = parse_nws_alerts(data)
        assert alerts.alerts[0].id == "identifier-based-id"

    def test_parse_alert_id_from_at_id(self):
        """Test alert ID extraction from @id property."""
        data = {
            "features": [
                {
                    "properties": {
                        "@id": "at-id-based-id",
                        "headline": "Test Alert",
                        "severity": "Moderate",
                    },
                }
            ]
        }
        alerts = parse_nws_alerts(data)
        assert alerts.alerts[0].id == "at-id-based-id"


class TestGetNwsAlertsParameters:
    """
    Tests for get_nws_alerts API parameters.

    These tests verify:
    - The API uses point query for precise polygon-based alert matching
    - The API does not incorrectly filter by message_type (which would exclude Update alerts)
    """

    @pytest.fixture
    def location(self):
        """Test location in the US."""
        return Location(name="Test City", latitude=40.7128, longitude=-74.0060)

    @pytest.mark.asyncio
    async def test_get_alerts_uses_point_query(self, location):
        """
        Test that get_nws_alerts uses point-based query for precise location matching.

        Point queries provide accurate polygon intersection for county-based alerts
        (tornado warnings, severe thunderstorm warnings, flash floods, etc.) rather
        than zone-based queries which may over-report alerts for your general area.
        """
        mock_response = MagicMock()
        mock_response.json.return_value = {"features": []}
        mock_response.raise_for_status = MagicMock()

        with patch("accessiweather.weather_client_nws.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            await get_nws_alerts(
                location=location,
                nws_base_url="https://api.weather.gov",
                user_agent="Test/1.0",
                timeout=10.0,
            )

            # Verify the request was made
            mock_client.get.assert_called_once()
            call_args = mock_client.get.call_args

            # Get the params from the call
            params = call_args.kwargs.get("params", {})

            # Critical assertion: point parameter must be present for precise location matching
            assert "point" in params, (
                "Point query is required for precise polygon-based alert matching. "
                "Zone-based queries may over-report alerts."
            )

            # Verify point format is correct (lat,lon)
            expected_point = f"{location.latitude},{location.longitude}"
            assert params.get("point") == expected_point, (
                f"Point parameter should be '{expected_point}', got '{params.get('point')}'"
            )

            # Verify zone is NOT used (we want point-based, not zone-based)
            assert "zone" not in params, (
                "Zone parameter should not be used - point query is preferred for precision"
            )

    @pytest.mark.asyncio
    async def test_get_alerts_no_message_type_filter(self, location):
        """
        Test that get_nws_alerts does NOT filter by message_type.

        Regression test for commit 7862708. The old code had:
            params = {"message_type": "alert"}
        which excluded alerts with messageType="Update".
        """
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "features": [
                {
                    "id": "test-alert-1",
                    "properties": {
                        "messageType": "Update",
                        "headline": "Test Update Alert",
                        "severity": "Moderate",
                        "event": "Test Warning",
                    },
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("accessiweather.weather_client_nws.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            await get_nws_alerts(
                location=location,
                nws_base_url="https://api.weather.gov",
                user_agent="Test/1.0",
                timeout=10.0,
            )

            # Verify the request was made
            mock_client.get.assert_called_once()
            call_args = mock_client.get.call_args

            # Get the params from the call
            params = call_args.kwargs.get("params", {})

            # The critical assertion: message_type should NOT be in params
            assert "message_type" not in params, (
                "message_type filter would exclude Update alerts! "
                "See commit 7862708 for context."
            )

            # Verify status=actual is still there (expected filter)
            assert params.get("status") == "actual"

            # Verify point is correctly formatted
            assert params.get("point") == f"{location.latitude},{location.longitude}"

    @pytest.mark.asyncio
    async def test_get_alerts_returns_update_type_alerts(self, location):
        """Test that Update type alerts are returned from API."""
        update_alert_response = {
            "features": [
                {
                    "id": "urn:oid:2.49.0.1.840.0.update-test",
                    "properties": {
                        "messageType": "Update",
                        "headline": "Winter Storm Warning UPDATED",
                        "description": "Warning extended through Saturday.",
                        "severity": "Severe",
                        "urgency": "Expected",
                        "certainty": "Likely",
                        "event": "Winter Storm Warning",
                        "expires": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
                    },
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = update_alert_response
        mock_response.raise_for_status = MagicMock()

        with patch("accessiweather.weather_client_nws.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            result = await get_nws_alerts(
                location=location,
                nws_base_url="https://api.weather.gov",
                user_agent="Test/1.0",
                timeout=10.0,
            )

            assert result is not None
            assert len(result.alerts) == 1
            assert result.alerts[0].event == "Winter Storm Warning"
            assert "UPDATED" in result.alerts[0].headline


class TestAlertTimeParsing:
    """Tests for alert time field parsing."""

    def test_parse_iso_datetime(self):
        """Test parsing ISO datetime with Z suffix."""
        data = {
            "features": [
                {
                    "id": "time-test-1",
                    "properties": {
                        "headline": "Test",
                        "severity": "Moderate",
                        "onset": "2026-01-24T12:00:00Z",
                        "expires": "2026-01-24T18:00:00Z",
                        "sent": "2026-01-24T11:00:00Z",
                        "effective": "2026-01-24T12:00:00Z",
                    },
                }
            ]
        }
        alerts = parse_nws_alerts(data)
        alert = alerts.alerts[0]

        assert alert.onset is not None
        assert alert.expires is not None
        assert alert.sent is not None
        assert alert.effective is not None

    def test_parse_iso_datetime_with_offset(self):
        """Test parsing ISO datetime with timezone offset."""
        data = {
            "features": [
                {
                    "id": "time-test-2",
                    "properties": {
                        "headline": "Test",
                        "severity": "Moderate",
                        "onset": "2026-01-24T12:00:00-05:00",
                        "expires": "2026-01-24T18:00:00-05:00",
                    },
                }
            ]
        }
        alerts = parse_nws_alerts(data)
        alert = alerts.alerts[0]

        assert alert.onset is not None
        assert alert.expires is not None

    def test_parse_missing_time_fields(self):
        """Test parsing when time fields are missing."""
        data = {
            "features": [
                {
                    "id": "time-test-3",
                    "properties": {
                        "headline": "Test",
                        "severity": "Moderate",
                        # No time fields
                    },
                }
            ]
        }
        alerts = parse_nws_alerts(data)
        alert = alerts.alerts[0]

        assert alert.onset is None
        assert alert.expires is None
        assert alert.sent is None
        assert alert.effective is None


class TestAlertAreasParsing:
    """Tests for alert area description parsing."""

    def test_parse_single_area(self):
        """Test parsing single area description."""
        data = {
            "features": [
                {
                    "id": "area-test-1",
                    "properties": {
                        "headline": "Test",
                        "severity": "Moderate",
                        "areaDesc": "New York, NY",
                    },
                }
            ]
        }
        alerts = parse_nws_alerts(data)
        assert alerts.alerts[0].areas == ["New York, NY"]

    def test_parse_multiple_areas(self):
        """Test parsing multiple areas separated by semicolons."""
        data = {
            "features": [
                {
                    "id": "area-test-2",
                    "properties": {
                        "headline": "Test",
                        "severity": "Moderate",
                        "areaDesc": "Kings, NY; Queens, NY; Brooklyn, NY",
                    },
                }
            ]
        }
        alerts = parse_nws_alerts(data)
        assert len(alerts.alerts[0].areas) == 3
        assert "Kings, NY" in alerts.alerts[0].areas
        assert "Queens, NY" in alerts.alerts[0].areas
        assert "Brooklyn, NY" in alerts.alerts[0].areas

    def test_parse_missing_area(self):
        """Test parsing when areaDesc is missing."""
        data = {
            "features": [
                {
                    "id": "area-test-3",
                    "properties": {
                        "headline": "Test",
                        "severity": "Moderate",
                    },
                }
            ]
        }
        alerts = parse_nws_alerts(data)
        assert alerts.alerts[0].areas == []
