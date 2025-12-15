# Architecture - AccessiWeather

**Generated:** December 11, 2025
**Version:** 0.4.2
**Architecture Type:** Multi-Layer Desktop Application with Data Fusion

---

## Executive Summary

AccessiWeather is a cross-platform desktop weather application built with Python 3.10+ and the BeeWare/Toga framework. The architecture prioritizes **accessibility**, **multi-source data reliability**, and **offline capability** through intelligent caching and fallback strategies.

**Key Characteristics:**
- **Monolith structure** - Single cohesive codebase
- **Event-driven UI** - Toga's native async event system
- **Multi-source data fusion** - NWS + Open-Meteo + Visual Crossing
- **Accessibility-first** - Full screen reader support with ARIA labels
- **Cross-platform** - Windows, macOS, Linux via Briefcase packaging

---

## System Context

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│                     AccessiWeather                          │
│                   (Desktop Application)                     │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │   Toga UI   │  │   Cache     │  │  Notifications   │  │
│  │  (Native)   │  │  (5-min)    │  │   (Desktop)      │  │
│  └─────────────┘  └─────────────┘  └──────────────────┘  │
│         │                │                   │             │
│  ┌──────▼────────────────▼───────────────────▼────────┐  │
│  │         Weather Client (Multi-Source)               │  │
│  └──────┬──────────────┬──────────────┬────────────────┘  │
│         │              │              │                    │
└─────────┼──────────────┼──────────────┼────────────────────┘
          │              │              │
      ┌───▼───┐    ┌────▼────┐   ┌────▼────────┐
      │  NWS  │    │ Open-   │   │  Visual     │
      │  API  │    │ Meteo   │   │ Crossing    │
      └───────┘    └─────────┘   └─────────────┘
         │              │              │
         └──────────────┴──────────────┘
                      │
              ┌───────▼────────┐
              │  Internet      │
              │  Weather Data  │
              └────────────────┘
