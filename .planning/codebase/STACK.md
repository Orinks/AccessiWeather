# Technology Stack

**Analysis Date:** 2026-03-14

## Languages

**Primary:**
- Python 3.10+ - Desktop application, weather data processing, API orchestration
- TOML - Configuration and build metadata

## Runtime

**Environment:**
- Python 3.10+

**Package Manager:**
- pip via setuptools
- Lockfile: Uses `pyproject.toml` with PEP 517 build backend

## Frameworks

**Core Application:**
- wxPython 4.2.5+ - Desktop GUI with full screen reader accessibility support (NVDA/JAWS compatible)
- Toga - NOT USED (see note below)

**HTTP/Networking:**
- httpx 0.20.0+ - Async HTTP client for all API communications, includes timeout and retry support

**Build/Packaging:**
- setuptools 64.0+ - Build backend (PEP 517 compliant)
- PyInstaller 6.0.0+ - Create standalone Windows/macOS executables
- Pillow 10.0.0+ - Image processing for UI icons

**Development:**
- pytest - Test runner (supports parallel execution via pytest-xdist)
- pytest-asyncio - Async test support
- pytest-mock - Mock fixtures
- pytest-cov - Coverage reporting
- pytest-recording (vcrpy 6.0+) - VCR cassette support for API mocking
- hypothesis 6.0+ - Property-based testing
- Ruff 0.9.0+ - Linting and formatting (line length: 100)
- Pyright - Static type checking
- mypy 1.0+ - Alternative type checking

## Key Dependencies

**Critical - API Communication:**
- httpx 0.20.0+ - Async HTTP requests (10s timeout by default, retries with exponential backoff)
- beautifulsoup4 - HTML parsing for weather discussions/alerts

**Critical - Weather Data Sources:**
- (Generated) weather_gov_api_client - OpenAPI-generated client for NOAA/weather.gov API
- (Custom) openmeteo_client - Open-Meteo API client wrapper
- (Custom) visual_crossing_client - Visual Crossing Weather API client

**Critical - Configuration & Storage:**
- keyring - System keyring integration for secure API key storage (Windows: uses Windows Credential Manager, macOS: Keychain, Linux: available if backend installed)
- cryptography 42.0+ - Encryption support for bundle-based storage

**Notifications & Audio:**
- desktop-notifier - Cross-platform desktop notifications (Windows/macOS/Linux)
- playsound3 - Audio playback for weather alerts
- sound_lib @ git+https://github.com/accessibleapps/sound_lib.git - Advanced audio support for NOAA Radio streaming
- toasted (Windows only) - Windows toast notification support

**UI & Accessibility:**
- gui_builder @ git+https://github.com/accessibleapps/gui_builder.git - Custom UI builder for wxPython
- attrs 22.2.0+ - Data class utilities

**Data Processing:**
- python-dateutil - Advanced date/time handling with timezone support
- tzdata - IANA timezone database
- psutil - System resource monitoring
- prismatoid 0.7.0+ - Geospatial/location utilities

## Configuration

**Environment:**
- Configuration stored in JSON: `~/.config/accessiweather/accessiweather.json` (or portable `config/` directory)
- API keys for Visual Crossing, OpenRouter stored in system keyring (lazy-loaded on first access)
- API keys for OpenRouter, Visual Crossing can be configured via UI wizard on first launch

**Build:**
- `pyproject.toml` - Single source of truth for dependencies, versioning, build config
- Ruff config: line-length=100, target=py310, lint rules enabled for quality (E, W, F, I, D, UP, B, C4, PIE, SIM, RET)
- Coverage config: `.coveragerc` - omits generated API clients and UI directory

## Platform Requirements

**Development:**
- Python 3.10+
- System keyring available (or use portable mode with bundled secrets)
- wxPython build dependencies: GTK3+ (Linux), Xcode (macOS), Visual Studio Build Tools (Windows)

**Production:**
- Windows: 10+ (includes pythonnet for WinForms interop if needed)
- macOS: 10.13+ (universal build for Intel + Apple Silicon)
- Linux: glibc 2.31+ with GTK3+

**Target Deployment:**
- Packaged as MSI installer (Windows)
- Packaged as DMG installer (macOS)
- Packaged as AppImage (Linux)
- Portable ZIP mode supported (no installer, config stays with executable)

---

*Stack analysis: 2026-03-14*
