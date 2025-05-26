"""Tests for the duplicate alert notifications fix.

This module tests that the WeatherNotifier correctly handles persistent storage
of alert state to prevent duplicate notifications on app restart or timer updates.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from accessiweather.notifications import WeatherNotifier


class TestAlertNotificationsFix:
    """Test cases for the duplicate alert notifications fix."""

    def setup_method(self):
        """Set up test environment before each test."""
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.alerts_state_file = os.path.join(self.temp_dir, "alert_state.json")

    def teardown_method(self):
        """Clean up after each test."""
        # Clean up temporary files
        if os.path.exists(self.alerts_state_file):
            os.remove(self.alerts_state_file)
        os.rmdir(self.temp_dir)

    def create_sample_alert(
        self, alert_id="test_alert_1", event="Tornado Warning", expires_hours=2
    ):
        """Create a sample alert for testing.

        Args:
            alert_id: Unique identifier for the alert
            event: Type of weather event
            expires_hours: Hours from now when the alert expires

        Returns:
            Dictionary containing alert data
        """
        expires_time = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
        return {
            "id": alert_id,
            "event": event,
            "headline": f"{event} in effect",
            "description": f"A {event} has been issued for your area",
            "severity": "Extreme",
            "urgency": "Immediate",
            "expires": expires_time.isoformat(),
            "sent": datetime.now(timezone.utc).isoformat(),
            "effective": datetime.now(timezone.utc).isoformat(),
            "status": "Actual",
            "messageType": "Alert",
            "category": "Met",
            "response": "Shelter",
            "parameters": {},
            "instruction": "Take shelter immediately",
            "areaDesc": "",  # Add areaDesc field for deduplication
        }

    def create_alerts_data(self, alerts):
        """Create alerts data in the format expected by process_alerts.

        Args:
            alerts: List of alert dictionaries

        Returns:
            Dictionary in the format expected by the API
        """
        features = []
        for alert in alerts:
            features.append({"properties": alert})
        return {"features": features}

    def test_persistent_storage_prevents_duplicate_notifications(self):
        """Test that persistent storage prevents duplicate notifications."""
        # Create notifier with persistence enabled
        notifier = WeatherNotifier(config_dir=self.temp_dir, enable_persistence=True)

        # Create a sample alert
        alert = self.create_sample_alert()
        alerts_data = self.create_alerts_data([alert])

        # Process alerts for the first time
        with patch.object(notifier, "show_notification") as mock_show:
            processed_alerts, new_count, updated_count = notifier.process_alerts(alerts_data)

            # Should show notification for new alert
            assert new_count == 1
            assert updated_count == 0
            assert len(processed_alerts) == 1
            mock_show.assert_called_once()

        # Verify alert state was saved
        assert os.path.exists(self.alerts_state_file)

        # Create a new notifier instance (simulating app restart)
        notifier2 = WeatherNotifier(config_dir=self.temp_dir, enable_persistence=True)

        # Process the same alerts again
        with patch.object(notifier2, "show_notification") as mock_show2:
            processed_alerts2, new_count2, updated_count2 = notifier2.process_alerts(alerts_data)

            # Should NOT show notification for existing alert
            assert new_count2 == 0
            assert updated_count2 == 0
            assert len(processed_alerts2) == 1
            mock_show2.assert_not_called()

    def test_expired_alerts_filtered_on_load(self):
        """Test that expired alerts are filtered out when loading state."""
        # Create an expired alert
        expired_alert = self.create_sample_alert(
            alert_id="expired_alert",
            event="Severe Thunderstorm Warning",
            expires_hours=-1,  # Expired 1 hour ago
        )

        # Manually create alert state file with expired alert
        state_data = {
            "active_alerts": {"expired_alert": expired_alert},
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
        }

        with open(self.alerts_state_file, "w") as f:
            json.dump(state_data, f)

        # Create notifier - should filter out expired alert
        notifier = WeatherNotifier(config_dir=self.temp_dir, enable_persistence=True)

        # Should have no active alerts
        assert len(notifier.active_alerts) == 0

    def test_alert_updates_trigger_notifications(self):
        """Test that updated alerts trigger notifications."""
        notifier = WeatherNotifier(config_dir=self.temp_dir, enable_persistence=True)

        # Create initial alert
        alert = self.create_sample_alert()
        alerts_data = self.create_alerts_data([alert])

        # Process initial alert
        with patch.object(notifier, "show_notification") as mock_show:
            notifier.process_alerts(alerts_data)
            mock_show.assert_called_once_with(alert, is_update=False)

        # Update the alert (change headline)
        updated_alert = alert.copy()
        updated_alert["headline"] = "Updated: Tornado Warning in effect"
        updated_alerts_data = self.create_alerts_data([updated_alert])

        # Process updated alert
        with patch.object(notifier, "show_notification") as mock_show2:
            processed_alerts, new_count, updated_count = notifier.process_alerts(
                updated_alerts_data
            )

            # Should show notification for updated alert
            assert new_count == 0
            assert updated_count == 1
            mock_show2.assert_called_once_with(updated_alert, is_update=True)

    def test_persistence_disabled_works_normally(self):
        """Test that disabling persistence works normally without errors."""
        # Create notifier with persistence disabled
        notifier = WeatherNotifier(config_dir=self.temp_dir, enable_persistence=False)

        # Create sample alert
        alert = self.create_sample_alert()
        alerts_data = self.create_alerts_data([alert])

        # Process alerts
        with patch.object(notifier, "show_notification") as mock_show:
            processed_alerts, new_count, updated_count = notifier.process_alerts(alerts_data)

            # Should work normally
            assert new_count == 1
            assert updated_count == 0
            mock_show.assert_called_once()

        # Should not create state file
        assert not os.path.exists(self.alerts_state_file)

    def test_multiple_alerts_processing(self):
        """Test processing multiple alerts correctly."""
        notifier = WeatherNotifier(config_dir=self.temp_dir, enable_persistence=True)

        # Create multiple alerts
        alert1 = self.create_sample_alert("alert1", "Tornado Warning")
        alert2 = self.create_sample_alert("alert2", "Severe Thunderstorm Warning")
        alerts_data = self.create_alerts_data([alert1, alert2])

        # Process alerts
        with patch.object(notifier, "show_notification") as mock_show:
            processed_alerts, new_count, updated_count = notifier.process_alerts(alerts_data)

            # Should process both alerts
            assert new_count == 2
            assert updated_count == 0
            assert len(processed_alerts) == 2
            assert mock_show.call_count == 2

        # Process same alerts again
        with patch.object(notifier, "show_notification") as mock_show2:
            processed_alerts2, new_count2, updated_count2 = notifier.process_alerts(alerts_data)

            # Should not show notifications for existing alerts
            assert new_count2 == 0
            assert updated_count2 == 0
            assert len(processed_alerts2) == 2
            mock_show2.assert_not_called()

    def test_alert_deduplication_same_event_different_offices(self):
        """Test that alerts from different offices for the same event are deduplicated."""
        notifier = WeatherNotifier(config_dir=self.temp_dir, enable_persistence=True)

        # Create duplicate alerts from different offices (same event, time, area)
        base_time = datetime.now(timezone.utc)
        expires_time = base_time + timedelta(hours=2)

        alert1 = {
            "id": "office1_alert_123",
            "event": "Tornado Warning",
            "headline": "Tornado Warning in effect",
            "description": "A tornado warning has been issued",
            "severity": "Extreme",
            "urgency": "Immediate",
            "expires": expires_time.isoformat(),
            "sent": base_time.isoformat(),
            "effective": base_time.isoformat(),
            "status": "Actual",
            "messageType": "Alert",
            "category": "Met",
            "response": "Shelter",
            "parameters": {},
            "instruction": "Take shelter immediately",
            "areaDesc": "Smith County",
        }

        alert2 = {
            "id": "office2_alert_456",  # Different ID from different office
            "event": "Tornado Warning",  # Same event
            "headline": "Tornado Warning in effect",
            "description": "A tornado warning has been issued",
            "severity": "Extreme",
            "urgency": "Immediate",
            "expires": expires_time.isoformat(),  # Same expiration
            "sent": base_time.isoformat(),  # Same time
            "effective": base_time.isoformat(),  # Same effective time
            "status": "Actual",
            "messageType": "Alert",
            "category": "Met",
            "response": "Shelter",
            "parameters": {},
            "instruction": "Take shelter immediately",
            "areaDesc": "Smith County",  # Same area
        }

        alerts_data = self.create_alerts_data([alert1, alert2])

        # Process alerts
        with patch.object(notifier, "show_notification") as mock_show:
            processed_alerts, new_count, updated_count = notifier.process_alerts(alerts_data)

            # Should only show ONE notification despite having 2 alerts
            assert new_count == 1, f"Expected 1 new alert, got {new_count}"
            assert updated_count == 0
            assert (
                len(processed_alerts) == 1
            ), f"Expected 1 processed alert, got {len(processed_alerts)}"
            assert mock_show.call_count == 1, f"Expected 1 notification, got {mock_show.call_count}"

            # The processed alert should be one of the original alerts
            processed_alert = processed_alerts[0]
            assert processed_alert["event"] == "Tornado Warning"
            assert processed_alert["severity"] == "Extreme"