```

**External Integrations:**
- **National Weather Service API** (weather.gov) - US weather data, no API key
- **Open-Meteo API** (open-meteo.com) - Global fallback, no API key
- **Visual Crossing API** (visualcrossing.com) - Enhanced alerts, requires API key (optional)
- **Geopy** - Geocoding via multiple providers (Nominatim, Google, etc.)
- **OpenAI API** (optional) - AI-powered weather explanations

---

## Architecture Pattern: Multi-Layer Desktop Application

### Layer 1: Presentation Layer
**Purpose:** User interface and accessibility
**Technologies:** Toga (BeeWare), desktop-notifier
**Components:**
- `ui/ui_builder.py` - Main window construction
- `dialogs/` - Modal dialog system
- `display/weather_presenter.py` - Screen reader formatting
- `notifications/toast_notifier.py` - System notifications

**Key Principles:**
- Every widget has `aria_label` + `aria_description`
- Keyboard-only navigation support
- Logical tab order in dialogs
- Focus management for modals

### Layer 2: Business Logic Layer
**Purpose:** Application logic and orchestration
**Components:**
- `handlers/` - Event handlers for UI actions
- `services/` - Business logic services
- `alert_manager.py` - Alert lifecycle management
- `location_manager.py` - Location CRUD operations
- `background_tasks.py` - Periodic update scheduler

**Design Pattern:** Observer + Strategy

### Layer 3: Data Integration Layer
**Purpose:** Weather data acquisition and fusion
**Components:**
- `weather_client.py` - Multi-source orchestrator
- `api/nws/` - National Weather Service integration
- `api/openmeteo_wrapper.py` - Open-Meteo integration
- `api/visualcrossing/` - Visual Crossing integration
- `api_client/base_wrapper.py` - HTTP client with retries

**Data Fusion Strategy:**
1. Try NWS first for US locations (most accurate)
2. Fall back to Open-Meteo on failure or international
3. Enrich with Visual Crossing if API key available
4. Merge data intelligently, preferring most reliable source per field

### Layer 4: Caching Layer
**Purpose:** Performance optimization and offline support
**Implementation:** `cache.py`
**Strategy:** Stale-while-revalidate
- Default TTL: 5 minutes (configurable)
- Serve cached data immediately
- Refresh in background if stale
- Graceful degradation on API failures

**Benefits:**
- 80%+ reduction in API calls
- Faster perceived performance
- Offline capability
- Reduced rate limit issues

### Layer 5: Configuration & Storage Layer
**Purpose:** Settings and persistent data
**Components:**
- `config/config_manager.py` - JSON I/O
- `config/settings.py` - Settings validation
- `config/locations.py` - Location operations
- `keyring` integration - Secure API key storage

**Storage Locations:**
- **Default:** `~/.config/accessiweather/accessiweather.json`
- **Portable Mode:** Check `portable.txt` → use local directory
- **API Keys:** System keyring (platform-specific secure storage)

---

## Component Architecture

### Weather Client (Multi-Source Orchestrator)

```
┌─────────────────────────────────────────────────────────┐
│                   WeatherClient                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Orchestration Logic                             │   │
│  │  • Location detection (US vs International)      │   │
│  │  • Source selection                              │   │
│  │  • Fallback strategy                             │   │
│  │  • Data merging                                  │   │
│  └───────┬──────────────┬──────────────┬────────────┘   │
│          │              │              │                 │
│  ┌───────▼──────┐ ┌────▼──────┐ ┌────▼──────────┐     │
│  │ NWSClient    │ │ OpenMeteo │ │ VisualCrossing│     │
│  │              │ │ Client    │ │ Client        │     │
│  │ • Alerts     │ │ • Forecast│ │ • Alerts      │     │
│  │ • Forecast   │ │ • History │ │ • History     │     │
│  │ • Gridpoints │ └───────────┘ └───────────────┘     │
│  │ • Obs        │                                      │
│  └──────────────┘                                      │
└─────────────────────────────────────────────────────────┘
```

**Source Selection Logic:**
1. Determine location type (US/international)
2. US locations → NWS primary, Open-Meteo fallback
3. International → Open-Meteo only
4. All locations → Visual Crossing enrichment (if API key)

### Alert Management System

```
┌─────────────────────────────────────────────────────────┐
│                 Alert Management Flow                    │
│                                                          │
│  API Response                                            │
│       │                                                  │
│       ▼                                                  │
│  ┌────────────────┐                                     │
│  │ AlertManager   │ ← Tracks alert lifecycle            │
│  │                │   (new, active, expired)            │
│  └────────┬───────┘                                     │
│           │                                              │
│           ▼                                              │
│  ┌─────────────────────────┐                           │
│  │ AlertNotificationSystem │                           │
│  │                         │                           │
│  │  • Rate limiting        │ ← Prevent spam            │
│  │  • Severity filtering   │ ← User preferences        │
│  │  • Deduplication        │ ← No repeat alerts        │
│  └───────┬─────────────────┘                           │
│          │                                              │
│      ┌───▼────┐                                         │
│      │ Notify │                                         │
│      └───┬────┘                                         │
│          │                                              │
│  ┌───────┴────────┐                                     │
│  │                │                                     │
│  ▼                ▼                                     │
│ Toast         Sound Pack                               │
│ Notification  Player                                   │
└─────────────────────────────────────────────────────────┘
```

**Alert Lifecycle States:**
- **New** - Just received from API
- **Active** - Currently in effect
- **Updated** - Modified by API
- **Expired** - No longer in effect
- **Dismissed** - User acknowledged

### Configuration Management

```
App Startup
     │
     ▼
Check portable.txt
     │
     ├─→ Found: config_dir = ./config/
     └─→ Not found: config_dir = ~/.config/accessiweather/
     │
     ▼
Load accessiweather.json
     │
     ▼
Validate with AppSettings (Pydantic-style attrs)
     │
     ├─→ Invalid: Use defaults + log warning
     └─→ Valid: Apply settings
     │
     ▼
Load API keys from keyring
     │
     ▼
Initialize weather clients
```

**Configuration Schema:**
```json
{
  "version": "0.4.2",
  "user_preferences": {
    "temperature_unit": "fahrenheit",
    "wind_speed_unit": "mph",
    "pressure_unit": "inHg",
    "alert_sound_enabled": true,
    "selected_sound_pack": "default"
  },
  "saved_locations": [
    {
      "name": "New York, NY",
      "latitude": 40.7128,
      "longitude": -74.0060,
      "timezone": "America/New_York"
    }
  ],
  "api_settings": {
    "cache_ttl_minutes": 5,
    "enable_visual_crossing": false
  }
}
```

### Background Task Scheduler

```
Application Start
     │
     ▼
