# AccessiWeather

A free desktop weather app for forecasts, alerts, and detailed weather data.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Rust](https://img.shields.io/badge/Rust-edition-orange)
![Platforms](https://img.shields.io/badge/Platforms-Windows%20%7C%20macOS%20%7C%20Linux-informational)

AccessiWeather brings forecasts, alerts, and detailed weather data into one open-source desktop app for Windows, macOS, and Linux. It keeps current conditions, daily forecast, hourly forecast, and alerts in clearly separated sections so you can jump straight to what you need with speech, braille, or the keyboard.

## User Manual

For setup instructions, everyday workflows, settings, troubleshooting, and weather-source guidance, see the full [User Manual](docs/user_manual.md).

## Highlights

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

- AirNow: official current US Air Quality Index observations
  - https://docs.airnowapi.org/account/request/
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

- Windows: installer `.exe` or portable ZIP
- macOS: ZIP and DMG
- Linux: tarball and AppImage

### Run or build from source

AccessiWeather ships as a native Rust desktop app. See [rust/README.md](rust/README.md) for the full toolchain notes.

```bash
git clone https://github.com/Orinks/AccessiWeather.git
cd AccessiWeather/rust
cargo build --release -p accessiweather
./target/release/accessiweather
```

Useful flags:

```bash
./target/release/accessiweather --portable   # config beside the executable
./target/release/accessiweather --offline    # recorded responses
./target/release/accessiweather --check      # headless self-check
./target/release/accessiweather --smoke      # open a window briefly
```

Release packaging uses `cargo xtask package` (same path as GitHub Actions).


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
