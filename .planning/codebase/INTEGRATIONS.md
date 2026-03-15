# External Integrations

**Analysis Date:** 2026-03-14

## APIs & External Services

**Primary Weather Data Sources:**

1. **NOAA/National Weather Service (NWS) - weather.gov**
   - What it's used for: US weather forecasts, detailed forecasts by zone, weather alerts, zone information
   - SDK/Client: `accessiweather.weather_gov_api_client` (OpenAPI-generated from weather.gov spec)
   - Base URL: `https://api.weather.gov`
   - Auth: None (public API, uses User-Agent header for identification)
   - Rate Limiting: Built-in with conditional GET (ETags, Last-Modified headers) to minimize requests
   - Files: `src/accessiweather/api/nws/`, `src/accessiweather/weather_client_nws.py`

2. **Open-Meteo - open-meteo.com**
   - What it's used for: Global weather forecasts, hourly forecasts, historical data, air quality, pollen
   - SDK/Client: `accessiweather.openmeteo_client` (custom async wrapper)
   - Base URLs:
     - Current/Forecast: `https://api.open-meteo.com/v1`
     - Archive: `https://archive-api.open-meteo.com/v1`
     - Geocoding: `https://geocoding-api.open-meteo.com/v1`
   - Auth: None (public API, free tier)
   - Rate Limiting: User-Agent header, client-side rate limiting (0.5s min interval)
   - Files: `src/accessiweather/openmeteo_client.py`, `src/accessiweather/weather_client_openmeteo.py`

3. **Visual Crossing Weather API - visualcrossing.com**
   - What it's used for: Historical weather, additional weather alerts, extended forecasts (optional with API key)
   - SDK/Client: `accessiweather.visual_crossing_client` (custom async wrapper)
   - Base URLs:
     - Low-latency: `https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timelinellx`
     - Standard: `https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline`
   - Auth: API key required (env var or keyring)
   - Env var: `visual_crossing_api_key` (stored in system keyring or portable config)
   - Rate Limiting: Exponential backoff with retry (max 3 attempts, 1s base delay, 2x multiplier)
   - Fallback: Automatically falls back from low-latency to standard endpoint if low-latency fails
   - Files: `src/accessiweather/visual_crossing_client.py`, `src/accessiweather/weather_client_visualcrossing.py`

**AI/Language Models:**

4. **OpenRouter - openrouter.ai**
   - What it's used for: Weather condition explanations, trend analysis via LLM
   - SDK/Client: `accessiweather.api.openrouter_models` (custom async client)
   - Base URL: `https://openrouter.ai/api/v1/models` (models list), inference via openai client
   - Auth: API key required (optional, uses free tier if not provided)
   - Env var: `openrouter_api_key` (stored in system keyring or portable config)
   - Configuration: App settings include `ai_model_preference` (default: "openrouter/free")
   - Files: `src/accessiweather/api/openrouter_models.py`

**Environmental Data:**

5. **Air Quality & Pollen Data** (integrated via Open-Meteo)
   - What it's used for: Air Quality Index (AQI), pollen forecasts
   - Service: `accessiweather.services.EnvironmentalDataClient`
   - Source: Fallback to multiple providers, queried via Open-Meteo
   - Files: `src/accessiweather/services/weather_service/`

## Data Storage

**Databases:**
- None - No database required. Configuration and weather cache stored as JSON files.

**Configuration Storage:**
- **Primary:** JSON file at `~/.config/accessiweather/accessiweather.json`
  - Stores: Display settings, location list, source priorities, update intervals, sound preferences
  - Format: JSON with schema versioning
  - Files: `src/accessiweather/config/config_manager.py`

- **Portable Mode:** `config/accessiweather.json` next to executable
  - Activated by `.portable` marker file or legacy `config/` directory
  - Env var: `ACCESSIWEATHER_FORCE_PORTABLE=1` (for testing)

**Cache:**
- **API Response Cache (In-Memory):**
  - TTL: 5 minutes (default)
  - Implementation: Simple dict-based cache with expiration timestamps
  - File: `src/accessiweather/cache.py` (class `Cache`)

- **Weather Data Cache (File-Based):**
  - Location: `~/.config/accessiweather/cache/` or portable `cache/` directory
  - TTL: 180 minutes (3 hours, configurable)
  - Format: JSON with schema versioning (CACHE_SCHEMA_VERSION)
  - Purpose: Offline fallback when API unreachable
  - File: `src/accessiweather/cache.py` (class `WeatherDataCache`)

