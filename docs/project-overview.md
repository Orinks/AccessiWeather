# Project Overview - AccessiWeather

**Generated:** December 11, 2025
**Version:** 0.4.2
**Project Type:** Cross-Platform Desktop Application

---

## What is AccessiWeather?

AccessiWeather is an **accessible desktop weather application** built with Python and the BeeWare/Toga framework. It delivers comprehensive weather forecasts, alerts, and environmental data with **full screen reader support** and keyboard navigation, making weather information accessible to everyone.

**Key Differentiator:** Multi-source weather data fusion (NWS + Open-Meteo + Visual Crossing) provides reliable coverage and graceful fallback when services are unavailable.

---

## Quick Facts

| Aspect | Details |
|--------|---------|
| **Language** | Python 3.10+ (3.12 recommended) |
| **Framework** | BeeWare/Toga (native UI) |
| **Packaging** | Briefcase |
| **Architecture** | Multi-layer desktop application with data fusion |
| **Platforms** | Windows (MSI), macOS (DMG), Linux (planned AppImage) |
| **License** | MIT |
| **Repository** | https://github.com/orinks/accessiweather |
| **Website** | https://accessiweather.orinks.net |

---

## Core Features

### 🌦️ Weather Data
- **Multi-source integration:** NWS (US), Open-Meteo (global), Visual Crossing (enhanced)
- **Current conditions:** Temperature, humidity, wind, pressure
- **7-day forecast:** Daily and hourly forecasts
- **Hourly forecasts:** Detailed hour-by-hour predictions
- **Weather alerts:** Real-time severe weather notifications
- **Air quality:** AQI tracking and alerts
- **UV index:** Sun exposure warnings
- **Pollen levels:** Allergy information

### ♿ Accessibility
- **Full screen reader support:** NVDA, JAWS, VoiceOver, Orca
- **Keyboard navigation:** All functions accessible without mouse
- **ARIA labels:** Every UI element properly labeled
- **Logical tab order:** Intuitive navigation flow
- **Focus management:** Clear focus indicators

### 🔔 Notifications
- **Desktop alerts:** Native system notifications for severe weather
- **Customizable sounds:** Community sound pack system
- **Alert filtering:** Severity-based filtering (extreme, severe, moderate, minor)
- **Rate limiting:** Prevents notification spam

### 🌍 Multiple Locations
- **Save favorite locations:** Store multiple cities/regions
- **Quick switching:** Switch between locations easily
- **Geocoding:** Find locations by name
- **Timezone support:** Automatic timezone detection

### 📊 Advanced Features
- **Weather history:** View historical weather trends
- **Aviation weather:** TAF/METAR decoding for pilots
- **AI explanations:** OpenAI-powered weather insights (optional)
- **Offline support:** Smart caching (5-minute TTL)
- **Portable mode:** Run from USB drive (no installation)

---

## Technology Stack Summary

### Core Technologies
- **Python 3.10+** - Primary language
- **Toga (BeeWare)** - Cross-platform native UI framework
- **Briefcase** - App packaging and distribution
- **httpx** - Async HTTP client for API calls
- **desktop-notifier** - Native desktop notifications

### Weather APIs
- **National Weather Service (NWS)** - US weather data (no API key)
- **Open-Meteo** - Global weather fallback (no API key)
- **Visual Crossing** - Enhanced alerts and history (API key required, optional)

### Development Tools
- **pytest** - Testing framework with async support
- **ruff** - Fast linter and formatter
- **pyright/mypy** - Static type checking
- **pre-commit** - Automated code quality checks

See [technology-stack.md](technology-stack.md) for complete details.

---

## Architecture Summary

**Pattern:** Multi-Layer Desktop Application with Data Fusion

### Layer Structure
1. **Presentation** - Toga UI, dialogs, screen reader formatting
2. **Business Logic** - Event handlers, services, alert management
3. **Data Integration** - Multi-source weather client with fallback
4. **Caching** - 5-minute TTL with stale-while-revalidate
5. **Configuration** - JSON-based settings with secure keyring storage

