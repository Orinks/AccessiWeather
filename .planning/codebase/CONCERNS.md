# Codebase Concerns

**Analysis Date:** 2026-03-14

## Tech Debt

**Monolithic Weather Client Architecture:**
- Issue: `src/accessiweather/weather_client_base.py` (1399 lines) and `src/accessiweather/weather_client_nws.py` (1533 lines) are extremely large single files. They handle data fetching, parsing, enrichment, alerts, fusion, and parallel coordination all tightly coupled. Refactoring to modular architecture has begun (parallel coordinator, fusion engine) but primary logic remains monolithic.
- Files: `src/accessiweather/weather_client_base.py`, `src/accessiweather/weather_client_nws.py`, `src/accessiweather/weather_client_openmeteo.py`
- Impact: Difficult to test individual components in isolation, high cognitive load for changes, ripple effects when modifying data flow. New features (pollen, air quality, AQ fallback) add complexity without corresponding decomposition.
- Fix approach: Complete separation into: data fetching (pure API calls), parsing/validation (schema conversion), enrichment (external data fusion), and orchestration (coordination logic). Establish clear interfaces between layers.

**HTTP Client Lifecycle Management:**
- Issue: `src/accessiweather/weather_client_base.py` creates and reuses a single `httpx.AsyncClient` instance with lazy initialization and closure detection via `is_closed` attribute check. Client lifecycle is implicit—closed clients are detected at usage time, not proactively managed. No explicit shutdown hook during app lifecycle.
- Files: `src/accessiweather/weather_client_base.py` (lines 101, 159-179), `src/accessiweather/location_manager.py` (creates new clients with context managers)
- Impact: Potential resource leaks if HTTP client gets closed unexpectedly without reinit. Inconsistent patterns (lazy singleton vs. context managers) in different modules create confusion. App shutdown may leave pooled connections open briefly.
- Fix approach: Implement explicit lifecycle management with `async with` context managers at app startup/shutdown, or create a dedicated HTTP client manager class. Document expected shutdown sequence.

**Exception Handling Granularity:**
- Issue: Widespread use of bare `except Exception` catches in API clients (`src/accessiweather/api_client/core_client.py` lines 254-260, `src/accessiweather/weather_client_base.py` lines 336, 359, 407, 460, 589, 631) and enrichment flows. While fallback strategies exist (cached data), these catches are too broad and mask unexpected errors.
- Files: `src/accessiweather/api_client/core_client.py`, `src/accessiweather/weather_client_base.py`, `src/accessiweather/weather_client_nws.py`
- Impact: Silent failures in edge cases are hard to diagnose. Specific error types (encoding issues, malformed JSON) get lumped into generic fallback paths. Test coverage may miss error conditions because exceptions are swallowed.
- Fix approach: Replace broad `except Exception` with specific exception types (ValueError, json.JSONDecodeError, httpx.RequestError subclasses). Re-raise or log unrecoverable errors distinctly.

**Settings Dialog Complexity:**
- Issue: `src/accessiweather/ui/dialogs/settings_dialog.py` (2801 lines) is a monolithic dialog with 8+ tabs, mixing UI construction, event handling, validation, and persistence. Tab creation methods are ~50+ lines each with significant state management.
- Files: `src/accessiweather/ui/dialogs/settings_dialog.py`
- Impact: Any settings change touches a very large file. Testing individual settings tabs is difficult. Adding new settings requires navigating hundreds of lines of existing code. High risk of accidentally breaking unrelated settings.
- Fix approach: Extract each tab into a separate tab panel class with focused responsibilities. Use composition instead of monolithic creation.

**Global State in Secure Storage:**
- Issue: `src/accessiweather/config/secure_storage.py` uses module-level globals (`_keyring_module`, `_keyring_checked`, `_keyring_available`) to cache keyring availability and module reference. While lazy-loading improves startup (defers 86ms keyring import), global state can cause subtle ordering dependencies.
- Files: `src/accessiweather/config/secure_storage.py` (lines 17-18, 31-40, 188-217)
- Impact: In tests or environments with multiple app instances, cached availability state might not reflect actual keyring status. Reset logic exists but requires explicit calls.
- Fix approach: Consider thread-safe lazy initialization pattern or contextvars if multi-instance scenarios become real.

