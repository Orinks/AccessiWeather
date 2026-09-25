# AccessiWeather — native Rust edition

A native desktop port of AccessiWeather (no Python, no webview). The UI is
built with [Slint](https://slint.dev) and exposes accessibility through
AccessKit (UIA on Windows, NSAccessibility on macOS, AT-SPI on Linux).

## Crates

| Crate | Purpose |
|-------|---------|
| `aw-core` | Domain models, settings (JSON-compatible with the Python app), units, source planning, alerts, text presentation |
| `aw-providers` | NWS, Open-Meteo, Pirate Weather, geocoding, multi-source fetch/merge with fallback |
| `aw-store` | Config directories, portable mode, atomic JSON persistence |
| `aw-speech` | Bounded worker-thread text-to-speech (`tts` crate) with recording/null sinks for tests |
| `aw-app` (`accessiweather`) | The executable: CLI, Slint windows, refresh loop, dialogs |

## Building

```bash
cd rust
cargo build --release -p accessiweather
./target/release/accessiweather            # live weather
./target/release/accessiweather --offline  # bundled sample data
./target/release/accessiweather --check    # headless self-check, exit 0 on success
./target/release/accessiweather --smoke    # open the window on sample data, exit 0 after ~2 s
```

Linux build dependencies (Debian/Ubuntu): `libclang-dev libspeechd-dev
libxkbcommon-dev libwayland-dev libfontconfig1-dev`.

## Configuration

The app reads and writes the same `accessiweather.json` as the Python app:

- Windows: `%LOCALAPPDATA%\Orinks\AccessiWeather\`
- macOS: `~/Library/Application Support/AccessiWeather/`
- Linux: `$XDG_DATA_HOME/accessiweather` (default `~/.local/share/accessiweather`)
- `--portable` or a `config` folder beside the executable: portable mode
- `ACCESSIWEATHER_CONFIG_DIR` / `--config-dir` override everything

Unknown settings keys are preserved on save so the two editions can be used
side by side.

## Packaging

`packaging/package.sh <artifact-name>` produces a tarball (Linux), zip
(Windows) or an ad-hoc-signed `.app` zip (macOS; unsigned for Gatekeeper
purposes until an Apple developer account is available). CI runs this for all
three platforms in `.github/workflows/rust.yml`.

## Not yet ported

Air quality, aviation (METAR/TAF), NOAA Weather Radio, AI explanations,
weather history, sound packs, system-tray/global hotkeys, and the update
checker remain in the Python edition for now.
