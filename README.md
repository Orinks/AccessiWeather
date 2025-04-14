# AccessiWeather (Beta 0.9.0)

A desktop application to check NOAA weather with robust accessibility features built using wxPython. This beta release provides all core functionality and is ready for user testing.

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
- Precise location alerts (county/township level)

## Installation

```bash
# Clone the repository
git clone https://github.com/Orinks/AccessiWeather.git
cd AccessiWeather

# Install in development mode
pip install -e .
```

## First-time Setup

1. Run the application once to create the configuration directory:
   ```bash
   accessiweather
   ```

2. The application will prompt you to enter your contact information for the NOAA API

3. Alternatively, you can manually set up the configuration:
   - Copy `config.sample.json` to `~/.accessiweather/config.json`
   - Update the contact information in `config.json` for NOAA API access
   - Customize other settings as needed:
     - Update interval (minutes)
     - Alert notification duration (seconds)
     - Alert radius (miles)

## Requirements

- Python 3.7+ (Python 3.11 recommended)
- wxPython 4.2.2
- Internet connection for NOAA data access

## Known Issues in Beta

- The geocoding service may find locations outside the United States that the National Weather Service does not support
- The application has been primarily tested on Windows; Linux support is experimental

## Reporting Issues

Please report any issues you encounter on the [GitHub Issues page](https://github.com/Orinks/AccessiWeather/issues).

## GitHub Repository

The project is available on GitHub at [Orinks/AccessiWeather](https://github.com/Orinks/AccessiWeather)
