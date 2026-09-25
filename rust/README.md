# AccessiWeather — native Rust edition

A native desktop port of AccessiWeather (no Python, no webview). The UI is
built with [wxDragon](https://crates.io/crates/wxdragon), the Rust bindings
for wxWidgets, so every control is the platform's own (Win32 on Windows,
Cocoa on macOS, GTK on Linux) and is exposed to screen readers through UIA,
NSAccessibility and AT-SPI respectively, like the wxPython edition.

## Crates

| Crate | Purpose |
|-------|---------|
| `aw-core` | Domain models, settings (JSON-compatible with the Python app), units, source planning, alerts, text presentation |
| `aw-providers` | NWS, Open-Meteo, Pirate Weather, geocoding, multi-source fetch/merge with fallback |
| `aw-store` | Config directories, portable mode, atomic JSON persistence |
| `aw-speech` | Bounded worker-thread text-to-speech (`tts` crate) with recording/null sinks for tests |
| `aw-app` (`accessiweather`) | The executable: CLI, wxDragon windows and dialogs, refresh loop |

## Building

```bash
cd rust
cargo build --release -p accessiweather
./target/release/accessiweather            # live weather
./target/release/accessiweather --offline  # bundled sample data
./target/release/accessiweather --check    # headless self-check, exit 0 on success
./target/release/accessiweather --smoke    # open the window on sample data, exit 0 after ~2 s
```

wxDragon compiles wxWidgets from source on first build (needs CMake and a C++
toolchain; allow several minutes). Linux build dependencies (Debian/Ubuntu):
`cmake build-essential libclang-dev libspeechd-dev libgtk-3-dev
libgl1-mesa-dev libglu1-mesa-dev`.

Keyboard shortcuts: F5 / Ctrl+R refresh, Alt+A add location, Ctrl+, settings,
Ctrl+D forecast discussion, Ctrl+Shift+S read aloud, Escape stop speaking or
close a dialog, Ctrl+1..5 jump to the location, current, hourly, extended and
alerts panels, Ctrl+Q quit. On macOS use Command in place of Ctrl.

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
