# Development Guide - AccessiWeather

**Generated:** December 11, 2025  
**Target Audience:** Contributors and developers

---

## Quick Start

### Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| **Python** | 3.10+ (3.12 recommended) | Core language |
| **Git** | Latest | Version control |
| **Briefcase** | Latest | App packaging (optional for dev) |

**Platform-Specific:**
- **Windows:** Visual Studio Build Tools (for some deps)
- **macOS:** Xcode Command Line Tools
- **Linux:** `python3-dev`, `build-essential`

---

## Initial Setup

### 1. Clone Repository

```bash
git clone https://github.com/orinks/accessiweather.git
cd accessiweather
```

### 2. Create Virtual Environment

```bash
# Using venv (recommended)
python3 -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install all development dependencies
pip install -e ".[dev,audio]"

# Or install from requirements files
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

**Dependencies Installed:**
- Production: toga, httpx, geopy, desktop-notifier, etc.
- Development: pytest, ruff, mypy, pyright, pre-commit
- Audio: playsound3 (cross-platform audio support)

### 4. Install Pre-Commit Hooks

```bash
pre-commit install
```

**Pre-commit hooks automatically:**
- Format code with `ruff format` (line length 100)
- Fix linting issues with `ruff check --fix`
- Run last-failed unit tests
- Type check with pyright
- Auto-stage formatted files

---

## Development Workflow

### Running the Application

#### Development Mode (Recommended)

```bash
# Hot reload mode - changes reload automatically
briefcase dev
```

**Benefits:**
- Instant feedback on code changes
- Full access to logs and stdout
- Faster than building full app

#### Direct Python Execution

```bash
# Run as module
python -m accessiweather

# Or use entry point (if installed)
accessiweather
```

### Making Changes

```bash
# 1. Create feature branch
git checkout -b feature/my-feature

# 2. Make changes to code

# 3. Format and lint (optional - pre-commit does this)
ruff check --fix . && ruff format .

# 4. Run tests
pytest -v

# 5. Commit changes (pre-commit hooks run automatically)
git add .
git commit -m "feat: Add my awesome feature"

# 6. Push to GitHub
git push origin feature/my-feature

# 7. Create Pull Request
```

---

## Testing

### Running Tests

```bash
# Run all tests (serial)
pytest -v

# Run all tests (parallel - ~4x faster)
pytest -n auto

# Run specific test file
pytest tests/test_weather_client.py -v

# Run specific test function
pytest tests/test_file.py::test_function -v

# Run tests matching pattern
pytest -k "alert" -v

# Run unit tests only (default)
pytest -m "unit" -v

# Run integration tests (real API calls)
pytest -m "integration" -v

# Run last failed tests first
pytest --lf --ff -v

# Generate coverage report
pytest --cov=accessiweather --cov-report=html
# View coverage: open htmlcov/index.html
```

### Test Environment Setup

**Unit Tests:** Use `TOGA_BACKEND=toga_dummy` automatically  
**Integration Tests:** Require internet connection

### Writing Tests

**Example Unit Test:**
```python
import pytest
from accessiweather.weather_client import WeatherClient

@pytest.mark.unit
async def test_weather_client_cache_hit(mock_config_manager):
    """Test that cached data is returned without API call."""
    client = WeatherClient(config_manager=mock_config_manager)
    # Test implementation...
```

**Example Integration Test:**
```python
import pytest
from accessiweather.api.nws.forecasts import NWSForecastClient

@pytest.mark.integration
async def test_nws_real_api_call():
    """Test real NWS API integration."""
    client = NWSForecastClient()
    forecast = await client.get_forecast(40.7128, -74.0060)
    assert forecast is not None
    assert "temperature" in forecast
```

---

## Code Quality

### Linting & Formatting

```bash
# Auto-fix linting issues and format code (recommended workflow)
ruff check --fix . && ruff format .

# Or run separately:

# Check for linting issues
ruff check .

# Auto-fix linting issues
ruff check --fix .

# Format code
ruff format .

# Check formatting without applying
ruff format --check .
```

### Type Checking

```bash
# Type check with pyright (recommended)
pyright

# Type check with mypy (alternative)
mypy src/
```

**Note:** Pyright excludes `tests/` directory (see `pyrightconfig.json`)

### Code Style Guidelines

**Line Length:** 100 characters  
**Quotes:** Double quotes (`"string"`)  
**Imports:** Ruff auto-sorts (stdlib → third-party → local)  
**Type Hints:** Use modern syntax: `dict[str, Any]` not `Dict[str, Any]`  
**Async:** Use `async`/`await` for all long-running operations

**Example:**
```python
from __future__ import annotations

import asyncio
from typing import Any

async def fetch_weather(lat: float, lon: float) -> dict[str, Any]:
    """Fetch weather data for coordinates.
    
    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
        
    Returns:
        Weather data dictionary
    """
    # Implementation...
