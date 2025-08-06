"""Test script for the enhanced alert system.

This module provides tests for the AlertManager, AlertNotificationSystem,
and integration with the main application.
"""

import asyncio
import json
import logging
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from .alert_manager import AlertManager, AlertSettings
from .alert_notification_system import AlertNotificationSystem
from .models import WeatherAlert, WeatherAlerts

# Set up logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_alert(alert_id: str = "test-alert-1", severity: str = "Moderate") -> WeatherAlert:
    """Create a test weather alert."""
    return WeatherAlert(
        title="Test Weather Alert",
        description="This is a test alert for system verification.",
        severity=severity,
        urgency="Immediate",
        certainty="Observed",
        event="Test Alert",
        headline=f"Test {severity} weather alert - system verification",
        instruction="No action required - this is a test.",
        onset=datetime.now(),
        expires=datetime.now() + timedelta(hours=2),
        areas=["Test Area", "Another Test Area"],
        id=alert_id,
    )


def test_alert_model():
    """Test WeatherAlert model enhancements."""
    logger.info("Testing WeatherAlert model...")

    alert = create_test_alert()

    # Test unique ID generation
    unique_id = alert.get_unique_id()
    assert unique_id == "test-alert-1", f"Expected 'test-alert-1', got '{unique_id}'"

    # Test content hash
    hash1 = alert.get_content_hash()
    assert len(hash1) == 32, f"Expected 32-char hash, got {len(hash1)}"

    # Test hash changes with content
    alert.description = "Modified description"
    hash2 = alert.get_content_hash()
    assert hash1 != hash2, "Hash should change when content changes"

    # Test severity priority
    assert alert.get_severity_priority() == 3, (
        f"Expected priority 3 for Moderate, got {alert.get_severity_priority()}"
    )

    # Test expiration
    assert not alert.is_expired(), "Alert should not be expired"

    logger.info("✓ WeatherAlert model tests passed")


def test_alert_manager():
    """Test AlertManager functionality."""
    logger.info("Testing AlertManager...")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create AlertManager with test directory
        settings = AlertSettings()
        settings.min_severity_priority = 2  # Minor and above
        settings.global_cooldown = 1  # 1 minute for testing

        manager = AlertManager(temp_dir, settings)

        # Test initial state
        stats = manager.get_alert_statistics()
        assert stats["total_tracked_alerts"] == 0, "Should start with no tracked alerts"

        # Create test alerts
        alert1 = create_test_alert("alert-1", "Severe")
        alert2 = create_test_alert("alert-2", "Minor")
        alerts = WeatherAlerts([alert1, alert2])

        # Process alerts
        notifications = manager.process_alerts(alerts)

        # Should notify for both (new alerts)
        assert len(notifications) == 2, f"Expected 2 notifications, got {len(notifications)}"

        # Process same alerts again
        notifications2 = manager.process_alerts(alerts)

        # Should not notify again (cooldown)
        assert len(notifications2) == 0, (
            f"Expected 0 notifications on repeat, got {len(notifications2)}"
        )

        # Test state persistence
        manager._save_state()
        state_file = Path(temp_dir) / "alert_state.json"
        assert state_file.exists(), "State file should be created"

        with open(state_file) as f:
            state_data = json.load(f)

        assert len(state_data["alert_states"]) == 2, "Should have 2 alert states saved"

        logger.info("✓ AlertManager tests passed")


async def test_notification_system():
    """Test AlertNotificationSystem."""
    logger.info("Testing AlertNotificationSystem...")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create components
        settings = AlertSettings()
        manager = AlertManager(temp_dir, settings)

        # Use a mock notifier for testing
        class MockNotifier:
            def __init__(self):
                """Initialize the instance."""
                self.notifications_sent = []

            def send_notification(self, title, message, timeout=10):
                self.notifications_sent.append({"title": title, "message": message})
                return True

        mock_notifier = MockNotifier()
        notification_system = AlertNotificationSystem(manager, mock_notifier)

        # Test notification processing
        alert = create_test_alert("test-notification", "Extreme")
        alerts = WeatherAlerts([alert])

        notifications_sent = await notification_system.process_and_notify(alerts)
        assert notifications_sent == 1, f"Expected 1 notification sent, got {notifications_sent}"
        assert len(mock_notifier.notifications_sent) == 1, (
            "Mock notifier should have 1 notification"
        )

        notification = mock_notifier.notifications_sent[0]
        assert "Test Alert" in notification["title"], (
            f"Title should contain 'Test Alert', got '{notification['title']}'"
        )

        # Test test notification
        success = await notification_system.test_notification("Severe")
        assert success, "Test notification should succeed"
        assert len(mock_notifier.notifications_sent) == 2, "Should have 2 notifications after test"

        logger.info("✓ AlertNotificationSystem tests passed")


def test_settings_conversion():
    """Test settings conversion between AppSettings and AlertSettings."""
    logger.info("Testing settings conversion...")

    from .models import AppSettings

    # Create AppSettings with alert preferences
    app_settings = AppSettings()
    app_settings.alert_notifications_enabled = True
    app_settings.alert_notify_extreme = True
    app_settings.alert_notify_severe = True
    app_settings.alert_notify_moderate = False  # Disabled
    app_settings.alert_global_cooldown_minutes = 10
    app_settings.alert_ignored_categories = ["Test Category"]

    # Convert to AlertSettings
    alert_settings = app_settings.to_alert_settings()

    assert alert_settings.notifications_enabled is True, "Notifications should be enabled"
    assert alert_settings.min_severity_priority == 4, "Should require Severe or higher (priority 4)"
    assert alert_settings.global_cooldown == 10, "Global cooldown should be 10 minutes"
    assert "Test Category" in alert_settings.ignored_categories, "Should include ignored category"

    logger.info("✓ Settings conversion tests passed")


async def run_all_tests():
    """Run all alert system tests."""
    logger.info("Starting alert system tests...")

    try:
        # Run synchronous tests
        test_alert_model()
        test_alert_manager()
        test_settings_conversion()

        # Run async tests
        await test_notification_system()

        logger.info("🎉 All alert system tests passed!")
        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False


def main():
    """Run all tests."""
    success = asyncio.run(run_all_tests())
    if not success:
        exit(1)


if __name__ == "__main__":
    main()
