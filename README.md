# AccessiWeather

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Platforms](https://img.shields.io/badge/Platforms-Windows%20%7C%20macOS%20%7C%20Linux-informational)
![Accessibility](https://img.shields.io/badge/Accessibility-Screen%20Reader%20Friendly-success)
[![Latest Release](https://img.shields.io/github/v/release/Orinks/AccessiWeather?sort=semver)](https://github.com/Orinks/AccessiWeather/releases)
[![Download](https://img.shields.io/badge/Download-GitHub%20Pages-2ea44f)](https://accessiweather.orinks.net)

A desktop weather application built for accessibility. Get current conditions, forecasts, and severe weather alerts with full screen reader support and keyboard navigation.

🌐 **Website**: [accessiweather.orinks.net](https://accessiweather.orinks.net)

## Download

Visit our [Releases page](https://github.com/Orinks/AccessiWeather/releases) or [accessiweather.orinks.net](https://accessiweather.orinks.net) to download:

- **Windows Installer (MSI)**: Full installation with Start Menu integration
- **Windows Portable (ZIP)**: Run from any folder without installation
- **macOS (DMG)**: Standard macOS application bundle

## Features

### Weather Data
- **Multiple providers**: National Weather Service (US), Open-Meteo (worldwide), Visual Crossing (global alerts)
- **Smart automatic mode**: Combines the best from each source—NWS discussions for US, Open-Meteo for international, Visual Crossing for global alerts
- **Current conditions**: Temperature, humidity, wind, pressure
- **Extended forecasts**: 7-day detailed forecasts
- **Hourly forecasts**: Short-term predictions
- **Weather alerts**: Watches, warnings, and advisories with desktop notifications
- **Forecast discussions**: In-depth analysis from Weather Prediction Center and Storm Prediction Center

### Accessibility
- **Full screen reader support**: Tested with NVDA, JAWS, and VoiceOver
- **Complete keyboard navigation**: Every feature accessible without a mouse
- **Clear focus indicators**: Always know where you are
- **Accessible notifications**: Screen reader-friendly alerts

### Additional Features
- **System tray**: Minimize to tray, quick access via context menu
- **Multiple locations**: Save and switch between favorite places
- **Portable mode**: Keep config alongside the app
- **Customizable units**: Fahrenheit, Celsius, or both
- **Smart caching**: Fast and responsive, even on slower connections

## Getting Started

1. **Download and install** from [accessiweather.orinks.net](https://accessiweather.orinks.net)
2. **Launch AccessiWeather**
3. **Add a location**: Search by address, ZIP code, or coordinates
4. **Configure your preferences** in Settings (optional):
   - Weather data source
   - Temperature units
   - Update interval
   - Notification settings

### API Setup (Optional)

- **NOAA contact info**: Required for NWS data (prompted on first use)
- **Visual Crossing API key**: Optional, enables global weather alerts. Get a free key at [visualcrossing.com](https://www.visualcrossing.com)

## System Requirements

- **Windows 10+**, macOS, or Linux
- Internet connection for weather data

## Support

- **Website**: [accessiweather.orinks.net](https://accessiweather.orinks.net)
- **User Manual**: [docs/user_manual.md](docs/user_manual.md)
- **Report Issues**: [GitHub Issues](https://github.com/Orinks/AccessiWeather/issues)

## Contributing

We welcome contributions! Check out the [dev branch](https://github.com/Orinks/AccessiWeather/tree/dev) for development setup and guidelines, or see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- **National Weather Service** for reliable US weather data
- **Open-Meteo** for free international weather coverage
- **BeeWare/Toga** for the cross-platform GUI framework
- **Accessibility community** for testing and feedback
