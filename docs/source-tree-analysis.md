# Source Tree Analysis - AccessiWeather

**Generated:** December 11, 2025
**Project Root:** `/home/josh/accessiweather`
**Project Type:** Desktop Application (Monolith)

---

## Project Structure Overview

AccessiWeather follows a standard Python package structure with Briefcase packaging configuration. The codebase is organized into logical modules with clear separation of concerns.

---

## Complete Directory Tree (Annotated)

```
accessiweather/
├── .github/                      # GitHub configuration
│   ├── workflows/               # CI/CD pipeline definitions
│   │   ├── ci.yml              # Linting + unit tests
│   │   ├── briefcase-build.yml # Platform-specific builds
│   │   ├── briefcase-release.yml # Release automation
│   │   ├── nightly-release.yml # Nightly builds
│   │   ├── integration-tests.yml # Real API tests
│   │   └── update-pages.yml    # Website deployment
│   ├── agents/                 # AI coding agent configs
│   └── copilot-instructions.md # GitHub Copilot guidelines
│
├── src/accessiweather/          # ⭐ MAIN APPLICATION SOURCE
│   ├── __init__.py             # Package initialization
│   ├── __main__.py             # Python -m entry point
│   ├── app.py                  # 🔹 ENTRY POINT: Main Toga App class
│   ├── main.py                 # Application bootstrap
│   ├── cli.py                  # Command-line interface
│   │
│   ├── api/                    # Weather API integration layer
│   │   ├── nws/               # National Weather Service API
│   │   │   ├── alerts.py      # Alert fetching
│   │   │   ├── forecasts.py   # Forecast data
│   │   │   └── gridpoints.py  # Grid point resolution
│   │   ├── openmeteo_wrapper.py # Open-Meteo integration
│   │   └── visualcrossing/    # Visual Crossing API
│   │       ├── alerts.py      # Enhanced alerts
│   │       └── historical.py  # Historical weather data
│   │
│   ├── api_client/            # HTTP client abstractions
│   │   └── base_wrapper.py   # Shared HTTP patterns with retries
│   │
│   ├── config/                # Configuration management
│   │   ├── settings.py       # AppSettings model
│   │   ├── locations.py      # Location operations
│   │   └── config_manager.py # JSON config I/O
│   │
│   ├── ui/                    # UI construction
│   │   └── ui_builder.py     # Main window and menu creation
│   │
│   ├── dialogs/               # Modal dialogs
│   │   ├── settings_dialog.py     # Settings UI
│   │   ├── settings_tabs.py       # Settings tab panels
│   │   ├── settings_handlers.py   # Settings save/load logic
│   │   ├── location_handlers.py   # Add/edit location dialogs
│   │   ├── alert_handlers.py      # Alert detail dialogs
│   │   ├── aviation_handlers.py   # TAF/METAR dialogs
│   │   ├── weather_handlers.py    # Weather display dialogs
│   │   └── update_handlers.py     # Update check dialogs
│   │
│   ├── handlers/              # Event handler modules
│   │   ├── menu_handlers.py  # Menu action handlers
│   │   └── event_handlers.py # UI event handlers
│   │
│   ├── services/              # Business logic services
│   │   ├── weather_service.py # Weather data orchestration
│   │   └── location_service.py # Location management
│   │
│   ├── notifications/         # Notification system
│   │   ├── alert_notification_system.py # Alert dispatcher
│   │   ├── toast_notifier.py         # Desktop notifications
│   │   └── weather_notifier.py       # Weather-specific alerts
│   │
│   ├── soundpacks/            # Sound pack system
│   │   ├── sound_player.py           # Audio playback
│   │   ├── alert_sound_mapper.py     # Alert → sound mapping
│   │   └── sound_pack_installer.py   # Pack installation
│   │
│   ├── models/                # Data models
│   │   ├── weather_models.py  # Weather data structures
│   │   ├── location_models.py # Location data structures
│   │   └── alert_models.py    # Alert data structures
│   │
│   ├── utils/                 # Utility modules
│   │   ├── temperature_utils.py # Unit conversions
│   │   ├── retry_utils.py       # Retry logic
│   │   └── taf_decoder.py       # Aviation weather parsing
│   │
│   ├── display/               # Data presentation
│   │   └── weather_presenter.py # Screen reader formatting
│   │
│   ├── resources/             # Static resources
│   │   ├── sounds/           # Alert sound files
│   │   ├── icons/            # Application icons
│   │   └── soundpacks/       # Bundled sound packs
│   │
│   ├── alert_manager.py            # Alert lifecycle management
│   ├── alert_notification_system.py # Rate limiting & filtering
│   ├── background_tasks.py         # Periodic update scheduler
│   ├── cache.py                    # Weather data cache (5-min TTL)
│   ├── weather_client.py           # Multi-source weather orchestrator
│   ├── weather_client_*.py         # Weather client strategy modules
│   ├── geocoding.py                # Location → coordinates
│   ├── location_manager.py         # Location CRUD operations
│   ├── weather_history.py          # Historical weather tracking
│   ├── ai_explainer.py             # OpenAI weather explanations
│   ├── single_instance.py          # Prevent multiple app instances
│   └── logging_config.py           # Logging setup
│
├── tests/                     # Test suite
│   ├── toga_test_helpers.py  # Test fixtures and utilities
│   ├── test_*.py             # Unit tests
│   └── integration/          # Integration tests
│
├── docs/                      # 📚 Documentation
│   ├── ACCESSIBILITY.md      # Accessibility guidelines
│   ├── SOUND_PACK_SYSTEM.md  # Sound pack documentation
│   ├── cicd_architecture.md  # CI/CD pipeline details
│   ├── git-workflow.md       # Branching strategy
│   ├── roadmap.md            # Feature roadmap
│   └── [additional docs]     # Feature-specific documentation
│
├── installer/                 # Custom installer scripts
│   └── build.py               # Briefcase build wrapper
│
├── examples/                  # Example scripts
│   ├── hourly_aqi_example.py # AQI usage example
│   └── weather_history_demo.py # History API example
│
├── build/                     # Briefcase build output
├── logs/                      # Application logs
│
├── pyproject.toml            # 🔹 PROJECT CONFIGURATION
├── pytest.ini                # Pytest configuration
├── .pre-commit-config.yaml   # Pre-commit hooks
├── pyrightconfig.json        # Pyright type checker config
├── mypy.ini                  # MyPy type checker config
├── requirements.txt          # Production dependencies
├── requirements-dev.txt      # Development dependencies
│
├── README.md                 # Project overview
├── CHANGELOG.md              # Version history
├── CONTRIBUTING.md           # Contribution guidelines
├── AGENTS.md                 # Development commands
├── LICENSE                   # MIT license
└── INSTALL.md                # Installation instructions
```

