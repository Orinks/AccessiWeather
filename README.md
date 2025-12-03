# AccessiWeather (Development)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
[![Built with BeeWare/Toga](https://img.shields.io/badge/Built%20with-BeeWare%20%2F%20Toga-ff6f00)](https://beeware.org/)
[![Packaging: Briefcase](https://img.shields.io/badge/Packaging-Briefcase-6f42c1)](https://briefcase.readthedocs.io/)
![Platforms](https://img.shields.io/badge/Platforms-Windows%20%7C%20macOS%20%7C%20Linux-informational)

This is the development branch of AccessiWeather. For stable releases, see the [main branch](https://github.com/Orinks/AccessiWeather/tree/main) or download from [accessiweather.orinks.net](https://accessiweather.orinks.net).

## Nightly Builds

Automated nightly builds are available for testing the latest development changes:

- **Windows (MSI/ZIP)** and **macOS (DMG)** builds run nightly when there are new commits
- Download from [GitHub Actions](https://github.com/Orinks/AccessiWeather/actions/workflows/briefcase-build.yml) (select a successful run → Artifacts)
- See [docs/nightly-link-setup.md](docs/nightly-link-setup.md) for direct download links

⚠️ Nightly builds may contain bugs or incomplete features. Use stable releases for production.

## Development Setup

### Prerequisites
- Python 3.10+ (3.12 recommended)
- Git

### Quick Start

```bash
# Clone and enter the repo
git clone https://github.com/Orinks/AccessiWeather.git
cd AccessiWeather
git checkout dev

# Create virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
# source .venv/Scripts/activate  # Windows (Git Bash)
# .venv\Scripts\activate         # Windows (CMD/PowerShell)

# Install dev dependencies
pip install -e ".[dev]"
```

### Running the App

```bash
# Run with Briefcase (recommended for development)
briefcase dev

# Or run directly (limited functionality)
python -m accessiweather
```

### Running Tests

```bash
# Run all tests (parallel, faster)
pytest -n auto

# Run all tests (serial)
pytest -v

# Run specific test file or function
pytest tests/test_file.py::test_func -v

# Run tests matching a pattern
pytest -k "test_name" -v

# Run only unit tests (skips integration tests that hit real APIs)
pytest -m "unit"
```

### Linting & Type Checking

```bash
# Lint and format (line length: 100)
ruff check --fix .
ruff format .

# Type checking
pyright
```

## Building & Packaging

### Using Briefcase Directly

```bash
# Create platform-specific project skeleton
briefcase create

# Build app artifacts
briefcase build

# Generate installers (MSI/DMG/PKG)
briefcase package
```

### Using installer/make.py (Recommended)

A convenience wrapper around Briefcase with additional helpers:

```bash
# Show environment info and detected versions
python installer/make.py status

# Create platform scaffold (first time only)
python installer/make.py create --platform windows  # or macOS, linux

# Build the app
python installer/make.py build --platform windows

# Package installer (MSI/DMG/PKG)
python installer/make.py package --platform windows

# Run in dev mode
python installer/make.py dev

# Run tests via Briefcase
python installer/make.py test

# Create portable ZIP (Windows)
python installer/make.py zip --platform windows

# Clean build artifacts
python installer/make.py clean --platform windows
```

## Project Structure

```
src/accessiweather/     # Main application package
├── app.py              # Main Toga app entry point
├── api/                # Weather API clients (NWS, Open-Meteo, Visual Crossing)
├── config/             # ConfigManager, AppSettings, LocationOperations
├── dialogs/            # UI dialogs
├── ui_builder.py       # Toga UI construction
├── weather_client.py   # Multi-source weather orchestration
├── alert_manager.py    # Weather alert handling
├── cache.py            # API response caching
└── background_tasks.py # Async periodic updates

tests/                  # Unit and integration tests
installer/              # Build scripts and make.py wrapper
docs/                   # Documentation
```

## Code Style

- **Formatter**: Ruff (100 char line length, double quotes)
- **Type hints**: Modern syntax (`dict[str, Any]` not `Dict`)
- **Async**: Use `await` for async functions, `asyncio.create_task()` for fire-and-forget
- **Toga UI**: All elements must have `aria_label` and `aria_description` for accessibility
- **Tests**: Mark with `@pytest.mark.unit` or `@pytest.mark.integration`

See [AGENTS.md](AGENTS.md) for detailed conventions and gotchas.

## CI/CD

- **ci.yml**: Runs linting (Ruff) and unit tests on Ubuntu/Windows/macOS
- **briefcase-build.yml**: Matrix builds for Windows (MSI) and macOS (DMG)

## Contributing

1. Fork the repo and create a feature branch from `dev`
2. Make your changes with tests
3. Run `ruff check --fix . && ruff format .` and `pytest`
4. Submit a PR to `dev`

See [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

## Documentation

- [User Manual](docs/user_manual.md)
- [Accessibility Guide](docs/ACCESSIBILITY.md)
- [CI/CD Architecture](docs/cicd_architecture.md)
- [Build & Artifacts](docs/build_and_artifacts.md)
- [Git Workflow](docs/git-workflow.md)

## License

MIT License - see [LICENSE](LICENSE) for details.