### Data Flow
```
User Request → WeatherClient → Check Cache
                    ↓
          ┌─────────┴─────────┬─────────────┐
          ▼                   ▼             ▼
    NWS API (US)      Open-Meteo      Visual Crossing
                           ↓
                    Data Merge & Cache
                           ↓
                   WeatherPresenter
                           ↓
                        Toga UI
```

**Key Patterns:**
- Multi-source data fusion with intelligent fallback
- Stale-while-revalidate caching for offline support
- Observer pattern for background updates
- Strategy pattern for API source selection

See [architecture.md](architecture.md) for complete details.

---

## Project Structure

```
accessiweather/
├── src/accessiweather/          # Main application source
│   ├── app.py                  # Entry point (Toga App)
│   ├── weather_client.py       # Multi-source orchestrator
│   ├── api/                    # Weather API integrations
│   ├── config/                 # Configuration management
│   ├── ui/                     # UI construction
│   ├── dialogs/                # Modal dialogs
│   ├── notifications/          # Alert notification system
│   ├── soundpacks/             # Sound pack system
│   └── ...                     # Additional modules
│
├── tests/                       # Unit and integration tests
├── docs/                        # Documentation
├── installer/                   # Build scripts
├── .github/workflows/           # CI/CD pipelines
│
├── pyproject.toml              # Project configuration
├── README.md                   # User documentation
├── CHANGELOG.md                # Version history
└── LICENSE                     # MIT license
```

See [source-tree-analysis.md](source-tree-analysis.md) for annotated structure.

---

## Development Status

**Current Version:** 0.4.2
**Maturity:** Beta (pre-1.0)
**Active Development:** Yes
**Release Cadence:** Minor releases every 2-4 weeks

### Recent Milestones
- ✅ Multi-source weather integration
- ✅ Sound pack system
- ✅ Weather history feature
- ✅ Aviation weather (TAF/METAR)
- ✅ CI/CD pipeline with nightly builds
- ✅ Full accessibility support

### Roadmap (See [roadmap.md](roadmap.md))
- ⏳ Linux AppImage distribution
- ⏳ Microsoft Store listing
- ⏳ Radar/satellite imagery
- ⏳ Widget system
- ⏳ Mobile support (iOS/Android)

---

## User Base

**Primary Audience:**
- Users relying on screen readers (NVDA, JAWS, VoiceOver)
- Users requiring keyboard-only navigation
- Weather enthusiasts wanting detailed data
- Pilots needing TAF/METAR decoding

**Platform Distribution (Estimated):**
- Windows: ~70%
- macOS: ~25%
- Linux: ~5%

---

## Development Team

**Primary Developer:** Orinks (Josh)
**Contributors:** Open source community (see GitHub contributors)
**License:** MIT (open source)

**Contributing:** See [CONTRIBUTING.md](../CONTRIBUTING.md)

---

## Quality Metrics

### Code Quality
- **Test Coverage:** >70% (goal)
- **Type Checking:** pyright (strict mode for src/)
- **Linting:** Ruff (auto-fix on pre-commit)
- **Code Style:** Ruff format (line length 100)

### Build System
- **CI Success Rate:** >95% target
- **Build Time:** ~20-30 minutes per platform
- **Automated Testing:** All commits, PRs, and releases

### Accessibility
- **Screen Reader Compatibility:** NVDA, JAWS, VoiceOver, Orca
- **Keyboard Navigation:** 100% keyboard accessible
- **WCAG Compliance:** Targeting WCAG 2.1 Level AA

---

## Installation & Distribution

### User Installation

**Windows:**
1. Download MSI installer from GitHub Releases or website
2. Run installer (double-click MSI)
3. Follow installation wizard
4. Launch from Start Menu

**macOS:**
1. Download DMG from GitHub Releases or website
2. Open DMG
3. Drag AccessiWeather.app to Applications
4. Launch from Applications folder

**Linux:**
- AppImage distribution (planned)
- Manual Python installation via pip (available now)

### Developer Setup

