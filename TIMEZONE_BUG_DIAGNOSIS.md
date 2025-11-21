# Timezone Display Bug Diagnosis

## Issue Summary
Times are displaying in UTC instead of respecting the user's time display settings for:
- Last updated time in current conditions
- Some hourly forecasts

## Root Cause Analysis

### The Formatter is Working Correctly
The formatters in `display/presentation/formatters.py` are properly implemented:
- `format_timestamp()` - accepts `time_display_mode` parameter
- `format_display_time()` - correctly handles "local", "utc", and "both" modes
- Settings are being passed through the call stack correctly

### The Problem: Missing Timezone Information in Parsed Data

The issue is that **incoming timestamps lack timezone information**:

1. **NWS Client** (`weather_client_nws.py`, line 1014):
   - Parses `last_updated` as UTC-aware (replaces "Z" with "+00:00")
   - **NEVER converts to location's timezone** before storing
   - When formatter receives it, even in "local" mode, it displays as UTC

2. **Visual Crossing Client** (`visual_crossing_client.py`, line 241):
   - Converts epoch timestamp directly to UTC using `datetime.fromtimestamp(timestamp, tz=UTC)`
   - **NEVER converts to location's timezone**
   - Results in UTC display regardless of user settings

3. **Open-Meteo Client** (`weather_client_openmeteo.py`, line 302):
   - ✅ **Correctly applies timezone offset** via `utc_offset_seconds` parameter
   - Handles naive datetimes and applies location timezone via `timezone(timedelta(seconds=utc_offset_seconds))`
   - Working as expected

### Where the Location Timezone Info Exists
When APIs are called, the location has timezone info available:
- Location has `timezone` field available
- Open-Meteo requests include `timezone="auto"` parameter, providing `utc_offset_seconds`
- NWS and Visual Crossing also know the location but don't use timezone info during parsing

## Files Requiring Changes

1. **`src/accessiweather/weather_client_nws.py`**
   - Line 1014: Parse `last_updated` to location's timezone, not UTC
   - Lines 976-1000: Check hourly forecast parsing for timezone issues
   - Need to pass location/timezone info to parsing functions

2. **`src/accessiweather/visual_crossing_client.py`**
   - Line 241: Convert epoch to location's timezone, not UTC
   - Line 246: Ensure datetime parsing respects location timezone
   - Need to pass location/timezone info to parsing functions

3. **`src/accessiweather/weather_client_base.py`**
   - May need to refactor API calls to pass timezone info to parsers
   - Ensure location context is available during parsing

## Testing Areas
- Current conditions "Last updated" display with different time modes
- Hourly forecast times with different time modes
- NWS and Visual Crossing clients specifically
- All three time display modes: "local", "utc", "both"