Create asyncio tasks:
     │
     ├─→ Periodic Weather Update (every 5 min)
     │   └─→ Update current location weather
     │
     ├─→ Alert Polling (every 2 min)
     │   └─→ Check for new/updated alerts
     │
     └─→ Cache Cleanup (every 30 min)
         └─→ Remove expired cache entries
```

**Implementation:** `asyncio.create_task()` with `while True` loops
**Cancellation:** Tasks cancelled on app shutdown
**Error Handling:** Each task has try-except with exponential backoff on failure

---

## Data Flow Diagrams

### Weather Data Request Flow

```
User selects location
     │
     ▼
UI triggers event
     │
     ▼
Handler calls WeatherClient.get_weather(lat, lon)
     │
     ▼
Check cache
     │
     ├─→ Fresh (< 5 min): Return cached data immediately
     │                     + Optionally refresh in background
     │
     └─→ Stale or missing:
         │
         ▼
     Determine location type
         │
         ├─→ US Location:
         │   └─→ Try NWS API
         │       ├─→ Success: Cache + return
         │       └─→ Failure: Try Open-Meteo
         │
         └─→ International:
             └─→ Use Open-Meteo
         │
         ▼
     Enrich with Visual Crossing (if enabled)
         │
         ▼
     Merge data
         │
         ▼
     Cache result
         │
         ▼
     Format with WeatherPresenter
         │
         ▼
     Update UI
```

### Settings Save Flow

```
User modifies settings in dialog
     │
     ▼
User clicks "Save"
     │
     ▼
Collect settings from UI widgets
     │
     ▼
Validate settings (AppSettings model)
     │
     ├─→ Invalid: Show error dialog
     │
     └─→ Valid:
         │
         ▼
     ConfigManager.save_config()
         │
         ▼
     Write to JSON file
         │
         ▼
     Store API keys in keyring (if changed)
         │
         ▼
     Apply settings to running app
         │
         ├─→ Update cache TTL
         ├─→ Reload weather clients
         └─→ Update UI preferences
         │
         ▼
     Close settings dialog
         │
         ▼
     Show success message
```

---

## API Integration Architecture

### NWS API Integration (US Only)

**Base URL:** `https://api.weather.gov`

**Endpoints Used:**
1. `POST /points/{lat},{lon}` - Get gridpoint coordinates
2. `GET /gridpoints/{office}/{gridX},{gridY}/forecast` - 7-day forecast
3. `GET /gridpoints/{office}/{gridX},{gridY}/forecast/hourly` - Hourly forecast
4. `GET /alerts/active?point={lat},{lon}` - Active alerts

**Rate Limiting:** Built-in exponential backoff
**Authentication:** None required
**Error Handling:** Retry with backoff → Fall back to Open-Meteo

**Data Mapping:**
- Temperature, conditions, wind from forecast
- Alert severity mapping: extreme → severe → moderate → minor
- TAF/METAR support for aviation weather

### Open-Meteo Integration (Global)

**Base URL:** `https://api.open-meteo.com/v1/forecast`

**Parameters:**
- `latitude`, `longitude` - Location coordinates
- `hourly` - Requested hourly variables
- `daily` - Requested daily variables
- `temperature_unit` - User preference (fahrenheit/celsius)
- `wind_speed_unit` - User preference (mph/kmh/ms/kn)

**Rate Limiting:** No API key required, generous rate limits
**Error Handling:** Retry with backoff → Serve stale cache if available

**Data Mapping:**
- Complete weather conditions (temp, humidity, wind, etc.)
- Air quality index (AQI)
- UV index
- Hourly and daily forecasts

### Visual Crossing Integration (Optional)

**Base URL:** `https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services`

**Endpoints:**
- `/timeline/{location}` - Historical and forecast data
- Enhanced alert details with impact descriptions

**Authentication:** API key required (stored in keyring)
**Rate Limiting:** Based on subscription tier
**Use Case:** Enhanced alert descriptions, historical weather trends

---

## UI Architecture

### Main Window Structure

