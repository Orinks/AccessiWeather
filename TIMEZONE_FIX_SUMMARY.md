# Timezone Display Bug Fix - Implementation Summary

## Issue Fixed
Times were displaying in UTC instead of respecting user's time display settings for:
- Last updated time in current conditions
- Hourly forecast times
- Sunrise/sunset times
- Moonrise/moonset times

Affected data sources: NWS and Visual Crossing APIs

## Root Cause
Both NWS and Visual Crossing clients were parsing timestamps in UTC and storing them without converting to the location's local timezone. When the formatter received these UTC-only times, it would display them as UTC regardless of user preference settings.

## Solution Implemented

### NWS Client (`weather_client_nws.py`)
1. **Modified `parse_nws_current_conditions()`**
   - Added optional `location: Location | None` parameter
   - Converts UTC `last_updated` timestamp to location's timezone using `ZoneInfo`
   - Falls back gracefully if location or timezone is unavailable

2. **Modified `parse_nws_hourly_forecast()`**
   - Added optional `location: Location | None` parameter
   - Converts both `start_time` and `end_time` to location's timezone
   - Independent conversion for each timestamp ensures robustness

3. **Updated Call Sites**
   - `get_nws_current_conditions()`: Passes location to parser
   - `get_nws_hourly_forecast()`: Passes location to parser (2 call sites)

### Visual Crossing Client (`visual_crossing_client.py`)
1. **Modified `_parse_current_conditions()`**
   - Added optional `location: Location | None` parameter
   - Converts all timestamps to location timezone:
     - `last_updated` (from epoch or ISO string)
     - `sunrise_time` / `sunset_time`
     - `moonrise_time` / `moonset_time`
   - Handles both epoch and ISO string formats

2. **Modified `_parse_hourly_forecast()`**
   - Added optional `location: Location | None` parameter
   - Converts `start_time` from combined date+time string to location timezone

3. **Updated Call Sites**
   - `get_current_conditions()`: Passes location to parser
   - `get_hourly_forecast()`: Passes location to parser

### Test Updates
- Updated mock in `test_visual_crossing_retries_on_request_error` to accept new `location` parameter

## How It Works

### Timezone Conversion Flow
```
1. API returns UTC timestamp (e.g., "2024-06-15T20:30:00Z")
2. Parser creates timezone-aware datetime in UTC
3. Parser checks if location.timezone is available
4. If available, uses ZoneInfo to convert to location's timezone
5. Formatter receives datetime in correct timezone
6. Formatter respects user's time_display_mode setting:
   - "local": Shows time in location's timezone
   - "utc": Shows time converted to UTC
   - "both": Shows both with timezone labels
```

### Example
For Los Angeles (America/Los_Angeles, UTC-7):
- API returns: `2024-06-15T20:30:00Z` (8:30 PM UTC)
- Parser converts to: `2024-06-15T13:30:00-07:00` (1:30 PM PDT)
- User sees: "1:30 PM" (when display mode is "local")

## Compatibility
- Open-Meteo client was already correctly handling timezone conversion (no changes needed)
- All changes are backward-compatible
  - `location` parameter is optional
  - Falls back gracefully if location/timezone is unavailable
- Uses Python 3.10+ standard library `zoneinfo` module (matches project requirements)

## Testing
- All 1306 existing tests pass
- Verified with manual testing:
  - UTC to PST (UTC-7) conversion
  - Correct hour offset calculation
  - Multiple timestamp types (epoch, ISO string)
- Integration tests validate time display across all providers

## Files Changed
1. `src/accessiweather/weather_client_nws.py`
   - Added ZoneInfo import
   - Updated 3 functions (2 parse functions, 2 call sites)

2. `src/accessiweather/visual_crossing_client.py`
   - Added ZoneInfo import
   - Updated 3 functions (2 parse functions, 2 call sites)

3. `tests/test_weather_client_retry.py`
   - Updated 1 mock to accept location parameter

## Branch
- Created from: `dev`
- Branch name: `diagnose/timezone-display-bug`
- Commits:
  1. `fix: Apply location timezone to NWS and Visual Crossing timestamps`
  2. `test: Update mock to accept location parameter in Visual Crossing retry test`
