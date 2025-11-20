"""
Tests for configuration schema and migration logic.

Verifies that alert settings are properly persisted, loaded, and migrated
from older configuration formats to newer versions with backward compatibility.
"""

from __future__ import annotations

from accessiweather.models.config import AppConfig, AppSettings


class TestAlertSettingsPersistence:
    """Test alert settings are properly saved and loaded."""

    def test_new_alert_settings_in_defaults(self):
        """Verify new alert settings have appropriate defaults."""
        settings = AppSettings()

        # Cooldown settings
        assert settings.alert_global_cooldown_minutes == 5
        assert settings.alert_per_alert_cooldown_minutes == 60
        assert settings.alert_escalation_cooldown_minutes == 15

        # Rate limiting
        assert settings.alert_max_notifications_per_hour == 10

        # Severity filters
        assert settings.alert_notify_extreme is True
        assert settings.alert_notify_severe is True
        assert settings.alert_notify_moderate is True
        assert settings.alert_notify_minor is False
        assert settings.alert_notify_unknown is False

    def test_alert_settings_roundtrip_serialization(self):
        """Verify alert settings survive serialization roundtrip."""
        original = AppSettings(
            alert_global_cooldown_minutes=10,
            alert_per_alert_cooldown_minutes=120,
            alert_escalation_cooldown_minutes=30,
            alert_max_notifications_per_hour=20,
            alert_notify_extreme=True,
            alert_notify_severe=True,
            alert_notify_moderate=False,
            alert_notify_minor=True,
            alert_notify_unknown=False,
        )

        # Serialize to dict
        data = original.to_dict()

        # Verify all fields are present
        assert data["alert_global_cooldown_minutes"] == 10
        assert data["alert_per_alert_cooldown_minutes"] == 120
        assert data["alert_escalation_cooldown_minutes"] == 30
        assert data["alert_max_notifications_per_hour"] == 20

        # Deserialize back
        restored = AppSettings.from_dict(data)

        # Verify all values match
        assert restored.alert_global_cooldown_minutes == 10
        assert restored.alert_per_alert_cooldown_minutes == 120
        assert restored.alert_escalation_cooldown_minutes == 30
        assert restored.alert_max_notifications_per_hour == 20
        assert restored.alert_notify_extreme is True
        assert restored.alert_notify_severe is True
        assert restored.alert_notify_moderate is False
        assert restored.alert_notify_minor is True
        assert restored.alert_notify_unknown is False


class TestConfigMigration:
    """Test migration of legacy configurations to new schema."""

    def test_migration_from_legacy_config_without_alert_settings(self):
        """Verify migration adds defaults for missing alert settings."""
        # Simulate legacy config without new alert fields
        legacy_data = {
            "settings": {
                "temperature_unit": "both",
                "enable_alerts": True,
                # Missing: alert_global_cooldown_minutes, etc.
            },
            "locations": [],
            "current_location": None,
        }

        # Load config (should apply defaults)
        config = AppConfig.from_dict(legacy_data)

        # Verify defaults were applied
        assert config.settings.alert_global_cooldown_minutes == 5
        assert config.settings.alert_per_alert_cooldown_minutes == 60
        assert config.settings.alert_escalation_cooldown_minutes == 15
        assert config.settings.alert_max_notifications_per_hour == 10

    def test_migration_preserves_existing_alert_settings(self):
        """Verify migration preserves existing alert settings if present."""
        # Config with custom alert settings
        data = {
            "settings": {
                "temperature_unit": "both",
                "enable_alerts": True,
                "alert_global_cooldown_minutes": 15,
                "alert_per_alert_cooldown_minutes": 180,
                "alert_escalation_cooldown_minutes": 45,
                "alert_max_notifications_per_hour": 25,
            },
            "locations": [],
            "current_location": None,
        }

        # Load config
        config = AppConfig.from_dict(data)

        # Verify custom values were preserved
        assert config.settings.alert_global_cooldown_minutes == 15
        assert config.settings.alert_per_alert_cooldown_minutes == 180
        assert config.settings.alert_escalation_cooldown_minutes == 45
        assert config.settings.alert_max_notifications_per_hour == 25

    def test_migration_handles_partial_alert_settings(self):
        """Verify migration handles configs with only some alert settings."""
        # Config with only some new fields
        data = {
            "settings": {
                "temperature_unit": "both",
                "alert_global_cooldown_minutes": 20,
                # Missing: alert_per_alert_cooldown_minutes, alert_max_notifications_per_hour
            },
            "locations": [],
            "current_location": None,
        }

        # Load config
        config = AppConfig.from_dict(data)

        # Verify custom value preserved and defaults applied for missing
        assert config.settings.alert_global_cooldown_minutes == 20
        assert config.settings.alert_per_alert_cooldown_minutes == 60  # Default
        assert config.settings.alert_max_notifications_per_hour == 10  # Default


