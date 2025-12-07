# AccessiWeather

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
[![Built with BeeWare/Toga](https://img.shields.io/badge/Built%20with-BeeWare%20%2F%20Toga-ff6f00)](https://beeware.org/)
![Platforms](https://img.shields.io/badge/Platforms-Windows%20%7C%20macOS%20%7C%20Linux-informational)

AccessiWeather is a cross-platform, accessible weather application built with Python and BeeWare/Toga. Get detailed weather forecasts, alerts, and conditions with full screen reader support and keyboard navigation.

## Features

- **Multi-Source Weather Data**: Combines National Weather Service (NWS), Open-Meteo, and Visual Crossing for comprehensive coverage
- **Weather Alerts**: Real-time notifications for severe weather with customizable alert sounds
- **Accessibility First**: Full screen reader support, keyboard shortcuts, and ARIA labels throughout
- **Air Quality & Environmental Data**: Track AQI, pollen, UV index, and more
- **Weather History**: View historical weather trends and patterns
- **Aviation Weather**: TAF/METAR decoding for pilots
- **Sound Packs**: Customize alert sounds with community-created packs
- **Offline Support**: Smart caching keeps data available when you're offline
- **Multiple Locations**: Save and switch between your favorite locations

## Installation

### Download Installers

Visit [accessiweather.orinks.net](https://accessiweather.orinks.net) to download:

- **Windows**: MSI installer or portable ZIP
- **macOS**: DMG installer
- **Linux**: AppImage (coming soon)

### Nightly Builds

Want to test the latest features? Nightly builds are available from the [dev branch](https://github.com/Orinks/AccessiWeather/tree/dev):

- Download from [GitHub Actions](https://github.com/Orinks/AccessiWeather/actions/workflows/briefcase-build.yml) (select a successful run → Artifacts)
- See [docs/nightly-link-setup.md](docs/nightly-link-setup.md) for direct download links

⚠️ Nightly builds may contain bugs or incomplete features.

## Getting Started

1. **Launch AccessiWeather** after installation
2. **Add a location**: Click "Add Location" or press `Ctrl+L` (Windows/Linux) / `Cmd+L` (macOS)
3. **View weather**: Select your location and choose from Current Conditions, Forecast, Alerts, and more
4. **Customize settings**: Access Settings via the menu or `Ctrl+,` / `Cmd+,`

### Keyboard Shortcuts

- `Ctrl/Cmd + L` - Add/manage locations
- `Ctrl/Cmd + R` - Refresh weather data
- `Ctrl/Cmd + ,` - Open settings
- `Ctrl/Cmd + Q` - Quit application
- `F1` - Help/documentation

See the [User Manual](docs/user_manual.md) for complete documentation.

## Configuration

AccessiWeather stores your settings and locations in:

- **Windows**: `%APPDATA%\accessiweather\accessiweather.json`
- **macOS**: `~/Library/Application Support/accessiweather/accessiweather.json`
- **Linux**: `~/.config/accessiweather/accessiweather.json`

You can export and import your configuration from the Settings dialog.

## API Keys (Optional)

AccessiWeather works out of the box with free data sources (NWS and Open-Meteo). For enhanced features, you can add:

- **Visual Crossing API**: Historical weather data and extended forecasts
  - Get a free key at [visualcrossing.com](https://www.visualcrossing.com/weather-api)
  - Add in Settings → Weather Sources

## Documentation

- [User Manual](docs/user_manual.md) - Complete guide to using AccessiWeather
- [Accessibility Guide](docs/ACCESSIBILITY.md) - Screen reader tips and keyboard navigation
- [Sound Pack System](docs/SOUND_PACK_SYSTEM.md) - Create and install custom alert sounds
- [Update System](docs/UPDATE_SYSTEM.md) - How automatic updates work

## Support & Community

- **Issues**: Report bugs or request features on [GitHub Issues](https://github.com/Orinks/AccessiWeather/issues)
- **Discussions**: Join the conversation on [GitHub Discussions](https://github.com/Orinks/AccessiWeather/discussions)
- **Website**: [accessiweather.orinks.net](https://accessiweather.orinks.net)

## Contributing

We welcome contributions! Whether you're fixing bugs, adding features, or improving documentation:

1. Fork the repo and create a feature branch from `dev`
2. Make your changes with tests
3. Run linting: `ruff check --fix . && ruff format .`
4. Run tests: `pytest -n auto`
5. Submit a PR to `dev`

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## Development

### Quick Setup

```bash
# Clone and setup
git clone https://github.com/Orinks/AccessiWeather.git
cd AccessiWeather
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Run the app
briefcase dev

# Run tests
pytest -n auto
```

### Key Commands

```bash
# Development
briefcase dev              # Run with hot reload
pytest -n auto             # Run tests (parallel)
ruff check --fix .         # Lint and fix
ruff format .              # Format code
pyright                    # Type checking

# Building
briefcase create           # Create platform skeleton
briefcase build            # Build app
briefcase package          # Generate installer
```

See [AGENTS.md](AGENTS.md) for detailed development conventions, architecture overview, and CI/CD information.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Built with [BeeWare/Toga](https://beeware.org/) for cross-platform Python GUI development. Weather data provided by:

- [National Weather Service](https://www.weather.gov/) (US)
- [Open-Meteo](https://open-meteo.com/) (Global)
- [Visual Crossing](https://www.visualcrossing.com/) (Optional, for historical data)
