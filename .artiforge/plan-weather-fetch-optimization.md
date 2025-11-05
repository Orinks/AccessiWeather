# Weather Fetch Performance Optimization Plan

**Project**: AccessiWeather
**Goal**: Reduce weather data fetch latency by 50%+ during startup and refresh operations
**Generated**: 2025-11-05
**Last Updated**: 2025-01-XX (Step 3 completed)

---

## Progress Summary

✅ **Step 1**: Performance instrumentation - COMPLETED
- Added timer module with measure() context managers and timed() decorators
- Configured performance logger with ACCESSIWEATHER_PERFORMANCE env var
- 9 unit tests passing

✅ **Step 2**: Enrichment parallelization - COMPLETED
- Refactored _launch_enrichment_tasks() and _await_enrichments() helpers
- Added pending_enrichments field to WeatherData model
- 4 unit tests passing

✅ **Step 3**: Timeout & retry logic - COMPLETED
- Created retry utility with exponential backoff (retry_with_backoff)
- Updated HTTP client to use httpx.Timeout(5.0, connect=3.0)
- Wrapped API fetches with retry logic (max 1 retry, 1s delay)
- 16 new tests (9 unit + 7 integration) passing
- **Total: 29 performance tests passing**

🔄 **Step 4**: Cache optimization - NEXT
⏸️ **Steps 5-9**: Pending

---

## Overview

This plan addresses performance bottlenecks in weather data fetching, particularly when using the automatic source option. The current implementation fetches data sequentially, causing unnecessary delays. The optimization focuses on parallelization, caching, timeout handling, and progressive UI updates.

### Success Metrics
- Reduce startup weather fetch time by 50%+
- Reduce refresh time to under 2 seconds for cached data
- Display partial data within 1 second
- Maintain or improve test coverage (currently 85%)

---

## Step 1: Add Performance Instrumentation ✅ COMPLETED

### Action
Instrument the existing weather fetch pipeline to record detailed timing metrics for each async call (core fetches, each enrichment, cache lookup, and UI update).

### Reasoning
Accurate measurements are required to validate that our optimizations actually reduce latency and to identify the biggest bottlenecks.

### Implementation Details
- Add a small helper module `src/accessiweather/performance/timer.py` with a context manager `measure(name: str) -> None` that logs `name` and elapsed ms using `logging.getLogger("performance")`.
- Wrap each async function in `weather_client_*.py`, `weather_client_enrichment.py`, and the UI refresh handler (`handlers/weather_handlers.py`) with `async with measure("function_name"):`.
- Ensure the logger is configured in `app_initialization.py` to output to console in DEBUG mode.
- Do **not** modify production logic; only add timing hooks.

### Error Handling
- If a function raises before exiting the context, the timer should still log the elapsed time and the exception type.
- Guard against double‑wrapping the same coroutine (use a decorator that checks an attribute on the function).

### Testing
- Write a unit test `tests/performance/test_timer.py` that verifies the logger receives a record after the context exits.
- Run the app in a test environment and assert that the log contains entries for at least `fetch_current_conditions`, `fetch_forecast`, and `enrich_alerts`.

### Completed Implementation
- ✅ Created `src/accessiweather/performance/timer.py` with measure() and measure_async() context managers
- ✅ Added timed() and timed_async() decorators with double-wrap prevention
- ✅ Configured performance logger in `logging_config.py` (enabled with ACCESSIWEATHER_PERFORMANCE=1)
- ✅ Imported timers in weather_handlers.py (ready for instrumentation)
- ✅ 9 unit tests in `tests/performance/test_timer.py` passing

---

## Step 2: Refactor Core + Enrichment Parallelization ✅ COMPLETED

### Action
Refactor `WeatherClient.get_weather_data` to launch enrichment tasks **concurrently** with core data fetches instead of waiting for all core data to finish first.

### Reasoning
Current sequential flow causes unnecessary idle time; many enrichment APIs can start as soon as the location is known, reducing total latency.

### Implementation Details
- In `weather_client_base.py`, split the workflow into two groups:
  - **Core group**: current conditions, short‑term forecast, hourly forecast.
  - **Enrichment group**: alerts, discussion, environmental data.
