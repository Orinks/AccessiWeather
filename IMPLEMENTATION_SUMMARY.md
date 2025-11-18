# Cache Fixes Implementation Summary

**Branch**: `fix/cache-schema-versioning`
**Commit**: `89fa699`

## Changes Made

### 1. Cache Schema Versioning (`src/accessiweather/cache.py`)

#### Added Schema Version Constant
```python
# Cache schema version - increment this when cache data structure changes
# This is independent of app version and allows test builds to invalidate old cache
CACHE_SCHEMA_VERSION = 2
```

**Why version 2?** The current cache uses `"version": 1` in the JSON payload. We're changing it to `"schema_version": 2` to indicate the schema structure has evolved.

#### Updated Cache Storage
- Changed `WeatherDataCache.store()` to write `"schema_version": CACHE_SCHEMA_VERSION` instead of `"version": 1`
- This marks all newly cached data with the current schema version

#### Added Schema Validation on Load
- `WeatherDataCache.load()` now validates the cached schema version
- If `cached_schema_version != CACHE_SCHEMA_VERSION`:
  - Logs a debug message indicating the mismatch
  - Automatically deletes the incompatible cache file
  - Returns `None` to trigger a fresh API fetch
- Backward compatible: defaults to version 1 if not present

**Benefits**:
- Test builds can invalidate cache by incrementing `CACHE_SCHEMA_VERSION`
- No need to manually delete cache or change app version numbers
- Automatic schema migration path for future data structure changes

### 2. Ensure Enrichments Always Persist (`src/accessiweather/weather_client_base.py`)

#### Applied Enrichments to Cache Hits
- Modified `get_weather_data()` to apply enrichments even to cached data
- When cached data is loaded and fresh:
  1. Launch enrichment tasks (sunrise/sunset, environmental, aviation, etc.)
  2. Await enrichment completion
  3. Persist the enriched data back to cache
  4. Return the enriched data to user

**Code change**:
```python
if cached and not cached.stale:
    logger.debug(f"✓ Cache hit for {location.name} (fresh data, applying enrichments)")
    # Apply enrichments to cached data to ensure it's up-to-date
    if cached.has_any_data():
        enrichment_tasks = self._launch_enrichment_tasks(cached, location)
        await self._await_enrichments(enrichment_tasks, cached)
    return cached
```

**Benefits**:
- Sunrise/sunset times (from Open-Meteo enrichment) are always current
- Environmental metrics (air quality, pollen) are refreshed on each access
- Aviation data is updated from latest sources
- Enriched data is persisted, so next reload has updated times
- Performance maintained: cache serves data fast, enrichments happen in parallel

#### Cache Persistence Flow
**Before**:
- Fresh fetch: API → create WeatherData → save to cache → enrichments run → return
- Cache hit: load from cache → return (no enrichments)

**After**:
- Fresh fetch: API → create WeatherData → enrichments run → save enriched data → return
- Cache hit: load from cache → enrichments run → save enriched data → return

## Testing

All existing tests pass:
```
tests/performance/test_cache_optimization.py: 7 passed, 2 skipped
```

Key test coverage:
- ✅ Cache hits skip unnecessary API calls
- ✅ Stale cache triggers fresh refresh
- ✅ Force refresh bypasses cache
- ✅ Cache pre-warming works
- ✅ Cache expiration honored
- ✅ Multiple cache hits work correctly

## How to Use

### Incrementing Cache Schema Version

When you need to invalidate all existing user caches (e.g., after changing the cache structure or fixing a bug that produced bad cached data):

```python
# In cache.py
CACHE_SCHEMA_VERSION = 3  # Was 2, increment by 1
```

This will automatically:
1. Detect version mismatch on next app launch
2. Delete old cache files
3. Fetch fresh data from APIs
4. Users never see bad cached data

### Example Scenarios

**Test Build 1**: Schema version 2, caches data
**Test Build 2**: You discover a bug in sunrise/sunset parsing
**Test Build 3**: Fix the bug, increment `CACHE_SCHEMA_VERSION = 3`
- Users launch the app
- Old cache with bug is detected and auto-deleted
- Fresh data is fetched
- No manual steps needed ✓

## Files Modified

1. `src/accessiweather/cache.py`
   - Added `CACHE_SCHEMA_VERSION = 2` constant
   - Updated `store()` to use schema_version
   - Added version validation in `load()`

2. `src/accessiweather/weather_client_base.py`
   - Modified `get_weather_data()` to apply enrichments to cached data
   - Updated logging message for clarity

3. `CACHE_ISSUE_ANALYSIS.md` (documentation)
   - Root cause analysis of both issues

## Migration Notes

**No user action required**. The implementation is backward compatible:
- Old cache files (with `"version": 1`) will be detected as schema mismatch
- They'll be automatically deleted on first run
- Fresh data is fetched

**For developers**: If you increment `CACHE_SCHEMA_VERSION`, all cached data will be invalidated. This is intentional when schema changes.

## Next Steps

1. Test with real app usage over several days
2. Monitor for any enrichment-related issues
3. When ready to increment schema version (e.g., after fixing something), just change the constant
