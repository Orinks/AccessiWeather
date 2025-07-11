# AccessiWeather Information

## Summary
AccessiWeather is an accessible weather application that provides current conditions, forecasts, and weather alerts with a focus on screen reader compatibility. The project is currently migrating from wxPython to Toga/BeeWare for improved cross-platform support and accessibility.

## Structure
- **src/accessiweather**: Main application code
  - **simple/**: New Toga-based implementation
  - **gui/**: Original wxPython implementation
- **tests/**: Comprehensive test suite
- **installer/**: Windows installer scripts
- **docs/**: Documentation files

## Language & Runtime
**Language**: Python
**Version**: Python 3.7+ (3.11+ recommended)
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
```bash
# Install from source
pip install -e .

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