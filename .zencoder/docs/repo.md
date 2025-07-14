# AccessiWeather Information

## Summary
AccessiWeather is a desktop weather application with robust accessibility features and international weather support. The current version is built using Python with the BeeWare/Toga framework, focusing on screen reader compatibility and keyboard navigation. The application supports multiple weather providers (National Weather Service and Open-Meteo) and offers comprehensive weather information including current conditions, extended forecasts, hourly forecasts, and weather alerts.

**Note**: The project is transitioning from a wxPython-based implementation to a Toga-based implementation. The Toga version (`src/accessiweather/simple/`) is the current focus of development, while the wxPython version is being phased out.

## Structure
- **src/accessiweather**: Main application source code
  - **api**: Weather API integration modules
  - **simple**: Simplified Toga-based implementation
  - **gui**: User interface components
  - **services**: Core service layer components
  - **weather_gov_api_client**: Generated NWS API client
  - **openmeteo_client.py**: Open-Meteo API client
- **tests**: Comprehensive test suite organized by component
- **installer**: Windows installer configuration and build scripts
- **docs**: Documentation files
- **scripts**: Utility scripts for development and testing

## Language & Runtime
**Language**: Python
**Version**: Python 3.7+ (3.11+ recommended)
**Build System**: setuptools, PyInstaller (for binaries)
**Package Manager**: pip

## Dependencies
**Main Dependencies**:
- toga (≥0.5.1): Cross-platform GUI toolkit
- httpx (≥0.20.0): Modern HTTP client
- geopy: Geocoding library
- desktop-notifier: System notification integration
- python-dateutil: Date/time utilities
- beautifulsoup4: HTML parsing
- attrs (≥22.2.0): Class attribute management
- psutil: Process and system utilities

**Development Dependencies**:
- pytest, pytest-mock, pytest-cov, pytest-asyncio: Testing framework and plugins
- ruff (≥0.9.0): Linting and formatting tool
- mypy (≥1.0.0): Static type checker
- types-requests: Type hints for requests
- PyInstaller: Binary packaging

## Code Quality Tools
**Linting & Formatting**: Ruff
**Type Checking**: mypy
**Pre-commit Hooks**: pre-commit
**Configuration Files**:
- pyproject.toml: Ruff configuration
- .pre-commit-config.yaml: Pre-commit hooks
- mypy.ini: Type checking configuration

**Ruff Configuration**:
- Line length: 100
- Target Python version: 3.12
- Selected rules: E, W, F, I, D, UP, B, C4, PIE, SIM, RET
- Auto-fix enabled in pre-commit

## Build & Installation

### Virtual Environment
A virtual environment is already set up for this project. Before running any commands, activate the existing virtual environment:

**For Windows Command Prompt:**
```cmd
# Activate the existing virtual environment
.venv\Scripts\activate
```

**For Windows PowerShell:**
```powershell
# Activate the existing virtual environment
.\.venv\Scripts\Activate.ps1
```

**For Linux/macOS:**
```bash
# Activate the existing virtual environment
source .venv/bin/activate
```

### Installation Commands
```bash
# Install from source
pip install -e .

# Install with development dependencies
pip install -e ".[dev]"
```

### Running the Toga Application
The Toga-based implementation is the current focus of development. To run the Toga version of the application:

```bash
# Run the application using the CLI entry point
accessiweather

# Alternatively, run the Toga app directly
python -m accessiweather.simple_main
```

You can also run the application with specific options:
```bash
# Run in portable mode (saves config in app directory)
accessiweather --portable

# Run in debug mode
accessiweather --debug

# Disable API response caching
accessiweather --no-cache
```

### Building Binaries
To build Windows binaries and installer for distribution:

```powershell
# Build Windows binaries and installer
.\installer\build_installer.ps1
```

This will create:
- A standalone executable in the `dist` directory
- A portable ZIP archive
- A Windows installer with Inno Setup

## Application Architecture

### Toga Application Structure
The Toga-based implementation (`src/accessiweather/simple/`) follows a more modern, async-first architecture:

- **AccessiWeatherApp** (`simple/app.py`): Main Toga application class
- **ConfigManager** (`simple/config.py`): Handles application configuration
- **WeatherClient** (`simple/weather_client.py`): Unified client for weather data
- **LocationManager** (`simple/location_manager.py`): Manages location search and storage
- **AlertManager** (`simple/alert_manager.py`): Processes and manages weather alerts
- **Models** (`simple/models.py`): Data models for weather information
- **Formatters** (`simple/formatters.py`): Weather data formatting utilities

### Main Components
- **Weather Clients**: API clients for NWS and Open-Meteo
- **Location Manager**: Handles location search and management
- **Alert Manager**: Processes and manages weather alerts
- **Config Manager**: Handles application configuration
- **UI Components**: Toga-based user interface

### Entry Points
- **CLI Entry Point**: accessiweather.cli:main
- **Main Application**: src/accessiweather/main.py
- **Toga App**: src/accessiweather/simple/app.py
- **Simple Main**: src/accessiweather/simple_main.py

### Platform Support
- **Primary**: Windows 10+
- **Experimental**: Linux support
- **Mobile/Web**: Configuration exists in pyproject.toml but implementation status unclear

## Testing
**Framework**: pytest
**Test Location**: tests/ directory
**Naming Convention**: test_*.py
**Configuration**: pytest.ini, tox.ini
**Test Categories**:
- unit: Fast, isolated tests
- integration: Component interaction tests
- gui: GUI-specific tests
- e2e: End-to-end workflow tests
- accessibility: Accessibility feature tests
- toga: Toga framework tests

**Run Command**:
```bash
# Run all tests
pytest

# Run specific test category
pytest -m unit
pytest -m integration
pytest -m gui

# Run with coverage
pytest --cov=src/accessiweather
```