**Secure Storage:**
- **System Keyring Integration:**
  - Service name: "accessiweather"
  - Stores: Visual Crossing API key, OpenRouter API key, GitHub App credentials, bundle passphrase
  - Backend: Windows Credential Manager (Windows), Keychain (macOS), available backends (Linux: GNOME Keyring, KWallet)
  - Lazy-loaded: Keyring access deferred until keys first accessed (improves startup by ~86ms)
  - File: `src/accessiweather/config/secure_storage.py` (classes `SecureStorage`, `LazySecureStorage`)

**File Storage:**
- Local filesystem only - No cloud storage integration
- Locations stored in JSON configuration file
- Weather data cached as JSON files per location

## Authentication & Identity

**Auth Providers:**
- Custom implementation with system keyring integration
- No OAuth/OIDC - Simple API key management

**API Key Management:**
- Visual Crossing: Optional, stored in keyring, prompted on first launch via wizard
- OpenRouter: Optional, stored in keyring, defaults to free tier if not provided
- GitHub: Optional, stored in keyring, for app-based updates/notifications

**Portable Mode Secret Storage:**
- Bundle-based encryption: `src/accessiweather/config/portable_secrets.py`
- Encryption: cryptography library with AES
- Passphrase: Cached in keyring for convenience, can be re-entered if keyring unavailable

## Monitoring & Observability

**Error Tracking:**
- None configured - Errors logged locally via Python logging

**Logs:**
- Approach: Python `logging` module with rotating file handler
- Log file: `accessiweather.log` (configurable verbosity)
- Config: `src/accessiweather/logging_config.py`
- Handlers: Console (development), File (production)

**Performance Monitoring:**
- Rate limiting tracked per API wrapper instance
- Last request time tracked to enforce min request intervals (0.5s default)
- Cache hit/miss logged at DEBUG level

## CI/CD & Deployment

**Hosting:**
- GitHub (source repo and releases)
- Self-hosted installer distribution (GitHub Releases)

**CI Pipeline:**
- GitHub Actions workflows in `.github/workflows/`
- `ci.yml`: Lint, type check, test on Ubuntu/Windows/macOS
- `briefcase-build.yml`: Build MSI/DMG after CI passes on dev branch
- `briefcase-release.yml`: Create GitHub release on version tag (v*.*.*)
- `integration-tests.yml`: Nightly VCR cassette recording (real API calls)

**Build Tools:**
- Briefcase - BeeWare tool for cross-platform packaging (NOTE: This is the INTENDED toolkit, but current codebase uses wxPython instead)
- PyInstaller 6.0.0+ - Currently used for Windows executable generation

## Environment Configuration

**Required env vars:**
- None required for basic operation (all optional APIs have fallbacks)

**Optional env vars:**
```
ACCESSIWEATHER_TEST_MODE=1          # Enable test mode (use mock APIs)
ACCESSIWEATHER_FORCE_PORTABLE=1     # Force portable mode detection
PYTHONIOENCODING=utf-8              # Encoding (especially for Windows)
FORCE_COLOR=0                        # Disable rich color on Windows CI (prevents crashes)
HYPOTHESIS_PROFILE=ci|dev|thorough  # Property test intensity (default: dev)
```

**Secrets location:**
- System keyring: `accessiweather` service (Windows Credential Manager, macOS Keychain, Linux backends)
- Portable bundle: Encrypted JSON in `config/secrets.json` with AES encryption
- Passphrase for portable bundle: Can be cached in keyring for convenience

## Webhooks & Callbacks

**Incoming:**
- None - Application is event-driven (user actions, timer ticks, background refresh)

**Outgoing:**
- None configured - Application reads from APIs, does not POST data back

**Desktop Notifications:**
- `desktop-notifier` library: Sends platform-native desktop notifications for weather alerts
- No webhook callbacks - Notifications are local system-level

**Audio Alerts:**
- `playsound3` / `sound_lib`: Play alert sounds when conditions change
- NOAA Radio streaming via `sound_lib.stream.URLStream` (low-latency URL streaming)

## Rate Limiting & Retry Strategy

**Client-Side Rate Limiting:**
- Base implementation: `BaseApiWrapper` enforces min_request_interval (default 0.5s)
- Thread-safe: Uses `threading.RLock()` for request coordination
- Per-API: Configurable retry parameters (max_retries=3, retry_backoff=2.0, retry_initial_wait=5.0)

**Conditional GET (HTTP 304):**
- NWS API uses ETags and Last-Modified headers for efficient polling
- Reduces bandwidth and avoids rate limits
- File: `src/accessiweather/api/nws/alerts_discussions.py`

**Exponential Backoff:**
- Formula: `wait_time = retry_initial_wait * (retry_backoff ^ attempt_count)`
- Applied on HTTP 429 (rate limit) responses
- Max retries: 3 by default

---

*Integration audit: 2026-03-14*
