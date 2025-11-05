"""
Tests for alert notification accessibility features.

Validates that alert messages are formatted appropriately for
screen reader users and assistive technology.
"""

from datetime import UTC, datetime, timedelta

import pytest

from accessiweather.alert_notification_system import format_accessible_message
from accessiweather.models import WeatherAlert


class TestAccessibleMessageFormatting:
    """Tests for format_accessible_message helper function."""

    def test_new_alert_basic_format(self):
        """Test basic message formatting for new alerts."""
        alert = WeatherAlert(
            title="Tornado Warning for Downtown",
            description="Take shelter immediately in a basement or interior room.",
            id="test-alert-1",
            event="Tornado Warning",
            severity="Extreme",
            urgency="Immediate",
            headline="Tornado warning issued for your area",
            areas=["Downtown", "Eastside"],
            expires=datetime.now(UTC) + timedelta(hours=1),
        )

        title, message = format_accessible_message(alert, "new_alert")

        # Title should include severity and event
        assert "EXTREME ALERT" in title
        assert "Tornado Warning" in title

        # Message should start with urgency
        assert message.startswith("Immediate action may be required.")

        # Message should include headline
        assert "Tornado warning issued for your area" in message

        # Message should include description
        assert "Take shelter immediately" in message

        # Message should include areas
        assert "Areas: Downtown, Eastside" in message

        # Message should include expiration (format: HH:MM PM on Mon DD)
        assert "Expires:" in message

    def test_escalated_alert_title(self):
        """Test that escalated alerts have proper title prefix."""
        alert = WeatherAlert(
            title="Thunderstorm Warning",
            description="Severe thunderstorms possible",
            id="test-alert-2",
            event="Thunderstorm Warning",
            severity="Severe",
            headline="Severe thunderstorm warning",
        )

        title, _ = format_accessible_message(alert, "escalation")

        assert title.startswith("ESCALATED SEVERE:")
        assert "Thunderstorm Warning" in title

    def test_updated_alert_title(self):
        """Test that updated alerts have proper title prefix."""
        alert = WeatherAlert(
            title="Flood Watch",
            description="Flooding possible in low-lying areas",
            id="test-alert-3",
            event="Flood Watch",
            severity="Moderate",
            headline="Flood watch extended",
        )

        title, _ = format_accessible_message(alert, "content_changed")

        assert title.startswith("UPDATED MODERATE:")
        assert "Flood Watch" in title

    def test_reminder_alert_title(self):
        """Test that reminder alerts have proper title prefix."""
        alert = WeatherAlert(
            title="Winter Storm Warning",
            description="Heavy snow and ice expected",
            id="test-alert-4",
            event="Winter Storm Warning",
            severity="Severe",
            headline="Winter storm warning remains in effect",
        )

        title, _ = format_accessible_message(alert, "reminder")

        assert title.startswith("ACTIVE SEVERE:")
        assert "Winter Storm Warning" in title

    def test_missing_headline_fallback(self):
        """Test that missing headlines are handled gracefully."""
        alert = WeatherAlert(
            title="Weather Advisory",
            description="Some weather condition exists.",
            id="test-alert-5",
            event="Weather Advisory",
            severity="Moderate",
            # No headline provided
        )

        title, message = format_accessible_message(alert, "new_alert")

        # Should use fallback message (from logger warning, using title as fallback)
        # Since headline is None, it should use title "Weather Advisory"
        assert (
            "Weather Advisory" in message
            or "moderate weather alert has been issued" in message.lower()
        )

    def test_urgency_filtering(self):
        """Test that only immediate/expected urgency is mentioned."""
        # Test immediate urgency
        alert_immediate = WeatherAlert(
            title="Test Alert",
            description="Test description",
            id="test-alert-6",
            event="Test Alert",
            severity="Moderate",
            urgency="Immediate",
            headline="Test headline",
        )

        _, message_immediate = format_accessible_message(alert_immediate, "new_alert")
        assert "Immediate action may be required." in message_immediate

        # Test expected urgency
        alert_expected = WeatherAlert(
            title="Test Alert",
            description="Test description",
            id="test-alert-7",
            event="Test Alert",
            severity="Moderate",
            urgency="Expected",
            headline="Test headline",
        )

        _, message_expected = format_accessible_message(alert_expected, "new_alert")
        assert "Expected action may be required." in message_expected

        # Test non-critical urgency (should not be mentioned)
        alert_future = WeatherAlert(
            title="Test Alert",
            description="Test description",
            id="test-alert-8",
            event="Test Alert",
            severity="Moderate",
            urgency="Future",
            headline="Test headline",
        )

        _, message_future = format_accessible_message(alert_future, "new_alert")
        assert "Future" not in message_future
        assert "action may be required" not in message_future

    def test_description_truncation(self):
        """Test that long descriptions are truncated with ellipsis."""
        long_desc = "A" * 200  # Longer than MAX_NOTIFICATION_DESCRIPTION_LENGTH (100)

        alert = WeatherAlert(
            title="Test Alert",
            description=long_desc,
            id="test-alert-9",
            event="Test Alert",
            severity="Moderate",
            headline="Test headline",
        )

        _, message = format_accessible_message(alert, "new_alert")

        # Should be truncated
        assert len(long_desc) > 100  # Verify test data
        assert "A" * 100 in message  # First 100 chars present
        assert message.count("...") == 1  # Ellipsis added
        assert "A" * 101 not in message  # Not full string

    def test_areas_list_truncation(self):
        """Test that long area lists are truncated with count."""
        many_areas = [f"Area{i}" for i in range(10)]

        alert = WeatherAlert(
            title="Test Alert",
            description="Test description",
            id="test-alert-10",
            event="Test Alert",
            severity="Moderate",
            headline="Test headline",
            areas=many_areas,
        )

        _, message = format_accessible_message(alert, "new_alert")

        # Should show first 2 areas (MAX_DISPLAYED_AREAS) + count
        assert "Area0" in message
        assert "Area1" in message
        assert "and 8 more" in message  # 10 total - 2 displayed = 8
        # Area2 should NOT be shown (only first 2)
        assert "Area2" not in message

    def test_exclude_areas_option(self):
        """Test that areas can be excluded from message."""
        alert = WeatherAlert(
            title="Test Alert",
            description="Test description",
            id="test-alert-11",
            event="Test Alert",
            severity="Moderate",
            headline="Test headline",
            areas=["Area1", "Area2"],
        )

        _, message = format_accessible_message(alert, "new_alert", include_areas=False)

        assert "Areas:" not in message
        assert "Area1" not in message
        assert "Area2" not in message

    def test_exclude_expiration_option(self):
        """Test that expiration can be excluded from message."""
        alert = WeatherAlert(
            title="Test Alert",
            description="Test description",
            id="test-alert-12",
            event="Test Alert",
            severity="Moderate",
            headline="Test headline",
            expires=datetime.now(UTC) + timedelta(hours=2),
        )

        _, message = format_accessible_message(alert, "new_alert", include_expiration=False)

        assert "Expires:" not in message

    def test_missing_severity_defaults_to_unknown(self):
        """Test that missing severity defaults to 'Unknown'."""
        alert = WeatherAlert(
            title="Test Alert",
            description="Test description",
            id="test-alert-13",
            event="Test Alert",
            # No severity provided (defaults to "Unknown")
            headline="Test headline",
        )

        title, message = format_accessible_message(alert, "new_alert")

        assert "UNKNOWN ALERT" in title

    def test_missing_event_defaults_to_weather_alert(self):
        """Test that missing event type defaults to 'Weather Alert'."""
        alert = WeatherAlert(
            title="Test Alert",
            description="Test description",
            id="test-alert-14",
            # No event provided
            severity="Moderate",
            headline="Test headline",
        )

        title, _ = format_accessible_message(alert, "new_alert")

        assert "Weather Alert" in title

    def test_message_structure_for_screen_readers(self):
        """Test that message has proper structure for screen reader pausing."""
        alert = WeatherAlert(
            title="Test Alert",
            description="Test description",
            id="test-alert-15",
            event="Test Alert",
            severity="Severe",
            urgency="Immediate",
            headline="Test headline",
            areas=["Area1"],
            expires=datetime.now(UTC) + timedelta(hours=1),
        )

        _, message = format_accessible_message(alert, "new_alert")

        # Should use double newlines for screen reader pausing
        assert "\n\n" in message

        # Verify order: urgency -> headline -> description -> areas -> expiration
        parts = message.split("\n\n")
        assert "action may be required" in parts[0].lower()
        assert "Test headline" in parts[1]
        assert "Test description" in parts[2]
        assert "Areas:" in parts[3]
        assert "Expires:" in parts[4]


