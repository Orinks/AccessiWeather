# Forecast Data Enhancement Summary

## What's Already Available in Forecasts

### Daily Forecast (ForecastPeriod)
**Currently has:**
- ✅ `snowfall: float | None` - Already exists!
- ✅ `uv_index: float | None` - Already exists!
- ✅ `precipitation_probability: float | None`
- ✅ Temperature, wind, conditions

**Providers:**
- **Open-Meteo:** Provides snowfall_sum, uv_index_max, precipitation_probability_max
- **Visual Crossing:** Provides snow, uvindex, precipprob
- **NWS:** Provides snowfall in text (needs parsing), no UV

### Hourly Forecast (HourlyForecastPeriod)
**Currently has:**
- ✅ `snowfall: float | None` - Already exists!
- ✅ `uv_index: float | None` - Already exists!
- ✅ `precipitation_probability: float | None`
- ✅ Temperature, wind, pressure, conditions

**Providers:**
- **Open-Meteo:** Provides snowfall, snow_depth, uv_index, freezing_level_height, visibility
- **Visual Crossing:** Provides snow, uvindex, precipprob
- **NWS:** Provides snowfall in text (needs parsing), no UV

## What We're Adding to Forecasts

### Daily Forecast Additions

```python
class ForecastPeriod:
    # NEW fields
    snow_depth: float | None = None  # Expected snow accumulation
    wind_chill_min_f: float | None = None  # Minimum wind chill
    heat_index_max_f: float | None = None  # Maximum heat index
    uv_index_max: float | None = None  # Max UV (enhance existing field)
    air_quality_forecast: int | None = None  # Forecasted AQI
    frost_risk: str | None = None  # "None", "Low", "Moderate", "High"
    pollen_forecast: str | None = None  # "Low", "Moderate", "High"
    precipitation_type: list[str] | None = None  # ["rain", "snow", "ice"]
    severe_weather_risk: int | None = None  # 0-100 scale
    feels_like_high: float | None = None  # High "feels like"
    feels_like_low: float | None = None  # Low "feels like"
```

### Hourly Forecast Additions

```python
class HourlyForecastPeriod:
    # NEW fields
    snow_depth: float | None = None  # Snow depth at this hour
    freezing_level_ft: float | None = None  # Freezing level
    wind_chill_f: float | None = None  # Wind chill
    heat_index_f: float | None = None  # Heat index
    air_quality_index: int | None = None  # AQI
    frost_risk: bool | None = None  # Frost expected
    pollen_level: str | None = None  # Pollen level
    precipitation_type: list[str] | None = None  # ["rain", "snow", "ice"]
    feels_like: float | None = None  # Feels like (auto wind chill/heat index)
    visibility_miles: float | None = None  # Visibility forecast
```

## Data Sources for Forecast Enhancements

### Open-Meteo Forecast API
**Already using, just need to request more fields:**

**Daily:**
```python
"daily": [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "precipitation_probability_max",
    "snowfall_sum",  # ✅ Already requested
    "uv_index_max",  # ✅ Already requested
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "weather_code",
    # ADD THESE:
    "apparent_temperature_max",  # For heat index
    "apparent_temperature_min",  # For wind chill
    "sunshine_duration",
]
```

**Hourly:**
```python
"hourly": [
    "temperature_2m",
    "precipitation",
    "precipitation_probability",
    "snowfall",  # ✅ Already requested
    "uv_index",  # ✅ Already requested
    "wind_speed_10m",
    "weather_code",
    # ADD THESE:
    "snow_depth",  # ❄️ Snow on ground
    "freezing_level_height",  # 🧊 Freezing level
    "apparent_temperature",  # 🌡️ Feels like
    "visibility",  # 👁️ Visibility
    "cloud_cover",
]
```

### Open-Meteo Air Quality API (NEW)
**Add this for air quality forecasts:**

```python
# Separate API call for air quality
url = "https://air-quality-api.open-meteo.com/v1/air-quality"
params = {
    "latitude": lat,
    "longitude": lon,
    "hourly": ["us_aqi", "pm2_5", "pm10", "ozone", "uv_index"],
    "forecast_days": 5,
}
```

