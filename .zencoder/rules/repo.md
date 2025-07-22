# AccessiWeather Information

## Summary
<<<<<<< HEAD
AccessiWeather is an accessible weather application that provides current conditions, forecasts, and weather alerts with a focus on screen reader compatibility. The project is currently migrating from wxPython to Toga/BeeWare for improved cross-platform support and accessibility.

## Structure
- **src/accessiweather**: Main application code
  - **simple/**: New Toga-based implementation
  - **gui/**: Original wxPython implementation
- **tests/**: Comprehensive test suite
- **installer/**: Windows installer scripts
- **docs/**: Documentation files
=======
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
>>>>>>> feature/visual-crossing-api

## Language & Runtime
**Language**: Python
**Version**: Python 3.7+ (3.11+ recommended)
<<<<<<< HEAD
**Build System**: setuptools, Briefcase (for Toga)
**Package Manager**: pip

## Code Quality Tools
**Linting & Formatting**: Ruff (configured in pyproject.toml)
**Type Checking**: mypy
**Line Length**: 100 characters
**Target Python**: 3.12

### Protecting Code from Ruff Auto-fixes
To prevent Ruff from modifying specific code sections:

1. **Inline noqa comments** - Disable specific rules:
   ```python
   # This import is needed for runtime type checking
   from typing import TYPE_CHECKING  # noqa: F401

   # Keep specific formatting intact
   my_list = [  # noqa: E201
       1,
       2,
   ]
   ```

2. **Block-level disabling** - For multiple lines:
   ```python
   # fmt: off
   matrix = [
       1, 0, 0,
       0, 1, 0,
       0, 0, 1,
   ]
   # fmt: on
   ```

3. **File-level configuration** - In pyproject.toml:
   ```toml
   [tool.ruff.lint.per-file-ignores]
   "src/accessiweather/legacy_module.py" = ["E501", "F401"]
   ```

4. **Ruff directives** - For specific sections:
   ```python
   # ruff: noqa
   import sys, os, re
   # ruff: noqa: end
   ```

## Dependencies
**Main Dependencies**:
- toga: Cross-platform GUI toolkit (replacing wxPython)
- httpx: Modern HTTP client
- geopy: Geocoding library
- desktop-notifier: Cross-platform notifications
- python-dateutil: Date parsing utilities
- beautifulsoup4: HTML parsing
- attrs: Data classes
- psutil: Process and system monitoring

**Development Dependencies**:
- pytest: Testing framework
- pytest-mock: Mocking for tests
- pytest-cov: Coverage reporting
- PyInstaller: Binary packaging
- ruff: Linting, formatting, and import sorting

## Build & Installation
=======
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
>>>>>>> feature/visual-crossing-api
```bash
# Install from source
pip install -e .

<<<<<<< HEAD
# Run the application
accessiweather

# Build with Briefcase (Toga)
briefcase build
briefcase run

# Build Windows installer
.\installer\build_installer.ps1
```

## Migration Status
The application is being migrated from wxPython to Toga/BeeWare:

- **Original Architecture**: wxPython-based GUI with complex service layers
- **New Architecture**: Simplified Toga-based implementation with async-first approach
- **Migration Strategy**:
  - Simplified data models
  - Async-first API calls
  - Improved testability
  - Better cross-platform support

The new implementation is located in `src/accessiweather/simple/` with Toga-specific tests in `tests/test_toga_*.py`.

## Weather Data Sources
- **National Weather Service (NWS)**: US locations with alerts
- **Open-Meteo**: International locations
- **Visual Crossing**: Additional provider (optional)

## Testing
**Framework**: pytest with pytest-asyncio
**Test Location**: tests/ directory
**Naming Convention**: test_*.py
**Configuration**: pytest.ini
**Run Command**:
```bash
pytest
```

## Key Features
- **Accessibility**: Screen reader compatibility, keyboard navigation
- **Multiple Weather Sources**: NWS, Open-Meteo, Visual Crossing
- **System Integration**: System tray, desktop notifications
- **Customization**: Temperature units, update intervals, alert settings
- **Cross-platform**: Windows, Linux support (macOS in development)
=======
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
>>>>>>> feature/visual-crossing-api
