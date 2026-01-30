# AccessiWeather

**Weather that speaks to you.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
[![Built with wxPython](https://img.shields.io/badge/Built%20with-wxPython-blue)](https://wxpython.org/)
![Platforms](https://img.shields.io/badge/Platforms-Windows%20%7C%20macOS%20%7C%20Linux-informational)

AccessiWeather is a cross-platform, accessible weather application built with Python and wxPython. Get detailed weather forecasts, alerts, and conditions with full screen reader support, customizable audio alerts, and keyboard navigation.

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

## Troubleshooting

### Antivirus False Positives

Some antivirus software (e.g., Avast, AVG) may flag AccessiWeather's auto-update service as malicious during builds or first run. This is a **false positive** caused by the update mechanism using standard Windows patterns (batch scripts, PowerShell for ZIP extraction) that superficially resemble malware techniques.

**The code is safe** - our update service:
- Only downloads from official GitHub releases
- Verifies all downloads with SHA256 checksums
- Uses no obfuscation or suspicious network calls

**If flagged:**
1. Report as false positive to your antivirus vendor
2. Add an exception for AccessiWeather in your antivirus settings
3. The flagged file is typically `github_update_service.cpython-*.pyc` in `__pycache__`

See [docs/UPDATE_SYSTEM.md](docs/UPDATE_SYSTEM.md) for technical details about the update system's security measures.

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

### Quick Start with uv (Recommended)

[uv](https://docs.astral.sh/uv/) handles everything automatically — no manual environment activation needed.

```bash
# Install uv first (if you don't have it)
# Windows (PowerShell):
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# macOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and run
git clone https://github.com/Orinks/AccessiWeather.git
cd AccessiWeather
uv sync
uv run python -m accessiweather
```

### Traditional Method

```bash
# Clone and setup
git clone https://github.com/Orinks/AccessiWeather.git
cd AccessiWeather
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Run the app
python -m accessiweather

# Run tests
pytest -n auto
```

### Key Commands

```bash
# Development
uv run python -m accessiweather  # Run the app
uv run pytest -n auto            # Run tests (parallel)
uv run ruff check --fix .        # Lint and fix
uv run ruff format .             # Format code
uv run pyright                   # Type checking
```

See [AGENTS.md](AGENTS.md) for detailed development conventions, architecture overview, and CI/CD information.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Built with [wxPython](https://wxpython.org/) for accessible cross-platform GUI development. Weather data provided by:

- [National Weather Service](https://www.weather.gov/) (US)
- [Open-Meteo](https://open-meteo.com/) (Global)
- [Visual Crossing](https://www.visualcrossing.com/) (Optional, for historical data)

## Related Projects

- [AccessiSky](https://github.com/Orinks/AccessiSky) - Accessible sky tracking app (ISS passes, moon phases, aurora forecasts)
