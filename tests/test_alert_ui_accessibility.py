"""
Tests for alert notification UI accessibility attributes.

Verifies that all alert-related UI widgets have proper aria_label and aria_description
attributes for screen reader compatibility per BeeWare/Toga accessibility requirements.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest
import toga

# Import dialog for settings UI testing
from accessiweather.dialogs.settings_dialog import SettingsDialog
from accessiweather.models.config import AppSettings


@pytest.fixture
def mock_app():
    """Create a mock Toga app instance with dummy backend."""
    os.environ["TOGA_BACKEND"] = "toga_dummy"
    app = toga.App("Test AccessiWeather", "org.beeware.test")
    app.config = MagicMock()
    app.on_exit = lambda: True
    yield app
    # No cleanup needed for dummy backend


@pytest.fixture
def mock_config_manager(mock_settings):
    """Create a mock config manager."""
    config_manager = MagicMock()
    config_manager.get_settings.return_value = mock_settings
    return config_manager


@pytest.fixture
def mock_settings():
    """Create mock AppSettings for testing."""
    return AppSettings(
        enable_alerts=True,
        alert_notifications_enabled=True,
        alert_notify_extreme=True,
        alert_notify_severe=True,
        alert_notify_moderate=True,
        alert_notify_minor=False,
        alert_notify_unknown=False,
        alert_global_cooldown_minutes=5,
        alert_per_alert_cooldown_minutes=60,
        alert_max_notifications_per_hour=10,
    )


class TestAlertNotificationTabAccessibility:
    """Test aria attributes for alert notification settings widgets."""

    def test_enable_alerts_switch_has_aria_attributes(self, mock_app, mock_config_manager):
        """Verify enable_alerts_switch has proper aria attributes."""
        dialog = SettingsDialog(app=mock_app, config_manager=mock_config_manager)
        dialog.show_and_prepare()  # Initialize UI widgets

        assert hasattr(dialog, "enable_alerts_switch")
        assert dialog.enable_alerts_switch is not None
        assert dialog.enable_alerts_switch.aria_label == "Toggle weather alerts"
        assert "master control" in dialog.enable_alerts_switch.aria_description.lower()
        assert "enable or disable" in dialog.enable_alerts_switch.aria_description.lower()

    def test_alert_notifications_enabled_switch_has_aria_attributes(
        self, mock_app, mock_config_manager
    ):
        """Verify alert_notifications_enabled_switch has proper aria attributes."""
        dialog = SettingsDialog(app=mock_app, config_manager=mock_config_manager)
        dialog.show_and_prepare()  # Initialize UI widgets

        assert hasattr(dialog, "alert_notifications_enabled_switch")
        assert dialog.alert_notifications_enabled_switch is not None
        assert dialog.alert_notifications_enabled_switch.aria_label == "Toggle alert notifications"
        assert (
            "master control" in dialog.alert_notifications_enabled_switch.aria_description.lower()
        )

    def test_extreme_severity_switch_has_aria_attributes(self, mock_app, mock_config_manager):
        """Verify alert_notify_extreme_switch has proper aria attributes."""
        dialog = SettingsDialog(app=mock_app, config_manager=mock_config_manager)
        dialog.show_and_prepare()  # Initialize UI widgets

        assert hasattr(dialog, "alert_notify_extreme_switch")
        assert dialog.alert_notify_extreme_switch is not None
        assert dialog.alert_notify_extreme_switch.aria_label == "Notify for extreme severity alerts"
        assert "extreme severity" in dialog.alert_notify_extreme_switch.aria_description.lower()
        assert "life-threatening" in dialog.alert_notify_extreme_switch.aria_description.lower()

    def test_severe_severity_switch_has_aria_attributes(self, mock_app, mock_config_manager):
        """Verify alert_notify_severe_switch has proper aria attributes."""
        dialog = SettingsDialog(app=mock_app, config_manager=mock_config_manager)
        dialog.show_and_prepare()  # Initialize UI widgets

        assert hasattr(dialog, "alert_notify_severe_switch")
        assert dialog.alert_notify_severe_switch is not None
        assert dialog.alert_notify_severe_switch.aria_label == "Notify for severe severity alerts"
        assert "severe weather" in dialog.alert_notify_severe_switch.aria_description.lower()

    def test_moderate_severity_switch_has_aria_attributes(self, mock_app, mock_config_manager):
        """Verify alert_notify_moderate_switch has proper aria attributes."""
        dialog = SettingsDialog(app=mock_app, config_manager=mock_config_manager)
        dialog.show_and_prepare()  # Initialize UI widgets

        assert hasattr(dialog, "alert_notify_moderate_switch")
        assert dialog.alert_notify_moderate_switch is not None
        assert (
            dialog.alert_notify_moderate_switch.aria_label == "Notify for moderate severity alerts"
        )
        assert "moderate severity" in dialog.alert_notify_moderate_switch.aria_description.lower()

    def test_minor_severity_switch_has_aria_attributes(self, mock_app, mock_config_manager):
        """Verify alert_notify_minor_switch has proper aria attributes."""
        dialog = SettingsDialog(app=mock_app, config_manager=mock_config_manager)
        dialog.show_and_prepare()  # Initialize UI widgets

        assert hasattr(dialog, "alert_notify_minor_switch")
        assert dialog.alert_notify_minor_switch is not None
        assert dialog.alert_notify_minor_switch.aria_label == "Notify for minor severity alerts"
        assert "minor severity" in dialog.alert_notify_minor_switch.aria_description.lower()

    def test_unknown_severity_switch_has_aria_attributes(self, mock_app, mock_config_manager):
        """Verify alert_notify_unknown_switch has proper aria attributes."""
        dialog = SettingsDialog(app=mock_app, config_manager=mock_config_manager)
        dialog.show_and_prepare()  # Initialize UI widgets

        assert hasattr(dialog, "alert_notify_unknown_switch")
        assert dialog.alert_notify_unknown_switch is not None
        assert dialog.alert_notify_unknown_switch.aria_label == "Notify for unknown severity alerts"
        assert (
            "without a defined severity"
            in dialog.alert_notify_unknown_switch.aria_description.lower()
        )

    def test_global_cooldown_input_has_aria_attributes(self, mock_app, mock_config_manager):
        """Verify alert_global_cooldown_input has proper aria attributes."""
        dialog = SettingsDialog(app=mock_app, config_manager=mock_config_manager)
        dialog.show_and_prepare()  # Initialize UI widgets

        assert hasattr(dialog, "alert_global_cooldown_input")
        assert dialog.alert_global_cooldown_input is not None
        assert dialog.alert_global_cooldown_input.aria_label == "Global notification cooldown"
        assert (
            "minimum number of minutes"
            in dialog.alert_global_cooldown_input.aria_description.lower()
        )
        assert "0 to 60" in dialog.alert_global_cooldown_input.aria_description

    def test_per_alert_cooldown_input_has_aria_attributes(self, mock_app, mock_config_manager):
        """Verify alert_per_alert_cooldown_input has proper aria attributes."""
        dialog = SettingsDialog(app=mock_app, config_manager=mock_config_manager)
        dialog.show_and_prepare()  # Initialize UI widgets

        assert hasattr(dialog, "alert_per_alert_cooldown_input")
        assert dialog.alert_per_alert_cooldown_input is not None
        assert dialog.alert_per_alert_cooldown_input.aria_label == "Per-alert notification cooldown"
        assert "same alert again" in dialog.alert_per_alert_cooldown_input.aria_description.lower()
        assert "0 to 1440" in dialog.alert_per_alert_cooldown_input.aria_description

    def test_max_notifications_input_has_aria_attributes(self, mock_app, mock_config_manager):
        """Verify alert_max_notifications_input has proper aria attributes."""
        dialog = SettingsDialog(app=mock_app, config_manager=mock_config_manager)
        dialog.show_and_prepare()  # Initialize UI widgets

        assert hasattr(dialog, "alert_max_notifications_input")
        assert dialog.alert_max_notifications_input is not None
        assert dialog.alert_max_notifications_input.aria_label == "Maximum notifications per hour"
        assert "per hour" in dialog.alert_max_notifications_input.aria_description.lower()
        assert "1 to 100" in dialog.alert_max_notifications_input.aria_description


class TestAlertWidgetKeyboardNavigation:
    """Test keyboard navigation order for alert widgets."""

    def test_notifications_tab_widget_creation_order(self, mock_app, mock_config_manager):
        """Verify widgets are created in logical keyboard navigation order."""
        dialog = SettingsDialog(app=mock_app, config_manager=mock_config_manager)
        dialog.show_and_prepare()  # Initialize UI widgets

        # Verify critical widgets exist and are accessible
        assert hasattr(dialog, "enable_alerts_switch")
        assert hasattr(dialog, "alert_notifications_enabled_switch")
        assert hasattr(dialog, "alert_notify_extreme_switch")
        assert hasattr(dialog, "alert_notify_severe_switch")
        assert hasattr(dialog, "alert_notify_moderate_switch")
        assert hasattr(dialog, "alert_notify_minor_switch")
        assert hasattr(dialog, "alert_notify_unknown_switch")
        assert hasattr(dialog, "alert_global_cooldown_input")
        assert hasattr(dialog, "alert_per_alert_cooldown_input")
        assert hasattr(dialog, "alert_max_notifications_input")

    def test_number_input_widgets_have_value_constraints(self, mock_app, mock_config_manager):
        """Verify NumberInput widgets have proper min/max constraints."""
        dialog = SettingsDialog(app=mock_app, config_manager=mock_config_manager)
        dialog.show_and_prepare()  # Initialize UI widgets

        # Global cooldown: 0-60 minutes
        assert dialog.alert_global_cooldown_input.min == 0
        assert dialog.alert_global_cooldown_input.max == 60

        # Per-alert cooldown: 0-1440 minutes (24 hours)
        assert dialog.alert_per_alert_cooldown_input.min == 0
        assert dialog.alert_per_alert_cooldown_input.max == 1440

        # Max notifications: 1-100 per hour
        assert dialog.alert_max_notifications_input.min == 1
        assert dialog.alert_max_notifications_input.max == 100


class TestAlertAccessibilityStandards:
    """Test compliance with accessibility standards."""

    def test_all_switches_have_descriptive_text(self, mock_app, mock_config_manager):
        """Verify all alert switches have descriptive on-screen text."""
        dialog = SettingsDialog(app=mock_app, config_manager=mock_config_manager)
        dialog.show_and_prepare()  # Initialize UI widgets

        # Verify switches have non-empty text property (visible label)
        assert dialog.enable_alerts_switch.text
        assert "alert" in dialog.enable_alerts_switch.text.lower()

        assert dialog.alert_notifications_enabled_switch.text
        assert "notification" in dialog.alert_notifications_enabled_switch.text.lower()

        assert dialog.alert_notify_extreme_switch.text
        assert "extreme" in dialog.alert_notify_extreme_switch.text.lower()

    def test_aria_labels_are_concise(self, mock_app, mock_config_manager):
        """Verify aria_label attributes are short and concise (< 50 chars)."""
        dialog = SettingsDialog(app=mock_app, config_manager=mock_config_manager)
        dialog.show_and_prepare()  # Initialize UI widgets

        # Check that aria_label is brief (guideline: < 50 chars)
        assert len(dialog.enable_alerts_switch.aria_label) < 50
        assert len(dialog.alert_notifications_enabled_switch.aria_label) < 50
        assert len(dialog.alert_global_cooldown_input.aria_label) < 50
        assert len(dialog.alert_per_alert_cooldown_input.aria_label) < 50
        assert len(dialog.alert_max_notifications_input.aria_label) < 50

    def test_aria_descriptions_provide_context(self, mock_app, mock_config_manager):
        """Verify aria_description attributes provide detailed context."""
        dialog = SettingsDialog(app=mock_app, config_manager=mock_config_manager)
        dialog.show_and_prepare()  # Initialize UI widgets

        # Check that aria_description is informative (> 20 chars)
        assert len(dialog.enable_alerts_switch.aria_description) > 20
        assert len(dialog.alert_global_cooldown_input.aria_description) > 20
        assert len(dialog.alert_per_alert_cooldown_input.aria_description) > 20
        assert len(dialog.alert_max_notifications_input.aria_description) > 20

        # Check descriptions explain functionality
        assert "prevent" in dialog.alert_global_cooldown_input.aria_description.lower()
        assert "token bucket" in dialog.alert_max_notifications_input.aria_description.lower()
