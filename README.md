# AccessiWeather

Accessible desktop weather for Windows, macOS, and Linux.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
[![Built with wxPython](https://img.shields.io/badge/Built%20with-wxPython-blue)](https://wxpython.org/)
![Platforms](https://img.shields.io/badge/Platforms-Windows%20%7C%20macOS%20%7C%20Linux-informational)

AccessiWeather is a screen-reader-friendly weather app with keyboard navigation, desktop notifications, optional alert sounds, and multiple weather sources. It separates current conditions, daily forecast, hourly forecast, and alerts so the information is easier to scan with speech or braille.

## What It Does

- Combines multiple weather sources instead of locking you to one provider
- Shows separate `Current Conditions`, `Daily Forecast`, `Hourly Forecast`, and `Weather Alerts` sections
- Supports US and international locations
- Tracks alert lifecycle changes such as new, updated, escalated, extended, and cancelled alerts
- Offers optional AI weather explanations and a conversational Weather Assistant
- Includes weather history, air quality, UV index, aviation weather, NOAA Weather Radio, and sound pack support

## Weather Sources

AccessiWeather supports four weather providers:

- **National Weather Service (NWS)**: Best for US forecasts, US alerts, and forecast discussions. This is the authoritative alert source for US locations.
- **Open-Meteo**: No API key required. Good global baseline forecasts, Open-Meteo model selection, and broad international coverage. It does not provide weather alerts in AccessiWeather.
- **Pirate Weather**: Optional API key. Best when you want worldwide WMO alerts, minutely precipitation guidance, and Dark Sky-style daily summaries. It is especially useful outside the US.
- **Visual Crossing**: Optional API key. Useful for weather history, global forecasts, and some alert coverage where available.

### Automatic Mode

`Automatic` is the default. It merges available sources and uses source priority rules to fill gaps.

- For **US locations**, AccessiWeather uses **NWS alerts only**. Pirate Weather and Visual Crossing alerts are intentionally ignored there to avoid duplicate alerts with weaker metadata.
- For **international locations**, AccessiWeather uses **Pirate Weather alerts when available**, otherwise **Visual Crossing** if configured.
- If you add a Pirate Weather key, Automatic mode can also pull **minutely precipitation** guidance.
- `Automatic` still uses your configured **US** and **International** source-priority presets for current conditions and forecast merging.

## Alerts

Alert behavior depends on the source and location:

- **NWS alerts**: Best for US users. They include stronger metadata such as severity, urgency, certainty, and NWS-specific targeting options.
- **Pirate Weather alerts**: Based on worldwide WMO alert feeds. These are useful outside the US, but they may be broader regional alerts and may not match your exact county or zone.
- **Visual Crossing alerts**: Available in some regions, but they are generally less detailed than NWS for US use.

In the app you can:

- Enable or disable alerts entirely
- Enable desktop alert notifications separately
- Choose alert area behavior for NWS alerts: county, point, zone, or state
- Filter notifications by severity
- Turn on event notifications for forecast discussion updates, severe risk changes, and minutely precipitation start/stop

## Optional API Keys

AccessiWeather works without paid services, but some features need optional keys:

- **Pirate Weather**: Global alerts, minutely precipitation, Dark Sky-style summaries
  - Get a key at [pirate-weather.apiable.io](https://pirate-weather.apiable.io/)
- **Visual Crossing**: Weather history, global forecast enrichment, some regional alerts
  - Get a key at [visualcrossing.com/weather-api](https://www.visualcrossing.com/weather-api)
- **OpenRouter**: Required for `Explain Weather` and `Weather Assistant`
  - Get a key at [openrouter.ai/keys](https://openrouter.ai/keys)
- **AVWX**: Optional for better international aviation weather translations and speech output
  - Entered from the `Aviation Weather` dialog, not the main Settings dialog
  - Get a key at [account.avwx.rest](https://account.avwx.rest)

API keys are stored in your system keyring by default.

### Portable API Key Transfer

Settings export/import does not include API keys. If you want to move keys between machines:

1. Open `Settings > Advanced`.
2. Choose `Export API keys (encrypted)`.
3. Save the encrypted bundle and remember the passphrase.
4. On the other machine, use `Import API keys (encrypted)` and enter the same passphrase.

## Install

### Prebuilt Downloads

Download builds from [orinks.net/accessiweather](https://orinks.net/accessiweather) or the [GitHub releases page](https://github.com/Orinks/AccessiWeather/releases).

- **Windows**: MSI installer or portable ZIP
- **macOS**: DMG
- **Linux**: Build from source for now

### Run From Source

Using `uv`:

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

Portable mode is also available:

```bash
accessiweather --portable
```

## First Run

On a fresh setup, AccessiWeather shows a short onboarding wizard.

1. Launch AccessiWeather.
2. In the onboarding wizard, add your first location or skip it for now.
3. Optionally enter OpenRouter, Visual Crossing, and Pirate Weather API keys during onboarding.
4. In portable mode, if you enter API keys, you can also create an encrypted portable key bundle during onboarding.
5. After the wizard closes, review the readiness summary, then refresh to load current conditions, daily forecast, hourly forecast, and alerts.

If you need to run the onboarding wizard again manually, launch the app with `--wizard`.

## Main Views

- **Current Conditions**: Temperature, condition, wind, humidity, and other enabled metrics
- **Daily Forecast**: Multi-day forecast in its own section
- **Hourly Forecast**: Separate short-range outlook with configurable hour count
- **Weather Alerts**: Active alerts with lifecycle labels when alerts change
- **Forecast Discussion**: NWS Area Forecast Discussion for US locations
- **Explain Weather**: One-shot AI summary of the current weather
- **Weather Assistant**: Chat-style AI weather help

If Pirate Weather minutely data is available, AccessiWeather adds a short precipitation outlook to current conditions and can notify you when precipitation is about to start or stop.

## Settings Overview

The Settings dialog currently includes these tabs:

- **General**: Update interval, Nationwide location, tray text
- **Display**: Units, visible metrics, forecast length, hourly hours, time display, verbosity
- **Data Sources**: Source selection, Pirate Weather key, Visual Crossing key, Open-Meteo model, NWS station selection
- **Notifications**: Alert behavior, severities, event notifications, cooldowns
- **Audio**: Sound packs and per-event sound controls
- **Updates**: Update channel and check interval
- **AI**: OpenRouter key, model, explanation style, custom prompts
- **Advanced**: Portable/config tools, settings backup, encrypted API key transfer, resets

## Keyboard Shortcuts

The current code binds these global shortcuts:

- `Ctrl+R` or `F5`: Refresh weather
- `Ctrl+L`: Add location
- `Ctrl+D`: Remove location
- `Ctrl+H`: Weather history
- `Ctrl+S`: Open settings
- `Ctrl+Q`: Quit
- `Ctrl+E`: Explain Weather
- `Ctrl+T`: Open Weather Assistant
- `Ctrl+Shift+R`: Open NOAA Weather Radio

## Documentation

- [User Manual](docs/user_manual.md)
- [Accessibility Guide](docs/ACCESSIBILITY.md)
- [Sound Pack System](docs/SOUND_PACK_SYSTEM.md)
- [Update System](docs/UPDATE_SYSTEM.md)

## Support

- [GitHub Issues](https://github.com/Orinks/AccessiWeather/issues)
- [GitHub Discussions](https://github.com/Orinks/AccessiWeather/discussions)
- [Project website](https://orinks.net/accessiweather)
- [GitHub Releases](https://github.com/Orinks/AccessiWeather/releases)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md).

## License

MIT. See [LICENSE](LICENSE).
