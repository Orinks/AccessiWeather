# AccessiWeather User Manual

## Overview

AccessiWeather is an accessible desktop weather app built with wxPython. It is designed for screen reader users first, but it is equally usable with keyboard or mouse. The main window separates weather into four core sections:

- `Current Conditions`
- `Daily Forecast`
- `Hourly Forecast`
- `Weather Alerts`

You can also open forecast discussions, weather history, air quality, UV index, aviation weather, NOAA Weather Radio, AI explanations, and the Weather Assistant from the menu.

## Install and Launch

### Prebuilt Downloads

Download the latest build from [accessiweather.orinks.net](https://accessiweather.orinks.net) or the [GitHub releases page](https://github.com/Orinks/AccessiWeather/releases).

- **Windows**: MSI installer or portable ZIP
- **macOS**: DMG
- **Linux**: Build from source for now

### Portable Mode

The Windows portable ZIP stores app data next to the app. If you install from source or want to force portable mode manually, run:

```bash
accessiweather --portable
```

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

## First-Time Setup

When you start AccessiWeather for the first time:

1. The app creates its config folder.
2. The `Nationwide` location is available by default.
3. Add your own location with `Location > Add Location` or `Ctrl+L`.
4. Leave `Settings > Data Sources > Weather Data Source` on `Automatic` unless you want to force a provider.
5. Add optional API keys only for the features you want.

## Main Window

### Current Conditions

This section shows the latest observed or merged current weather. Depending on your settings and source, it can include:

- Temperature
- Feels like temperature
- Wind
- Humidity
- Dewpoint
- Visibility
- UV index
- Pressure trend
- Environmental data such as air quality or pollen when available

If Pirate Weather minutely data is available, you will also see a short `Precipitation outlook` line in current conditions.

### Daily Forecast

The daily forecast is shown in its own section. It is separate from the hourly forecast and uses your configured forecast duration. Current options are 3, 5, 7, 10, 14, or 15 days depending on the source data available.

### Hourly Forecast

The hourly forecast has its own section and is no longer mixed into the daily forecast text. You can choose how many hours to show in `Settings > Display > Hourly forecast hours`.

### Weather Alerts

The alerts list shows active alerts for the selected location. When AccessiWeather detects changes between refreshes, alerts can be labeled with lifecycle states such as:

- `New`
- `Updated`
- `Escalated`
- `Extended`

Cancelled alerts can also trigger notifications even after they disappear from the active list.

Use `View Alert Details` or press Enter/Space on a selected alert to open the full alert text.

## Weather Sources

AccessiWeather supports four weather providers. They do not all behave the same, so it helps to know what each one is best at.

### National Weather Service (NWS)

Best for:

- US forecasts
- US alerts
- Area Forecast Discussions
- NOAA Weather Radio integration

User-facing behavior:

- NWS is the authoritative alert source for US locations.
- It supports county, point, zone, and state alert targeting.
- It provides the forecast discussion used by `View > Forecast Discussion...`.

### Open-Meteo

Best for:

- No-key global forecasts
- International coverage
- Open-Meteo model selection
- UV and environmental support

User-facing behavior:

- No API key is required.
- It does not provide weather alerts in AccessiWeather.
- You can choose the Open-Meteo model in `Settings > Data Sources`.

### Pirate Weather

Best for:

- Worldwide WMO alerts
- Minutely precipitation guidance
- Dark Sky-style summaries
- International use when you want alert coverage outside the US

User-facing behavior:

- Requires an API key.
- Adds minutely precipitation guidance when available.
- Can trigger start/stop precipitation notifications.
- Pirate Weather alerts are often regional WMO alerts, so the listed areas may be broader than an exact county or zone.

### Visual Crossing

Best for:

- Weather history
- Global forecast enrichment
- Some alert coverage where available

User-facing behavior:

- Requires an API key.
- It is useful when you want weather history and broader source coverage.
- For US alerts, AccessiWeather still prefers NWS because NWS metadata is stronger.

### Automatic Mode

`Automatic` is the default and usually the best choice.

What it does:

- Merges available sources instead of blindly picking only one
- Uses NWS, Open-Meteo, and any configured optional sources to fill gaps
- Keeps US alerts on NWS only
- Uses Pirate Weather alerts outside the US when available
- Falls back to Visual Crossing alerts outside the US if Pirate Weather is not configured

## Alerts and Notifications

### Alert Sources

Alerts are source-dependent:

- **US locations**: NWS alerts are used as the active alert source in Automatic mode
- **International locations**: Pirate Weather alerts are preferred when configured; otherwise Visual Crossing may provide alert coverage
- **Open-Meteo**: No alerts

### Why NWS and Pirate Weather Alerts Feel Different

Users should expect real differences:

- **NWS alerts** are usually more precise for US users and include stronger metadata such as severity, urgency, and certainty.
- **Pirate Weather/WMO alerts** are better for worldwide coverage, but they may be broader regional alerts and may not align with county-based US alert targeting.
- **Visual Crossing alerts** can be useful, but for US locations they are not treated as the authoritative alert source.

### Notification Settings

Open `Settings > Notifications` to control:

- Whether weather alerts are enabled at all
- Whether desktop alert notifications are enabled
- Which severities can notify you
- Alert area behavior for NWS alerts
- Cooldowns and rate limits
- Event-based notifications

Current event-based notification options include:

- `Notify when Area Forecast Discussion is updated (NWS US only)`
- `Notify when severe weather risk level changes (Visual Crossing only)`
- `Notify when precipitation is expected to start soon (Pirate Weather)`
- `Notify when precipitation is expected to stop soon (Pirate Weather)`

## Settings Guide

The Settings dialog currently has these tabs.

### General

Use this tab for:

- Update interval
- Showing or hiding the `Nationwide` location
- Tray icon weather text

### Display

Use this tab for:

- Temperature display
- Turning metrics on or off
- Rounding values
- Forecast duration
- Hourly forecast hours
- Time display and timezone display
- Verbosity level
- Severe weather prioritization

### Data Sources

Use this tab for:

- Choosing `Automatic`, `NWS`, `Open-Meteo`, `Visual Crossing`, or `Pirate Weather`
- Entering `Visual Crossing` and `Pirate Weather` API keys
- Choosing Open-Meteo weather models
- Choosing the NWS station selection strategy for current conditions

Available Open-Meteo model choices currently include:

- Best Match
- ICON Seamless
- ICON Global
- ICON EU
- ICON D2
- GFS Seamless
- GFS Global
- ECMWF IFS
- Météo-France
- GEM
- JMA

### Notifications

Use this tab for:

- Alert on/off controls
- Severity filters
- NWS alert area behavior
- Event notifications
- Notification cooldowns and hourly caps

### Audio

Use this tab for:

- Enabling or disabling notification sounds
- Choosing the active sound pack
- Enabling or disabling sounds for individual event types

### Updates

Use this tab for:

- Automatic update checks
- Update channel
- Update check interval
- Manual update checks

### AI

Use this tab for:

- Entering your OpenRouter API key
- Choosing the AI model
- Picking brief, standard, or detailed explanations
- Adding optional custom system prompts or custom instructions

AccessiWeather currently requires an OpenRouter API key for AI features, including free models.

### Advanced

Use this tab for:

- Minimize to tray behavior
- Start minimized
- Launch at startup
- Weather history toggle
- Resetting settings
- Resetting all app data
- Opening config folders
- Exporting or importing settings
- Exporting or importing API keys with encryption
- Opening the sound packs folder

## Optional API Keys

### Pirate Weather

Needed for:

- Worldwide WMO alerts
- Minutely precipitation guidance
- Dark Sky-style daily summaries

Where to add it:

- `Settings > Data Sources`

### Visual Crossing

Needed for:

- Weather history
- Extra global forecast coverage
- Some regional alert coverage

Where to add it:

- `Settings > Data Sources`

### OpenRouter

Needed for:

- `View > Explain Weather`
- `View > Weather Assistant`

Where to add it:

- `Settings > AI`

### AVWX

Needed for:

- Better international aviation weather translations and speech output

Where to add it:

- `View > Aviation Weather...`

US airport aviation weather uses the NWS/AWC path by default. AVWX is mainly for international airport coverage.

## AI Features

AccessiWeather has two separate AI features.

### Explain Weather

`View > Explain Weather` gives you a one-shot natural-language summary of the current weather. It is best when you want a quick explanation instead of a conversation.

You can control:

- Model preference
- Explanation style
- Optional custom prompt behavior

### Weather Assistant

`View > Weather Assistant...` opens a chat-style assistant that can help you understand weather conditions and forecasts in more detail.

Both AI features require an OpenRouter API key.

## Weather Discussions

`View > Forecast Discussion...` opens the NWS Area Forecast Discussion when it is available for the selected US location. This is a technical forecast product written by forecasters, and it is useful when you want reasoning behind the forecast.

`Nationwide` also gives access to national discussion products.

## Additional Tools

### Weather History

`View > Weather History` shows past weather comparisons. This feature depends on the app's weather history support and may rely on optional source data.

### Air Quality and UV Index

Use the `View` menu to open dedicated dialogs for air quality and UV index details, including hourly outlooks when available.

### Aviation Weather

Use `View > Aviation Weather...` to fetch TAF data by ICAO airport code. For international airports, adding an AVWX key improves translated and speech-friendly output.

### NOAA Weather Radio

Use `View > NOAA Weather Radio...` for NOAA Weather Radio access.

## Keyboard Shortcuts

Current shortcuts exposed by the app include:

- `Ctrl+L`: Add location
- `Ctrl+D`: Remove location
- `Ctrl+R` or `F5`: Refresh
- `Ctrl+S`: Settings
- `Ctrl+E`: Explain Weather
- `Ctrl+H`: Weather History
- `Ctrl+T`: Weather Assistant
- `Ctrl+Q`: Quit
- `Ctrl+Shift+R`: NOAA Weather Radio

## Configuration and Portability

AccessiWeather stores settings in the standard per-user config location unless you run in portable mode.

Settings export/import:

- Includes app settings and locations
- Does not include API keys

API key portability:

1. Open `Settings > Advanced`.
2. Choose `Export API keys (encrypted)`.
3. Save the encrypted bundle and keep the passphrase.
4. On the destination machine, use `Import API keys (encrypted)`.

This keeps plaintext keys out of regular config exports.

## Troubleshooting

### I am not seeing alerts

Check these points:

- Open-Meteo does not provide alerts.
- For US locations, use `Automatic` or `NWS`.
- For international locations, add a Pirate Weather key if you want better global alert coverage.
- In `Settings > Notifications`, make sure alerts and alert notifications are enabled.

### Alerts look too broad outside the US

That can be normal with Pirate Weather or other non-NWS alert feeds. Those alerts may be regional WMO alerts instead of exact county or zone alerts.

### I want rain start/stop notifications

You need:

- A Pirate Weather API key
- `Settings > Notifications > Notify when precipitation is expected to start soon`
  or
- `Settings > Notifications > Notify when precipitation is expected to stop soon`

### Forecast times look wrong

Check `Settings > Display`:

- `Forecast time display`
- `Time zone display`
- `Use 12-hour time format`
- `Show timezone abbreviations`

### AI features do not work

Check these points:

- Add a valid OpenRouter API key in `Settings > AI`
- Make sure the selected model is still available
- Try the free router first if a paid model fails

### Aviation weather is limited for non-US airports

Add an AVWX key in the `Aviation Weather` dialog for better international decoding and speech output.