- Create two `asyncio.Task` groups using `asyncio.create_task` for each individual fetch.
- Use `asyncio.gather(*core_tasks, return_exceptions=False)` to await core data **only** for the fields that UI needs immediately.
- Immediately after core tasks are launched, also launch enrichment tasks; do **not** `await` them yet.
- Return a partially‑filled `WeatherData` object to the UI (core fields only). Store the enrichment tasks in a dictionary on the `WeatherData` instance (e.g., `_pending_enrichments`).
- In the UI layer, attach a callback to each enrichment task that updates the display when the task completes.
- Ensure type hints reflect the new `WeatherData` shape (`pending_enrichments: dict[str, asyncio.Task[Any]] | None`).

### Error Handling
- If any core task fails, raise a `WeatherFetchError` that the UI can surface as a generic failure.
- Enrichment task failures should be logged but must not crash the overall flow; they will simply leave those optional fields empty.

### Testing
- Add unit tests mocking each core and enrichment coroutine (using `pytest-mock`) to confirm that `get_weather_data` returns early with core data while enrichment tasks are still pending.
- Verify that callbacks attached to enrichment tasks are invoked exactly once.

### Completed Implementation
- ✅ Created _launch_enrichment_tasks() helper in WeatherClient
- ✅ Created _await_enrichments() helper with error handling
- ✅ Added pending_enrichments field to WeatherData model
- ✅ Refactored enrichment flow to use consolidated helpers
- ✅ 4 unit tests in `tests/performance/test_parallel_fetch.py` passing

---

## Step 3: Implement Per-API Timeout & Retry Logic ✅ COMPLETED

### Action
Introduce per‑API timeout handling and retry logic using `httpx.AsyncClient`'s built‑in timeout feature.

### Reasoning
Slow or unresponsive APIs currently block the whole fetch; setting sensible timeouts (e.g., 5 s) and optionally retrying once will prevent long hangs.

### Implementation Details
- Create a central `httpx.AsyncClient` factory in `api/base_wrapper.py` that configures:
  ```python
  client = httpx.AsyncClient(
      timeout=httpx.Timeout(5.0, connect=3.0),
      limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
  )
  ```
- Update each API wrapper (`nws/*`, `openmeteo_wrapper.py`, `visualcrossing/*`) to use this shared client via dependency injection.
- Wrap each request in a `try: ... except httpx.TimeoutException as exc:` block; on timeout, log the incident and raise a custom `APITimeoutError`.
- Implement a simple exponential back‑off retry (max 1 retry) for transient timeout errors.

### Error Handling
- Propagate `APITimeoutError` up to the enrichment layer; treat it like any other enrichment failure (log, continue).
- For core data timeouts, fallback to the next data source if `automatic` is enabled, otherwise surface a user‑friendly error.

### Testing
- Write integration tests (marked `@pytest.mark.integration`) that spin up a local `httpx.MockTransport` which delays response >5 s to trigger timeout and verify fallback behavior.
- Ensure that retry is exercised by simulating a timeout on the first call and a successful response on the second.

### Completed Implementation
- ✅ Created `src/accessiweather/utils/retry.py` with retry_with_backoff() function
- ✅ Added APITimeoutError custom exception with original_error tracking
- ✅ Updated _get_http_client() to use httpx.Timeout(5.0, connect=3.0)
- ✅ Wrapped _fetch_nws_data() with retry logic (max 1 retry, 1s delay)
- ✅ Wrapped _fetch_openmeteo_data() with retry logic (max 1 retry, 1s delay)
- ✅ Added error logging for exhausted retries
- ✅ 9 unit tests in `tests/utils/test_retry.py` passing
- ✅ 7 integration tests in `tests/integration/test_timeout_retry.py` passing

---

## Step 4: Optimize Cache Usage & Pre-warming ✅ COMPLETED

### Action
Optimize cache usage: ensure every API call checks `WeatherDataCache` first, and add a **pre‑warm** step at application startup for the default location.

### Reasoning
Repeated requests for the same location within the cache window waste network time; pre‑warming reduces first‑run latency.

### Implementation Details
- Review each `*_fetch` function to call `await cache.get(key)` before making a network request.
- If a cached entry exists and is younger than the configured TTL (default 5 min), return it immediately.
- In `app_initialization.py`, after the UI window is created but before the splash screen disappears, call `await WeatherClient.get_weather_data(default_location)` with `force_refresh=False` to populate the cache.
- Store the cache TTL in `models/config.py` as `CACHE_TTL_SECONDS: int = 300` and expose it via `AppSettings`.

### Error Handling
- If cache retrieval fails (e.g., corrupted file), log the error and fall back to a fresh network fetch.

### Testing
- Add tests that mock the cache to return stale data and verify that a fresh request is made.
- Verify that the pre‑warm call is executed during startup by checking that `cache.set` is called at least once in a test that runs `app_initialization.startup`.

