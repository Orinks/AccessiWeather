# Technology Stack — AccessiWeather

## Language & Runtime
- **Python 3.10+** (requires-python = ">=3.10")
- Type annotations with `from __future__ import annotations` throughout

## GUI Framework
- **wxPython ≥ 4.2.5** — primary UI framework, screen-reader-first
- `gui_builder` (accessibleapps fork) — declarative widget building
- `sound_lib` (accessibleapps fork) — audio playback for sound events

## Networking & Async
- **httpx ≥ 0.20.0** — async HTTP client
- **asyncio** — background event loop runs in a dedicated daemon thread; wx.CallAfter used for UI thread dispatch
- **beautifulsoup4** — HTML scraping (discussion/alert text)

## Data & Config
- **attrs ≥ 22.2.0** — model layer (WeatherData, Location, etc.)
- **keyring** — OS credential storage for API keys
- **cryptography ≥ 42.0.0** — portable secrets encryption
- **python-dateutil** — datetime parsing helpers

## Notification & Tray
- **desktop-notifier** — cross-platform desktop notifications
- **toasted** (Windows only) — Windows toast notifications
- **psutil** — process management for single-instance locking

## AI / External APIs
- **openai ≥ 1.0.0** — AI weather explanation (via OpenRouter)
- **playsound3** — sound playback
- **prismatoid ≥ 0.7.0** — (dependency, purpose unclear from surface scan)
- **tzdata** — IANA timezone data for cross-platform tz support

## Build & Packaging
- **setuptools ≥ 64** + pyproject.toml (PEP 517/518)
- **PyInstaller ≥ 6.0** — frozen binary builds (Windows .exe)
- `accessiweather` entry point → `accessiweather.main:main`
- `accessiweather-gui` GUI entry point (same target)

## Code Quality
- **ruff ≥ 0.9.0** — lint (E/W/F/I/D/UP/B/C4/PIE/SIM/RET) + format; line-length 100; target py310
- **mypy ≥ 1.0.0** + **pyright** — static type checking (mypy.ini present)
- Auto-generated client directories (`weather_gov_api_client/`, `weatherapi_client/`) excluded from linting

## Testing
- **pytest** + **pytest-mock** + **pytest-cov**
- **pytest-asyncio** — async test support
- **pytest-xdist ≥ 3.0** — parallel test execution
- **pytest-recording ≥ 0.13** + **vcrpy ≥ 6.0** — HTTP cassette recording
- **pytest-rerunfailures ≥ 12.0** — flaky test retry
- **hypothesis ≥ 6.0** — property-based testing

## Coverage
- Overall: **76.1%** (5213/6852 statements)
- UI (`src/accessiweather/ui/`) excluded from coverage measurement
- `weather_gov_api_client/` excluded from coverage

## CI / Distribution
- **cliff.toml** — git-cliff changelog generation
- **installer/** directory — Windows NSIS or similar installer assets
- `powershell_profile_additions.ps1` — dev environment helpers
