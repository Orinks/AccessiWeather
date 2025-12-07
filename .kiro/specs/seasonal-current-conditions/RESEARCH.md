# Year-Round Seasonal Weather Enhancement - Research Summary

**Feature Branch:** `feat/seasonal-current-conditions`
**Base Branch:** `feat/smart-auto-source`
**Research Date:** December 7, 2025
**Design Philosophy:** Future-proof, year-round seasonal data

## Executive Summary

This document contains comprehensive research on adding **year-round seasonal weather information** to **existing current conditions and forecast displays** across all three weather data providers (NWS, Open-Meteo, Visual Crossing). The goal is to enhance the user experience with season-appropriate data that remains useful throughout the entire year, not just during winter.

### ⚠️ IMPORTANT: No New UI/Dialogs

**This enhancement modifies EXISTING displays only:**
- ✅ Enhances the **existing current conditions** display
- ✅ Enhances the **existing daily forecast** display
- ✅ Enhances the **existing hourly forecast** display
- ❌ **NO new dialogs or windows**
- ❌ **NO new UI screens**
- ✅ Smart, automatic season detection based on date + location
- ✅ Existing UI adapts to show season-relevant data

### Year-Round Approach

Rather than adding winter-only features, this enhancement provides **contextual seasonal data** that adapts to the current season:

- **Winter (Dec-Feb):** Snow depth, wind chill, freezing level, ice conditions
- **Spring (Mar-May):** Pollen levels, precipitation type, severe weather risk, growing degree days
- **Summer (Jun-Aug):** Heat index, UV index, air quality, drought indicators, fire weather
- **Fall (Sep-Nov):** Frost warnings, leaf conditions, harvest weather, transition indicators

All data sources provide year-round coverage with season-appropriate emphasis.

---

## 1. National Weather Service (NWS) API

### Current Implementation
- **File:** `src/accessiweather/weather_client_nws.py`
- **Base URL:** `https://api.weather.gov`
- **Current Endpoints Used:**
  - `/points/{lat},{lon}` - Grid point metadata
  - `/stations/{stationId}/observations/latest` - Current conditions
  - `/gridpoints/{office}/{gridX},{gridY}/forecast` - Forecast
  - `/gridpoints/{office}/{gridX},{gridY}/forecast/hourly` - Hourly forecast
  - `/alerts/active` - Weather alerts

### Available Seasonal Data

#### Current Observations Endpoint
**Endpoint:** `/stations/{stationId}/observations/latest`

**Winter-Relevant Fields Already Available:**
- `temperature` - Current temperature
- `dewpoint` - Dew point temperature
- `windChill` - Wind chill (critical for winter)
- `heatIndex` - Heat index (less relevant in winter)
- `relativeHumidity` - Relative humidity
- `windSpeed` - Wind speed
- `windGust` - Wind gusts
- `barometricPressure` - Atmospheric pressure
- `seaLevelPressure` - Sea level pressure
- `visibility` - Visibility (important for snow/fog)
- `precipitationLastHour` - Recent precipitation
- `precipitationLast3Hours` - 3-hour precipitation
- `precipitationLast6Hours` - 6-hour precipitation

**Quality Control:**
- All measurements include `qualityControl` field
- Valid QC codes: "V" (valid), "C" (coarse pass), null
- Current implementation already scrubs invalid measurements

#### Forecast Gridpoint Data
**Endpoint:** `/gridpoints/{office}/{gridX},{gridY}`

**Additional Winter-Relevant Fields:**
- `snowfallAmount` - Snowfall forecast
- `iceAccumulation` - Ice accumulation forecast
- `probabilityOfPrecipitation` - Precipitation probability
- `quantitativePrecipitation` - Precipitation amount
- `snowLevel` - Snow level elevation

### Recommendations for NWS

**High Priority:**
1. **Wind Chill Display** - Already available, ensure prominent display in winter
2. **Visibility** - Critical for winter driving conditions
3. **Precipitation Type** - Distinguish rain/snow/ice in current conditions
4. **Snow Accumulation** - From gridpoint forecast data

**Medium Priority:**
5. **Freezing Level** - Useful for determining rain vs. snow
6. **Road Conditions** - Derived from temp + precipitation + wind

**Implementation Notes:**
- NWS data is already comprehensive for winter conditions
- Main enhancement: better presentation and derived metrics
- Wind chill is already parsed but may need UI prominence
- Consider adding "feels like" temperature that switches between heat index (summer) and wind chill (winter)

---

## 2. Open-Meteo API

### Current Implementation
- **File:** `src/accessiweather/openmeteo_client.py`
- **Base URL:** `https://api.open-meteo.com/v1`
- **Archive URL:** `https://archive-api.open-meteo.com/v1`

### Available Seasonal Data

#### Current Weather Endpoint
**Endpoint:** `/v1/forecast`

**Current Parameters Used:**
```python
"current": [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "is_day",
    "precipitation",
    "weather_code",
    "cloud_cover",
    "pressure_msl",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "uv_index",
]
```

**Additional Winter-Relevant Parameters Available:**

**Snow & Ice:**
- `snowfall` - Current snowfall rate (cm or inch)
- `snow_depth` - Snow depth on ground (cm or inch)
- `freezing_level_height` - Height of 0°C isotherm (meters)
- `is_day` - Already used, important for winter daylight hours

**Temperature & Comfort:**
- `apparent_temperature` - Already used (feels-like temperature)
- `dew_point_2m` - Dew point at 2m
- `temperature_80m` - Temperature at 80m (for inversions)
- `temperature_120m` - Temperature at 120m
- `temperature_180m` - Temperature at 180m