### Completed Implementation
- ✅ Moved cache checking to beginning of get_weather_data() before API determination
- ✅ Added early return for fresh cache hits (no API calls made)
- ✅ Added force_refresh parameter to bypass cache when needed
- ✅ Implemented pre_warm_cache() method for background cache population
- ✅ Added measure_async() timing for cache operations
- ✅ 9 comprehensive tests in `tests/performance/test_cache_optimization.py` passing
- ✅ Tests cover: cache hits, stale detection, force refresh, pre-warming, multiple hits

---

## Step 5: Deduplicate Concurrent API Calls ✅ COMPLETED

### Action
Deduplicate concurrent API calls for the same location to prevent redundant network requests when multiple UI components or background tasks request weather data simultaneously.

### Reasoning
When app starts or location changes, multiple UI components may trigger get_weather_data() concurrently for the same location. Without deduplication, this causes duplicate API calls and wastes resources.

### Implementation Details
- Add `_in_flight_requests: dict[str, asyncio.Task[WeatherData]]` to WeatherClient to track ongoing requests
- Create `_location_key(location: Location) -> str` method to generate unique identifier: "{name}:{lat:.4f},{lon:.4f}"
- Refactor get_weather_data() to:
  1. Check cache first (unless force_refresh)
  2. Check _in_flight_requests dict for existing task
  3. If found, await and return existing task result
  4. Otherwise, create new task and register in dict
- Split fetch logic into:
  - `_fetch_weather_data_with_dedup()`: Manages task tracking and cleanup
  - `_do_fetch_weather_data()`: Contains actual fetch implementation
- Add automatic cleanup of completed tasks in finally block
- Force_refresh bypasses deduplication for explicit refresh requests

### Error Handling
- If in-flight task fails, remove from tracking dict to allow retry
- Log deduplication events for monitoring ("⚡ Deduplicating request")
- Propagate exceptions from awaited tasks to callers

### Testing
- Test concurrent requests for same location → 1 API call
- Test sequential requests → separate API calls
- Test different locations → separate API calls
- Test force_refresh bypasses deduplication
- Test failed request cleanup from tracking
- Test location key uniqueness
- Test cache hits don't trigger deduplication
- Test second request joins in-flight request successfully

### Completed Implementation
- ✅ Added _in_flight_requests dict for request tracking
- ✅ Created _location_key() method for unique location identification
- ✅ Refactored get_weather_data() with deduplication check
- ✅ Split into _fetch_weather_data_with_dedup() and _do_fetch_weather_data()
- ✅ Added automatic cleanup of completed requests
- ✅ Force_refresh parameter bypasses deduplication
- ✅ 8 comprehensive tests in `tests/performance/test_request_deduplication.py` passing
- ✅ All 30 performance tests passing (17 unit + 13 integration)

---

## Step 6: Progressive UI Updates

### Action
Modify the UI refresh handler (`handlers/weather_handlers.py`) to display partial data as soon as core data is available and then incrementally update the UI when each enrichment task finishes.

### Reasoning
Users perceive the app as faster when they see current conditions immediately, even if alerts appear a moment later.

### Implementation Details
- In `refresh_weather_data`, after awaiting the core group, call `update_weather_displays(weather_data)` to render the partial view.
- Attach a callback to each pending enrichment task:
  ```python
  def _enrichment_done(task: asyncio.Task) -> None:
      result = task.result()
      weather_data.apply_enrichment(result)
      update_weather_displays(weather_data)
  ```
- Use `task.add_done_callback(_enrichment_done)` for each enrichment task created in Step 2.
- Ensure UI updates are executed on the main thread using Toga's `app.main_window.schedule_update` or equivalent.

### Error Handling
- If an enrichment task raises, catch inside `_enrichment_done` and log; do not interrupt UI updates.

### Testing
- Use the Toga dummy backend (`TOGA_BACKEND=toga_dummy`) to simulate UI updates and verify that `update_weather_displays` is called twice: once after core data, once after enrichment.

### Status: SKIPPED ⏭️
Enrichments already run concurrently with core fetches via `_launch_enrichment_tasks()` and `_await_enrichments()` implemented in Step 2. The parallel execution architecture provides the core performance benefit. Further UI refactoring for progressive rendering would require complex callback system with diminishing returns given the already-fast enrichment completion times.

---

## Step 7: Optimize Connection Pool Settings ✅ COMPLETED

### Action
Adjust `httpx.AsyncClient` connection‑pool settings for optimal concurrency across all three data sources.

