# Technology Stack & Build System

## Core Technologies
- **Python 3.7+** (3.11+ recommended for best performance)
- **GUI Framework**: Toga (primary), wxPython (legacy support)
- **HTTP Client**: httpx (>=0.20.0) for API requests
- **Notifications**: desktop-notifier for cross-platform notifications
- **Geocoding**: geopy for location services
- **HTML Parsing**: beautifulsoup4 for web scraping
- **Date Handling**: python-dateutil for timestamp parsing

## Weather Data Sources
- **National Weather Service (NWS)**: US locations with alerts
- **Open-Meteo**: International weather data (no alerts)
- **Auto-generated API clients**: weather_gov_api_client, weatherapi_client

## Build System & Packaging
- **Build Backend**: setuptools (>=64.0)
- **Package Manager**: pip with requirements.txt/pyproject.toml
- **Binary Creation**: PyInstaller for standalone executables
- **Installer**: Inno Setup for Windows installers
- **Cross-platform**: Briefcase for multi-platform packaging

## Development Tools
- **Testing**: pytest with pytest-cov, pytest-mock, pytest-asyncio
- **Code Quality**: ruff (linting & formatting), mypy (type checking)
- **Security**: bandit, safety, semgrep, pip-audit
- **CI/CD**: tox for environment management
- **Pre-commit**: Automated code quality checks

## Common Commands

### Development Setup
```bash
# Install in development mode
pip install -e .

# Install dev dependencies
pip install -r requirements-dev.txt

# Run in portable mode
accessiweather --portable
```

### Testing
```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest --cov=src/accessiweather tests/

# Run specific test categories
python -m pytest -m "unit" tests/
python -m pytest -m "accessibility" tests/
```

### Code Quality
```bash
# Lint and format with ruff
ruff check src tests
ruff format src tests

# Type checking
mypy src/accessiweather

# Security scanning
bandit -r src/
safety check
```

### Building
```bash
# Build with Briefcase (recommended)
briefcase dev
briefcase build
briefcase package

# Build Windows installer (PowerShell)
.\installer\build_installer.ps1

# Manual PyInstaller build
python -m PyInstaller AccessiWeather.spec
```

### Environment Management
```bash
# Run quality checks
tox -e lint
tox -e type-check

# Test in isolated environment
tox
```

## Configuration Files
- **pyproject.toml**: Main project configuration, dependencies, tool settings
- **requirements.txt**: Runtime dependencies
- **requirements-dev.txt**: Development dependencies
- **pytest.ini**: Test configuration and markers
- **mypy.ini**: Type checking configuration
- **tox.ini**: Environment and quality check configuration
- **.pre-commit-config.yaml**: Git hooks for code quality
