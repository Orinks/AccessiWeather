# Technology Stack - AccessiWeather

**Generated:** December 11, 2025  
**Project Version:** 0.4.2  
**Python Version:** 3.10+

---

## Overview

AccessiWeather is a cross-platform desktop weather application built with Python and the BeeWare/Toga framework. The architecture emphasizes accessibility, multi-source data integration, and offline capability through intelligent caching.

---

## Core Technology

| Category | Technology | Version | Justification |
|----------|-----------|---------|---------------|
| **Language** | Python | 3.10+ | Required for modern type hints, asyncio features, and Toga compatibility |
| **GUI Framework** | Toga (BeeWare) | Latest | Cross-platform native UI with built-in accessibility support |
| **Packaging** | Briefcase | 0.3.23+ | BeeWare's packaging tool for creating platform-specific installers |
| **Build System** | setuptools | 64.0+ | Standard Python build backend |

---

## Key Dependencies

### UI & Desktop Integration
| Library | Version | Purpose |
|---------|---------|---------|
| **toga** | Latest | Native cross-platform GUI framework with accessibility |
| **desktop-notifier** | Latest | Native system notifications for weather alerts |
| **keyring** | Latest | Secure storage for API keys and credentials |
| **psutil** | Latest | System integration and process management |

### Weather Data & APIs
| Library | Version | Purpose |
|---------|---------|---------|
| **httpx** | ≥0.20.0 | Async HTTP client for API calls with retry support |
| **beautifulsoup4** | Latest | HTML parsing for weather data extraction |
| **geopy** | Latest | Geocoding and location services |
| **python-dateutil** | Latest | Advanced date/time handling for forecasts |
| **timezonefinder** | Latest | Timezone detection from coordinates |

### AI & Advanced Features
| Library | Version | Purpose |
|---------|---------|---------|
| **openai** | ≥1.0.0 | AI-powered weather explanations |
| **attrs** | ≥22.2.0 | Data class validation and serialization |

### Audio & Accessibility
| Library | Version | Purpose |
|---------|---------|---------|
| **playsound3** | Latest | Alert sound playback (cross-platform fallback) |
| **pythonnet** | 2.x | Windows-specific audio support via winsound |

---

## Development Tools

### Testing Framework
| Tool | Version | Purpose |
|------|---------|---------|
| **pytest** | ≥7.0.0 | Primary test framework |
| **pytest-asyncio** | ≥0.20.0 | Async test support |
| **pytest-cov** | ≥4.0.0 | Code coverage reporting |
| **pytest-mock** | Latest | Mock objects and patching |
| **pytest-xdist** | ≥3.0.0 | Parallel test execution (~4x faster) |
| **hypothesis** | ≥6.0.0 | Property-based testing |

### Code Quality
| Tool | Version | Purpose |
|------|---------|---------|
| **ruff** | ≥0.9.0 | Fast linter and formatter (replaces Black, isort, Flake8) |
| **mypy** | ≥1.0.0 | Static type checking |
| **pyright** | Latest | Alternative type checker (excludes tests/) |
| **pre-commit** | Latest | Git hooks for automated quality checks |

---

## Architecture Pattern

**Pattern:** Multi-Layer Desktop Application with Data Fusion

### Layer Structure
1. **Presentation Layer** (`ui/`, `dialogs/`)
   - Toga UI components
   - Accessibility-first design with ARIA labels
   - Screen reader optimization

2. **Business Logic Layer** (`handlers/`, `services/`)
   - Weather data orchestration
   - Alert management and notification routing
   - Background task scheduling

3. **Data Integration Layer** (`api/`, `api_client/`)
   - Multi-source weather data (NWS, Open-Meteo, Visual Crossing)
   - Data fusion and enrichment
   - Smart fallback strategies

4. **Caching Layer** (`cache.py`)
   - 5-minute default TTL
   - Stale-while-revalidate pattern
   - Offline support

5. **Configuration Layer** (`config/`)
   - JSON-based settings
   - Portable mode support
   - Location management

---

## Build & Deployment

### Platform Targets
| Platform | Installer Format | Build Tool |
|----------|------------------|------------|
| **Windows** | MSI / Portable ZIP | Briefcase + GitHub Actions |
| **macOS** | DMG (Universal Binary) | Briefcase + GitHub Actions |
| **Linux** | AppImage (planned) | Briefcase |