```
┌──────────────────────────────────────────────────────────┐
│  AccessiWeather                                    [_][□][X]│
├──────────────────────────────────────────────────────────┤
│  File   Locations   Weather   Alerts   Help              │
├──────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────┐ │
│  │  Location Selector: [New York, NY ▼]              │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Current Conditions                                │ │
│  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │ │
│  │                                                    │ │
│  │  Temperature: 72°F                                │ │
│  │  Conditions: Partly Cloudy                        │ │
│  │  Wind: 10 mph from NW                             │ │
│  │  Humidity: 65%                                    │ │
│  │  Updated: 2 minutes ago                           │ │
│  │                                                    │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  [Forecast] [Alerts] [History] [Aviation]        │ │
│  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │ │
│  │                                                    │ │
│  │  (Tab content area - OptionContainer)             │ │
│  │                                                    │ │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

**Accessibility Annotations:**
- Location Selector: `aria_label="Select location"`, keyboard accessible
- Current Conditions: `aria_description="Current weather at [location]"`
- Tab Container: Proper ARIA roles for tablist/tabpanel
- All buttons: Clear aria_label describing action

### Dialog System

**Pattern:** Modal dialogs via `toga.Window`

**Common Dialogs:**
1. **Settings Dialog** - Multi-tab settings interface
2. **Add Location** - Geocoding with validation
3. **Alert Details** - Full alert information
4. **Weather History** - Historical trends chart/table
5. **Aviation Weather** - TAF/METAR decoder
6. **About** - Version info and credits

**Accessibility:** Focus trap in modal, ESC to close, logical tab order

---

## Security Architecture

### API Key Storage
**Problem:** API keys should never be stored in plain text
**Solution:** Platform-specific secure storage via `keyring` library

**Storage Backends:**
- **Windows:** Windows Credential Manager
- **macOS:** Keychain
- **Linux:** Secret Service API / KWallet / Gnome Keyring

**Implementation:**
```python
import keyring

# Store API key
keyring.set_password("accessiweather", "visual_crossing_api_key", api_key)

# Retrieve API key
api_key = keyring.get_password("accessiweather", "visual_crossing_api_key")
```

### Configuration File Security
**File Permissions:** Standard user-only access (`chmod 600` on Unix)
**Content:** No sensitive data in JSON config (keys stored separately)
**Validation:** All config values validated before use

---

## Performance Optimizations

### 1. Stale-While-Revalidate Caching
**Impact:** 80%+ reduction in API calls
**User Benefit:** Instant data display, faster perceived performance

### 2. Parallel API Requests
**Implementation:** `asyncio.gather()` for simultaneous API calls
**Use Case:** Fetching alerts + forecast + conditions in parallel

### 3. Background Task Scheduling
**Benefit:** UI never blocks on data fetches
**Implementation:** All weather updates happen in background tasks

### 4. Lazy Loading
**Resource Loading:** Sound files loaded on-demand, not at startup
**Dialog Creation:** Dialogs created when needed, not at app init

### 5. Test Parallelization
**Tool:** `pytest-xdist` with `-n auto` flag
**Result:** ~4x faster test suite execution

---

## Error Handling Strategy

### API Failure Cascade
```
NWS API call
     │
     ├─→ Success: Return data
     │
     └─→ Failure:
         │
         ▼
     Retry with exponential backoff (3 attempts)
         │
         ├─→ Success: Return data
         │
         └─→ All retries failed:
             │
             ▼
         Try Open-Meteo fallback
             │
             ├─→ Success: Return data
             │
             └─→ Failure:
                 │
                 ▼
             Serve stale cache (if available)
                 │
                 ├─→ Cache exists: Return stale data + warning
                 │
                 └─→ No cache: Show user-friendly error message
```

### User-Facing Error Messages
**Principle:** Never show raw API errors to users
**Implementation:**
- Network errors → "Unable to connect to weather service"
- API errors → "Weather service temporarily unavailable"
- Cache available → "Showing cached data from [time]"

---

## Testing Architecture

### Test Strategy

**Unit Tests (Fast, Isolated)**
- Mock all external API calls
- Use `toga_dummy` backend for UI tests
- Test business logic in isolation
- Run on every commit via pre-commit hooks

**Integration Tests (Real APIs)**
- Mark with `@pytest.mark.integration`
- Test actual API integration
- Run on schedule (nightly) or manually
- Verify data parsing and error handling

### Test Organization

```
tests/
├── toga_test_helpers.py       # Fixtures and utilities
├── conftest.py                # Pytest configuration
│
├── test_weather_client.py     # Weather client unit tests
├── test_alert_manager.py      # Alert management tests
├── test_config_manager.py     # Configuration tests
├── test_ui_builder.py         # UI construction tests
│
└── integration/
    ├── test_nws_integration.py
    ├── test_openmeteo_integration.py
    └── test_visualcrossing_integration.py