**Precipitation:**
- `precipitation` - Already used
- `rain` - Rain amount
- `showers` - Shower amount
- `snowfall` - Snowfall amount
- `precipitation_probability` - Probability of precipitation

**Visibility & Conditions:**
- `visibility` - Visibility distance
- `cloud_cover` - Already used
- `cloud_cover_low` - Low cloud cover (0-3km)
- `cloud_cover_mid` - Mid cloud cover (3-8km)
- `cloud_cover_high` - High cloud cover (>8km)
- `fog` - Fog presence

**Wind:**
- `wind_speed_10m` - Already used
- `wind_speed_80m` - Wind at 80m
- `wind_speed_120m` - Wind at 120m
- `wind_speed_180m` - Wind at 180m
- `wind_gusts_10m` - Already used

#### Seasonal Forecast API
**Endpoint:** `https://seasonal-api.open-meteo.com/v1/seasonal`

**Key Features:**
- ECMWF SEAS5 model (7 months ahead)
- ECMWF EC46 model (46 days ahead)
- 51 ensemble members
- 36 km resolution

**Winter-Relevant Variables:**
- `temperature_2m_max/min/mean` - Temperature forecasts
- `snowfall` - Snowfall forecasts
- `snow_depth` - Snow depth forecasts
- `precipitation` - Precipitation forecasts
- `cloud_cover` - Cloud cover forecasts
- `wind_speed_10m` - Wind speed forecasts
- `soil_temperature` - Soil temperature (frost depth)
- `soil_moisture` - Soil moisture

**Anomaly Data:**
- Temperature anomalies (warmer/colder than normal)
- Precipitation anomalies (wetter/drier than normal)
- Snow depth anomalies

**Extreme Forecast Index (EFI):**
- Highlights potential extreme winter events
- Values near +1: much warmer than normal
- Values near -1: much colder than normal

### Recommendations for Open-Meteo

**High Priority:**
1. **Snowfall** - Add to current conditions
2. **Snow Depth** - Critical for winter conditions
3. **Freezing Level** - Determines rain vs. snow
4. **Visibility** - Important for winter weather

**Medium Priority:**
5. **Fog** - Common in winter mornings
6. **Cloud Cover Layers** - Better sky condition detail
7. **Dew Point** - For frost prediction

**Low Priority (Future Enhancement):**
8. **Seasonal Forecast Integration** - Long-range winter outlook
9. **Temperature Anomalies** - Is it warmer/colder than normal?
10. **Extreme Forecast Index** - Severe winter weather probability

**Implementation Notes:**
- Open-Meteo has excellent winter-specific data
- Snowfall and snow depth are key additions
- Freezing level helps determine precipitation type
- Seasonal API could provide "winter outlook" feature

---

## 3. Visual Crossing API

### Current Implementation
- **File:** `src/accessiweather/visual_crossing_client.py`
- **Base URL:** `https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline`

### Available Seasonal Data

#### Current Conditions Endpoint
**Endpoint:** `/timeline/{lat},{lon}`

**Current Parameters Used:**
```python
"elements": "temp,feelslike,humidity,windspeed,winddir,pressure,conditions,datetime,sunrise,sunset,moonrise,moonset,moonphase,sunriseEpoch,sunsetEpoch,moonriseEpoch,moonsetEpoch"
```

**Additional Winter-Relevant Elements Available:**

**Snow & Ice:**
- `snow` - Snow amount (inches or cm)
- `snowdepth` - Snow depth on ground
- `preciptype` - Precipitation type (rain, snow, ice, etc.)

**Temperature & Comfort:**
- `temp` - Already used
- `feelslike` - Already used
- `dew` - Dew point
- `windchill` - Wind chill temperature
- `heatindex` - Heat index (less relevant in winter)

**Precipitation:**
- `precip` - Total precipitation
- `precipprob` - Precipitation probability
- `precipcover` - Percentage of time with precipitation
- `preciptype` - Type of precipitation (array: rain, snow, ice, etc.)

**Visibility & Conditions:**
- `visibility` - Visibility distance
- `cloudcover` - Cloud cover percentage
- `conditions` - Already used (text description)
- `icon` - Weather icon code

**Wind:**
- `windspeed` - Already used
- `windgust` - Wind gust speed
- `winddir` - Already used

**Solar & Astronomical:**
- `sunrise/sunset` - Already used
- `moonrise/moonset` - Already used
- `moonphase` - Already used
- `solarradiation` - Solar radiation
- `solarenergy` - Solar energy
- `uvindex` - UV index

**Severe Weather:**
- `severerisk` - Severe weather risk (0-100)
- `stations` - Weather stations used

### Recommendations for Visual Crossing

**High Priority:**
1. **Snow Amount** - Add to current conditions
2. **Snow Depth** - Snow on ground
3. **Precipitation Type** - Distinguish rain/snow/ice
4. **Wind Chill** - Critical for winter comfort

**Medium Priority:**
5. **Visibility** - Important for winter driving
6. **Dew Point** - For frost/freeze prediction
7. **Cloud Cover** - Sky conditions
8. **Precipitation Probability** - Forecast confidence

**Low Priority:**
9. **Severe Risk** - Winter storm severity
10. **Precipitation Cover** - Duration of precipitation

**Implementation Notes:**
- Visual Crossing has comprehensive winter data
- Snow and precipitation type are key additions
- Wind chill should be prominently displayed
- Precipitation type array helps distinguish winter precip

---

## 4. Data Model Enhancements

### Current Models
**File:** `src/accessiweather/models.py`

