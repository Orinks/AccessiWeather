# Weather History Comparison Feature

## Overview

The Weather History Comparison feature allows AccessiWeather to compare current weather conditions with historical data using Open-Meteo's archive API. This provides users with context about how today's weather compares to past days without requiring local storage or background recording.

## Key Features

### API-Based Historical Data
- **Open-Meteo Archive API**: Leverages Open-Meteo's robust historical weather endpoint
- **Decades of Data**: Access historical weather data going back many years
- **No Local Storage**: No JSON files, databases, or cleanup required
- **Instant Access**: Works immediately for all users without prior setup

### Weather Comparison
- **Yesterday Comparison**: Compare current weather with yesterday's conditions
- **Last Week Comparison**: Compare with weather from 7 days ago
- **Custom Date**: Compare with any specific date in the past
- **Accessible Summaries**: Screen-reader friendly natural language descriptions

### Accessibility

The feature was designed with accessibility as a priority:
- **Natural Language**: Uses plain English descriptions
- **Clear Context**: Always provides time references ("yesterday", "last week", "5 days ago")
- **Concise**: Brief but informative summaries
- **Screen Reader Optimized**: Designed for optimal screen reader experience

## Architecture

### Components

1. **HistoricalWeatherData**: Data model for historical weather snapshots
2. **WeatherComparison**: Comparison logic and accessible summary generation
3. **WeatherHistoryService**: Service for fetching historical data and making comparisons

### How It Works

```
Current Weather + Open-Meteo Archive API → Historical Data → Comparison → Accessible Summary
```

The service:
1. Receives current weather conditions and a location
2. Calls Open-Meteo's archive endpoint for historical data
3. Compares current conditions with historical data
4. Generates an accessible natural language summary

## Configuration

### Settings

Only one setting is needed in `AppSettings`:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `weather_history_enabled` | bool | True | Enable/disable weather history comparisons |

No retention period setting needed since data comes from the API.

## Usage

### Basic Usage

```python
from accessiweather.weather_history import WeatherHistoryService
from accessiweather.models import Location, CurrentConditions

# Initialize service
service = WeatherHistoryService()

# Create location and current conditions
location = Location(
    name="New York",
    latitude=40.7128,
    longitude=-74.0060,
    timezone="America/New_York"
)

current_conditions = CurrentConditions(
    temperature=75.0,
    condition="Sunny",
    humidity=60,
    wind_speed=10.0,
    wind_direction="NW",
    pressure=30.1
)

# Compare with yesterday
comparison = service.compare_with_yesterday(location, current_conditions)
if comparison:
    print(comparison.get_accessible_summary())
    # Output: "Compared to yesterday: 5.0 degrees warmer. Changed from Cloudy to Sunny."
```

### Comparing with Different Time Periods

```python
# Compare with last week
week_comparison = service.compare_with_last_week(location, current_conditions)

# Compare with custom date
from datetime import date
target_date = date(2025, 9, 1)
custom_comparison = service.compare_with_date(location, current_conditions, target_date)
```

## Data Model

### HistoricalWeatherData

Historical weather snapshot from Open-Meteo:

```python
@dataclass
class HistoricalWeatherData:
    date: date
    temperature_max: float
    temperature_min: float
    temperature_mean: float  # Used for comparison
    condition: str
    humidity: int | None
    wind_speed: float
    wind_direction: int | None
    pressure: float | None
```

### WeatherComparison

Comparison results:

```python
@dataclass
class WeatherComparison:
    temperature_difference: float       # Temperature change
    temperature_description: str        # Human-readable description
    condition_changed: bool            # Whether condition changed
    previous_condition: str            # Previous weather condition
    condition_description: str | None  # Description of change
    days_ago: int                      # Days since comparison point
```

## API Endpoint

The feature uses Open-Meteo's archive endpoint:

```
https://api.open-meteo.com/v1/archive
```

