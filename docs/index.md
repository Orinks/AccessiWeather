# AccessiWeather - Documentation Index

**Generated:** December 11, 2025  
**Version:** 0.4.2  
**Project Type:** Desktop Application (Monolith)

---

## 🚀 Quick Start

**New to AccessiWeather?** Start here:
1. [Project Overview](project-overview.md) - What is AccessiWeather?
2. [Architecture](architecture.md) - How it's built
3. [Development Guide](development-guide.md) - Set up your dev environment

**Building something?** Go directly to:
- [Technology Stack](technology-stack.md) - All dependencies and tools
- [Source Tree Analysis](source-tree-analysis.md) - Navigate the codebase
- [Deployment Guide](deployment-guide.md) - Build and release process

---

## 📊 Project Quick Reference

### Overview
- **Type:** Monolith (single cohesive codebase)
- **Primary Language:** Python 3.10+
- **Framework:** BeeWare/Toga (native cross-platform UI)
- **Architecture Pattern:** Multi-layer desktop application with data fusion
- **Entry Point:** [`src/accessiweather/app.py`](../src/accessiweather/app.py) → `AccessiWeatherApp(toga.App)`

### Tech Stack at a Glance
| Layer | Technologies |
|-------|-------------|
| **UI** | Toga, desktop-notifier, ARIA accessibility |
| **Business Logic** | Python, asyncio, background tasks |
| **Data Sources** | NWS API, Open-Meteo, Visual Crossing |
| **Caching** | 5-minute TTL, stale-while-revalidate |
| **Storage** | JSON config, system keyring (API keys) |
| **Testing** | pytest, pytest-asyncio, hypothesis |
| **Build/Deploy** | Briefcase, GitHub Actions |

### Architecture Pattern
**Multi-Source Data Fusion** with intelligent fallback:
- Primary: NWS (US locations, most accurate)
- Fallback: Open-Meteo (global coverage)
- Enrichment: Visual Crossing (optional, enhanced data)

---

## 📚 Generated Documentation

### Core Architecture Documents
- **[Project Overview](project-overview.md)** - Executive summary, features, and project status
- **[Architecture](architecture.md)** - Complete system architecture, patterns, and design decisions
- **[Technology Stack](technology-stack.md)** - All dependencies, frameworks, tools, and versions
- **[Source Tree Analysis](source-tree-analysis.md)** - Annotated directory structure and codebase navigation

### Development & Operations
- **[Development Guide](development-guide.md)** - Setup, workflow, testing, and common tasks
- **[Deployment Guide](deployment-guide.md)** - CI/CD pipeline, build process, and release workflow

---

## 📖 Existing Project Documentation

### User Documentation
- [README.md](../README.md) - Project introduction and getting started
- [INSTALL.md](../INSTALL.md) - Installation instructions for end users
- [CHANGELOG.md](../CHANGELOG.md) - Version history and release notes
- [LICENSE](../LICENSE) - MIT License

### Contributor Documentation
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines and process
- [AGENTS.md](../AGENTS.md) - Development commands and quick reference for AI agents
- [knowledge.md](../knowledge.md) - Project-specific knowledge and patterns

### Technical Documentation

#### Core Features
- [ACCESSIBILITY.md](ACCESSIBILITY.md) - Accessibility features, guidelines, and screen reader support
- [SOUND_PACK_SYSTEM.md](SOUND_PACK_SYSTEM.md) - Sound pack system architecture
- [SOUND_PACKS.md](SOUND_PACKS.md) - Sound pack creation and usage guide
- [weather_history_feature.md](weather_history_feature.md) - Historical weather tracking
- [UPDATE_SYSTEM.md](UPDATE_SYSTEM.md) - Auto-update system design

#### Nationwide Forecast Feature
- [nationwide_forecast_integration.md](nationwide_forecast_integration.md) - Integration details
- [nationwide_settings.md](nationwide_settings.md) - Settings and configuration
- [nationwide_view.md](nationwide_view.md) - UI implementation
- [nationwide_discussions.md](nationwide_discussions.md) - Design discussions

