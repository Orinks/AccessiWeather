# Visual Crossing Alerts Solution

## Problem Analysis

Visual Crossing weather alerts were not being sent as notifications because:

1. **Missing Notification Pipeline**: Visual Crossing alerts were fetched but not processed through the notification system
2. **Different Processing Path**: NWS alerts go through `WeatherService.get_alerts()` which includes notification processing, but Visual Crossing alerts bypassed this
3. **Alert Format Differences**: Visual Crossing may return alerts in different structures than expected
4. **Incomplete Alert Parsing**: The original parsing was basic and missed important alert fields

## Solution Implementation

### 1. Enhanced Weather Client Integration

**File**: `src/accessiweather/simple/weather_client.py`

Added notification processing for Visual Crossing alerts:
```python
# Process alerts for notifications if we have any
if alerts and alerts.has_alerts():
    logger.info(f"Processing {len(alerts.alerts)} Visual Crossing alerts for notifications")
    await self._process_visual_crossing_alerts(alerts, location)
```

Added new method to handle Visual Crossing alert notifications:
```python
async def _process_visual_crossing_alerts(self, alerts: WeatherAlerts, location: Location):
    """Process Visual Crossing alerts for notifications."""
    try:
        # Import the alert notification system
        from .alert_notification_system import AlertNotificationSystem
        from .alert_manager import AlertManager

        # Create alert manager and notification system
        alert_manager = AlertManager()
        notification_system = AlertNotificationSystem(alert_manager)

        # Process and send notifications
        notifications_sent = await notification_system.process_and_notify(alerts)

        if notifications_sent > 0:
            logger.info(f"Sent {notifications_sent} Visual Crossing alert notifications for {location.name}")
        else:
            logger.debug(f"No Visual Crossing alert notifications sent for {location.name}")

    except Exception as e:
        logger.error(f"Failed to process Visual Crossing alerts for notifications: {e}")
```

### 2. Improved Visual Crossing Alert Parsing

**File**: `src/accessiweather/simple/visual_crossing_client.py`

Enhanced the `_parse_alerts` method to:
- Check multiple possible locations for alert data (top-level, nested in days, current conditions)
- Better field mapping with fallbacks
- Proper severity level mapping
- Time parsing for onset/expires
- Unique ID generation
- Better debugging information

Key improvements:
```python
def _parse_alerts(self, data: dict) -> WeatherAlerts:
    """Parse Visual Crossing alerts data."""
    alerts = []

    # Visual Crossing may return alerts in different structures
    # Check multiple possible locations for alert data
    alert_data_list = []

    # Check top-level alerts
    if "alerts" in data:
        alert_data_list.extend(data["alerts"])

    # Check if alerts are nested in days
    if "days" in data:
        for day in data["days"]:
            if "alerts" in day:
                alert_data_list.extend(day["alerts"])

    # Check current conditions for alerts
    if "currentConditions" in data and "alerts" in data["currentConditions"]:
        alert_data_list.extend(data["currentConditions"]["alerts"])

    logger.debug(f"Found {len(alert_data_list)} alert(s) in Visual Crossing response")

    # Process each alert with enhanced field mapping...
```

Added severity mapping:
```python
def _map_visual_crossing_severity(self, vc_severity: str | None) -> str:
    """Map Visual Crossing severity to standard severity levels."""
    severity_map = {
        "extreme": "Extreme",
        "severe": "Severe",
        "moderate": "Moderate",
        "minor": "Minor",
        "unknown": "Unknown",
        # Additional mappings for Visual Crossing specific terms
        "high": "Severe",
        "medium": "Moderate",
        "low": "Minor",
        "critical": "Extreme",
        "warning": "Severe",
        "watch": "Moderate",
        "advisory": "Minor",
    }
    return severity_map.get(vc_severity.lower(), "Unknown")
```

### 3. Debug and Testing Tools

**File**: `debug_visual_crossing_alerts.py`

Created comprehensive debugging script that tests:
1. Direct Visual Crossing API calls
2. Weather client integration
3. Notification system processing
4. Manual notification testing
5. Comparison between NWS and Visual Crossing alerts

## Usage Instructions

### 1. Set Up Visual Crossing API Key

```bash
# Set environment variable
export VISUAL_CROSSING_API_KEY="your_api_key_here"

# Or configure in AccessiWeather settings
```

### 2. Configure Data Source

In AccessiWeather settings, set data source to "Visual Crossing" and enter your API key.

### 3. Test the Implementation

Run the debug script:
```bash
python debug_visual_crossing_alerts.py
```

Choose option 1 for end-to-end testing or option 2 for comparing alert sources.

### 4. Monitor Logs

Enable debug logging to see detailed information:
```python
import logging
logging.getLogger('accessiweather.simple.visual_crossing_client').setLevel(logging.DEBUG)
logging.getLogger('accessiweather.simple.weather_client').setLevel(logging.DEBUG)
```

## Visual Crossing Alert Capabilities

Based on the API documentation, Visual Crossing supports:

- **Alert Types**: Weather warnings, watches, advisories
- **Geographic Coverage**: Global (unlike NWS which is US-only)
- **Alert Fields**: Event type, severity, headline, description, affected areas, timing
- **API Parameter**: Use `include=alerts` to fetch alert data

## Potential Issues and Solutions

### 1. No Alerts Found
**Cause**: Visual Crossing may not have alerts for all locations
**Solution**: The debug script tests multiple locations known to have frequent alerts

### 2. Different Alert Structure
**Cause**: Visual Crossing may structure alerts differently than expected
**Solution**: Enhanced parsing checks multiple possible locations in the response

### 3. Notification Settings
**Cause**: Alert notification settings may filter out Visual Crossing alerts
**Solution**: Check notification preferences and severity thresholds

### 4. API Rate Limits
**Cause**: Visual Crossing has API rate limits
**Solution**: Implement proper error handling and respect rate limits

## Testing Locations

The debug script tests these locations known for frequent weather alerts:
- Miami, FL (hurricanes, thunderstorms)
- Oklahoma City, OK (tornadoes, severe weather)
- Denver, CO (winter weather, high wind)
- Phoenix, AZ (heat warnings, dust storms)

## Next Steps

1. **Run the debug script** to verify the implementation works
2. **Test with your specific locations** to ensure alerts are relevant
3. **Monitor notification behavior** during actual weather events
4. **Adjust notification settings** if needed for Visual Crossing alerts
5. **Consider fallback logic** if Visual Crossing doesn't have alerts for certain areas

## API Documentation Reference

Visual Crossing Timeline Weather API:
- Base URL: `https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/`
- Alert Parameter: `include=alerts`
- Documentation: https://www.visualcrossing.com/resources/documentation/weather-api/timeline-weather-api/

## Troubleshooting

If alerts still aren't working:

1. **Check API Key**: Ensure your Visual Crossing API key is valid and has sufficient quota
2. **Verify Location**: Some locations may not have active alerts
3. **Check Logs**: Look for error messages in the application logs
4. **Test Manually**: Use the debug script to isolate issues
5. **Compare with NWS**: For US locations, compare Visual Crossing alerts with NWS alerts
6. **Notification Settings**: Verify that notification preferences allow the alert severity levels

The implementation now provides a complete pipeline from Visual Crossing API → Alert Parsing → Notification System → Desktop Notifications, matching the behavior of NWS alerts.