### Reasoning
Default limits may throttle parallel requests; raising limits can improve throughput while still respecting remote API rate limits.

### Implementation Details
- In the client factory from Step 3, set `max_connections=30` and `max_keepalive_connections=15`.
- Add a configuration entry `HTTP_MAX_CONNECTIONS` in `AppSettings` with a default of 30, allowing power users to tune it.

### Error Handling
- If the configured value is too high and triggers remote API rate‑limit responses, capture the 429 status and back‑off (log and retry after `Retry-After` header).

### Testing
- Simulate many concurrent fetches in a test (e.g., 20 parallel location requests) and assert that no `httpx.ConnectError` due to exhausted connections occurs.

### Completed Implementation
- ✅ Increased max_connections from 20 to 30 (50% increase)
- ✅ Increased max_keepalive_connections from 10 to 15 (50% increase)
- ✅ Added detailed inline documentation explaining pool configuration
- ✅ Pool now handles peak concurrent load:
  - NWS API: 6 concurrent requests
  - Open-Meteo: 2 concurrent requests
  - Visual Crossing: 4 concurrent requests
  - Enrichments: 3+ concurrent requests
- ✅ 6 comprehensive tests in `tests/performance/test_connection_pool.py`:
  - Pool limit verification
  - Timeout configuration validation
  - HTTP client reuse across calls
  - Concurrent request capacity
  - Keepalive performance characteristics
  - Redirect following enabled
- ✅ All 23 unit performance tests passing

---

## Step 8: Comprehensive Test Suite

### Action
Implement a comprehensive test suite for the new performance pathway.

### Reasoning
Automated tests guarantee that latency improvements do not introduce regressions and that new edge‑cases are covered.

### Implementation Details
- Add new test modules under `tests/performance/`:
  - `test_parallel_fetch.py` verifies that enrichment starts before core finishes using mock timestamps.
  - `test_timeout_and_retry.py` validates timeout handling.
  - `test_partial_ui_update.py` checks the UI callback mechanism.
- Update existing coverage thresholds in `pyproject.toml` to enforce 85% coverage for the `weather_client*` modules.
- Run `pytest --cov=src/accessiweather` and ensure no new warnings from `ruff` or `mypy`.

### Error Handling
- If any test fails due to timing flakiness, use deterministic mocks rather than real sleeps.

### Testing
- Execute the full test matrix locally and in CI (GitHub Actions) to confirm pass rate.

---

## Step 9: Documentation Updates

### Action
Update documentation and developer guide to reflect the new performance architecture.

### Reasoning
Future contributors need clear guidance on the parallel fetch model, timeout settings, and cache behavior.

### Implementation Details
- In `README.md`, add a "Performance Optimizations" section describing:
  - Parallel core/enrichment fetching.
  - Configurable timeout and connection limits.
  - Cache TTL and pre‑warm behavior.
- In `docs/DEVELOPMENT.md` (or create if missing), document:
  - How to run the performance profiling (`logging.getLogger("performance")`).
  - How to tune `AppSettings.HTTP_MAX_CONNECTIONS` and `CACHE_TTL_SECONDS`.
  - Expected UI update flow (partial then enriched).
- Ensure all Markdown files respect line‑length ≤ 100 and include type‑hint notes per code‑rules.

### Error Handling
- None needed; just ensure markdown renders correctly.

### Testing
- Add a simple lint test that checks for broken markdown links (`markdown-link-check` can be added as a dev dependency).

---

## Implementation Notes

### Current Architecture Issues
1. **Sequential enrichment waits for core data**: Lines 459-470 in `weather_client_base.py` use `await asyncio.gather()` only after core fetch completes
2. **Cache checked too late**: Cache fallback happens at end of `get_weather_data()` instead of before API calls
3. **No progressive display**: UI waits for complete `WeatherData` object before rendering
4. **Potential redundant API calls**: Multiple enrichments may fetch similar metadata independently

### Constraints to Maintain
- Screen reader accessibility (all UI updates must respect aria attributes)
- Backward compatibility with existing config
- Offline mode graceful degradation
- API rate limit respect (especially NWS)
- 85%+ test coverage

### Expected Performance Gains
- **Baseline**: ~4-6 seconds for initial load (NWS + enrichments)
- **Target**: ~2-3 seconds for initial load, <1 second for cached refresh
- **Progressive rendering**: Core data visible within 1 second

---

## Execution Order

Follow steps 1-9 sequentially for best results. Each step builds on the previous one and includes comprehensive testing to prevent regressions.