### Proposed Additions to `CurrentConditions` (Existing Display)

```python
class CurrentConditions:
    # Existing fields...

    # NEW: Year-round seasonal fields

    # Winter-specific (Dec-Feb)
    snowfall_rate: float | None = None  # Current snowfall rate (in/hr or cm/hr)
    snow_depth: float | None = None  # Snow depth on ground (inches or cm)
    freezing_level_ft: float | None = None  # Freezing level in feet
    freezing_level_m: float | None = None  # Freezing level in meters
    wind_chill_f: float | None = None  # Wind chill in Fahrenheit
    wind_chill_c: float | None = None  # Wind chill in Celsius

    # Summer-specific (Jun-Aug)
    heat_index_f: float | None = None  # Heat index in Fahrenheit
    heat_index_c: float | None = None  # Heat index in Celsius
    uv_index: float | None = None  # UV index (already exists, ensure populated)
    air_quality_index: int | None = None  # AQI (US or European)
    air_quality_category: str | None = None  # "Good", "Moderate", "Unhealthy", etc.

    # Spring-specific (Mar-May)
    pollen_count: dict[str, float] | None = None  # {"grass": 50, "tree": 30, etc.}
    pollen_level: str | None = None  # "Low", "Moderate", "High", "Very High"

    # Fall-specific (Sep-Nov)
    frost_risk: str | None = None  # "None", "Low", "Moderate", "High"

    # Year-round
    precipitation_type: list[str] | None = None  # ["rain", "snow", "ice", etc.]
    severe_weather_risk: int | None = None  # 0-100 scale

    # Enhanced existing fields
    # visibility_miles: float | None  # Already exists
    # visibility_km: float | None  # Already exists
    # feels_like_f: float | None  # Already exists - use for heat index/wind chill
    # feels_like_c: float | None  # Already exists
```

### Seasonal Context

```python
class SeasonalContext:
    """Year-round seasonal weather context for enhanced user experience."""

    # Season detection
    season: str  # "winter", "spring", "summer", "fall"
    season_name: str  # Localized season name

    # Temperature context
    is_freezing: bool  # Temperature below 32°F/0°C
    is_hot: bool  # Temperature above 85°F/29°C
    is_extreme_heat: bool  # Temperature above 95°F/35°C
    is_extreme_cold: bool  # Temperature below 0°F/-18°C

    # Precipitation context
    is_snowing: bool
    is_raining: bool
    has_mixed_precip: bool

    # Seasonal severity indicators
    winter_severity: str | None  # "mild", "moderate", "severe", "extreme"
    summer_heat_severity: str | None  # "comfortable", "warm", "hot", "extreme"

    # Environmental conditions
    air_quality_alert: bool  # AQI above threshold
    pollen_alert: bool  # High pollen levels
    uv_alert: bool  # High UV index
    frost_alert: bool  # Frost expected

    # Daylight
    daylight_hours: float | None  # Hours of daylight
    is_short_day: bool  # Less than 10 hours of daylight (winter)
    is_long_day: bool  # More than 14 hours of daylight (summer)
```

### Environmental Conditions (Enhanced)

```python
class EnvironmentalConditions:
    """Enhanced environmental data for year-round use."""

    # Air Quality (year-round, emphasis in summer)
    aqi: int | None  # Air Quality Index
    aqi_category: str | None  # "Good", "Moderate", "Unhealthy", etc.
    pm25: float | None  # PM2.5 particulate matter
    pm10: float | None  # PM10 particulate matter
    ozone: float | None  # Ozone levels

    # Pollen (spring/summer/fall)
    pollen_levels: dict[str, float] | None  # {"grass": 50, "tree": 30, "ragweed": 20}
    pollen_category: str | None  # "Low", "Moderate", "High", "Very High"
    dominant_pollen: str | None  # "Grass", "Tree", "Ragweed", etc.

    # UV (spring/summer)
    uv_index: float | None
    uv_category: str | None  # "Low", "Moderate", "High", "Very High", "Extreme"

    # Additional year-round data
    visibility_category: str | None  # "Excellent", "Good", "Moderate", "Poor"
```

### Proposed Additions to `ForecastPeriod` (Existing Daily Forecast Display)

```python
class ForecastPeriod:
    # Existing fields...
    name: str
    temperature: float | None
    temperature_unit: str = "F"
    short_forecast: str | None
    detailed_forecast: str | None
    wind_speed: str | None
    wind_direction: str | None
    icon: str | None
    start_time: datetime | None
    end_time: datetime | None
    precipitation_probability: float | None
    snowfall: float | None  # Already exists!
    uv_index: float | None  # Already exists!

    # NEW: Year-round seasonal forecast fields

    # Winter
    snow_depth: float | None = None  # Expected snow depth
    freezing_level_ft: float | None = None  # Freezing level
    wind_chill_min_f: float | None = None  # Minimum wind chill for the day
    ice_risk: str | None = None  # "None", "Low", "Moderate", "High"

    # Summer
    heat_index_max_f: float | None = None  # Maximum heat index for the day
    uv_index_max: float | None = None  # Maximum UV index (enhance existing)
    air_quality_forecast: int | None = None  # Forecasted AQI

    # Spring/Fall
    frost_risk: str | None = None  # "None", "Low", "Moderate", "High"
    pollen_forecast: str | None = None  # "Low", "Moderate", "High", "Very High"

    # Year-round
    precipitation_type: list[str] | None = None  # ["rain", "snow", "ice"]
    severe_weather_risk: int | None = None  # 0-100 scale
    feels_like_high: float | None = None  # High "feels like" (heat index or temp)
    feels_like_low: float | None = None  # Low "feels like" (wind chill or temp)
```