```bash
# Clone repository
git clone https://github.com/orinks/accessiweather.git
cd accessiweather

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -e ".[dev,audio]"

# Run in development mode
briefcase dev
```

See [development-guide.md](development-guide.md) for complete setup.

---

## Configuration & Data Storage

### Configuration File
**Location:** `~/.config/accessiweather/accessiweather.json`
**Portable Mode:** Check for `portable.txt` → use local directory
**Format:** JSON with validation

### API Keys
**Storage:** System keyring (platform-specific secure storage)
- Windows: Credential Manager
- macOS: Keychain
- Linux: Secret Service / KWallet / Gnome Keyring

### Logs
**Location:** `~/.local/share/accessiweather/logs/` (or portable directory)
**Rotation:** Automatic log rotation (keeps last 3 log files)

---

## API Integration

### Data Sources

**National Weather Service (NWS)**
- **Coverage:** United States only
- **API Key:** Not required (free public API)
- **Rate Limiting:** Built-in exponential backoff
- **Data:** Alerts, forecasts, observations, gridpoints

**Open-Meteo**
- **Coverage:** Global
- **API Key:** Not required
- **Use Case:** International locations, NWS fallback
- **Data:** Forecasts, historical data, air quality

**Visual Crossing** (Optional)
- **Coverage:** Global
- **API Key:** Required (user-provided)
- **Use Case:** Enhanced alert descriptions, historical trends
- **Data:** Detailed alerts, weather history

### API Strategy
1. Detect location type (US vs international)
2. Use NWS for US locations (most accurate)
3. Fall back to Open-Meteo on NWS failure or international
4. Enrich with Visual Crossing if API key available
5. Merge data intelligently, preferring most reliable source per field

---

## Build & Release Process

### CI/CD Pipeline (GitHub Actions)

**Continuous Integration (`ci.yml`):**
- Runs on every push/PR
- Linting (Ruff)
- Unit tests (pytest)
- Cross-platform (Ubuntu, Windows, macOS)

**Platform Builds (`briefcase-build.yml`):**
- Manual or tag-triggered
- Builds Windows MSI and macOS DMG
- Universal binary for macOS (Intel + Apple Silicon)

**Release Automation (`briefcase-release.yml`):**
- Triggered on tag push (e.g., `v0.4.2`)
- Creates GitHub Release
- Uploads installers

**Nightly Builds (`nightly-release.yml`):**
- Daily schedule (2 AM UTC)
- Pre-release builds for testing
- Version format: `0.4.2-nightly-20251211`

See [deployment-guide.md](deployment-guide.md) for complete pipeline docs.

---

## Testing Strategy

### Unit Tests
- **Framework:** pytest with async support
- **Coverage:** >70% target
- **Backend:** `toga_dummy` (no real UI)
- **Speed:** Fast (~1-2 minutes for full suite)
- **Execution:** `pytest -n auto` (parallel)

### Integration Tests
- **Marker:** `@pytest.mark.integration`
- **Purpose:** Real API calls to weather services
- **Execution:** Manual or scheduled (nightly)
- **Requirements:** Internet connection

### Accessibility Testing
- **Manual:** Screen reader testing (NVDA, VoiceOver, etc.)
- **Automated:** ARIA label validation
- **Frequency:** Before each release

---

## Community & Support

### Getting Help
- **GitHub Issues:** Bug reports and feature requests
- **Documentation:** Comprehensive docs in `/docs` folder
- **BeeWare Community:** Discord for Toga-specific questions

### Contributing
- **Welcome:** Contributions encouraged!
- **Process:** Fork → Branch → PR → Review
- **Guidelines:** See [CONTRIBUTING.md](../CONTRIBUTING.md)
- **Code Style:** Auto-formatted via pre-commit hooks

### Communication
- **Primary:** GitHub Issues and Pull Requests
- **Updates:** CHANGELOG.md tracks all user-facing changes
- **Roadmap:** [roadmap.md](roadmap.md) shows future plans

---

## Security & Privacy

### Data Privacy
- **No telemetry:** App does not collect user data
- **Local storage:** All data stored locally
- **API keys:** Stored securely in system keyring
- **No tracking:** No analytics or usage tracking