#### CI/CD & Infrastructure
- [cicd_architecture.md](cicd_architecture.md) - CI/CD pipeline architecture
- [cicd_setup.md](cicd_setup.md) - Pipeline setup and configuration
- [github_actions.md](github_actions.md) - GitHub Actions workflows
- [build_and_artifacts.md](build_and_artifacts.md) - Build system and artifacts
- [nightly-link-setup.md](nightly-link-setup.md) - Nightly build configuration
- [GITHUB_BACKEND_SETUP.md](GITHUB_BACKEND_SETUP.md) - GitHub backend setup

#### Development Process
- [git-workflow.md](git-workflow.md) - Git branching strategy and workflow
- [quality_gates.md](quality_gates.md) - Code quality standards and gates
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - Migration procedures
- [toga_migration_analysis.md](toga_migration_analysis.md) - Toga framework migration notes

#### Planning & Roadmap
- [roadmap.md](roadmap.md) - Feature roadmap and future plans
- [implementation_plan.md](implementation_plan.md) - Implementation planning
- [alert_audit_report.md](alert_audit_report.md) - Alert system audit

#### Implementation Details
- [IMPLEMENTATION_DETAILS.md](../IMPLEMENTATION_DETAILS.md) - Detailed implementation notes
- [HOURLY_AQI_IMPLEMENTATION.md](../HOURLY_AQI_IMPLEMENTATION.md) - Hourly AQI feature implementation

---

## 🔍 Documentation by Use Case

### I Want to...

#### **Understand the Project**
→ Start with [Project Overview](project-overview.md)  
→ Read [Architecture](architecture.md) for system design  
→ Check [Technology Stack](technology-stack.md) for tech details

#### **Set Up Development Environment**
→ Follow [Development Guide](development-guide.md) - Quick Start section  
→ Review [AGENTS.md](../AGENTS.md) for command reference  
→ Check [Source Tree Analysis](source-tree-analysis.md) to navigate codebase

#### **Add a New Feature**
→ Review [Architecture](architecture.md) - Component Architecture section  
→ Check [Development Guide](development-guide.md) - Common Development Tasks  
→ Follow [git-workflow.md](git-workflow.md) for branching strategy  
→ Run tests per [Development Guide](development-guide.md) - Testing section

#### **Modify UI**
→ See [Source Tree Analysis](source-tree-analysis.md) - UI directories  
→ Review [ACCESSIBILITY.md](ACCESSIBILITY.md) - All UI must be accessible  
→ Check [`ui/ui_builder.py`](../src/accessiweather/ui_builder.py) for main window  
→ Look in [`dialogs/`](../src/accessiweather/dialogs/) for modal dialogs

#### **Integrate New Weather API**
→ Review [Architecture](architecture.md) - API Integration Architecture  
→ See [`api/`](../src/accessiweather/api/) for existing integrations  
→ Follow [Development Guide](development-guide.md) - Add New API Integration  
→ Update [weather_client.py](../src/accessiweather/weather_client.py) orchestrator

#### **Build & Release**
→ Follow [Deployment Guide](deployment-guide.md) - Complete pipeline guide  
→ Check [cicd_architecture.md](cicd_architecture.md) for workflow details  
→ Review [build_and_artifacts.md](build_and_artifacts.md) for build system

#### **Fix a Bug**
→ Search [Source Tree Analysis](source-tree-analysis.md) for relevant files  
→ Write test reproducing bug (see [Development Guide](development-guide.md))  
→ Fix bug and verify with tests  
→ Update [CHANGELOG.md](../CHANGELOG.md)

#### **Improve Accessibility**
→ Read [ACCESSIBILITY.md](ACCESSIBILITY.md) - Complete guidelines  
→ Check [Architecture](architecture.md) - Accessibility Architecture  
→ Test with screen readers (NVDA, JAWS, VoiceOver)  
→ Ensure all widgets have `aria_label` + `aria_description`