```

---

## Building & Packaging

### Create Platform-Specific App

```bash
# Create platform-specific skeleton
briefcase create

# Build app bundle
briefcase build

# Run built app
briefcase run
```

### Generate Installers

```bash
# Package for distribution
briefcase package

# Output locations:
# Windows: build/accessiweather/windows/app/*.msi
# macOS: build/accessiweather/macOS/app/*.dmg
# Linux: build/accessiweather/linux/appimage/*.AppImage
```

### Using Helper Script

```bash
# Wrapper around Briefcase commands
python installer/make.py dev     # Build for development
python installer/make.py release # Build for release
```

---

## Project Structure Navigation

### Key Files to Know

| File | Purpose |
|------|---------|
| **pyproject.toml** | Project config, dependencies, build settings |
| **src/accessiweather/app.py** | Main application entry point |
| **src/accessiweather/ui_builder.py** | UI construction |
| **src/accessiweather/weather_client.py** | Weather data orchestrator |
| **tests/conftest.py** | Pytest configuration and fixtures |
| **.pre-commit-config.yaml** | Pre-commit hook configuration |

### Where to Find Things

**Need to...** → **Look in...**
- Add UI element → `ui/ui_builder.py` or `dialogs/`
- Modify API integration → `api/nws/`, `api/openmeteo_wrapper.py`, etc.
- Change settings schema → `config/settings.py`
- Add dialog → `dialogs/` (create new file, wire in handlers)
- Modify alert logic → `alert_manager.py`, `alert_notification_system.py`
- Change caching → `cache.py`
- Add background task → `background_tasks.py`

---

## Common Development Tasks

### Add a New Setting

1. **Update settings model** (`config/settings.py`):
```python
@dataclass
class AppSettings:
    # ... existing fields ...
    my_new_setting: bool = False
```

2. **Add UI widget** (`dialogs/settings_tabs.py`):
```python
self.my_setting_switch = toga.Switch(
    "Enable my feature",
    aria_label="Enable my feature setting",
    on_change=self.on_setting_changed
)
```

3. **Wire save/load** (`dialogs/settings_handlers.py`):
```python
def apply_settings_to_ui(self, settings: AppSettings):
    self.my_setting_switch.value = settings.my_new_setting

def collect_settings_from_ui(self) -> AppSettings:
    return AppSettings(
        # ... existing fields ...
        my_new_setting=self.my_setting_switch.value
    )
```

### Add a New API Integration

1. **Create API client** (`api/my_api_client.py`):
```python
from api_client.base_wrapper import BaseAPIWrapper

class MyAPIClient(BaseAPIWrapper):
    async def fetch_data(self, lat: float, lon: float):
        return await self._get(f"/endpoint?lat={lat}&lon={lon}")
```

2. **Integrate with WeatherClient** (`weather_client.py`):
```python
self.my_api_client = MyAPIClient()

async def get_weather(self, lat, lon):
    # ... existing logic ...
    my_data = await self.my_api_client.fetch_data(lat, lon)
    # Merge with existing data
```

3. **Add tests** (`tests/test_my_api_client.py`):
```python
@pytest.mark.unit
async def test_my_api_client():
    # Unit test with mocks
    
@pytest.mark.integration
async def test_my_api_real_call():
    # Integration test with real API
```

### Add a New Dialog

1. **Create dialog class** (`dialogs/my_dialog.py`):
```python
import toga

class MyDialog:
    def __init__(self, app, parent_window):
        self.app = app
        self.parent = parent_window
        self.window = None
        
    def show(self):
        self.window = toga.Window(
            title="My Dialog",
            position=(100, 100),
            size=(400, 300)
        )
        # Build UI...
        self.window.show()
```

2. **Add menu item** (`ui_builder.py`):
```python
my_command = toga.Command(
    lambda widget: MyDialog(self.app, self.app.main_window).show(),
    text="My Dialog",
    tooltip="Open my dialog",
    group=toga.Group.APP
)
```

3. **Add accessibility** - ALL widgets need `aria_label` and `aria_description`

---

## Debugging

### Enable Debug Logging

```python
# Set in app.py or via env var
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Toga Backend Selection

```bash
# Force specific backend (for testing)
export TOGA_BACKEND=toga_dummy  # Dummy backend
export TOGA_BACKEND=toga_winforms  # Windows
export TOGA_BACKEND=toga_cocoa  # macOS
export TOGA_BACKEND=toga_gtk  # Linux
```

### Common Issues

**Issue:** `ImportError: No module named 'toga'`  
**Solution:** Activate virtual environment, reinstall dependencies

**Issue:** Pre-commit hooks failing  
**Solution:** Run `ruff check --fix . && ruff format .` manually, commit again

**Issue:** Tests failing with Toga errors  
**Solution:** Ensure `TOGA_BACKEND=toga_dummy` is set for unit tests