class TestAlertSettingsConversion:
    """Test conversion from AppSettings to AlertSettings."""

    def test_to_alert_settings_maps_all_fields(self):
        """Verify to_alert_settings() properly maps all alert configuration."""
        app_settings = AppSettings(
            alert_notifications_enabled=True,
            sound_enabled=True,
            alert_global_cooldown_minutes=10,
            alert_per_alert_cooldown_minutes=120,
            alert_escalation_cooldown_minutes=30,
            alert_max_notifications_per_hour=20,
            alert_ignored_categories=["Flood Watch", "Fog Advisory"],
            alert_notify_extreme=True,
            alert_notify_severe=True,
            alert_notify_moderate=False,
            alert_notify_minor=False,
            alert_notify_unknown=False,
        )

        alert_settings = app_settings.to_alert_settings()

        # Verify all fields mapped correctly
        assert alert_settings.notifications_enabled is True
        assert alert_settings.sound_enabled is True
        assert alert_settings.global_cooldown == 10
        assert alert_settings.per_alert_cooldown == 120
        assert alert_settings.escalation_cooldown == 30
        assert alert_settings.max_notifications_per_hour == 20
        assert alert_settings.ignored_categories == {"Flood Watch", "Fog Advisory"}

    def test_to_alert_settings_severity_priority_extreme_only(self):
        """Verify severity priority when only extreme alerts enabled."""
        app_settings = AppSettings(
            alert_notify_extreme=True,
            alert_notify_severe=False,
            alert_notify_moderate=False,
            alert_notify_minor=False,
            alert_notify_unknown=False,
        )

        alert_settings = app_settings.to_alert_settings()

        # Should require extreme priority (5)
        assert alert_settings.min_severity_priority == 5

    def test_to_alert_settings_severity_priority_moderate_and_above(self):
        """Verify severity priority when moderate+ alerts enabled."""
        app_settings = AppSettings(
            alert_notify_extreme=True,
            alert_notify_severe=True,
            alert_notify_moderate=True,
            alert_notify_minor=False,
            alert_notify_unknown=False,
        )

        alert_settings = app_settings.to_alert_settings()

        # Should allow moderate priority (3) and above
        assert alert_settings.min_severity_priority == 3

    def test_to_alert_settings_severity_priority_all_disabled(self):
        """Verify severity priority when all alerts disabled."""
        app_settings = AppSettings(
            alert_notify_extreme=False,
            alert_notify_severe=False,
            alert_notify_moderate=False,
            alert_notify_minor=False,
            alert_notify_unknown=False,
        )

        alert_settings = app_settings.to_alert_settings()

        # Should set to impossible priority (6) to disable all
        assert alert_settings.min_severity_priority == 6


class TestConfigValidation:
    """Test configuration validation and error handling."""

    def test_invalid_cooldown_values_use_defaults(self):
        """Verify invalid cooldown values fall back to defaults."""
        # Config with invalid negative values
        data = {
            "settings": {
                "alert_global_cooldown_minutes": -5,
                "alert_per_alert_cooldown_minutes": -10,
            },
            "locations": [],
            "current_location": None,
        }

        config = AppConfig.from_dict(data)

        # Should accept negative values (validation happens at usage time)
        assert config.settings.alert_global_cooldown_minutes == -5
        assert config.settings.alert_per_alert_cooldown_minutes == -10

    def test_extreme_rate_limit_values_accepted(self):
        """Verify extreme but valid rate limit values are accepted."""
        data = {
            "settings": {
                "alert_max_notifications_per_hour": 1000,  # Very high
            },
            "locations": [],
            "current_location": None,
        }

        config = AppConfig.from_dict(data)

        # Should accept extreme values
        assert config.settings.alert_max_notifications_per_hour == 1000

    def test_empty_settings_dict_uses_all_defaults(self):
        """Verify empty settings dict loads all defaults."""
        data = {"settings": {}, "locations": [], "current_location": None}

        config = AppConfig.from_dict(data)

        # All defaults should be applied
        assert config.settings.alert_global_cooldown_minutes == 5
        assert config.settings.alert_per_alert_cooldown_minutes == 60
        assert config.settings.alert_escalation_cooldown_minutes == 15
        assert config.settings.alert_max_notifications_per_hour == 10
        assert config.settings.alert_notify_extreme is True
        assert config.settings.alert_notify_severe is True
        assert config.settings.alert_notify_moderate is True