### Proposed Additions to `HourlyForecastPeriod` (Existing Hourly Forecast Display)

```python
class HourlyForecastPeriod:
    # Existing fields...
    start_time: datetime
    temperature: float | None
    temperature_unit: str = "F"
    short_forecast: str | None
    wind_speed: str | None
    wind_direction: str | None
    icon: str | None
    end_time: datetime | None
    pressure_mb: float | None
    pressure_in: float | None
    precipitation_probability: float | None
    snowfall: float | None  # Already exists!
    uv_index: float | None  # Already exists!

    # NEW: Year-round seasonal hourly forecast fields

    # Winter
    snow_depth: float | None = None  # Snow depth at this hour
    freezing_level_ft: float | None = None  # Freezing level
    wind_chill_f: float | None = None  # Wind chill at this hour

    # Summer
    heat_index_f: float | None = None  # Heat index at this hour
    air_quality_index: int | None = None  # AQI at this hour

    # Spring/Fall
    frost_risk: bool | None = None  # Frost expected this hour
    pollen_level: str | None = None  # Pollen level this hour

    # Year-round
    precipitation_type: list[str] | None = None  # ["rain", "snow", "ice"]
    feels_like: float | None = None  # Feels like (wind chill or heat index)
    visibility_miles: float | None = None  # Visibility forecast
```

---

## 5. UI/UX Considerations

### Winter-Specific Display Priorities

**December 2025 Focus:**
1. **Temperature Display:**
   - Show "Feels Like" prominently (wind chill in winter)
   - Indicate if below freezing with icon/color

2. **Precipitation:**
   - Clearly show type (rain vs. snow vs. ice)
   - Show accumulation amounts
   - Show snow depth if applicable

3. **Visibility:**
   - Highlight low visibility conditions
   - Important for winter driving safety

4. **Wind:**
   - Show wind chill calculation
   - Highlight dangerous wind chill values

5. **Daylight:**
   - Show sunrise/sunset (already available)
   - Consider showing daylight hours remaining

### Accessibility Considerations
- Screen reader announcements for winter hazards
- Clear distinction between temperature and "feels like"
- Audible alerts for dangerous wind chill
- Text descriptions of precipitation type

---

## 6. Implementation Strategy

### Phase 1: Core Winter Data (Immediate)
1. Add snow-related fields to `CurrentConditions` model
2. Update NWS parser to extract wind chill
3. Update Open-Meteo client to request snowfall/snow depth
4. Update Visual Crossing client to request snow data
5. Enhance data fusion to merge winter data from multiple sources

### Phase 2: Enhanced Display (Short-term)
1. Update weather presenter to format winter data
2. Add winter-specific formatters
3. Enhance UI to show winter conditions prominently
4. Add seasonal context detection

### Phase 3: Advanced Features (Future)
1. Integrate Open-Meteo Seasonal Forecast API
2. Add winter outlook/anomaly data
3. Implement extreme weather index
4. Add historical winter comparisons

---

## 7. Forecast Data Availability

### Daily Forecast Fields (Already Available)

**NWS Daily Forecast:**
- ✅ Temperature high/low
- ✅ Precipitation probability
- ✅ Wind speed/direction
- ✅ Short/detailed forecast text
- ⚠️ Snowfall (in forecast text, needs parsing)
- ❌ UV index (not in daily forecast)
- ❌ Air quality (not available)

**Open-Meteo Daily Forecast:**
- ✅ Temperature max/min
- ✅ Precipitation sum, probability
- ✅ **Snowfall sum** (already available!)
- ✅ **UV index max** (already available!)
- ✅ Wind speed max, gusts
- ✅ Sunshine duration
- ✅ Weather code
- ⚠️ Growing degree days (available, not currently used)

**Visual Crossing Daily Forecast:**
- ✅ Temperature max/min
- ✅ Precipitation probability
- ✅ **Snow** (already available!)
- ✅ **UV index** (already available!)
- ✅ Wind speed/direction
- ✅ Conditions description
- ✅ Icon

### Hourly Forecast Fields (Already Available)

**NWS Hourly Forecast:**
- ✅ Temperature
- ✅ Precipitation probability
- ✅ Wind speed/direction
- ✅ Short forecast
- ⚠️ Snowfall (in forecast text)
- ❌ UV index (not in hourly)
- ❌ Air quality (not available)

**Open-Meteo Hourly Forecast:**
- ✅ Temperature
- ✅ Precipitation, probability
- ✅ **Snowfall** (already available!)
- ✅ **Snow depth** (available!)
- ✅ **UV index** (available!)
- ✅ **Freezing level height** (available!)
- ✅ Wind speed/direction/gusts
- ✅ Visibility
- ✅ Weather code
- ✅ Cloud cover
- ✅ Apparent temperature

**Visual Crossing Hourly Forecast:**
- ✅ Temperature
- ✅ Precipitation probability
- ✅ **Snow** (already available!)
- ✅ **UV index** (already available!)
- ✅ Wind speed/direction
- ✅ Conditions
- ✅ Icon

### NEW: Air Quality Forecast (Open-Meteo)

**Available for Hourly Forecast:**
```python
# Air Quality API provides 5-day hourly forecast
"hourly": [
    "us_aqi",  # or "european_aqi"
    "pm10",
    "pm2_5",
    "ozone",
    "uv_index",
]
```

**Pollen Forecast (Europe only):**
```python
"hourly": [
    "alder_pollen",  # Spring
    "birch_pollen",  # Spring
    "grass_pollen",  # Spring/Summer
    "ragweed_pollen",  # Fall
]
```