class TestAccessibilityEdgeCases:
    """Tests for edge cases in accessibility formatting."""

    def test_empty_description(self):
        """Test handling of empty description."""
        alert = WeatherAlert(
            title="Test Alert",
            description="",  # Empty string
            id="test-alert-16",
            event="Test Alert",
            severity="Moderate",
            headline="Test headline",
        )

        _, message = format_accessible_message(alert, "new_alert")

        # Should not crash, should have headline
        assert "Test headline" in message
        # Should not have triple newlines (proper filtering of empty parts)
        # Note: May have double newlines between valid parts
        assert "\n\n\n\n" not in message

    def test_none_values(self):
        """Test handling of None values in various fields."""
        alert = WeatherAlert(
            title="Minimal Alert",
            description="Minimal description",
            id="test-alert-17",
            event=None,
            severity="Unknown",  # Can't be None in dataclass with default
            urgency=None,
            headline=None,
            areas=[],
            expires=None,
        )

        # Should not crash
        title, message = format_accessible_message(alert, "new_alert")

        assert "UNKNOWN ALERT" in title
        assert "Weather Alert" in title
        assert len(message) > 0  # Should have fallback content

    def test_expires_datetime_formatting(self):
        """Test that expiration datetime is formatted properly."""
        # Use specific date/time for predictable formatting
        expires = datetime(2024, 12, 25, 14, 30, tzinfo=UTC)

        alert = WeatherAlert(
            title="Test Alert",
            description="Test description",
            id="test-alert-18",
            event="Test Alert",
            severity="Moderate",
            headline="Test headline",
            expires=expires,
        )

        _, message = format_accessible_message(alert, "new_alert")

        # Should use 12-hour format with AM/PM
        assert "02:30 PM" in message or "14:30" in message  # Allow for timezone conversion
        # Should include abbreviated month
        assert "Dec" in message

    def test_case_insensitive_urgency_check(self):
        """Test that urgency checking is case-insensitive."""
        alert_upper = WeatherAlert(
            title="Test Alert",
            description="Test description",
            id="test-alert-19",
            event="Test Alert",
            severity="Moderate",
            urgency="IMMEDIATE",  # Uppercase
            headline="Test headline",
        )

        _, message_upper = format_accessible_message(alert_upper, "new_alert")
        assert "Immediate action may be required." in message_upper

        alert_mixed = WeatherAlert(
            title="Test Alert",
            description="Test description",
            id="test-alert-20",
            event="Test Alert",
            severity="Moderate",
            urgency="ImMeDiAtE",  # Mixed case
            headline="Test headline",
        )

        _, message_mixed = format_accessible_message(alert_mixed, "new_alert")
        assert "Immediate action may be required." in message_mixed


