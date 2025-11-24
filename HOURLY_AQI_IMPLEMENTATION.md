# Hourly Air Quality Implementation

## Summary

Implemented hourly air quality forecasting using Open-Meteo's Air Quality API. Users can now see AQI trends, peak times, and best times for outdoor activities.

## What Was Added

### 1. Data Model (`models/weather.py`)
- `HourlyAirQuality` dataclass: Stores timestamp, AQI, category, and individual pollutant levels (PM2.5, PM10, ozone, NO2, SO2, CO)
- Added `hourly_air_quality` field to `EnvironmentalConditions`

### 2. API Client (`services/environmental_client.py`)
- `fetch_hourly_air_quality()`: Fetches up to 120 hours of AQI forecast
- Returns list of hourly data with AQI values and pollutant breakdowns
- Integrated into main `fetch()` method with `include_hourly_air_quality` parameter

### 3. Presentation Layer (`display/presentation/environmental.py`)
- `format_hourly_air_quality()`: Formats hourly data into readable text
- Shows current AQI, trend analysis (improving/worsening/stable), peak times, and best times for outdoor activities
- Respects user time format preferences (12/24 hour)

## API Details

**Endpoint**: `https://air-quality-api.open-meteo.com/v1/air-quality`

**Parameters**:
- `hourly`: us_aqi, pm2_5, pm10, ozone, nitrogen_dioxide, sulphur_dioxide, carbon_monoxide
- `forecast_hours`: 1-120 (default: 48)
- `timezone`: auto

**Example Response**:
```json
{
  "hourly": {
    "time": ["2025-11-23T00:00", "2025-11-23T01:00", ...],
    "us_aqi": [59, 57, 56, ...],
    "pm2_5": [12.7, 13.2, 14.1, ...],
    "pm10": [12.8, 13.3, 14.2, ...]
  }
}
```

## Usage Example

```python
from accessiweather.services.environmental_client import EnvironmentalDataClient
from accessiweather.models import Location

client = EnvironmentalDataClient()
location = Location(name="New York", latitude=40.7128, longitude=-74.0060)

# Fetch 24 hours of air quality forecast
result = await client.fetch(
    location,
    include_hourly_air_quality=True,
    hourly_hours=24
)

# Access hourly data
for hour in result.hourly_air_quality:
    print(f"{hour.timestamp}: AQI {hour.aqi} ({hour.category})")
```

## Output Example

```
Current: AQI 45 (Good)
Trend: Worsening (AQI 45 → 125)
Peak: AQI 125 (Unhealthy for Sensitive Groups) at 2:00 PM
Best time: AQI 35 (Good) at 6:00 AM
```

## Tests

- `tests/test_hourly_air_quality.py`: API client tests (5 tests)
- `tests/test_environmental_hourly_integration.py`: Integration tests (4 tests)
- `tests/test_hourly_air_quality_presentation.py`: Presentation tests (7 tests)

**Total: 16 new tests, all passing**

## Next Steps (Not Implemented Yet)

1. UI integration - display hourly forecast in the app
2. Settings toggle for hourly forecast
3. Alerts when AQI will exceed threshold in next N hours
4. Graph/chart visualization of hourly trends
5. Individual pollutant breakdown display
