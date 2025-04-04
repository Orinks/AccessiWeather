# AccessiWeather

A desktop application to check NOAA weather with robust accessibility features built using wxPython.

## Features

- Real-time weather data from NOAA's official API
- Location management:
  - Save multiple locations
  - Search by address or ZIP code
  - Manual coordinate entry support
  - Automatic location persistence
- Comprehensive weather information:
  - Detailed forecasts with temperature and conditions
  - Active weather alerts, watches, and warnings
  - Weather discussion reader for in-depth analysis
  - Auto-refresh every 15 minutes
- Full accessibility support:
  - Screen reader compatibility
  - Keyboard navigation
  - Accessible widgets and controls
  - Clear, readable notifications
- Desktop notifications for weather alerts
- Built using Test-Driven Development practices

## Installation

```bash
pip install -e .
```

## Configuration

1. Copy `config.sample.json` to `config.json`
2. Update the contact information in `config.json` for NOAA API access
3. Customize other settings as needed:
   - Update interval
   - Alert notification duration
   - Alert radius

## Development

This project uses a test-driven development approach. To run tests:

```bash
python -m pytest tests/
```

### GitHub Workflow

This project includes a GitHub workflow that runs on push to main and on pull requests:

- Runs on Windows environment
- Sets up Python 3.12
- Installs dependencies
- Runs linting with flake8
- Checks API connectivity
- Runs tests with pytest

### Pre-commit Hooks

To ensure code quality, this project uses pre-commit hooks. To set up:

```bash
pip install pre-commit
pre-commit install
```

The pre-commit hooks include:
- Code formatting with Black and isort
- Linting with flake8
- Type checking with mypy
- Various file checks (trailing whitespace, YAML validation, etc.)

## Requirements

- Python 3.7+
- wxPython
- Internet connection for NOAA data access

## GitHub Repository

The project is available on GitHub at [Orinks/AccessiWeather](https://github.com/Orinks/AccessiWeather)