---

## 🏗️ Architecture Deep Dive

### System Layers

**Layer 1: Presentation**
- Location: [`ui/`](../src/accessiweather/ui/), [`dialogs/`](../src/accessiweather/dialogs/)
- Technologies: Toga, desktop-notifier
- Key Files: `ui_builder.py`, `display/weather_presenter.py`
- Docs: [Architecture](architecture.md) - UI Architecture section

**Layer 2: Business Logic**
- Location: [`handlers/`](../src/accessiweather/handlers/), [`services/`](../src/accessiweather/services/)
- Key Files: `alert_manager.py`, `location_manager.py`, `background_tasks.py`
- Docs: [Architecture](architecture.md) - Business Logic Layer

**Layer 3: Data Integration**
- Location: [`api/`](../src/accessiweather/api/), `weather_client.py`
- Technologies: httpx, NWS API, Open-Meteo, Visual Crossing
- Key Files: `weather_client.py`, `api/nws/`, `api/openmeteo_wrapper.py`
- Docs: [Architecture](architecture.md) - Data Integration Layer

**Layer 4: Caching**
- Location: `cache.py`
- Strategy: Stale-while-revalidate, 5-minute TTL
- Docs: [Architecture](architecture.md) - Caching Layer

**Layer 5: Configuration**
- Location: [`config/`](../src/accessiweather/config/)
- Storage: JSON config + system keyring
- Key Files: `config_manager.py`, `settings.py`, `locations.py`
- Docs: [Architecture](architecture.md) - Configuration Layer

### Data Flow

```
User Action
     ↓
UI Event Handler
     ↓
WeatherClient.get_weather()
     ↓
Cache Check
     ├─→ Hit: Return cached + optional background refresh
     └─→ Miss: Fetch from API
         ↓
     ┌───┴────────────┬────────────┐
     ▼                ▼            ▼
  NWS API      Open-Meteo    Visual Crossing
     └────────────┬───────────────┘
                  ▼
            Data Merge
                  ▼
              Cache Store
                  ▼
         WeatherPresenter
                  ▼
              UI Update
```

---

## 🧪 Testing & Quality

### Test Organization
- **Location:** [`tests/`](../tests/)
- **Framework:** pytest with async support
- **Fixtures:** `tests/toga_test_helpers.py`
- **Docs:** [Development Guide](development-guide.md) - Testing section

### Test Commands

```bash
# Run all tests (parallel)
pytest -n auto

# Run unit tests only
pytest -m "unit" -v

# Run integration tests (real APIs)
pytest -m "integration" -v

# Run specific test file
pytest tests/test_weather_client.py -v

# Generate coverage report
pytest --cov=accessiweather --cov-report=html
```

### Code Quality Tools
- **Linter:** Ruff (`ruff check --fix .`)
- **Formatter:** Ruff (`ruff format .`)
- **Type Checker:** Pyright (`pyright`)
- **Pre-commit:** Automated checks on commit

**Docs:** [Development Guide](development-guide.md) - Code Quality section

---

## 🚢 Build & Deployment

### Quick Build Commands

```bash
# Development mode (hot reload)
briefcase dev

# Create platform app
briefcase create

# Build app bundle
briefcase build

# Generate installer
briefcase package
```

### CI/CD Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| **ci.yml** | Push, PR | Lint + unit tests |
| **briefcase-build.yml** | Manual, tag | Platform builds (MSI, DMG) |
| **briefcase-release.yml** | Tag push | GitHub Release automation |
| **nightly-release.yml** | Daily | Nightly pre-release builds |
| **integration-tests.yml** | Manual | Real API integration tests |

**Docs:** [Deployment Guide](deployment-guide.md) - Complete CI/CD details

---

## 📂 Key Directories

