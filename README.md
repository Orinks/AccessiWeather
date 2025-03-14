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

## Requirements

- Python 3.7+
- wxPython
- Internet connection for NOAA data access

## GitHub Repository

The project is available on GitHub at [Orinks/AccessiWeather](https://github.com/Orinks/AccessiWeather)