**Parallel Fetch Coordinator Zip Safety:**
- Issue: `src/accessiweather/weather_client_parallel.py` line 117 uses `zip(tasks, task_results, strict=False)`. The `strict=False` parameter means mismatched tuple lengths silently drop results without warning. If task creation logic diverges from result processing, data loss goes undetected.
- Files: `src/accessiweather/weather_client_parallel.py` (line 117)
- Impact: Subtle data loss if task list and result list lengths differ. This could happen if a task creation branch is removed but result handler branch isn't updated.
- Fix approach: Change `strict=False` to `strict=True` to catch tuple length mismatches. Handle potential errors explicitly.

---

## Known Bugs

**AFD Discussion Fetch Isolation (Fixed but Monitor):**
- Symptoms: Weather update notifications were missing AFD discussion content when forecasts were fetched. Notifications showed weather update but AFD summary was absent or stale.
- Files: `src/accessiweather/weather_client_base.py` (data fetching coordination), `src/accessiweather/services/national_discussion_scraper.py` (AFD fetch)
- Trigger: Rapid consecutive weather updates (< AFD fetch latency)
- Status: Fixed in commit ababc1e6 - AFD discussion fetch now isolated from forecast fetch. Monitor for regression if refactoring coordination logic.

**NWS Alert Cancel Detection (Fixed but Monitor):**
- Symptoms: False alert cancel+reissue pairs where alerts appeared to be cancelled then reissued despite being continuous.
- Files: `src/accessiweather/alert_manager.py`, `src/accessiweather/weather_client_alerts.py`
- Trigger: Relying solely on alert ID presence/absence; NWS sometimes removes then re-adds alerts during updates.
- Status: Fixed in commit 12956f02 - now uses NWS cancel endpoint for genuine cancellation detection. Verify cancel endpoint reliability in edge cases.

**Stale Notification Suppression (Fixed but Risk):**
- Symptoms: First app launch after update shows notifications for old alerts from cache (false positives).
- Files: `src/accessiweather/alert_manager.py` (first-run detection), cache initialization
- Trigger: Initial alert load from offline cache before user location is set
- Status: Fixed in commit d02af87b with skip logic on first load. Risk: This skip logic is fragile—it depends on accurate "first load" detection which involves state management across shutdown/startup.

---

## Security Considerations

**API Key Exposure via Logging:**
- Risk: While logging generally masks API keys (e.g., `src/accessiweather/config/secure_storage.py` line 70 logs "Securely stored credential for {username}"), debug logging at INFO level could inadvertently log full URLs containing query parameters with API keys.
- Files: `src/accessiweather/weather_client_base.py` (logging of URLs), `src/accessiweather/api_client/core_client.py` (error logging with URLs)
- Current mitigation: API key stored in keyring, not in config files. URLs with sensitive params are generally not logged.
- Recommendations: Audit all logger calls in API modules to ensure query params are stripped before logging. Add a utility function to sanitize URLs before logging.

**Keyring Fallback Silent Failure:**
- Risk: If system keyring is unavailable (e.g., headless server, broken keyring daemon), `is_keyring_available()` returns False and app gracefully degrades—but security implications of storing keys fallback location are unclear.
- Files: `src/accessiweather/config/secure_storage.py` (lines 191-217)
- Current mitigation: Graceful degradation warning logged. Test round-trip validates functionality.
- Recommendations: Document fallback behavior clearly. Consider refusing to run if API keys are required and keyring is unavailable rather than silently accepting insecure alternatives.

**Subprocess Execution Hardening:**
- Risk: `src/accessiweather/app.py` (lines 92-113) and `src/accessiweather/single_instance.py` (lines 194-204) invoke PowerShell and tasklist without explicit shell escaping. Arguments are passed positionally but could be vulnerable to injection if argument values are user-controlled.
- Files: `src/accessiweather/app.py`, `src/accessiweather/single_instance.py`
- Current mitigation: Arguments are app-controlled (not user input), `check=False` prevents exceptions from escalating.
- Recommendations: Use `shlex.quote()` for any user-influenced input. Document that these calls are safe only when arguments are hardcoded.

---

## Performance Bottlenecks