```

### Key Test Fixtures

**`DummyConfigManager`** - Mock config for testing without file I/O
**`WeatherDataFactory`** - Generate realistic weather data for tests
**`mock_toga_app`** - Toga app instance with dummy backend

---

## Deployment Architecture

### Build Process (Briefcase)

```
Source Code (src/accessiweather/)
     │
     ▼
Briefcase create
     │ (Creates platform-specific template)
     ▼
Platform-specific project structure
     │
     ▼
Briefcase build
     │ (Compiles and bundles)
     ▼
Platform-specific binary
     │
     ├─→ Windows: .exe + dependencies
     ├─→ macOS: .app bundle (Universal)
     └─→ Linux: AppImage (planned)
     │
     ▼
Briefcase package
     │
     ▼
Installer artifact
     │
     ├─→ Windows: MSI installer
     ├─→ macOS: DMG disk image
     └─→ Linux: AppImage (self-contained)
```

### CI/CD Pipeline (GitHub Actions)

**Workflow: `ci.yml`** (on every push/PR)
1. Checkout code
2. Set up Python 3.10+
3. Install dependencies
4. Run Ruff linter
5. Run Ruff formatter (check only)
6. Run pytest (unit tests)
7. Generate coverage report

**Workflow: `briefcase-build.yml`** (manual/tag)
1. Matrix build: Windows + macOS
2. Set up platform-specific environment
3. Install Briefcase
4. `briefcase create`
5. `briefcase build`
6. `briefcase package`
7. Upload artifacts (MSI, DMG)

**Workflow: `briefcase-release.yml`** (on tag push)
1. Trigger briefcase-build.yml
2. Create GitHub Release
3. Attach build artifacts
4. Generate release notes from CHANGELOG.md

**Workflow: `nightly-release.yml`** (daily schedule)
1. Build with nightly version (e.g., 0.4.2-nightly-20251211)
2. Create pre-release on GitHub
3. Attach build artifacts
4. Clean up old nightly releases (keep last 7)

---

## Extensibility & Future Architecture

### Plugin System (Planned)
Allow community-created extensions:
- Custom weather data sources
- Additional sound pack formats
- Theme/skin system
- Widget plugins

### Multi-Instance Support (Planned)
Currently single-instance; future: multiple windows with different locations

### Mobile Support (Possible)
Briefcase supports iOS/Android; UI would need adaptation for mobile form factors

---

## Architecture Decision Records (ADRs)

### ADR-001: Why Toga over other GUI frameworks?
**Decision:** Use Toga (BeeWare)
**Rationale:**
- Native accessibility support (no custom screen reader integration needed)
- Cross-platform with single codebase
- Python-native (no JavaScript/HTML like Electron)
- Active development and BeeWare community support

**Trade-offs:**
- Smaller ecosystem than Electron or Qt
- Some platform-specific quirks
- Fewer third-party widgets

### ADR-002: Why multi-source weather data?
**Decision:** Integrate NWS + Open-Meteo + Visual Crossing
**Rationale:**
- NWS most accurate for US but US-only
- Open-Meteo provides global coverage and good fallback
- Visual Crossing adds enhanced details for power users

**Trade-offs:**
- Increased complexity
- More failure modes
- Data merging challenges

### ADR-003: Why JSON config instead of database?
**Decision:** Use JSON file for configuration
**Rationale:**
- Simple, human-readable
- Easy backup (single file)
- Portable mode support (just copy file)
- Sufficient for desktop app scale

**Trade-offs:**
- No concurrent access (fine for desktop)
- Manual schema migration on upgrades

---

## Key Metrics & SLIs

### Performance Targets
- **App Startup:** < 3 seconds
- **Weather Data Load:** < 1 second (cached), < 5 seconds (fresh)
- **Alert Notification:** < 2 seconds from API to toast

### Reliability Targets
- **API Success Rate:** > 95% (with fallbacks)
- **Cache Hit Rate:** > 80%
- **Test Coverage:** > 70%

---

## References

- **BeeWare/Toga Documentation:** https://toga.readthedocs.io/
- **NWS API Documentation:** https://www.weather.gov/documentation/services-web-api
- **Open-Meteo API Docs:** https://open-meteo.com/en/docs
- **Visual Crossing API:** https://www.visualcrossing.com/resources/documentation/weather-api/
- **Briefcase Packaging:** https://briefcase.readthedocs.io/