### What We Need to Add

**For Daily Forecast:**
1. ✅ Parse snowfall from NWS text (or use Open-Meteo/VC)
2. ✅ Add UV index from Open-Meteo/VC
3. ✅ Add air quality forecast from Open-Meteo
4. ✅ Calculate wind chill/heat index for daily high/low
5. ✅ Add precipitation type from Visual Crossing
6. ✅ Add severe weather risk from Visual Crossing

**For Hourly Forecast:**
1. ✅ Add snow depth from Open-Meteo
2. ✅ Add freezing level from Open-Meteo
3. ✅ Add UV index from Open-Meteo/VC
4. ✅ Add air quality from Open-Meteo
5. ✅ Calculate wind chill/heat index
6. ✅ Add visibility from Open-Meteo
7. ✅ Add precipitation type from Visual Crossing

---

## 8. Year-Round Data Availability Matrix

### Data by Season

| Data Type | Winter | Spring | Summer | Fall | Provider(s) |
|-----------|--------|--------|--------|------|-------------|
| **Temperature Comfort** |
| Wind Chill | ✅ Primary | ⚠️ Occasional | ❌ Rare | ⚠️ Occasional | NWS, VC |
| Heat Index | ❌ Rare | ⚠️ Occasional | ✅ Primary | ⚠️ Occasional | NWS, VC |
| Feels Like | ✅ Always | ✅ Always | ✅ Always | ✅ Always | All |
| **Precipitation** |
| Snow Depth | ✅ Primary | ⚠️ Occasional | ❌ Rare | ⚠️ Occasional | OM, VC |
| Snowfall Rate | ✅ Primary | ⚠️ Occasional | ❌ Rare | ⚠️ Occasional | OM, VC |
| Freezing Level | ✅ Primary | ✅ Useful | ⚠️ High | ✅ Useful | OM |
| Precip Type | ✅ Critical | ✅ Useful | ✅ Useful | ✅ Useful | VC |
| **Air Quality** |
| AQI | ✅ Always | ✅ Always | ✅ Primary | ✅ Always | OM |
| PM2.5/PM10 | ✅ Always | ✅ Always | ✅ Primary | ✅ Always | OM |
| Ozone | ⚠️ Lower | ✅ Rising | ✅ Primary | ✅ Moderate | OM |
| **Pollen** |
| Tree Pollen | ❌ Dormant | ✅ Primary | ⚠️ Lower | ❌ Dormant | OM (EU) |
| Grass Pollen | ❌ Dormant | ✅ Rising | ✅ Primary | ⚠️ Lower | OM (EU) |
| Ragweed Pollen | ❌ Dormant | ❌ Dormant | ⚠️ Rising | ✅ Primary | OM (EU) |
| **Solar/UV** |
| UV Index | ⚠️ Low | ✅ Moderate | ✅ Primary | ✅ Moderate | All |
| Solar Radiation | ⚠️ Low | ✅ Rising | ✅ Primary | ✅ Falling | OM |
| **Visibility** |
| Visibility | ✅ Critical | ✅ Useful | ✅ Useful | ✅ Critical | All |
| Fog | ✅ Common | ✅ Common | ⚠️ Less | ✅ Common | OM |
| **Severe Weather** |
| Severe Risk | ⚠️ Lower | ✅ Rising | ✅ Primary | ✅ Moderate | VC |
| Lightning | ❌ Rare | ✅ Rising | ✅ Primary | ✅ Moderate | NWS |

**Legend:**
- ✅ Primary: Most relevant/common for this season
- ✅ Always: Relevant year-round
- ✅ Useful: Available and useful
- ⚠️ Occasional: Available but less common
- ❌ Rare: Rarely applicable

### Provider Capabilities by Season

#### National Weather Service (NWS)
**Year-Round Strengths:**
- Temperature (all seasons)
- Precipitation (all types)
- Wind data (all seasons)
- Visibility (all seasons)
- Alerts (all seasons)

**Seasonal Emphasis:**
- **Winter:** Wind chill, snow forecasts, winter storm warnings
- **Spring:** Severe weather, tornado warnings, flood alerts
- **Summer:** Heat advisories, excessive heat warnings
- **Fall:** Frost advisories, winter weather outlooks

#### Open-Meteo
**Year-Round Strengths:**
- Temperature (all seasons)
- Precipitation (all types)
- Wind data (all seasons)
- Solar radiation (all seasons)
- Air quality (all seasons)

**Seasonal Emphasis:**
- **Winter:** Snow depth, freezing level, seasonal forecast
- **Spring:** Pollen (EU only), precipitation probability
- **Summer:** UV index, air quality, heat stress
- **Fall:** Pollen (ragweed), frost risk, seasonal outlook

**Unique Capabilities:**
- Seasonal Forecast API (7 months ahead)
- Air Quality API (PM2.5, PM10, O3, pollen)
- Temperature anomalies (warmer/colder than normal)
- Extreme Forecast Index (EFI)

#### Visual Crossing
**Year-Round Strengths:**
- Temperature (all seasons)
- Precipitation type (all seasons)
- Wind data (all seasons)
- Visibility (all seasons)
- Comprehensive historical data

**Seasonal Emphasis:**
- **Winter:** Snow depth, wind chill, precipitation type
- **Spring:** Severe weather risk, precipitation probability
- **Summer:** Heat index, UV index, severe risk
- **Fall:** Frost risk, precipitation type

