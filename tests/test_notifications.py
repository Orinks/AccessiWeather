"""Tests for the notification module"""

import pytest
from unittest.mock import patch, MagicMock

from noaa_weather_app.notifications import WeatherNotifier


@pytest.fixture
def weather_notifier():
    """Create a WeatherNotifier instance"""
    return WeatherNotifier()


@pytest.fixture
def sample_alerts_data():
    """Sample alerts data for testing"""
    return {
        "features": [
            {
                "properties": {
                    "id": "test-alert-1",
                    "event": "Severe Thunderstorm Warning",
                    "headline": "Severe Thunderstorm Warning for Example County",
                    "description": "A severe thunderstorm is moving through the area",
                    "severity": "Severe",
                    "urgency": "Immediate",
                    "sent": "2025-03-12T10:00:00-04:00",
                    "effective": "2025-03-12T10:00:00-04:00",
                    "expires": "2025-03-12T11:00:00-04:00",
                    "status": "Actual",
                    "messageType": "Alert",
                    "category": "Met",
                    "response": "Shelter"
                }
            },
            {
                "properties": {
                    "id": "test-alert-2",
                    "event": "Flood Warning",
                    "headline": "Flood Warning for Example River",
                    "description": "Flooding is expected in low-lying areas",
                    "severity": "Moderate",
                    "urgency": "Expected",
                    "sent": "2025-03-12T09:00:00-04:00",
                    "effective": "2025-03-12T09:00:00-04:00",
                    "expires": "2025-03-13T09:00:00-04:00",
                    "status": "Actual",
                    "messageType": "Alert",
                    "category": "Met",
                    "response": "Execute"
                }
            }
        ]
    }


class TestWeatherNotifier:
    """Test suite for WeatherNotifier"""

    def test_init(self, weather_notifier):
        """Test initialization"""
        assert weather_notifier.active_alerts == {}
        assert weather_notifier.toaster is not None

    def test_process_alerts(self, weather_notifier, sample_alerts_data):
        """Test alert processing"""
        with patch.object(weather_notifier, 'show_notification') as mock_show:
            processed = weather_notifier.process_alerts(sample_alerts_data)
            
            # Check that we processed both alerts
            assert len(processed) == 2
            assert processed[0]["id"] == "test-alert-1"
            assert processed[1]["id"] == "test-alert-2"
            
            # Check that notifications were shown
            assert mock_show.call_count == 2
            
            # Check that active alerts were updated
            assert len(weather_notifier.active_alerts) == 2
            assert "test-alert-1" in weather_notifier.active_alerts
            assert "test-alert-2" in weather_notifier.active_alerts

    @patch('noaa_weather_app.notifications.ToastNotifier.show_toast')
    def test_show_notification(self, mock_toast, weather_notifier):
        """Test showing a notification"""
        alert = {
            "id": "test-alert",
            "event": "Tornado Warning",
            "headline": "Tornado Warning for Test County"
        }
        
        weather_notifier.show_notification(alert)
        
        # Check that the toast was shown
        mock_toast.assert_called_once()
        args, kwargs = mock_toast.call_args
        
        # Check the arguments
        assert kwargs["title"] == "Weather Tornado Warning"
        assert kwargs["msg"] == "Tornado Warning for Test County"
        assert kwargs["threaded"] is True

    def test_clear_expired_alerts(self, weather_notifier, sample_alerts_data):
        """Test clearing expired alerts"""
        # First add some alerts
        weather_notifier.process_alerts(sample_alerts_data)
        assert len(weather_notifier.active_alerts) == 2
        
        # Clear them
        weather_notifier.clear_expired_alerts()
        assert len(weather_notifier.active_alerts) == 0

    def test_get_sorted_alerts(self, weather_notifier, sample_alerts_data):
        """Test getting alerts sorted by priority"""
        # Add alerts
        weather_notifier.process_alerts(sample_alerts_data)
        
        # Get sorted alerts
        sorted_alerts = weather_notifier.get_sorted_alerts()
        
        # Should be sorted with Severe first, then Moderate
        assert len(sorted_alerts) == 2
        assert sorted_alerts[0]["severity"] == "Severe"
        assert sorted_alerts[1]["severity"] == "Moderate"