class TestAccessibilityIntegration:
    """Integration tests for accessibility with AlertNotificationSystem."""

    @pytest.mark.asyncio
    async def test_notification_system_uses_accessible_format(self, mock_notifier, tmp_path):
        """Test that AlertNotificationSystem uses format_accessible_message."""
        from accessiweather.alert_manager import AlertManager
        from accessiweather.alert_notification_system import AlertNotificationSystem

        # AlertManager requires config_dir
        alert_manager = AlertManager(config_dir=tmp_path)
        notification_system = AlertNotificationSystem(alert_manager, mock_notifier)

        alert = WeatherAlert(
            title="Tornado Warning",
            description="Seek shelter immediately.",
            id="test-alert-21",
            event="Tornado Warning",
            severity="Extreme",
            urgency="Immediate",
            headline="Tornado approaching",
            areas=["Downtown"],
        )

        # Send notification
        success = await notification_system._send_alert_notification(alert, "new_alert")

        assert success
        assert mock_notifier.last_notification is not None

        # Verify accessible format was used
        title = mock_notifier.last_notification["title"]
        message = mock_notifier.last_notification["message"]

        assert "EXTREME ALERT" in title
        assert "Immediate action may be required." in message
        assert "Tornado approaching" in message


@pytest.fixture
def mock_notifier():
    """Create a mock notifier for testing."""

    class MockNotifier:
        def __init__(self):
            self.last_notification = None

        def send_notification(self, title, message, timeout=10, sound_candidates=None):
            self.last_notification = {
                "title": title,
                "message": message,
                "timeout": timeout,
                "sound_candidates": sound_candidates,
            }
            return True

    return MockNotifier()