---

## Critical Directories

### `/src/accessiweather/` (Main Application)
**Purpose:** All application source code
**Entry Point:** `app.py` - `AccessiWeatherApp(toga.App)` class
**Key Modules:**
- `app.py` - Main application class with lifecycle management
- `ui_builder.py` - Constructs main window and menu system
- `weather_client.py` - Orchestrates multi-source weather data
- `background_tasks.py` - Async periodic updates

### `/src/accessiweather/api/` (Weather Data Sources)
**Purpose:** Weather API wrappers and integrations
**Data Sources:**
1. **NWS** (`api/nws/`) - US weather via weather.gov
2. **Open-Meteo** (`openmeteo_wrapper.py`) - Global fallback
3. **Visual Crossing** (`visualcrossing/`) - Enhanced alerts

**Integration Pattern:** Multi-source with smart fallback

### `/src/accessiweather/config/` (Configuration Layer)
**Purpose:** Settings and location management
**Storage:** `~/.config/accessiweather/accessiweather.json`
**Portable Mode:** Check for `portable.txt` flag
**Key Classes:**
- `ConfigManager` - JSON I/O
- `AppSettings` - Settings validation
- `LocationOperations` - Location CRUD

### `/src/accessiweather/ui/` & `/src/accessiweather/dialogs/`
**Purpose:** User interface construction
**Framework:** Toga (BeeWare)
**Accessibility:** All widgets have `aria_label` + `aria_description`
**Pattern:** Modal dialogs created with `toga.Window`

### `/src/accessiweather/notifications/` (Alert System)
**Purpose:** Weather alert notifications
**Components:**
- `AlertNotificationSystem` - Rate limiting, severity filtering
- `ToastNotifier` - Desktop notification integration
- `WeatherNotifier` - Weather-specific formatting

### `/soundpacks/` (Audio System)
**Purpose:** Customizable alert sounds
**Features:**
- Community sound pack support
- Alert severity → sound mapping
- Cross-platform audio playback

### `/tests/` (Test Suite)
**Purpose:** Unit and integration tests
**Framework:** pytest with async support
**Backend:** `toga_dummy` (unit tests), real Toga (integration)
**Fixtures:** `tests/toga_test_helpers.py`

### `/docs/` (Documentation)
**Purpose:** Project documentation and guides
**Key Documents:**
- Feature specifications (nationwide forecast, sound packs, etc.)
- Architecture guides (CI/CD, accessibility)
- Developer guides (git workflow, roadmap)