**Unique Capabilities:**
- Precipitation type arrays (rain, snow, ice, mixed)
- Severe weather risk score (0-100)
- Historical forecast data

---

## 8. API Endpoint Summary

### NWS
- **Current:** `/stations/{stationId}/observations/latest`
- **Gridpoint:** `/gridpoints/{office}/{gridX},{gridY}`
- **Year-Round Fields:**
  - **Winter:** windChill, visibility, precipitationLastHour
  - **Spring:** temperature, dewpoint, precipitation, wind
  - **Summer:** heatIndex, temperature, humidity, wind
  - **Fall:** temperature, dewpoint, visibility, wind

### Open-Meteo
- **Current Weather:** `/v1/forecast?current=...`
- **Air Quality:** `https://air-quality-api.open-meteo.com/v1/air-quality`
- **Seasonal Forecast:** `https://seasonal-api.open-meteo.com/v1/seasonal`

**Year-Round Fields:**
- **Winter:** snowfall, snow_depth, freezing_level_height, visibility
- **Spring:** precipitation, pollen (EU), temperature, wind
- **Summer:** uv_index, air_quality (PM2.5, O3), temperature, solar_radiation
- **Fall:** pollen (ragweed), temperature, precipitation, wind

**Air Quality Parameters (Year-Round):**
```python
"current": [
    "us_aqi",  # or "european_aqi"
    "pm10",
    "pm2_5",
    "ozone",
    "nitrogen_dioxide",
    "sulphur_dioxide",
    "uv_index",
    "uv_index_clear_sky",
]

# Pollen (Europe only, seasonal)
"hourly": [
    "alder_pollen",  # Spring
    "birch_pollen",  # Spring
    "grass_pollen",  # Spring/Summer
    "mugwort_pollen",  # Summer/Fall
    "olive_pollen",  # Spring/Summer
    "ragweed_pollen",  # Fall
]
```

### Visual Crossing
- **Timeline:** `/timeline/{lat},{lon}?elements=...`

**Year-Round Fields:**
- **Winter:** snow, snowdepth, preciptype, windchill, visibility
- **Spring:** preciptype, precipprob, temp, humidity
- **Summer:** heatindex, uvindex, temp, humidity, severerisk
- **Fall:** preciptype, temp, dewpoint, visibility

---

## 8. Testing Considerations

### Test Scenarios
1. **Below Freezing:** Temperature < 32°F/0°C
2. **Snowing:** Active snowfall with accumulation
3. **Wind Chill:** High winds + cold temperature
4. **Mixed Precipitation:** Rain/snow/ice mix
5. **Low Visibility:** Fog or heavy snow
6. **No Winter Conditions:** Baseline test

### Test Locations (December 2025)
- **Minneapolis, MN** - Likely snow and cold
- **Buffalo, NY** - Lake effect snow
- **Denver, CO** - Mountain winter conditions
- **International:** Oslo, Norway; Moscow, Russia

---

## 9. Configuration & Settings

### User Preferences
- Enable/disable winter-specific alerts
- Snow depth units (inches vs. cm)
- Wind chill calculation method
- Visibility units (miles vs. km)

### Smart Auto Source Priority
- NWS: Best for US winter alerts and wind chill
- Open-Meteo: Best for snow depth and freezing level
- Visual Crossing: Best for precipitation type detail

---

## 10. Next Steps

**Before Implementation:**
1. ✅ Research complete
2. ⏳ Review research with user
3. ⏳ Create requirements document
4. ⏳ Create design document
5. ⏳ Create implementation tasks

**Ready for User Review:**
This research document is now complete and ready for your review. Please review the findings and let me know when you're ready to proceed with creating the formal spec (requirements, design, and tasks).

---

## References