Parameters:
- `latitude`, `longitude`: Location coordinates
- `start_date`, `end_date`: Date range (ISO format)
- `daily`: Requested weather variables
- `temperature_unit`: celsius or fahrenheit
- `timezone`: Timezone for results

## Advantages Over Local Tracking

### Immediate Benefits
- ✅ No setup required - works immediately for all users
- ✅ No background recording needed
- ✅ No local storage files to manage
- ✅ No cleanup of old entries required
- ✅ Access to historical data even for new installations

### Long-Term Benefits
- ✅ Decades of historical data available
- ✅ No storage limitations
- ✅ Always up-to-date with API improvements
- ✅ Lower maintenance burden
- ✅ Consistent data quality

### Trade-offs
- ⚠️ Requires API call for each comparison
- ⚠️ Dependent on Open-Meteo API availability
- ✅ Open-Meteo has generous rate limits

## Integration

### App Initialization

Add to `app_initialization.py`:

```python
from .weather_history import WeatherHistoryService

def initialize_components(app: AccessiWeatherApp) -> None:
    """Initialize core application components."""

    # ... existing initialization ...

    # Initialize weather history service
    config = app.config_manager.get_config()
    if config.settings.weather_history_enabled:
        app.weather_history_service = WeatherHistoryService()
        logger.info("Weather history service initialized")
    else:
        app.weather_history_service = None
```

### Display in UI

Add to weather presenter:

```python
def format_current_conditions(self, weather_data: WeatherData, app) -> str:
    """Format current conditions with history comparison."""

    parts = []
    # ... existing formatting ...

    # Add history comparison if available
    if app.weather_history_service and app.current_location:
        try:
            comparison = app.weather_history_service.compare_with_yesterday(
                app.current_location,
                weather_data.current_conditions
            )
            if comparison:
                parts.append("\n" + comparison.get_accessible_summary())
        except Exception as e:
            logger.debug(f"Could not get weather comparison: {e}")

    return "\n".join(parts)
```

### Menu Command

Add menu command for viewing history:

```python
async def view_weather_history(app, widget=None):
    """Show weather history comparison."""

    if not app.weather_history_service:
        # Show message that feature is disabled
        return

    # Get comparisons
    yesterday_comp = app.weather_history_service.compare_with_yesterday(
        app.current_location, current_conditions
    )
    week_comp = app.weather_history_service.compare_with_last_week(
        app.current_location, current_conditions
    )

    # Display in dialog
    # ...
```

## Testing

The feature includes comprehensive tests:

### Unit Tests

- `test_weather_history.py`: Tests all classes and methods
- Mock Open-Meteo API responses
- Test comparison logic
- Test accessible summary generation

### Running Tests

```bash
pytest tests/test_weather_history.py -v
```

## Demo

Run the demonstration script:

```bash
python3 examples/weather_history_demo.py
```

Example output:
```
Comparing with Yesterday:
   Fetching historical data from Open-Meteo archive API...
   ✓ Historical data retrieved
   Temperature difference: +11.0°F

   Accessible Summary:
   "Compared to yesterday: 11.0 degrees warmer. Changed from Overcast to Sunny."
```

## Error Handling

The service handles errors gracefully:

- **API Errors**: Returns `None` if API call fails
- **Missing Data**: Returns `None` if no historical data available
- **Network Issues**: Logs error and returns `None`

Calling code should check for `None` return values:

```python
comparison = service.compare_with_yesterday(location, conditions)
if comparison:
    print(comparison.get_accessible_summary())
else:
    print("Historical data not available")
```

## Future Enhancements

Potential additions:

1. **Extended Comparisons**: Compare with same day last month/year
2. **Statistical Analysis**: Show averages, trends over time
3. **Visual Graphs**: Chart temperature trends
4. **Anomaly Detection**: Identify unusual weather patterns
5. **Caching**: Cache recent API responses to reduce calls

## License

This feature is part of AccessiWeather and is licensed under the MIT License.