### Security Practices
- **Dependency scanning:** Automated Dependabot checks
- **Code review:** All PRs reviewed before merge
- **API key security:** Never stored in plain text
- **Build provenance:** All builds via GitHub Actions (transparent)

---

## Performance Characteristics

### App Performance
- **Startup Time:** <3 seconds typical
- **Weather Data Load:** <1 second (cached), <5 seconds (fresh)
- **Memory Usage:** ~50-100 MB typical
- **CPU Usage:** Minimal (background tasks only)

### Caching Strategy
- **TTL:** 5 minutes default (configurable)
- **Hit Rate:** >80% typical
- **Offline Support:** Serves stale cache when network unavailable
- **API Reduction:** 80%+ fewer API calls vs no caching

---

## Accessibility Commitment

**Philosophy:** Weather information should be accessible to everyone, regardless of ability.

**Implementation:**
- Every UI element has proper ARIA labels
- Full keyboard navigation (no mouse required)
- Screen reader testing on every release
- Logical tab order throughout app
- Focus indicators clear and visible

**Supported Screen Readers:**
- **Windows:** NVDA, JAWS
- **macOS:** VoiceOver
- **Linux:** Orca

See [ACCESSIBILITY.md](ACCESSIBILITY.md) for complete guidelines.

---

## Related Documentation

### For Users
- [README.md](../README.md) - Getting started guide
- [INSTALL.md](../INSTALL.md) - Installation instructions
- [CHANGELOG.md](../CHANGELOG.md) - Version history

### For Developers
- [architecture.md](architecture.md) - System architecture
- [technology-stack.md](technology-stack.md) - Tech stack details
- [development-guide.md](development-guide.md) - Setup and workflow
- [deployment-guide.md](deployment-guide.md) - Build and release
- [source-tree-analysis.md](source-tree-analysis.md) - Codebase structure

### For Contributors
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines
- [AGENTS.md](../AGENTS.md) - Development commands
- [git-workflow.md](git-workflow.md) - Branching strategy

---

## Project Timeline

### Origins
- **Conception:** Need for accessible weather app for screen reader users
- **Initial Development:** Started as Python/Tkinter app
- **Framework Migration:** Moved to Toga for better accessibility and cross-platform support
- **Current Status:** Active development, beta maturity

### Version History Highlights
- **v0.1.0:** Initial release (basic weather display)
- **v0.2.0:** Added NWS integration
- **v0.3.0:** Multi-source support (NWS + Open-Meteo)
- **v0.4.0:** Sound pack system, alerts, accessibility improvements
- **v0.4.2:** Current version (weather history, aviation weather)
- **v1.0.0:** Planned stable release (future)

---

## Success Metrics

### Project Health
- ✅ Active development (regular commits)
- ✅ Automated testing (CI pipeline)
- ✅ Documentation coverage (comprehensive)
- ✅ Code quality standards (Ruff, mypy, pyright)
- ✅ Accessibility compliance (screen reader support)

### User Satisfaction (Goals)
- High usability for screen reader users
- Reliable weather data (multi-source fallback)
- Fast performance (caching, async)
- Regular updates (2-4 week cadence)

---

## Future Vision

**Short-term (3-6 months):**
- Linux AppImage distribution
- Microsoft Store listing
- Enhanced radar/satellite imagery
- Widget system for customization

**Long-term (1-2 years):**
- Mobile support (iOS/Android via Briefcase)
- Plugin architecture for extensibility
- Community marketplace for sound packs and themes
- International language support (i18n/l10n)

**Ultimate Goal:** Be the most accessible and reliable weather app across all platforms.

---

## Acknowledgments

- **BeeWare Project:** For Toga framework and Briefcase packaging
- **Weather Services:** NWS, Open-Meteo, Visual Crossing for data
- **Community:** Contributors and users who provide feedback
- **Open Source:** All the libraries that make this possible

---

**For complete documentation, see [index.md](index.md) - the master documentation hub.**