### CI/CD Workflows
| Workflow | Purpose | Triggers |
|----------|---------|----------|
| **ci.yml** | Linting + Unit Tests | Push, PR |
| **briefcase-build.yml** | Platform builds (MSI, DMG) | Manual, tag |
| **briefcase-release.yml** | GitHub releases | Tag push |
| **nightly-release.yml** | Nightly builds | Schedule (daily) |
| **integration-tests.yml** | Real API testing | Manual, schedule |
| **update-pages.yml** | Website deployment | Push to main |

---

## Weather Data Sources

### Primary: National Weather Service (NWS)
- **Coverage:** US locations only
- **API Key:** Not required
- **Rate Limiting:** Built-in exponential backoff
- **Data:** Alerts, forecasts, observations, gridpoints

### Fallback: Open-Meteo
- **Coverage:** Global
- **API Key:** Not required
- **Purpose:** International locations, NWS failures
- **Data:** Forecasts, historical data

### Enrichment: Visual Crossing
- **Coverage:** Global
- **API Key:** Required (optional)
- **Purpose:** Enhanced alerts, historical trends
- **Data:** Detailed alerts, weather history

---

## Configuration Management

### Config Storage
- **Default:** `~/.config/accessiweather/accessiweather.json`
- **Portable Mode:** Check for `portable.txt` flag → use local directory
- **Format:** JSON with validation via `AppSettings` model

### Key Config Areas
- User preferences (units, alert settings)
- Saved locations with coordinates
- API keys (stored securely via keyring)
- Sound pack selection
- UI customization

---

## Audio System

### Platform-Specific Strategy
1. **Windows:** `winsound` (stdlib) primary
2. **macOS/Linux:** `playsound3` (external dependency)
3. **Fallback:** `playsound3` if winsound fails on Windows

### Sound Pack System
- Community-created alert sounds
- Customizable per alert severity
- Documented in [SOUND_PACK_SYSTEM.md](SOUND_PACK_SYSTEM.md)

---

## Accessibility Features

### Screen Reader Support
- Full ARIA labels throughout UI
- Keyboard navigation (no mouse required)
- Logical tab order
- Focus management

### Technical Implementation
- All Toga widgets include `aria_label` and `aria_description`
- Modal dialogs with proper focus handling
- Screen reader-optimized weather descriptions via `WeatherPresenter`

### Documentation
See [ACCESSIBILITY.md](ACCESSIBILITY.md) for complete guidelines.

---

## Performance Optimizations

### Caching Strategy
- **TTL:** 5 minutes default (configurable)
- **Pattern:** Stale-while-revalidate
- **Result:** 80%+ fewer API calls, noticeably faster on slow connections

### Background Tasks
- Async periodic weather updates via `asyncio.create_task()`
- Non-blocking UI during data fetches
- Parallel API calls where possible

### Testing Performance
- Parallel test execution with `pytest-xdist`
- Test suite runs ~4x faster with `-n auto` flag

---

## Code Quality Standards

### Formatting
- **Line Length:** 100 characters
- **Quotes:** Double quotes
- **Tool:** Ruff (auto-format on pre-commit)

### Type Hints
- Modern syntax: `dict[str, Any]` (not `Dict`)
- Use `from __future__ import annotations` for forward refs
- Pyright checks all code except tests/

### Pre-Commit Hooks
1. Auto-format with `ruff format`
2. Auto-fix linting with `ruff check --fix`
3. Run last-failed tests (`pytest --lf --ff -m "unit"`)
4. Type check with pyright
5. Auto-stage formatted files

---

## Entry Points

### Main Application
- **Module:** `src/accessiweather/app.py`
- **Class:** `AccessiWeatherApp(toga.App)`
- **Entry:** `accessiweather:main` (Briefcase)
- **CLI:** `accessiweather` command (when installed)

### Development
- **Dev Mode:** `briefcase dev` (hot reload)
- **Tests:** `pytest -v -p pytest_asyncio`

---

## Testing Strategy

### Unit Tests
- Fast, isolated tests
- Mock external APIs
- Use `toga_dummy` backend
- Mark: `@pytest.mark.unit` (default)

### Integration Tests
- Real API calls to weather services
- Mark: `@pytest.mark.integration`
- Run manually or on schedule

### Test Fixtures
- `DummyConfigManager` - Mock config for tests
- `WeatherDataFactory` - Create mock weather data
- Located in: `tests/toga_test_helpers.py`

---

## External Resources

- **Repository:** https://github.com/orinks/accessiweather
- **Website:** https://accessiweather.orinks.net
- **BeeWare/Toga:** https://beeware.org/
- **Weather APIs:** weather.gov (NWS), open-meteo.com, visualcrossing.com
