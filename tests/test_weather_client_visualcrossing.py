"""Tests for Visual Crossing alert processing."""

import os
import tempfile
from unittest.mock import AsyncMock, Mock, patch

import pytest

from accessiweather.models import Location, WeatherAlert, WeatherAlerts
from accessiweather.weather_client_visualcrossing import process_visual_crossing_alerts


@pytest.fixture
def sample_location():
    """Create a sample location."""
    return Location(name="New York", latitude=40.7128, longitude=-74.0060)


@pytest.fixture
def sample_alerts():
    """Create sample weather alerts."""
    alerts = [
        WeatherAlert(
            title="Severe Thunderstorm Warning",
            description="A severe thunderstorm warning has been issued",
            event="Severe Thunderstorm Warning",
            severity="Severe",
            headline="Severe Thunderstorm Warning in effect",
        ),
        WeatherAlert(
            title="Flash Flood Watch",
            description="A flash flood watch has been issued",
            event="Flash Flood Watch",
            severity="Moderate",
            headline="Flash Flood Watch in effect",
        ),
    ]
    return WeatherAlerts(alerts=alerts)


@pytest.fixture
def empty_alerts():
    """Create empty weather alerts."""
    return WeatherAlerts(alerts=[])


class TestProcessVisualCrossingAlerts:
    """Test process_visual_crossing_alerts function."""

    @pytest.mark.asyncio
    async def test_process_alerts_success(self, sample_location, sample_alerts):
        """Test successfully processing alerts."""
        with (
            patch(
                "accessiweather.weather_client_visualcrossing.AlertManager"
            ) as mock_alert_manager_class,
            patch(
                "accessiweather.weather_client_visualcrossing.AlertNotificationSystem"
            ) as mock_notification_system_class,
        ):
            mock_alert_manager = Mock()
            mock_alert_manager_class.return_value = mock_alert_manager

            mock_notification_system = Mock()
            mock_notification_system.get_settings.return_value = Mock(
                notifications_enabled=True, min_severity_priority=1
            )
            mock_notification_system.process_and_notify = AsyncMock(return_value=2)
            mock_notification_system_class.return_value = mock_notification_system

            await process_visual_crossing_alerts(sample_alerts, sample_location)

            mock_notification_system.process_and_notify.assert_called_once_with(sample_alerts)

    @pytest.mark.asyncio
    async def test_process_empty_alerts(self, sample_location, empty_alerts):
        """Test processing when there are no alerts."""
        with (
            patch(
                "accessiweather.weather_client_visualcrossing.AlertManager"
            ) as mock_alert_manager_class,
            patch(
                "accessiweather.weather_client_visualcrossing.AlertNotificationSystem"
            ) as mock_notification_system_class,
        ):
            mock_alert_manager = Mock()
            mock_alert_manager_class.return_value = mock_alert_manager

            mock_notification_system = Mock()
            mock_notification_system.get_settings.return_value = Mock(
                notifications_enabled=True, min_severity_priority=1
            )
            mock_notification_system.process_and_notify = AsyncMock(return_value=0)
            mock_notification_system.get_statistics.return_value = {"total": 0, "sent": 0}
            mock_notification_system_class.return_value = mock_notification_system

            await process_visual_crossing_alerts(empty_alerts, sample_location)

            mock_notification_system.process_and_notify.assert_called_once_with(empty_alerts)
            mock_notification_system.get_statistics.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_alerts_no_notifications_sent(self, sample_location, sample_alerts):
        """Test processing when no notifications are sent."""
        with (
            patch(
                "accessiweather.weather_client_visualcrossing.AlertManager"
            ) as mock_alert_manager_class,
            patch(
                "accessiweather.weather_client_visualcrossing.AlertNotificationSystem"
            ) as mock_notification_system_class,
        ):
            mock_alert_manager = Mock()
            mock_alert_manager_class.return_value = mock_alert_manager

            mock_notification_system = Mock()
            mock_notification_system.get_settings.return_value = Mock(
                notifications_enabled=True, min_severity_priority=1
            )
            mock_notification_system.process_and_notify = AsyncMock(return_value=0)
            mock_notification_system.get_statistics.return_value = {
                "total": 2,
                "sent": 0,
                "filtered": 2,
            }
            mock_notification_system_class.return_value = mock_notification_system

            await process_visual_crossing_alerts(sample_alerts, sample_location)

            mock_notification_system.get_statistics.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_alerts_exception_handling(self, sample_location, sample_alerts):
        """Test exception handling during alert processing."""
        with patch(
            "accessiweather.weather_client_visualcrossing.AlertManager"
        ) as mock_alert_manager_class:
            mock_alert_manager_class.side_effect = Exception("Alert manager initialization failed")

            # Should not raise exception
            await process_visual_crossing_alerts(sample_alerts, sample_location)

    @pytest.mark.asyncio
    async def test_process_alerts_notification_error(self, sample_location, sample_alerts):
        """Test handling notification errors."""
        with (
            patch(
                "accessiweather.weather_client_visualcrossing.AlertManager"
            ) as mock_alert_manager_class,
            patch(
                "accessiweather.weather_client_visualcrossing.AlertNotificationSystem"
            ) as mock_notification_system_class,
        ):
            mock_alert_manager = Mock()
            mock_alert_manager_class.return_value = mock_alert_manager

            mock_notification_system = Mock()
            mock_notification_system.get_settings.return_value = Mock(
                notifications_enabled=True, min_severity_priority=1
            )
            mock_notification_system.process_and_notify = AsyncMock(
                side_effect=Exception("Notification failed")
            )
            mock_notification_system_class.return_value = mock_notification_system

            # Should not raise exception
            await process_visual_crossing_alerts(sample_alerts, sample_location)

    @pytest.mark.asyncio
    async def test_process_alerts_creates_temp_config_dir(self, sample_location, sample_alerts):
        """Test that alert processing uses temp directory for config."""
        with (
            patch(
                "accessiweather.weather_client_visualcrossing.AlertManager"
            ) as mock_alert_manager_class,
            patch(
                "accessiweather.weather_client_visualcrossing.AlertNotificationSystem"
            ) as mock_notification_system_class,
        ):
            mock_alert_manager = Mock()
            mock_alert_manager_class.return_value = mock_alert_manager

            mock_notification_system = Mock()
            mock_notification_system.get_settings.return_value = Mock(
                notifications_enabled=True, min_severity_priority=1
            )
            mock_notification_system.process_and_notify = AsyncMock(return_value=1)
            mock_notification_system_class.return_value = mock_notification_system

            await process_visual_crossing_alerts(sample_alerts, sample_location)

            expected_config_dir = os.path.join(tempfile.gettempdir(), "accessiweather_alerts")
            mock_alert_manager_class.assert_called_once()
            args = mock_alert_manager_class.call_args[0]
            assert args[0] == expected_config_dir

    @pytest.mark.asyncio
    async def test_process_alerts_uses_correct_settings(self, sample_location, sample_alerts):
        """Test that alert processing uses correct settings."""
        with (
            patch(
                "accessiweather.weather_client_visualcrossing.AlertManager"
            ) as mock_alert_manager_class,
            patch(
                "accessiweather.weather_client_visualcrossing.AlertNotificationSystem"
            ) as mock_notification_system_class,
        ):
            mock_alert_manager = Mock()
            mock_alert_manager_class.return_value = mock_alert_manager

            mock_notification_system = Mock()
            mock_notification_system.get_settings.return_value = Mock(
                notifications_enabled=True, min_severity_priority=1
            )
            mock_notification_system.process_and_notify = AsyncMock(return_value=1)
            mock_notification_system_class.return_value = mock_notification_system

            await process_visual_crossing_alerts(sample_alerts, sample_location)

            args = mock_alert_manager_class.call_args[0]
            settings = args[1]
            assert settings.min_severity_priority == 1
            assert settings.notifications_enabled is True

    @pytest.mark.asyncio
    async def test_process_alerts_logs_location_info(self, sample_location, sample_alerts, caplog):
        """Test that location info is logged."""
        import logging

        caplog.set_level(logging.INFO)

        with (
            patch(
                "accessiweather.weather_client_visualcrossing.AlertManager"
            ) as mock_alert_manager_class,
            patch(
                "accessiweather.weather_client_visualcrossing.AlertNotificationSystem"
            ) as mock_notification_system_class,
        ):
            mock_alert_manager = Mock()
            mock_alert_manager_class.return_value = mock_alert_manager

            mock_notification_system = Mock()
            mock_notification_system.get_settings.return_value = Mock(
                notifications_enabled=True, min_severity_priority=1
            )
            mock_notification_system.process_and_notify = AsyncMock(return_value=2)
            mock_notification_system_class.return_value = mock_notification_system

            await process_visual_crossing_alerts(sample_alerts, sample_location)

            assert f"Processing Visual Crossing alerts for {sample_location.name}" in caplog.text
            assert "Sent 2 Visual Crossing alert notifications" in caplog.text

    @pytest.mark.asyncio
    async def test_process_alerts_logs_individual_alerts(
        self, sample_location, sample_alerts, caplog
    ):
        """Test that individual alerts are logged."""
        import logging

        caplog.set_level(logging.INFO)

        with (
            patch(
                "accessiweather.weather_client_visualcrossing.AlertManager"
            ) as mock_alert_manager_class,
            patch(
                "accessiweather.weather_client_visualcrossing.AlertNotificationSystem"
            ) as mock_notification_system_class,
        ):
            mock_alert_manager = Mock()
            mock_alert_manager_class.return_value = mock_alert_manager

            mock_notification_system = Mock()
            mock_notification_system.get_settings.return_value = Mock(
                notifications_enabled=True, min_severity_priority=1
            )
            mock_notification_system.process_and_notify = AsyncMock(return_value=0)
            mock_notification_system.get_statistics.return_value = {}
            mock_notification_system_class.return_value = mock_notification_system

            await process_visual_crossing_alerts(sample_alerts, sample_location)

            assert "Alert 1: Severe Thunderstorm Warning - Severe" in caplog.text
            assert "Alert 2: Flash Flood Watch - Moderate" in caplog.text

    @pytest.mark.asyncio
    async def test_process_alerts_logs_notification_settings(
        self, sample_location, sample_alerts, caplog
    ):
        """Test that notification settings are logged."""
        import logging

        caplog.set_level(logging.INFO)

        with (
            patch(
                "accessiweather.weather_client_visualcrossing.AlertManager"
            ) as mock_alert_manager_class,
            patch(
                "accessiweather.weather_client_visualcrossing.AlertNotificationSystem"
            ) as mock_notification_system_class,
        ):
            mock_alert_manager = Mock()
            mock_alert_manager_class.return_value = mock_alert_manager

            mock_notification_system = Mock()
            mock_notification_system.get_settings.return_value = Mock(
                notifications_enabled=False, min_severity_priority=3
            )
            mock_notification_system.process_and_notify = AsyncMock(return_value=0)
            mock_notification_system.get_statistics.return_value = {}
            mock_notification_system_class.return_value = mock_notification_system

            await process_visual_crossing_alerts(sample_alerts, sample_location)

            assert "Notification settings - enabled: False" in caplog.text
            assert "min_severity: 3" in caplog.text