**Issue:** Build fails with Briefcase  
**Solution:** Check Briefcase version, ensure all deps in `pyproject.toml`

---

## Git Workflow

### Branching Strategy

- **main** - Stable, production-ready code
- **dev** - Integration branch (not currently used)
- **feature/*** - New features
- **fix/*** - Bug fixes
- **docs/*** - Documentation updates

### Merge Strategy

1. Regularly merge `main` into `dev` to avoid conflicts
2. Feature branches from `dev`
3. Merge feature branches back to `dev` frequently
4. Never commit directly to `main`
5. Hotfixes on `main` must be immediately backported to `dev`

See [git-workflow.md](git-workflow.md) for details.

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:** feat, fix, docs, style, refactor, test, chore  
**Example:**
```
feat(alerts): Add sound pack customization

- Users can now select from multiple alert sound packs
- Added sound pack installer dialog
- Documented in SOUND_PACK_SYSTEM.md

Closes #42
```

---

## CI/CD Pipeline

### Workflows Overview

**ci.yml** - Runs on every push/PR:
- Linting (Ruff)
- Unit tests (pytest)
- Code coverage report

**briefcase-build.yml** - Platform builds:
- Windows MSI
- macOS DMG (Universal Binary)
- Triggered manually or on tag

**briefcase-release.yml** - Release automation:
- Triggered on tag push (e.g., `v0.4.2`)
- Creates GitHub Release
- Attaches build artifacts

**nightly-release.yml** - Daily builds:
- Runs on schedule (nightly)
- Creates pre-release with nightly version
- Cleans up old nightly releases

**integration-tests.yml** - Real API tests:
- Runs on schedule or manually
- Tests actual API integration

See [cicd_architecture.md](cicd_architecture.md) for details.

### Triggering Builds

```bash
# Manual workflow dispatch via GitHub UI
# Or create tag for release:
git tag v0.4.3
git push origin v0.4.3
```

---

## Performance Tips

### Development Performance

- Use `briefcase dev` for fast iteration (no full build)
- Run tests in parallel: `pytest -n auto`
- Use `--lf --ff` flags for faster test feedback
- Cache API responses during development

### Application Performance

- Keep UI updates on main thread
- Use background tasks for all network I/O
- Implement caching for expensive operations
- Lazy load resources (dialogs, sound files)

---

## Accessibility Guidelines

**Every UI element MUST have:**
- `aria_label` - Brief label (e.g., "Temperature unit selector")
- `aria_description` - Detailed context (e.g., "Choose between Fahrenheit and Celsius")

**Keyboard navigation:**
- All functions accessible via keyboard (no mouse required)
- Logical tab order in dialogs
- Focus management for modals

**Screen reader testing:**
- Windows: NVDA or JAWS
- macOS: VoiceOver
- Linux: Orca

See [ACCESSIBILITY.md](ACCESSIBILITY.md) for complete guidelines.

---

## Resources

### Documentation
- [Architecture Documentation](architecture.md)
- [Technology Stack](technology-stack.md)
- [Source Tree Analysis](source-tree-analysis.md)
- [Deployment Guide](deployment-guide.md)

### External Resources
- **BeeWare/Toga Docs:** https://toga.readthedocs.io/
- **Briefcase Docs:** https://briefcase.readthedocs.io/
- **Pytest Docs:** https://docs.pytest.org/
- **Ruff Docs:** https://docs.astral.sh/ruff/

### Getting Help
- **GitHub Issues:** https://github.com/orinks/accessiweather/issues
- **Contributing Guide:** [CONTRIBUTING.md](../CONTRIBUTING.md)
- **Community:** BeeWare Discord (for Toga questions)

---

## Troubleshooting

### Build Issues

**Briefcase create fails:**
```bash
# Clear build cache
rm -rf build/
briefcase create
```

**Missing dependencies:**
```bash
# Reinstall all dependencies
pip install -e ".[dev,audio]" --force-reinstall
```

### Test Issues

**Toga tests failing:**
```bash
# Ensure dummy backend is used
export TOGA_BACKEND=toga_dummy
pytest -v
```

**Integration tests timeout:**
```bash
# Check internet connection
# Some APIs may be slow or rate-limited
pytest -m "unit" -v  # Run only unit tests
```

### Runtime Issues

**Config file corrupted:**
```bash
# Backup and reset config
mv ~/.config/accessiweather/accessiweather.json ~/.config/accessiweather/accessiweather.json.bak
# Restart app - will create new config with defaults
```

**API key issues:**
```bash
# Check keyring
python -c "import keyring; print(keyring.get_password('accessiweather', 'visual_crossing_api_key'))"
```

---

## Next Steps

1. **Read architecture docs** to understand system design
2. **Run tests** to verify setup: `pytest -n auto`
3. **Make a small change** to get familiar with workflow
4. **Check existing issues** on GitHub for contribution ideas
5. **Join community** via BeeWare Discord for questions

Happy coding! 🎉
