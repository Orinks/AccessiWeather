# AccessiWeather

Accessible desktop weather for Windows, macOS, and Linux.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
[![Built with wxPython](https://img.shields.io/badge/Built%20with-wxPython-blue)](https://wxpython.org/)
![Platforms](https://img.shields.io/badge/Platforms-Windows%20%7C%20macOS%20%7C%20Linux-informational)

AccessiWeather is a screen-reader-friendly weather app with keyboard navigation, desktop notifications, optional alert sounds, and multiple weather providers. It keeps current conditions, daily forecast, hourly forecast, and alerts in separate sections so the information is easier to scan with speech or braille.

## User Manual

For setup instructions, everyday workflows, settings, troubleshooting, and weather-source guidance, see the full [User Manual](docs/user_manual.md).

## Highlights

- Accessible desktop weather designed for screen readers and keyboard use
- Separate Current Conditions, Daily Forecast, Hourly Forecast, and Weather Alerts sections
- Support for US and international locations
- Forecast discussions, weather history, air quality, UV, aviation weather, and NOAA Weather Radio
- Optional AI explanations and Weather Assistant chat through OpenRouter
- Optional notification sounds and sound packs

## Weather Sources

AccessiWeather supports three providers:

- National Weather Service (NWS): best for US forecasts, US alerts, and forecast discussions
- Open-Meteo: global no-key forecast coverage
- Pirate Weather: optional key, global alerts, minutely precipitation, moon phase, and summary-style forecasts

### Automatic mode

Automatic is the default source mode.

- Default behavior is Max coverage, a fusion-first mode that combines all enabled and available sources for the current region.
- Economy and Balanced are optional reduced-call modes.
- US and international automatic source lists are configured separately.
- Automatic mode follows your saved source ordering.
- US alerts use NWS as the authoritative source when available.
- International alerts use Pirate Weather when it is available.

For the full explanation of source behavior, see the [User Manual](docs/user_manual.md#6-weather-sources-and-automatic-mode).

## Optional API Keys

AccessiWeather works without paid services, but some features need optional keys:

- Pirate Weather: global alerts, minutely precipitation, Dark Sky-style summaries
  - https://pirate-weather.apiable.io/
- OpenRouter: Explain Weather and Weather Assistant
  - https://openrouter.ai/keys
- AVWX: optional extra support for international aviation weather
  - https://account.avwx.rest

API keys are stored in your system keyring by default. In portable mode, encrypted API key bundles are used instead.

## Install

### Prebuilt downloads

Download builds from:

- https://orinks.net/accessiweather
- https://github.com/Orinks/AccessiWeather/releases

Packages currently include:

- Windows: MSI installer or portable ZIP
- macOS: DMG
- Linux: run from source

### Run from source

Using uv:

```bash
git clone https://github.com/Orinks/AccessiWeather.git
cd AccessiWeather
uv sync
uv run accessiweather
```

Using a virtual environment:

```bash
git clone https://github.com/Orinks/AccessiWeather.git
cd AccessiWeather
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
accessiweather
```

Portable mode:

```bash
accessiweather --portable
```

## Quick start

1. Launch AccessiWeather.
2. Add your first location when prompted, or later with Ctrl+L.
3. Leave the weather source on Automatic unless you want a specific provider.
4. Refresh to load current conditions, forecast, and alerts.
5. Open the [User Manual](docs/user_manual.md) for detailed settings and troubleshooting help.

## Documentation

- [User Manual](docs/user_manual.md)
- [Accessibility Guide](docs/ACCESSIBILITY.md)
- [Sound Pack System](docs/SOUND_PACK_SYSTEM.md)
- [Update System](docs/UPDATE_SYSTEM.md)

## Support

- https://github.com/Orinks/AccessiWeather/issues
- https://github.com/Orinks/AccessiWeather/discussions
- https://orinks.net/accessiweather
- https://github.com/Orinks/AccessiWeather/releases

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md).

## License

MIT. See [LICENSE](LICENSE).