- [NWS API Documentation](https://www.weather.gov/documentation/services-web-api)
- [Open-Meteo Weather Forecast API](https://open-meteo.com/en/docs)
- [Open-Meteo Seasonal Forecast API](https://open-meteo.com/en/docs/seasonal-forecast-api)
- [Visual Crossing Weather API](https://www.visualcrossing.com/weather-api/)
- [Visual Crossing Timeline API](https://www.visualcrossing.com/resources/documentation/weather-api/timeline-weather-api/)


---

## 10. Year-Round UI/UX Strategy

### Adaptive Display by Season

The UI should automatically adapt to show the most relevant information for the current season:

#### Winter Display (Dec-Feb)
**Primary Focus:**
1. Wind chill / "Feels like" temperature
2. Snow depth and snowfall rate
3. Precipitation type (rain/snow/ice)
4. Visibility (fog, snow)
5. Freezing level

**Visual Indicators:**
- ❄️ Snow icon when snowing
- 🧊 Ice warning for freezing conditions
- 🌫️ Fog icon for low visibility
- Blue color scheme for cold temperatures

#### Spring Display (Mar-May)
**Primary Focus:**
1. Temperature and "feels like"
2. Pollen levels (if available)
3. Precipitation probability
4. Severe weather risk
5. UV index (rising)

**Visual Indicators:**
- 🌸 Pollen alert icon
- ⚡ Severe weather warning
- 🌧️ Rain probability
- Green/yellow color scheme

#### Summer Display (Jun-Aug)
**Primary Focus:**
1. Heat index / "Feels like" temperature
2. UV index
3. Air quality index
4. Humidity
5. Severe weather risk

**Visual Indicators:**
- ☀️ High UV warning
- 🌡️ Extreme heat alert
- 💨 Air quality alert
- Red/orange color scheme for heat

#### Fall Display (Sep-Nov)
**Primary Focus:**
1. Temperature and "feels like"
2. Frost warnings
3. Precipitation type
4. Ragweed pollen (if available)
5. Visibility

**Visual Indicators:**
- 🍂 Frost warning icon
- 🌾 Ragweed pollen alert
- 🌧️ Precipitation type
- Orange/brown color scheme

### Universal Elements (All Seasons)
- Current temperature
- Condition description
- Wind speed and direction
- Humidity
- Pressure
- Sunrise/sunset times

---

## 11. Implementation Strategy (Revised for Year-Round)

### Phase 1: Core Seasonal Data Infrastructure
**Goal:** Add data models and API integration for year-round seasonal data

1. **Data Models** (Week 1)
   - Add seasonal fields to `CurrentConditions`
   - Create `SeasonalContext` class
   - Enhance `EnvironmentalConditions` class
   - Add season detection logic

2. **API Integration** (Week 2-3)
   - **NWS:** Extract wind chill, heat index
   - **Open-Meteo:** Add snowfall, snow depth, UV, air quality
   - **Visual Crossing:** Add snow data, precipitation type, severe risk
   - Integrate Open-Meteo Air Quality API

3. **Data Fusion** (Week 3)
   - Merge seasonal data from multiple sources
   - Prioritize sources based on season
   - Handle missing data gracefully

### Phase 2: Seasonal Context & Display
**Goal:** Implement season-aware UI and formatting

1. **Season Detection** (Week 4)
   - Automatic season detection based on date and hemisphere
   - Seasonal thresholds (temperature, daylight)
   - Seasonal context generation

2. **Formatters** (Week 4-5)
   - Winter formatters (wind chill, snow depth)
   - Summer formatters (heat index, UV, AQI)
   - Spring/Fall formatters (pollen, frost)
   - Adaptive "feels like" (wind chill vs heat index)

3. **UI Enhancements** (Week 5-6)
   - Seasonal display priorities
   - Adaptive icons and colors
   - Seasonal alerts and warnings
   - Accessibility improvements

### Phase 3: Advanced Seasonal Features
**Goal:** Add predictive and historical seasonal data

1. **Seasonal Forecast Integration** (Week 7-8)
   - Integrate Open-Meteo Seasonal Forecast API
   - Show seasonal outlook (warmer/colder than normal)
   - Temperature anomalies
   - Extreme Forecast Index (EFI)

2. **Historical Comparisons** (Week 9)
   - Compare current conditions to historical averages
   - "Warmer/colder than usual for this time of year"
   - Seasonal trends

3. **Advanced Alerts** (Week 10)
   - Season-specific alert thresholds
   - Pollen alerts (spring/summer/fall)
   - Air quality alerts (summer)
   - Frost alerts (fall/spring)
   - Heat alerts (summer)

---

## 12. Testing Strategy (Year-Round)

### Automated Testing

#### Unit Tests
1. **Season Detection**
   - Test season calculation for all months
   - Test hemisphere differences (Northern/Southern)
   - Test edge cases (equinoxes, solstices)

2. **Data Parsing**
   - Test parsing of seasonal data from each provider
   - Test handling of missing seasonal data
   - Test data type conversions (units)

3. **Formatters**
   - Test wind chill calculation
   - Test heat index calculation
   - Test AQI category mapping
   - Test pollen level categorization

#### Integration Tests
1. **API Integration**
   - Test NWS seasonal data retrieval
   - Test Open-Meteo Air Quality API
   - Test Visual Crossing seasonal fields
   - Test data fusion with seasonal data

2. **Seasonal Context**
   - Test context generation for each season
   - Test alert generation
   - Test UI adaptation

### Manual Testing Scenarios

#### Winter Testing (Dec-Feb)
- **Location:** Minneapolis, MN or Oslo, Norway
- **Conditions:** Below freezing, snowing, wind chill
- **Verify:** Snow depth, wind chill, visibility, ice warnings

#### Spring Testing (Mar-May)
- **Location:** Atlanta, GA or London, UK
- **Conditions:** High pollen, variable temperatures
- **Verify:** Pollen levels, frost warnings, precipitation type

#### Summer Testing (Jun-Aug)
- **Location:** Phoenix, AZ or Athens, Greece
- **Conditions:** Extreme heat, high UV, poor air quality
- **Verify:** Heat index, UV index, AQI, heat warnings

#### Fall Testing (Sep-Nov)
- **Location:** Boston, MA or Munich, Germany
- **Conditions:** Frost risk, ragweed pollen, temperature swings
- **Verify:** Frost warnings, pollen levels, precipitation type

### Cross-Season Testing
- Test season transitions (Mar 20, Jun 21, Sep 22, Dec 21)
- Test Southern Hemisphere locations (reversed seasons)
- Test tropical locations (minimal seasonal variation)
- Test Arctic locations (extreme seasonal variation)

---

## 13. Configuration & User Preferences

### Seasonal Data Settings

```python
class SeasonalSettings:
    """User preferences for seasonal data display."""

    # General
    enable_seasonal_data: bool = True
    auto_detect_season: bool = True
    manual_season_override: str | None = None  # For testing

    # Winter
    show_wind_chill: bool = True
    show_snow_depth: bool = True
    show_freezing_level: bool = True
    wind_chill_threshold: float = 32.0  # °F

    # Summer
    show_heat_index: bool = True
    show_uv_index: bool = True
    show_air_quality: bool = True
    heat_index_threshold: float = 80.0  # °F
    uv_alert_threshold: float = 6.0  # Moderate
    aqi_alert_threshold: int = 100  # Unhealthy for sensitive groups

    # Spring/Fall
    show_pollen: bool = True
    show_frost_warnings: bool = True
    pollen_alert_threshold: str = "High"

    # Display
    seasonal_color_scheme: bool = True
    seasonal_icons: bool = True
    adaptive_feels_like: bool = True  # Auto-switch wind chill/heat index
```

### Smart Auto Source Priority (Seasonal)

The smart auto source feature should prioritize providers based on season:

**Winter Priority:**
1. NWS (US) - Best for wind chill, winter alerts
2. Open-Meteo - Best for snow depth, freezing level
3. Visual Crossing - Best for precipitation type

**Summer Priority:**
1. Open-Meteo - Best for UV, air quality
2. NWS (US) - Best for heat advisories
3. Visual Crossing - Best for severe weather risk

**Spring/Fall Priority:**
1. Open-Meteo - Best for pollen (EU), temperature
2. NWS (US) - Best for frost advisories, alerts
3. Visual Crossing - Best for precipitation type

---

## 14. Performance Considerations

### API Call Optimization

**Current Conditions:**
- NWS: 1 call (observations)
- Open-Meteo: 1 call (forecast with current)
- Visual Crossing: 1 call (timeline)

**With Seasonal Data:**
- NWS: 1 call (no change)
- Open-Meteo: 2 calls (forecast + air quality)
- Visual Crossing: 1 call (no change)

**Total:** 4 API calls (up from 3)

**Optimization Strategies:**
1. Cache air quality data separately (updates less frequently)
2. Only fetch air quality in summer or when AQI is enabled
3. Batch pollen data with air quality (same API)
4. Use smart auto source to fetch only from needed providers

### Data Storage

**Additional Storage per Location:**
- Seasonal fields: ~200 bytes
- Air quality data: ~150 bytes
- Pollen data: ~100 bytes
- **Total:** ~450 bytes per location

**Impact:** Minimal (< 1KB per location)

---

## 15. Accessibility Enhancements

### Screen Reader Announcements

**Winter:**
- "Current temperature 25 degrees, feels like 15 degrees due to wind chill"
- "Snow depth 6 inches, visibility reduced to 1 mile"
- "Freezing conditions, use caution when driving"

**Summer:**
- "Current temperature 95 degrees, feels like 105 degrees due to humidity"
- "UV index 9, very high, sun protection recommended"
- "Air quality unhealthy for sensitive groups, limit outdoor activity"

**Spring/Fall:**
- "High pollen levels, allergy sufferers should take precautions"
- "Frost warning in effect, protect sensitive plants"
- "Mixed precipitation expected, rain changing to snow"

### Visual Indicators

**Color Coding:**
- Blue: Cold/winter conditions
- Red/Orange: Hot/summer conditions
- Yellow: Caution (moderate conditions)
- Green: Good conditions
- Purple: Poor air quality

**Icons:**
- Season-appropriate weather icons
- Alert icons for hazardous conditions
- Trend indicators (rising/falling)

---

## 16. Future Enhancements

### Phase 4: Machine Learning & Predictions
1. **Personalized Seasonal Alerts**
   - Learn user preferences for alerts
   - Predict when user will want seasonal data
   - Adaptive threshold recommendations

2. **Seasonal Pattern Recognition**
   - Identify unusual seasonal patterns
   - "Warmest December in 10 years"
   - "Earliest frost in 5 years"

3. **Health Impact Predictions**
   - Pollen impact on user (if tracked)
   - Heat stress risk assessment
   - Cold weather health advisories

### Phase 5: Extended Seasonal Data
1. **Agricultural Data**
   - Growing degree days
   - Frost depth
   - Soil moisture
   - Crop-specific advisories

2. **Energy Data**
   - Heating/cooling degree days
   - Solar potential
   - Wind energy potential

3. **Recreation Data**
   - Ski conditions (winter)
   - Beach conditions (summer)
   - Hiking conditions (spring/fall)

---

## 17. Success Metrics

### User Engagement
- Increased time spent viewing current conditions
- Higher engagement with seasonal alerts
- Positive user feedback on seasonal features

### Data Quality
- Successful data retrieval rate (>95%)
- Data fusion accuracy
- Alert accuracy (true positive rate)

### Performance
- API response time (<2 seconds)
- Cache hit rate (>80%)
- App startup time (no degradation)

---

## 18. Conclusion

This year-round seasonal weather enhancement provides:

✅ **Future-Proof Design:** Useful in all seasons, not just winter
✅ **Comprehensive Coverage:** All three providers contribute seasonal data
✅ **Adaptive UI:** Automatically shows relevant information for current season
✅ **User Value:** Enhanced weather awareness year-round
✅ **Scalable:** Easy to add new seasonal data types
✅ **Accessible:** Screen reader support and visual indicators

**Next Steps:**
1. Review this research document
2. Create formal requirements document
3. Create design document with technical specifications
4. Create implementation tasks
5. Begin Phase 1 development

---

## References

- [NWS API Documentation](https://www.weather.gov/documentation/services-web-api)
- [Open-Meteo Weather Forecast API](https://open-meteo.com/en/docs)
- [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api)
- [Open-Meteo Seasonal Forecast API](https://open-meteo.com/en/docs/seasonal-forecast-api)
- [Visual Crossing Weather API](https://www.visualcrossing.com/weather-api/)
- [Visual Crossing Timeline API](https://www.visualcrossing.com/resources/documentation/weather-api/timeline-weather-api/)
- [EPA Air Quality Index](https://www.airnow.gov/aqi/aqi-basics/)
- [European Air Quality Index](https://www.eea.europa.eu/themes/air/air-quality-index)