| Directory | Purpose | Key Files |
|-----------|---------|-----------|
| **src/accessiweather/** | Main application source | `app.py`, `weather_client.py` |
| **src/accessiweather/api/** | Weather API integrations | `nws/`, `openmeteo_wrapper.py` |
| **src/accessiweather/config/** | Configuration management | `config_manager.py`, `settings.py` |
| **src/accessiweather/ui/** | UI construction | `ui_builder.py` |
| **src/accessiweather/dialogs/** | Modal dialogs | `settings_dialog.py`, etc. |
| **src/accessiweather/notifications/** | Alert system | `alert_notification_system.py` |
| **src/accessiweather/soundpacks/** | Sound pack system | `sound_player.py`, `sound_pack_installer.py` |
| **tests/** | Test suite | `test_*.py`, `toga_test_helpers.py` |
| **docs/** | Documentation | This file and all linked docs |
| **.github/workflows/** | CI/CD pipelines | `ci.yml`, `briefcase-build.yml`, etc. |
| **installer/** | Build scripts | `make.py` |

**Docs:** [Source Tree Analysis](source-tree-analysis.md) - Complete annotated tree

---

## 🔗 External Resources

### Project Links
- **Repository:** https://github.com/orinks/accessiweather
- **Website:** https://accessiweather.orinks.net
- **Releases:** https://github.com/orinks/accessiweather/releases
- **Issues:** https://github.com/orinks/accessiweather/issues

### Framework & Tools
- **BeeWare/Toga:** https://toga.readthedocs.io/
- **Briefcase:** https://briefcase.readthedocs.io/
- **Pytest:** https://docs.pytest.org/
- **Ruff:** https://docs.astral.sh/ruff/

### Weather APIs
- **NWS API:** https://www.weather.gov/documentation/services-web-api
- **Open-Meteo:** https://open-meteo.com/en/docs
- **Visual Crossing:** https://www.visualcrossing.com/resources/documentation/weather-api/

---

## 🎯 For Brownfield PRD Creation

**This documentation was generated for brownfield PRD creation.** When creating a Product Requirements Document (PRD) for new features:

1. **Reference this index** as your primary entry point
2. **Link to specific sections:**
   - [Architecture](architecture.md) for system constraints
   - [Technology Stack](technology-stack.md) for technical capabilities
   - [Source Tree Analysis](source-tree-analysis.md) for implementation locations
   - [Development Guide](development-guide.md) for development patterns

3. **Key architectural constraints to consider:**
   - Must maintain accessibility (ARIA labels, keyboard nav)
   - Must integrate with existing WeatherClient multi-source pattern
   - Must use Toga UI framework conventions
   - Must support offline mode via caching
   - Must work cross-platform (Windows, macOS, Linux)

4. **Common integration points:**
   - New API source → Add to `api/` and integrate with `weather_client.py`
   - New UI feature → Add to `dialogs/` or `ui/`, ensure accessibility
   - New setting → Update `config/settings.py` and settings dialog
   - New alert type → Extend `alert_manager.py` and notification system

---

## 📝 Documentation Maintenance

**Generated Files:**
- `index.md` (this file)
- `project-overview.md`
- `architecture.md`
- `technology-stack.md`
- `source-tree-analysis.md`
- `development-guide.md`
- `deployment-guide.md`

**To Regenerate:** Run the `document-project` workflow with the analyst agent

**Last Updated:** December 11, 2025  
**Workflow Version:** 1.2.0  
**Scan Level:** Quick (pattern-based analysis)

---

## 🆘 Getting Help

**For Development Questions:**
- Check [Development Guide](development-guide.md)
- Review [Architecture](architecture.md)
- Search [GitHub Issues](https://github.com/orinks/accessiweather/issues)
- Ask in BeeWare Discord (for Toga questions)

**For Build/Deploy Issues:**
- See [Deployment Guide](deployment-guide.md)
- Check [cicd_architecture.md](cicd_architecture.md)
- Review GitHub Actions workflow runs

**For Feature Planning:**
- Review [roadmap.md](roadmap.md)
- Check existing issues and discussions
- Create RFC issue for major changes

---

**Welcome to AccessiWeather! 🌦️ This index is your gateway to understanding and contributing to the project.**
