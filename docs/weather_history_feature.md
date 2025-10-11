# Weather History Tracker Feature

## Overview

The Weather History Tracker feature allows AccessiWeather to track and compare weather conditions over time. Users can see how today's weather compares to yesterday or last week, providing valuable context and insights.

## Features

### Automatic History Tracking
- **Daily Snapshots**: Automatically records weather conditions at each update
- **Persistent Storage**: Saves history to a JSON file for retrieval across sessions
- **Configurable Retention**: Keeps history for a configurable number of days (default: 30 days)
- **Automatic Cleanup**: Removes old entries beyond the retention period

### Weather Comparison
- **Yesterday Comparison**: Compare current weather with yesterday's conditions
- **Last Week Comparison**: Compare current weather with conditions from 7 days ago
- **Detailed Insights**: Shows temperature differences, condition changes, humidity changes, and wind speed changes
- **Accessible Summaries**: Screen-reader friendly summaries of weather changes

### Accessibility

The feature is designed with accessibility as a priority:
- **Screen Reader Friendly**: All comparisons generate human-readable summaries
- **Clear Language**: Uses natural language like "5 degrees warmer than yesterday"
- **Contextual Information**: Provides relevant time references ("yesterday", "last week", "5 days ago")

## Configuration

The feature can be configured through `AppSettings`:

```python
from accessiweather.models import AppSettings

settings = AppSettings(
    weather_history_enabled=True,           # Enable/disable history tracking
    weather_history_retention_days=30,      # Days to keep history (default: 30)
)
```

### Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `weather_history_enabled` | bool | True | Enable or disable weather history tracking |
| `weather_history_retention_days` | int | 30 | Number of days to retain weather history |

## Usage

### Basic Usage

```python
from accessiweather.weather_history import WeatherHistoryTracker
from accessiweather.models import Location, CurrentConditions

# Initialize tracker
tracker = WeatherHistoryTracker(
    history_file="/path/to/weather_history.json",
    max_days=30
)

# Create location and conditions
location = Location(
    name="New York",
    latitude=40.7128,
    longitude=-74.0060,
    timezone="America/New_York"
)

conditions = CurrentConditions(
    temperature=75.0,
    condition="Sunny",
    humidity=60,
    wind_speed=10.0,
    wind_direction="NW",
    pressure=30.1
)

# Add current weather to history
tracker.add_entry(location=location, conditions=conditions)

# Save history
tracker.save()
```

### Comparing Weather

```python
# Compare with yesterday
comparison = tracker.get_comparison_for_yesterday("New York", current_conditions)

if comparison:
    print(f"Temperature: {comparison.temperature_description}")
    print(f"Condition changed: {comparison.condition_changed}")
    
    # Get accessible summary
    summary = comparison.get_accessible_summary()
    print(summary)
    # Output: "Compared to yesterday: 5.0 degrees warmer. Changed from Cloudy to Sunny."

# Compare with last week
week_comparison = tracker.get_comparison_for_last_week("New York", current_conditions)
```

### Custom Comparisons

```python
from datetime import datetime, timedelta

# Get entry for a specific day
target_date = (datetime.now() - timedelta(days=3)).date()
entry = tracker.get_entry_for_location_and_day("New York", target_date)

if entry:
    # Create custom comparison
    from accessiweather.weather_history import WeatherComparison
    comparison = WeatherComparison.compare(current_conditions, entry)
```

## Data Model

### WeatherHistoryEntry

Represents a single weather observation:

```python
@dataclass
class WeatherHistoryEntry:
    location_name: str
    temperature: float
    condition: str
    humidity: int
    wind_speed: float
    wind_direction: str
    pressure: float
    timestamp: datetime
```

### WeatherComparison

Contains comparison results:

```python
@dataclass
class WeatherComparison:
    temperature_difference: float       # Temperature change in degrees
    temperature_description: str        # Human-readable description
    condition_changed: bool            # Whether condition changed
    previous_condition: str            # Previous weather condition
    condition_description: str | None  # Description of condition change
    humidity_difference: int           # Humidity change in percent
    wind_speed_difference: float       # Wind speed change
    days_ago: int                      # Days since comparison point
```

## Storage Format

Weather history is stored in JSON format:

```json
{
  "version": "1.0",
  "entries": [
    {
      "location_name": "New York",
      "temperature": 75.0,
      "condition": "Sunny",
      "humidity": 60,
      "wind_speed": 10.0,
      "wind_direction": "NW",
      "pressure": 30.1,
      "timestamp": "2025-01-10T12:00:00"
    }
  ]
}
```

## Implementation Details

### Architecture

The feature consists of three main classes:

1. **WeatherHistoryEntry**: Data model for a single weather observation
2. **WeatherHistoryTracker**: Manages storage, retrieval, and cleanup of history
3. **WeatherComparison**: Handles comparison logic and generates summaries

### Design Decisions

- **JSON Storage**: Simple, human-readable format for easy debugging and portability
- **Automatic Cleanup**: Prevents unbounded growth of history files
- **Timezone Aware**: Uses Python's datetime for proper timezone handling
- **Type Safety**: Uses dataclasses with type hints for better IDE support

### Integration Points

The feature integrates with:
- **AppSettings**: Configuration management
- **Location**: Location data model
- **CurrentConditions**: Weather data model
- **ConfigManager**: Settings persistence (through AppSettings)

## Testing

The feature includes comprehensive tests:

### Unit Tests (`test_weather_history.py`)
- Entry creation and serialization
- Tracker initialization and basic operations
- Comparison logic and summaries
- Cleanup of old entries

### Integration Tests (`test_weather_history_integration.py`)
- Full workflow: add, save, load, compare
- Multi-location tracking
- Automatic cleanup on load
- Convenience methods

### Running Tests

```bash
# Run all weather history tests
pytest tests/test_weather_history.py -v
pytest tests/test_weather_history_integration.py -v

# Run with coverage
pytest tests/test_weather_history*.py --cov=accessiweather.weather_history
```

## Future Enhancements

Potential improvements for future versions:

1. **Graphing**: Visual representation of temperature trends
2. **Statistics**: Calculate averages, highs, lows over time
3. **Anomaly Detection**: Alert users to unusual weather patterns
4. **Export**: Export history to CSV or other formats
5. **Cloud Sync**: Optional cloud backup of weather history
6. **Hourly Tracking**: Track weather at hourly intervals instead of just daily
7. **Comparison Presets**: Quick access to common comparisons (yesterday, last week, same day last month)

## Accessibility Considerations

The feature was designed with accessibility in mind:

- **Natural Language**: Uses plain English descriptions
- **Context**: Always provides time context ("yesterday", "5 days ago")
- **Conciseness**: Summaries are brief but informative
- **Significance Threshold**: Only mentions significant changes (e.g., humidity ≥10%, wind ≥5mph)
- **Consistent Format**: Predictable structure for screen reader users

## Troubleshooting

### History Not Saving

Check that:
- The history file path is writable
- The parent directory exists
- There's sufficient disk space

### Old Entries Not Cleaned Up

Ensure that:
- `cleanup_old_entries()` is called after loading
- The `max_days` setting is correct
- The system clock is accurate

### Comparison Returns None

This happens when:
- No history exists for the requested date
- The location name doesn't match exactly
- The entry was cleaned up due to age

## License

This feature is part of AccessiWeather and is licensed under the MIT License.