### `/.github/workflows/` (CI/CD)
**Purpose:** Automated builds, tests, and releases
**Platforms:** Windows (MSI), macOS (DMG), Linux (planned AppImage)
**Workflows:** 7 total (see technology-stack.md)

---

## Multi-Source Integration Flow

```
User Request
     ↓
WeatherClient (orchestrator)
     ↓
├─→ NWS API (US locations)
│   ├─→ Alerts
│   ├─→ Forecasts
│   └─→ Observations
│
├─→ Open-Meteo (fallback/international)
│   ├─→ Forecasts
│   └─→ Historical data
│
└─→ Visual Crossing (enrichment)
    ├─→ Enhanced alerts
    └─→ Weather history

     ↓
WeatherDataCache (5-min TTL)
     ↓
WeatherPresenter (screen reader formatting)
     ↓
Toga UI Display
```

---

## Configuration Flow

```
Application Start
     ↓
Check for portable.txt
     ↓
├─→ Found: Use local directory
└─→ Not found: Use ~/.config/accessiweather/
     ↓
ConfigManager.load_config()
     ↓
Validate with AppSettings model
     ↓
Load saved locations
     ↓
Initialize weather clients
     ↓
Start background tasks
```

---

## Alert Notification Flow

```
Weather API Response
     ↓
AlertManager (lifecycle tracking)
     ↓
AlertNotificationSystem
     ↓
├─→ Check rate limits (prevent spam)
├─→ Filter by severity
└─→ Check user preferences
     ↓
Toast Notification (desktop-notifier)
     +
Sound Pack Player (alert-specific sound)
```

---

## Build & Deployment Flow

```
Code Push/Tag
     ↓
GitHub Actions Trigger
     ↓
├─→ ci.yml (lint + unit tests)
│   ├─→ Ruff format check
│   ├─→ Ruff lint
│   └─→ Pytest (Ubuntu/Windows/macOS)
│
├─→ briefcase-build.yml (platform builds)
│   ├─→ Windows MSI
│   └─→ macOS DMG (universal binary)
│
└─→ briefcase-release.yml (on tag push)
    └─→ Create GitHub Release with artifacts
```

---

## Entry Points Summary

| Entry Method | File | Purpose |
|--------------|------|---------|
| **Briefcase App** | `app.py` → `AccessiWeatherApp` | Main GUI application |
| **CLI Command** | `cli.py` → `main()` | Command-line interface |
| **Python Module** | `__main__.py` | `python -m accessiweather` |
| **Development** | `briefcase dev` | Hot reload mode |
| **Tests** | `pytest` | Test suite execution |

---

## Key Design Patterns

### 1. Multi-Source Data Fusion
Weather data from multiple APIs is combined intelligently with fallback strategies.

### 2. Stale-While-Revalidate Caching
Serve cached data immediately while fetching fresh data in background.

### 3. Observer Pattern
Background tasks update weather data; UI updates via Toga's event system.

### 4. Strategy Pattern
`WeatherClient` delegates to source-specific clients (NWS, Open-Meteo, Visual Crossing).

### 5. Repository Pattern
`LocationManager` abstracts location storage from business logic.

---

## Testing Architecture

```
tests/
├── unit tests (fast, isolated)
│   └── Mock external APIs
│   └── Use toga_dummy backend
│
└── integration tests (real APIs)
    └── @pytest.mark.integration
    └── Run on schedule/manual
```

**Test Execution:**
- **Serial:** `pytest -v`
- **Parallel:** `pytest` (stable default worker cap)
- **Last Failed:** `pytest --lf --ff`
- **Unit Only:** `pytest -m "unit"`

---

## Resource Organization

### Sound Files (`resources/sounds/`)
- Default alert sounds
- Organized by severity (warning, watch, advisory)
- Community sound packs stored separately

### Icons (`resources/icons/`)
- Application icon (multiple sizes)
- Platform-specific formats
- Used in taskbar/dock

### Sound Packs (`resources/soundpacks/`)
- Bundled community sound packs
- JSON manifest + audio files
- Installable via UI

---

## Accessibility Architecture

**Core Principle:** Every UI element must be navigable and understandable via screen reader.

**Implementation:**
- All widgets: `aria_label` + `aria_description`
- Logical tab order throughout dialogs
- Focus management for modal dialogs
- Screen reader-optimized text via `WeatherPresenter`

**Documentation:** See [ACCESSIBILITY.md](ACCESSIBILITY.md)

---

## Notes

- **Mono repo structure** with single cohesive codebase
- **Clear separation of concerns** across modules
- **Extensive documentation** in docs/ folder
- **Robust CI/CD** with platform-specific builds
- **Community-friendly** with sound pack system