**Pollen (Europe only):**
```python
"hourly": [
    "alder_pollen",  # Spring
    "birch_pollen",  # Spring
    "grass_pollen",  # Spring/Summer
    "ragweed_pollen",  # Fall
]
```

### Visual Crossing Timeline API
**Already using, just need to request more fields:**

```python
"elements": "datetime,tempmax,tempmin,temp,conditions,description,windspeed,winddir,icon,precipprob,snow,uvindex,
    # ADD THESE:
    windchill,  # ❄️ Wind chill
    heatindex,  # 🌡️ Heat index
    preciptype,  # 🌧️ Precipitation type
    severerisk,  # ⚡ Severe weather risk
    visibility,  # 👁️ Visibility
    cloudcover,  # ☁️ Cloud cover
"
```

### NWS API
**Already using, no changes needed:**
- Snowfall mentioned in forecast text (can parse)
- Wind chill/heat index can be calculated from temp + wind + humidity
- No UV or air quality available

## Implementation Strategy

### Phase 1: Enhance Open-Meteo Integration
1. Add new fields to Open-Meteo forecast requests
2. Parse snow_depth, freezing_level_height, visibility
3. Calculate wind chill/heat index from apparent_temperature

### Phase 2: Add Air Quality Forecasts
1. Integrate Open-Meteo Air Quality API
2. Fetch 5-day hourly AQI forecast
3. Add to hourly forecast periods
4. Aggregate to daily max AQI

### Phase 3: Enhance Visual Crossing Integration
1. Add new fields to Visual Crossing requests
2. Parse precipitation type arrays
3. Extract severe weather risk
4. Get wind chill/heat index directly

### Phase 4: Smart Data Fusion
1. Merge seasonal forecast data from all sources
2. Prioritize based on season:
   - **Winter:** Open-Meteo (snow depth) > Visual Crossing (precip type) > NWS
   - **Summer:** Open-Meteo (UV, AQI) > Visual Crossing (heat index) > NWS
3. Fill gaps intelligently

## Performance Impact

**Current API Calls per Location:**
- NWS: 1 call (forecast)
- Open-Meteo: 1 call (forecast)
- Visual Crossing: 1 call (timeline)
**Total: 3 calls**

**With Enhancements:**
- NWS: 1 call (no change)
- Open-Meteo: 2 calls (forecast + air quality)
- Visual Crossing: 1 call (no change)
**Total: 4 calls**

**Optimization:**
- Air quality only fetched when needed (summer) or when enabled
- Cache air quality separately (updates less frequently)
- Batch pollen with air quality (same API)

## UI Display Examples

### Daily Forecast Card (Winter)
```
Tuesday
High: 30°F (feels like 20°F)
Low: 20°F (feels like 10°F)
❄️ 4-6" snow expected
🌨️ Snow
👁️ Visibility: 1 mile
💨 Wind: 15 mph NW
```

### Daily Forecast Card (Summer)
```
Tuesday
High: 95°F (feels like 105°F)
Low: 75°F
☀️ UV Index: 10 (Extreme)
💨 AQI: 125 (Unhealthy)
🌡️ Heat Advisory
💧 Humidity: 70%
```

### Hourly Forecast Row (Winter)
```
2 PM | 28°F (feels like 18°F) | ❄️ Snowing | 3" depth | 0.5 mi vis
```

### Hourly Forecast Row (Summer)
```
2 PM | 95°F (feels like 105°F) | ☀️ Sunny | UV: 9 | AQI: 120
```

## Benefits

✅ **Richer Forecasts:** More detailed, season-appropriate forecast data
✅ **Better Planning:** Users can plan activities based on UV, air quality, snow depth
✅ **Safety:** Wind chill, heat index, visibility warnings in forecasts
✅ **No New UI:** All enhancements fit into existing forecast displays
✅ **Year-Round Value:** Useful in all seasons

## Next Steps

1. ✅ Research complete
2. ⏳ User approval
3. ⏳ Update data models (ForecastPeriod, HourlyForecastPeriod)
4. ⏳ Enhance API clients (Open-Meteo, Visual Crossing)
5. ⏳ Update data fusion logic
6. ⏳ Update forecast presenters/formatters
7. ⏳ Test across all seasons