**Startup Keyring Import Delay:**
- Problem: System keyring module import takes ~86ms on initial access (`src/accessiweather/config/secure_storage.py` comment). If any startup code triggers keyring access before lazy-load, this blocks app initialization.
- Files: `src/accessiweather/config/secure_storage.py` (lines 21-40)
- Cause: Keyring module does system integration (D-Bus on Linux, Keychain API on macOS, registry on Windows) synchronously during import.
- Improvement path: Keep lazy-loading as-is. Monitor if startup profile shows keyring becoming critical path. If so, push keyring init to background task after UI is visible.

**Large File Processing (Settings Dialog Rendering):**
- Problem: `src/accessiweather/ui/dialogs/settings_dialog.py` (2801 lines) creates all 8 tabs upfront even if user only views 1-2. Each tab has dozens of controls.
- Files: `src/accessiweather/ui/dialogs/settings_dialog.py` (lines 46-61: `_create_*_tab()` methods)
- Cause: All tabs instantiated in `_create_ui()` before dialog is shown. No lazy/on-demand tab creation.
- Improvement path: Implement lazy tab creation—create tab panel only when first clicked. Cache after creation.

**Parallel Fetch Timeout Hardcoded:**
- Problem: `src/accessiweather/weather_client_parallel.py` line 35 and usage in `src/accessiweather/weather_client_base.py` line 679 hardcodes 5-second timeout. If one source is slow, entire fetch operation times out even if other sources complete.
- Files: `src/accessiweather/weather_client_parallel.py`, `src/accessiweather/weather_client_base.py`
- Cause: Single timeout for all sources; no per-source timeout adaptation.
- Improvement path: Make timeout configurable per source or implement adaptive timeout based on source history.

---

## Fragile Areas

**Alert State Deque Bounded History:**
- Files: `src/accessiweather/alert_manager.py` (lines 74-76)
- Why fragile: Alert change history is limited to `ALERT_HISTORY_MAX_LENGTH` (defined in `src/accessiweather/constants.py`). If an alert cycles through many changes (e.g., updates then escalation then update again), older changes fall off the deque silently. Change detection logic depends on history—if history is lost, escalation detection may break.
- Safe modification: Before modifying `ALERT_HISTORY_MAX_LENGTH`, audit all code paths that rely on complete history (especially escalation detection, change notification). Write tests that exercise the max-length boundary.
- Test coverage: `tests/test_alert_manager.py` should have tests for bounded history behavior.

**NWS Station Selection Heuristic:**
- Files: `src/accessiweather/weather_client_nws.py` (lines 67-84: `_station_sort_key`)
- Why fragile: Station preference logic uses priority (ICAO K-code stations > other 4-letter > others) and distance sorting. If NWS API schema changes (e.g., stationIdentifier renamed), parsing silently returns None and stations sort by distance only, potentially selecting distant/poor-quality stations.
- Safe modification: Add explicit error logging if stationIdentifier is missing. Write tests with malformed station data. Consider fallback station selection logic.
- Test coverage: Need integration tests with real NWS API responses and edge cases (missing identifiers, no nearby stations).

**QC Code Measurement Validation:**
- Files: `src/accessiweather/weather_client_nws.py` (lines 87-108: `_scrub_measurements`, line 38: `VALID_QC_CODES`)
- Why fragile: Measurements with non-validating QC codes (anything not in `{"V", "C", None}`) are set to None. If NWS adds new valid QC codes, they'll be silently dropped. If a measurement's QC field is missing entirely, it's treated as valid (None is in VALID_QC_CODES).
- Safe modification: Add logging when measurements are scrubbed. Document what each QC code means. Add a configuration option to override valid codes if needed.
- Test coverage: Test cases for unusual QC codes, missing QC fields.

**Mock Detection in HTTP Client:**
- Files: `src/accessiweather/weather_client_base.py` (lines 172-177, 190-191)
- Why fragile: Code checks `isinstance(client, Mock)` and inspects `__aenter__` attribute to detect mocked clients and extract the actual mock. This is brittle—if Mock implementation changes or a different mocking library is used, detection fails silently.
- Safe modification: Use explicit test mode flag instead of isinstance checks. Configure HTTP client differently in test vs. production via dependency injection.
- Test coverage: Tests must verify both mocked and real HTTP client paths work.

