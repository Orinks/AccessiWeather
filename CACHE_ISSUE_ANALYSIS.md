# Cache Issues Root Cause Analysis

## Issues Identified

### Issue #1: Sunrise/Sunset Times Changing During App Runtime
**Symptom**: Sunrise and sunset times change from API values when the app is kept open for extended periods.

**Root Cause**: The enrichment system is fetching fresh sunrise/sunset data from Open-Meteo **after** the cache is persisted, and then overwriting the cached values.

**Where it happens**:
1. `weather_client_base.py:631` - `_persist_weather_data()` is called to save weather data to the persistent cache
2. This persists the weather data that may or may not have sunrise/sunset times filled in
3. Later (potentially at next refresh), `weather_client_enrichment.py:312-343` - `enrich_with_sunrise_sunset()` fetches fresh sunrise/sunset from Open-Meteo
4. This enrichment updates the in-memory `weather_data.current.sunrise_time` and `weather_data.sunset_time`
5. But the persistent cache has already been written with different (or missing) values
6. On next app startup or refresh, the stale cached values are loaded, showing old times

**The Problem**:
- The enrichment tasks (including sunrise/sunset) run **after** the initial cache persist
- The enrichment data is displayed to the user but not saved back to the persistent cache
- On next load, the cache data (without enrichments) is returned instead

### Issue #2: Users Must Delete Cache When Updating to New Builds
**Symptom**: Users need to manually delete the cache folder when updating the app to new test builds.

**Root Cause**: There is no version checking or automatic cache invalidation on app startup. The cache persists indefinitely without any mechanism to clear it when the app version changes.

**Where it happens**:
1. `cache.py:527` - Cache payload has a `"version": 1` field, but it's never checked on load
2. `cache.py:543-579` - `WeatherDataCache.load()` reads the cached data without validating the app version
3. `app_initialization.py:29-115` - Component initialization never checks app version against cache version
4. There's `purge_expired()` but it only removes entries older than 2x `max_age_minutes` (default 180 min * 2 = 360 min = 6 hours)

**The Problem**:
- If the API response format or field names change between versions, the old cached data might be incompatible
- Cache schema migrations are not handled
- No version mismatch detection or automatic invalidation

## Recommended Fixes

### Fix #1: Persist Enrichment Data Back to Cache
**Approach**: After all enrichments complete, save the enriched data back to the persistent cache.

**Implementation Location**: `weather_client_base.py` - `_await_enrichments()` method (around line 609)

**Changes Required**:
1. Move `_persist_weather_data()` call to **after** enrichments complete (not before)
2. Ensure sunrise/sunset enrichments (and other enrichments) update the persistent cache
3. This ensures that what the user sees is what gets cached

**Code Path**:
```
_do_fetch_weather_data()
  → fetch API data
  → _launch_enrichment_tasks()
  → _await_enrichments()
    → enrich_with_sunrise_sunset()  [modifies weather_data]
    → populate_environmental_metrics()  [modifies weather_data]
    → etc.
    → _persist_weather_data(weather_data)  [SHOULD BE HERE, not before]
```

### Fix #2: Add App Version to Cache with Validation
**Approach**: Store the app version in the cache and invalidate (or migrate) on version mismatch.

**Implementation Locations**:
1. `cache.py` - `WeatherDataCache.store()` method (line 524)
2. `cache.py` - `WeatherDataCache.load()` method (line 543)
3. `app_initialization.py` - Component initialization (line 29)

**Changes Required**:
1. Include app version in the cache payload when storing
2. On load, compare stored version with current app version
3. If version mismatch detected:
   - Option A (Conservative): Invalidate the entire cache entry
   - Option B (Cautious): Log a warning and allow stale data fallback only
4. Add an optional `--force-clear-cache` startup flag for manual clearing

**Benefits**:
- Automatic invalidation when schema changes
- No more manual cache deletion needed by users
- Can detect incompatible cached data

## Implementation Priority

1. **Fix #1 (High Priority)**: Solves the sunrise/sunset issue immediately
   - Simpler to implement
   - Affects all enriched data (not just sunrise/sunset)
   - One-liner code move in most cases

2. **Fix #2 (High Priority)**: Solves the manual deletion issue
   - Prevents future compatibility issues
   - Improves user experience for test builds
   - Medium complexity but straightforward

Both fixes should be implemented together for a complete solution.
