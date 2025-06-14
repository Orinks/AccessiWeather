"""Tests for WeatherService alert processing functionality."""

from tests.services.weather_service_test_utils import weather_service


def test_process_alerts(weather_service):
    """Test processing alerts data."""
    alerts_data = {
        "features": [
            {
                "id": "alert1",
                "properties": {
                    "headline": "Test Alert 1",
                    "description": "Description 1",
                    "instruction": "Instruction 1",
                    "severity": "Moderate",
                    "event": "Test Event 1",
                    "effective": "2024-01-01T00:00:00Z",
                    "expires": "2024-01-02T00:00:00Z",
                    "status": "Actual",
                    "messageType": "Alert",
                    "areaDesc": "Test Area 1",
                },
            },
            {
                "id": "alert2",
                "properties": {
                    "headline": "Test Alert 2",
                    "description": "Description 2",
                    "instruction": "Instruction 2",
                    "severity": "Severe",
                    "event": "Test Event 2",
                    "effective": "2024-01-01T00:00:00Z",
                    "expires": "2024-01-02T00:00:00Z",
                    "status": "Actual",
                    "messageType": "Alert",
                    "areaDesc": "Test Area 2",
                },
            },
        ]
    }

    processed_alerts, new_count, updated_count = weather_service.process_alerts(alerts_data)

    assert len(processed_alerts) == 2
    assert new_count == 2  # Both alerts are new
    assert updated_count == 0  # No alerts were updated
    assert processed_alerts[0]["headline"] == "Test Alert 1"
    assert processed_alerts[0]["severity"] == "Moderate"
    assert processed_alerts[1]["headline"] == "Test Alert 2"
    assert processed_alerts[1]["severity"] == "Severe"


def test_process_alerts_empty(weather_service):
    """Test processing empty alerts data."""
    alerts_data: dict = {"features": []}

    processed_alerts, new_count, updated_count = weather_service.process_alerts(alerts_data)

    assert len(processed_alerts) == 0
    assert new_count == 0
    assert updated_count == 0


def test_process_alerts_missing_properties(weather_service):
    """Test processing alerts data with missing properties."""
    alerts_data = {
        "features": [
            {
                "id": "alert1",
                "properties": {
                    # Missing most properties
                    "headline": "Test Alert"
                },
            }
        ]
    }

    processed_alerts, new_count, updated_count = weather_service.process_alerts(alerts_data)

    assert len(processed_alerts) == 1
    assert new_count == 1
    assert updated_count == 0
    assert processed_alerts[0]["headline"] == "Test Alert"
    # Check default values for missing properties
    assert processed_alerts[0]["description"] == "No description available"
    assert processed_alerts[0]["instruction"] == ""
    assert processed_alerts[0]["severity"] == "Unknown"
    assert processed_alerts[0]["event"] == "Unknown Event"
