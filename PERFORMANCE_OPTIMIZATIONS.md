# Weather Data Refresh Performance Optimizations

## Summary

This document describes performance optimizations implemented to speed up weather data refresh operations in AccessiWeather.

## Problem

Weather data refresh was slow due to several inefficiencies:

1. **Multiple HTTP Client Creations**: Each API call created a new `httpx.AsyncClient`, which is expensive
   - NWS data fetching alone created 4 separate clients per refresh
   - Each client initialization has overhead for connection setup

2. **Sequential API Calls**: Weather data was fetched sequentially
   - Current conditions → Forecast → Alerts → Hourly forecast
   - Total time = sum of all individual API call times

3. **Duplicate Grid Point Requests**: NWS grid point was fetched multiple times
   - Once for current conditions
   - Once for forecast/discussion
   - Once for hourly forecast

4. **No Connection Pooling**: HTTP clients were destroyed after each use
   - Lost benefits of HTTP keep-alive and connection reuse

5. **Sequential Enrichment**: In auto mode, enrichment calls ran sequentially
   - Sunrise/sunset → NWS discussion → Visual Crossing alerts

## Solution

### 1. HTTP Client Reuse

Added a reusable `httpx.AsyncClient` with connection pooling:

```python
class WeatherClient:
    def __init__(self, ...):
        self._http_client: httpx.AsyncClient | None = None
    
    def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create the reusable HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return self._http_client
```

**Benefits:**
- Single client instance reused across all API calls
- Connection pooling with up to 10 keep-alive connections
- Reduced overhead from client initialization

### 2. Parallel API Calls with asyncio.gather()

Created new functions to fetch all data in parallel:

#### NWS Parallel Fetching
```python
async def get_nws_all_data_parallel(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient,
) -> tuple[CurrentConditions | None, Forecast | None, str | None, WeatherAlerts | None, HourlyForecast | None]:
    # Fetch grid data once
    grid_data = await fetch_grid_data(...)
    
    # Fetch all other data in parallel, reusing grid_data
    current, (forecast, discussion), alerts, hourly = await asyncio.gather(
        get_nws_current_conditions(...),
        get_nws_forecast_and_discussion(..., grid_data=grid_data),
        get_nws_alerts(...),
        get_nws_hourly_forecast(..., grid_data=grid_data),
    )
```

#### Open-Meteo Parallel Fetching
```python
async def get_openmeteo_all_data_parallel(
    location: Location,
    openmeteo_base_url: str,
    timeout: float,
    client: httpx.AsyncClient,
) -> tuple[CurrentConditions | None, Forecast | None, HourlyForecast | None]:
    # Fetch all data in parallel
    current, forecast, hourly = await asyncio.gather(
        get_openmeteo_current_conditions(...),
        get_openmeteo_forecast(...),
        get_openmeteo_hourly_forecast(...),
    )
```

**Benefits:**
- API calls run concurrently instead of sequentially
- Total time ≈ max(individual call times) instead of sum
- Grid data is fetched once and reused

### 3. Grid Data Caching

Modified NWS functions to accept optional `grid_data` parameter:

```python
async def get_nws_forecast_and_discussion(
    location: Location,
    nws_base_url: str,
    user_agent: str,
    timeout: float,
    client: httpx.AsyncClient | None = None,
    grid_data: dict[str, Any] | None = None,  # New parameter
) -> tuple[Forecast | None, str | None]:
    # Fetch grid data only if not provided
    if grid_data is None:
        grid_data = await fetch_grid_data(...)
```

**Benefits:**
- Eliminates duplicate grid point API calls
- Reduces API requests from 4 to 1 for grid data

### 4. Parallel Enrichment in Auto Mode

Parallelized enrichment and post-processing tasks:

```python
# Smart enrichment in auto mode (parallel)
if self.data_source == "auto":
    await asyncio.gather(
        self._enrich_with_sunrise_sunset(weather_data, location),
        self._enrich_with_nws_discussion(weather_data, location),
        self._enrich_with_visual_crossing_alerts(weather_data, location),
        return_exceptions=True,
    )

# Post-processing tasks (parallel)
await asyncio.gather(
    self._populate_environmental_metrics(weather_data, location),
    self._merge_international_alerts(weather_data, location),
    return_exceptions=True,
)
```

**Benefits:**
- Enrichment calls run concurrently
- Faster overall data processing

### 5. Async Context Manager Support

Added context manager support for proper resource cleanup:

```python
async def close(self) -> None:
    """Close the HTTP client and release resources."""
    if self._http_client is not None and not self._http_client.is_closed:
        await self._http_client.aclose()
        self._http_client = None

async def __aenter__(self):
    return self

async def __aexit__(self, exc_type, exc_val, exc_tb):
    await self.close()
```

**Usage:**
```python
async with WeatherClient() as client:
    weather_data = await client.get_weather_data(location)
```

## Performance Impact

### Expected Improvements

For a typical NWS data fetch with 4 API calls (grid, current, forecast, hourly) at 200ms each:

**Before (Sequential):**
- HTTP client creation overhead: ~50ms × 4 = 200ms
- API calls: 200ms + 200ms + 200ms + 200ms = 800ms
- **Total: ~1000ms (1 second)**

**After (Parallel):**
- HTTP client reuse: 0ms overhead (amortized)
- Grid data fetch: 200ms (once)
- Parallel API calls: max(200ms, 200ms, 200ms) = 200ms
- **Total: ~400ms (0.4 seconds)**

**Speedup: ~2.5x faster**

With enrichment in auto mode (3 additional calls):

**Before:** 1000ms + (3 × 200ms) = 1600ms
**After:** 400ms + max(200ms, 200ms, 200ms) = 600ms

**Speedup: ~2.7x faster**

### Actual Performance

Actual speedup will vary based on:
- Network latency
- API response times
- Number of concurrent requests
- Connection reuse efficiency

In practice, users should see:
- **2-3x faster** weather refreshes for US locations (NWS)
- **2x faster** for international locations (Open-Meteo)
- **Improved responsiveness** during app usage

## Testing

Performance tests are included in `tests/test_weather_client_performance.py`:

1. **HTTP Client Reuse**: Verifies the same client instance is reused
2. **Context Manager**: Tests proper resource cleanup
3. **Parallel vs Sequential**: Demonstrates parallel execution is faster
4. **Enrichment Parallelism**: Confirms enrichment calls run concurrently

Run tests with:
```bash
pytest tests/test_weather_client_performance.py -v
```

## Backward Compatibility

All changes are backward compatible:
- Existing API signatures remain unchanged (new parameters are optional)
- WeatherClient can still be used without context manager
- No changes required to existing code

## Future Improvements

Potential further optimizations:
1. **Response Caching**: Cache API responses for short periods (30-60 seconds)
2. **Request Deduplication**: Prevent duplicate concurrent requests for same data
3. **Lazy Loading**: Only fetch data types that are actually displayed
4. **Progressive Rendering**: Display data as it becomes available

## Files Changed

- `src/accessiweather/weather_client.py`: Main WeatherClient with parallel fetching
- `src/accessiweather/weather_client_nws.py`: NWS parallel fetching and client reuse
- `src/accessiweather/weather_client_openmeteo.py`: Open-Meteo parallel fetching and client reuse
- `tests/test_weather_client_performance.py`: Performance tests