**Timezone-Aware Datetime Parsing:**
- Files: `src/accessiweather/weather_client_nws.py` (lines 41-64: `_parse_iso_datetime`)
- Why fragile: Assumes NWS timestamps ending with "Z" should be treated as UTC. If NWS changes format or returns non-UTC timestamps, this silently converts to wrong timezone. Fallback to UTC assumption for naive datetimes could cause display bugs.
- Safe modification: Add explicit timezone validation/logging. Test with various NWS timestamp formats. Document assumptions about NWS time representation.
- Test coverage: Unit tests with various ISO 8601 formats, missing timezone info, unusual formats.

---

## Scaling Limits

**HTTP Connection Pool Hardcoded Size:**
- Current capacity: `max_connections=30`, `max_keepalive_connections=15` (src/accessiweather/weather_client_base.py line 170)
- Limit: If app scales to fetching 30+ concurrent requests (e.g., monitoring 30+ locations simultaneously), pool exhaustion occurs. Additional requests queue or timeout.
- Scaling path: Make pool size configurable. Monitor actual concurrent request patterns. If needed, implement multi-client architecture (separate client per location or request type).

**Alert History Deque Bounded:**
- Current capacity: `ALERT_HISTORY_MAX_LENGTH` (likely 10-20, value in `src/accessiweather/constants.py`)
- Limit: If user monitors 100+ alerts that frequently change, history will be pruned, potentially losing escalation tracking data.
- Scaling path: Consider persistent alert history store (JSON or lightweight database) instead of in-memory bounded deque.

**Cache TTL Fixed Default:**
- Current capacity: 5-minute default TTL (`src/accessiweather/cache.py` line 49)
- Limit: Cache hit rate degrades if weather is requested more frequently than 5 minutes or if data freshness requirements tighten.
- Scaling path: Make TTL configurable per data source. Implement adaptive TTL based on data staleness/change frequency.

---

## Dependencies at Risk

**httpx Upgrade Risk (Current: 0.28.1):**
- Risk: Major version jump from 0.x could introduce breaking changes in async client API, timeout handling, or connection pool behavior. The manual Mock inspection logic (`src/accessiweather/weather_client_base.py` lines 172-177) may break if httpx changes client construction.
- Impact: AsyncClient interface changes, timeout config format, context manager behavior, connection limits.
- Migration plan: Pin httpx version in pyproject.toml. Before upgrading, audit all httpx usage in: weather_client_base, api_client, location_manager, services. Verify Mock detection still works or remove in favor of dependency injection.

**wxPython Tight Binding (Critical for UI):**
- Risk: Application is now tightly coupled to wxPython (switched from Toga). wxPython is mature but less accessible than Toga. Any major version upgrade (4.x to 5.x) could break screen reader integration or event handling.
- Impact: Dialog focus management, accessibility labels, event dispatching, platform-specific quirks.
- Migration plan: Document all wxPython accessibility assumptions (JAWS, NVDA, Narrator compatibility). Create abstraction layer over wxPython if future switch to another framework is possible. Add accessibility regression tests to CI.

**Keyring Availability Uncertainty:**
- Risk: System keyring (Python keyring module) is optional—app degrades gracefully if unavailable. However, this silently reduces security. If API keys are required for critical features, graceful degradation may be dangerous.
- Impact: API keys not stored securely, potentially exposed if config files are accessible.
- Migration plan: Make keyring availability explicit in startup checks. Warn user if API keys are required but keyring unavailable. Consider alternative secure storage (config file encryption) if keyring can't be required.

---

## Missing Critical Features

**Structured Logging Not Implemented:**
- Problem: All logging uses basic Python logging with no structured fields. Hard to analyze logs programmatically, difficult to correlate events across components.
- Files: All modules use `logger.info()`, `logger.error()` with string formatting
- Blocks: Operational debugging in production, log aggregation/analysis, performance tracing
- Solution: Migrate to structured logging library (e.g., `structlog`) with context propagation.

**Health Check Mechanism Absent:**
- Problem: No built-in health check for API client status, alert system state, or notification delivery. App may appear healthy while core services are degraded.
- Files: Would need implementation in app lifecycle
- Blocks: Monitoring, automated recovery, user notification of service issues
- Solution: Implement async health check endpoints returning status of each service tier.

