# AccessiWeather (v0.9.4-dev)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
[![Built with BeeWare/Toga](https://img.shields.io/badge/Built%20with-BeeWare%20%2F%20Toga-ff6f00)](https://beeware.org/)
[![Packaging: Briefcase](https://img.shields.io/badge/Packaging-Briefcase-6f42c1)](https://briefcase.readthedocs.io/)
![Platforms](https://img.shields.io/badge/Platforms-Windows%20%7C%20macOS%20%7C%20Linux-informational)
![Accessibility](https://img.shields.io/badge/Accessibility-Screen%20Reader%20Friendly-success)
[![Download](https://img.shields.io/badge/Download-GitHub%20Pages-2ea44f)](https://orinks.github.io/AccessiWeather/)
[![Latest Release](https://img.shields.io/github/v/release/Orinks/AccessiWeather?sort=semver)](https://github.com/Orinks/AccessiWeather/releases)



A desktop weather application with robust accessibility features and international weather support. Built using the BeeWare/Toga framework with a focus on screen reader compatibility and keyboard navigation.

## Quickstart (Developers)

- Prereqs: Python 3.10+ (3.12 recommended), Git
- Create a virtual environment and install dev deps:

```bash
python -m venv .venv
# Windows (bash)
source .venv/Scripts/activate
# macOS/Linux
# source .venv/bin/activate
pip install -e ".[dev]"
```

- Run the app with Briefcase during development:

```bash
briefcase dev
```

- Run tests and linters:

```bash
pytest -q
ruff check --fix . && ruff format
```

## Packaging & Distribution (Briefcase)

This project uses BeeWare Briefcase for packaging. Common commands:

```bash
# Create platform-specific project skeletons
briefcase create

# Build app artifacts
briefcase build

# Generate distributables (MSI/DMG/PKG/ZIP where supported)
briefcase package
```

Updates are delivered via GitHub Releases and integrated with the app’s Settings → Updates tab.

### Using installer/make.py

A convenience wrapper around Briefcase is provided at installer/make.py:

```bash
# Show environment and detected versions
python installer/make.py status

# First-time platform scaffold (windows|macOS|linux)
python installer/make.py create --platform windows

# Build and then package an installer (MSI/DMG/PKG depending on platform)
python installer/make.py build --platform windows
python installer/make.py package --platform windows

# Run the app in development mode (same as `briefcase dev`)
python installer/make.py dev

# Run tests in a Briefcase dev app (falls back to pytest if needed)
python installer/make.py test

# Create a portable ZIP from the build output (Windows-focused helper)
python installer/make.py zip --platform windows

# Clean Briefcase artifacts
python installer/make.py clean --platform windows
```


## Configuration & Portable Mode

- Default config/data lives in a user app data directory (platform-dependent)
- Portable mode stores configuration alongside the app; you can force it with:

```bash
accessiweather --portable
```

## Project Structure (high level)

- src/accessiweather: main application package (Toga app, dialogs, services, clients)
- tests: unit/integration tests (Toga dummy used where needed)
- pyproject.toml: project metadata, Briefcase and Ruff configuration
- pytest.ini: test configuration

## Accessibility

- Screen reader friendly text and focus management
- Keyboard-first navigation across all dialogs and main views
- Temperature display format: 84°F (29°C)

## Notes

- This README section reflects the current Toga + Briefcase workflow.
- The legacy “Building Binaries” section below describes a historical PyInstaller/Inno Setup process; use Briefcase for packaging going forward.


## Features

### Weather Data Sources
- **Multiple weather providers**: Choose between National Weather Service (NWS), Open-Meteo, or automatic selection
- **International support**: Open-Meteo integration provides free weather data for locations worldwide
- **Automatic provider selection**: Uses NWS for US locations (with alerts) and Open-Meteo for international locations
- **Real-time weather data**: Current conditions, forecasts, and alerts from trusted sources

### Location Management
- **Multiple saved locations**: Save and switch between favorite locations
- **Flexible location search**: Search by address, ZIP code, or coordinates
- **Manual coordinate entry**: Precise location specification support
- **Automatic location persistence**: Your locations are remembered between sessions
- **Nationwide view**: National weather outlook and discussions

### Comprehensive Weather Information
- **Current conditions**: Real-time temperature, humidity, wind speed, and pressure
- **Extended forecasts**: 7-day detailed forecasts with all 14 periods
- **Hourly forecasts**: Short-term detailed predictions
- **Weather alerts**: Active watches, warnings, and advisories (NWS locations only)
- **Weather discussions**: In-depth analysis from Weather Prediction Center and Storm Prediction Center
- **Weather history tracking**: Compare current weather with past days (yesterday, last week)
- **Configurable updates**: Customizable refresh intervals (1-1440 minutes)

### System Integration
- **System tray support**: Minimize to system tray with context menu access
- **Desktop notifications**: Real-time alerts for severe weather conditions
- **Portable mode**: Automatic detection for portable installations
- **Keyboard shortcuts**: Escape key to minimize to tray, full keyboard navigation

### Display & Customization
- **Temperature units**: Choose Fahrenheit, Celsius, or display both
- **Dynamic taskbar icons**: Customizable weather-based icon text
- **Precise location alerts**: County/township level alert targeting
- **Configurable alert radius**: Customize alert coverage area (miles)

### Accessibility Features
- **Full screen reader compatibility**: Tested with NVDA, JAWS, and other screen readers
- **Complete keyboard navigation**: All features accessible without a mouse
- **Accessible UI controls**: Properly labeled widgets and clear focus indicators
- **Clear notifications**: Screen reader-friendly alert and status messages

## Installation

### Option 1: Download Pre-built Binaries (Recommended)
Visit our [GitHub Pages download site](https://orinks.github.io/AccessiWeather/) to download:
- **Windows Installer**: Full installation with Start Menu integration
- **Portable Version**: Run from any folder without installation

### Option 2: Install from Source
```bash
# Clone the repository
git clone https://github.com/Orinks/AccessiWeather.git
cd AccessiWeather

# Install in development mode
pip install -e .
```

### Option 3: Run with Portable Mode
```bash
# Force portable mode (saves config in app directory)
accessiweather --portable
```

## First-time Setup

1. **Run the application** to create the configuration directory:
   ```bash
   accessiweather
   ```

2. **Configure weather data source** (optional):
   - Go to Settings → General tab
   - Choose your preferred weather data source:
     - **National Weather Service**: US locations only (includes alerts)
     - **Open-Meteo**: International locations (no alerts)
     - **Automatic**: Best of both (recommended)

3. **NOAA API setup** (required for NWS data):
   - The application will prompt for your contact information
   - This is required by NOAA's terms of service for API access
   - Your information is stored locally and only sent to NOAA

4. **Customize settings** (optional):
   - Update interval (1-1440 minutes)
   - Temperature units (Fahrenheit, Celsius, or both)
   - Alert radius and precision
   - System tray behavior
   - Taskbar icon customization


## Requirements

- **Python 3.7+** (Python 3.11+ recommended for best performance)
- **Toga** (BeeWare GUI framework, automatically installed with pip)
- **Internet connection** for weather data access
- **Windows 10+** (primary platform), Linux and macOS support available

## Weather Data Sources

### National Weather Service (NWS)
- **Coverage**: United States only
- **Features**: Weather alerts, watches, warnings, detailed forecasts
- **API**: Free, no registration required
- **Contact info**: Required by NOAA terms of service

### Open-Meteo
- **Coverage**: Worldwide
- **Features**: Current conditions, forecasts (no alerts)
- **API**: Free, no registration required
- **Limitations**: No severe weather alerts available

### Automatic Mode (Recommended)
- **US locations**: Uses NWS (includes alerts)
- **International locations**: Uses Open-Meteo
- **Best of both**: Maximum coverage with alerts where available

## Known Issues

- **Screen reader parsing**: Nationwide discussions may be read incorrectly by some screen readers despite correct data formatting
- **Escape key**: Minimize to tray shortcut may not work consistently in all scenarios
- **Linux support**: Experimental - some features may not work as expected
- **API limitations**: Open-Meteo does not provide severe weather alerts
- **Geocoding**: May occasionally find locations outside supported coverage areas

## Usage Tips

### Keyboard Navigation
- **Tab/Shift+Tab**: Navigate between controls
- **Enter/Space**: Activate buttons and checkboxes
- **Arrow keys**: Navigate lists and dropdowns
- **Escape**: Minimize to system tray (when enabled)
- **F5**: Refresh weather data
- **Ctrl+S**: Open settings dialog

### System Tray
- **Right-click tray icon**: Access context menu
- **Double-click tray icon**: Show/hide main window
- **Minimize behavior**: Configurable in settings

### Weather Alerts
- **Desktop notifications**: Automatic for new alerts
- **Alert details**: Click any alert for full information
- **Precise targeting**: County/township level accuracy
- **Customizable radius**: Adjust coverage area in settings

## Contributing

We welcome contributions! Please see our [Developer Guide](docs/developer_guide.md) for information on:
- Setting up the development environment
- Running tests
- Code style guidelines
- Submitting pull requests

## Support & Documentation

- **Download**: [GitHub Pages](https://orinks.github.io/AccessiWeather/)
- **User Manual**: [docs/user_manual.md](docs/user_manual.md)
- **Developer Guide**: [docs/developer_guide.md](docs/developer_guide.md)
- **Report Issues**: [GitHub Issues](https://github.com/Orinks/AccessiWeather/issues)
- **Source Code**: [GitHub Repository](https://github.com/Orinks/AccessiWeather)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- **National Weather Service**: For providing free, reliable weather data
- **Open-Meteo**: For international weather data coverage
- **BeeWare/Toga Community**: For the cross-platform GUI framework
- **Accessibility Community**: For testing and feedback on screen reader compatibility
Test auto-trigger: Sat, Jun  7, 2025  1:42:50 PM
