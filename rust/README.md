# AccessiWeather — native Rust edition

A native desktop port of AccessiWeather (no Python, no webview). The UI is
built with [wxDragon](https://crates.io/crates/wxdragon), the Rust bindings
for wxWidgets, so every control is the platform's own (Win32 on Windows,
Cocoa on macOS, GTK on Linux) and is exposed to screen readers through UIA,
NSAccessibility and AT-SPI respectively, like the wxPython edition.

## Crates

| Crate | Purpose |
|-------|---------|
| `aw-core` | Domain models, settings (JSON-compatible with the Python app), source selection, fusion, alert lifecycle, the weather presenter |
| `aw-providers` | NWS, Open-Meteo, Pirate Weather, environmental, geocoding and text-product clients, and the multi-source weather client |
| `aw-store` | Config directories, portable mode, API keys (keyring / encrypted bundle), atomic JSON persistence |
| `aw-audio` | Sound playback (rodio), sound packs, Sound Pack Manager/wizard logic, community packs and pack sharing |
| `aw-radio` | NOAA Weather Radio: station finder, stream lookup, network playback (rodio + symphonia), hotkey toggle, alert auto-tune |
| `aw-ai` | AI explanations, model catalogs, key validation and the Weather Assistant (OpenRouter, Venice) |
| `aw-notify` | Alert and event notification decisions, `runtime_state.json` (shared with Python), toast delivery and click activation |
| `aw-services` | Update checks, launch at login, single instance, settings import/export, logging, onboarding |
| `aw-app` (`accessiweather`) | The executable: CLI, wxDragon windows and dialogs, refresh loop |
| `xtask` | Build, packaging and release tooling (`cargo xtask <cmd>`), replacing the Python scripts |

## Building

```bash
cd rust
cargo build --release -p accessiweather
./target/release/accessiweather            # live weather
./target/release/accessiweather --offline  # recorded NWS/Open-Meteo responses instead of the network
./target/release/accessiweather --check    # headless: replay recorded responses, require the Python app's text
./target/release/accessiweather --smoke    # open the window on sample data, exit 0 after ~2 s
```

wxDragon compiles wxWidgets from source on first build (needs CMake and a C++
toolchain; allow several minutes). Linux build dependencies (Debian/Ubuntu):
`cmake build-essential libclang-dev pkg-config libglibmm-2.68-dev libgtk-3-dev
libgl1-mesa-dev libglu1-mesa-dev libasound2-dev`.

Keyboard shortcuts (the same as the Python app):

- F5 or Ctrl+R: Refresh weather
- Ctrl+L: Add location
- F2: Edit the selected location
- Ctrl+D: Remove location
- Ctrl+S: Open Settings
- Ctrl+H: Open Weather History
- Ctrl+E: Explain Weather
- Ctrl+T: Open Weather Assistant
- Ctrl+N: Open NOAA Weather Radio
- Ctrl+1 to Ctrl+5: Current Conditions, Hourly Forecast, Daily Forecast,
  Weather Alerts, Event Center
- F6: Cycle through the visible sections
- Ctrl+Q: Quit

On macOS use Command in place of Ctrl.

## Configuration

The app reads and writes the same `accessiweather.json` as the Python app:

- Windows: `%LOCALAPPDATA%\Orinks\AccessiWeather\Config\`
- macOS: `~/Library/Application Support/AccessiWeather/Config/`
- Linux: `$XDG_DATA_HOME/accessiweather/Config` (default `~/.local/share/accessiweather/Config`)
- Portable mode (`--portable`, a `.portable` marker, or a `config` folder
  beside the executable): `<exe folder>/config`
- `--config-dir` overrides everything

API keys come from the same places too: the system keyring (service
`accessiweather`), or the encrypted `api-keys.keys` bundle in portable mode.
They are never written to the JSON file. Unknown settings keys are preserved
on save so the two editions can be used side by side.

Screen reader announcements go through [prism](https://github.com/ethindp/prism)
via [prismer](https://crates.io/crates/prismer), the same library the Python
app uses through prismatoid. On Linux and macOS prism is a shared library
shipped next to the executable.

## Build and release tasks (`cargo xtask`)

Run from `rust/` (the alias lives in `rust/.cargo/config.toml`). No Python is
needed anywhere in the pipeline.

| Command | Does | Replaces |
|---------|------|----------|
| `cargo xtask package [ARTIFACT...]` | Release build, staging and packages in `rust/dist/`, each with a `.sha256` | `installer/build_nuitka.py`, `build.py`, `build_appimage.py` |
| `cargo xtask build-meta [TAG]` | Prints `ACCESSIWEATHER_BUILD_TAG=<tag>` for `$GITHUB_ENV`; a nightly tag baked into the build sets the update channel and version display | `scripts/generate_build_meta.py` (and `generate_version.py`, `generate_build_info.py`) |
| `cargo xtask icons` | Draws the app icon into `crates/aw-app/ui/`: `app.ico`, `app.icns`, PNGs and the tray's RGBA frames | `installer/create_icons.py` |
| `cargo xtask changelog check\|notes\|should-build-nightly` | CHANGELOG gate for PRs, release notes, the nightly build decision | `scripts/changelog_tools.py` |
| `cargo xtask pages` | Download page from `docs/index.template.html` (needs `GITHUB_REPOSITORY`, `GITHUB_TOKEN`) | `scripts/build_pages.py` |
| `cargo xtask check-streams [--json] [--fail-on-errors]` | Probes every bundled NOAA Weather Radio stream | `scripts/check_streams.py` |

`package` builds every artifact of the current platform, or the ones named:

| Artifact | File in `rust/dist/` | Release asset |
|----------|----------------------|---------------|
| `windows-setup` | `AccessiWeather_Setup_v<ver>.exe` (Inno Setup; needs ISCC) | `AccessiWeather-<ver>-windows-setup.exe` |
| `windows-portable` | `AccessiWeather_Portable_v<ver>.zip` | `AccessiWeather-<ver>-windows-portable.zip` |
| `macos` | `AccessiWeather_macOS_v<ver>.zip` | `AccessiWeather-<ver>-macOS.zip` |
| `macos-dmg` | `AccessiWeather_v<ver>.dmg` | `AccessiWeather-<ver>-macOS.dmg` |
| `linux` | `AccessiWeather_Linux_v<ver>.tar.gz` | `AccessiWeather-<ver>-linux.tar.gz` |
| `linux-appimage` | `AccessiWeather_Linux_v<ver>_x86_64.AppImage` (downloads linuxdeploy) | `AccessiWeather-<ver>-linux-x86_64.AppImage` |

Nightlies use `nightly-YYYYMMDD` in place of `<ver>` in the release asset
names. These are the Python edition's names, so both editions' updaters find
them. Every package carries the executable (`AccessiWeather.exe` on Windows,
`AccessiWeather` elsewhere), prism's shared library on Linux and macOS, and
the repository's `soundpacks/default`. Windows packages also carry the Visual
C++ runtime DLLs. The portable zip follows the Python rules: a `.portable`
marker, an empty `config` folder and `data/soundpacks/default`. The macOS
app is ad-hoc signed; Gatekeeper users need right-click > Open until there
is a Developer ID. The installer script is `packaging/windows/accessiweather.iss`
and keeps the Python installer's AppId, install folder and uninstall entry,
removing the Python runtime files when it upgrades a Python install.

## Releasing

`.github/workflows/rust-build.yml` builds, smoke-tests and publishes
releases, replacing the Python `build.yml` with the same rules:

- **Nightly** (00:17 UTC, from `dev`): builds only when `CHANGELOG.md` gained
  curated `## [Unreleased]` entries since the last nightly and the latest
  stable release, or a commit says `Nightly: build`. Recreates the
  `nightly-YYYYMMDD` prerelease.
- **Stable**: push a `vX.Y.Z` tag. The notes come from the matching
  `## [X.Y.Z]` section of `CHANGELOG.md` (or Unreleased if it isn't cut yet).
- **Manual**: run the workflow; `dry_run` builds everything without
  publishing.

Every release carries `checksums.txt`, which both updaters verify.
`rust-integration.yml` runs the live NWS, Open-Meteo and IEM tests
(`cargo test -p aw-providers --test live -- --ignored`) every morning.

## Parity with the Python edition

Every window, dialog, menu, shortcut, setting and notification of the Python
app is ported. Golden tests under `testdata/golden/` compare the Rust output
with the Python app's own output for the same inputs; their generators are in
`tools/golden/` and run against a checkout of the Python app
(`uv run python rust/tools/golden/<area>.py` from its root).

Both editions share the configuration, API keys, alert state, weather cache
and NOAA radio preferences, and the same single-instance lock: while one is
running, starting the other brings the running one to the front instead.

Deliberate differences (mostly fixes for Python bugs):

- Settings > Advanced "Reset settings to defaults" keeps saved locations, and
  importing settings keeps the active API keys (Python wipes both).
- NOAA Weather Radio keeps favorites and the playing station across failed
  stream attempts, so alert auto-tune always stops the stream it started.
- Clicking a toast in All Locations view opens the alert it named.
- Advanced Text Product Lookup's date presets fill in the dates, and closing
  it from the title bar doesn't run a lookup.
- Forecaster Notes loads the tab it lands on after removing an empty one, and
  reuses cached plain-language summaries (Regenerate asks again).
- The About box names wxWidgets.