**Graceful Degradation Lacks Visibility:**
- Problem: When API sources fail and app falls back to cached data, user has no indication that displayed data is stale or from cache.
- Files: Display/presentation layer (`src/accessiweather/display/`), UI main window
- Blocks: User trust, informed decisions based on data freshness
- Solution: Add visual indicators (badges, colors, timestamps) showing data source and freshness.

---

## Test Coverage Gaps

**Full Async/Await Integration Not Tested:**
- What's not tested: End-to-end async operations from app startup through background weather update cycles. Tests either mock all async operations or test in isolation.
- Files: `src/accessiweather/weather_client_base.py` (main async orchestration), `src/accessiweather/app.py` (background task lifecycle), `tests/integration/`
- Risk: Deadlocks, race conditions, or event loop exhaustion may lurk undetected. Changes to async coordination logic could break real-world usage.
- Priority: **High** - Background updates are core feature.

**NWS API Integration with Unreliable Network:**
- What's not tested: NWS API behavior under slow/flaky network conditions. VCR cassettes provide fast recorded responses, not realistic latency/retries.
- Files: `src/accessiweather/weather_client_nws.py`, `tests/integration/`
- Risk: Timeout handling, connection error recovery, and retry logic may fail under real slow networks.
- Priority: **Medium** - Affects field users on weak connections.

**Settings Persistence and Migration:**
- What's not tested: Loading settings from old config versions, applying defaults to missing fields, persistence across app crashes.
- Files: `src/accessiweather/config/config_manager.py`, `src/accessiweather/models/config.py`
- Risk: Settings loss or corruption during upgrade.
- Priority: **Medium** - User data loss risk.

**Error Recovery in Alert Pipeline:**
- What's not tested: Alert manager behavior when NWS API fails, when notifications fail to send, when cache is corrupted.
- Files: `src/accessiweather/alert_manager.py`, `src/accessiweather/alert_notification_system.py`
- Risk: Alerts lost silently, repeated notifications, notification daemon crashes unhandled.
- Priority: **High** - Core safety feature.

**UI Focus Management and Keyboard Navigation:**
- What's not tested: Screen reader tab order, focus trapping in dialogs, keyboard shortcuts, focus restoration after dialogs close.
- Files: `src/accessiweather/ui/main_window.py`, `src/accessiweather/ui/dialogs/*.py`
- Risk: Screen reader users cannot navigate UI, focus lost in complex dialogs.
- Priority: **High** - Accessibility is a core requirement.

**Cross-Platform Behavior (Windows vs. macOS vs. Linux):**
- What's not tested: Path handling differences, process-checking behavior, notification display, file permission quirks per platform.
- Files: `src/accessiweather/app.py` (Windows shortcuts, AppUserModelID), `src/accessiweather/single_instance.py` (cross-platform process checks)
- Risk: Features work on dev platform (likely Windows/macOS) but break on Linux or vice versa.
- Priority: **Medium** - Affects some users.

---

## Architectural Debt

**Multiple API Client Implementations Not Unified:**
- Issue: Three parallel API client architectures exist: old `src/accessiweather/api/` (base_wrapper, openmeteo_wrapper), new `src/accessiweather/api_client/` (core_client, nws client), and weather_client modules. They don't share interfaces.
- Files: `src/accessiweather/api/`, `src/accessiweather/api_client/`, `src/accessiweather/weather_client_*.py`
- Impact: Inconsistent error handling, different timeout strategies, no unified client factory. Adding new sources requires understanding multiple patterns.
- Fix approach: Unify under single client architecture with clear abstract base. Standardize error handling, timeouts, and caching.

**Refactor Phase 1 Incomplete:**
- Issue: Refactoring mentioned as "monolith-phase1" branch indicates partial completion. Parallel coordinator extracted but main orchestration still in monolithic weather_client_base.
- Files: `src/accessiweather/weather_client_base.py` (still 1399 lines despite extraction)
- Impact: Risk of half-finished refactor where some code uses new patterns and some uses old, creating inconsistency.
- Fix approach: Complete extraction to data layer (fetching) + parsing layer + enrichment layer + orchestration layer. Remove intermediate legacy patterns.

---

*Concerns audit: 2026-03-14*
