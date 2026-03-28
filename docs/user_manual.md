# AccessiWeather User Manual

## What AccessiWeather Is

AccessiWeather is an accessible desktop weather app built with wxPython. It is designed to work well with screen readers, keyboard navigation, and standard desktop notifications.

The main window keeps weather split into separate sections so you do not have to dig through one long block of text:

- `Current Conditions`
- `Daily Forecast`
- `Hourly Forecast`
- `Weather Alerts`

The app also includes forecast discussions, air quality, UV index, aviation weather, NOAA Weather Radio, AI weather explanations, Weather Assistant chat, and optional alert sounds.

## Install and Launch

### Prebuilt Downloads

Download builds from [orinks.net/accessiweather](https://orinks.net/accessiweather) or the [GitHub releases page](https://github.com/Orinks/AccessiWeather/releases).

- Windows: MSI installer or portable ZIP
- macOS: DMG
- Linux: run from source

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

### Portable Mode

Portable mode keeps the app's data next to the app instead of using your normal per-user config location.

```bash
accessiweather --portable
```

## First-Time Setup

On a fresh setup, AccessiWeather shows a short onboarding wizard.

What the onboarding wizard does:

1. Offers to add your first location right away.
2. Lets you enter an optional OpenRouter API key for AI features.
3. Lets you enter an optional Visual Crossing API key.
4. Lets you enter an optional Pirate Weather API key.
5. In portable mode, if you entered keys, offers to save them in an encrypted portable key bundle.
6. Ends with a readiness summary showing what was configured.

You can skip any optional key step and configure those features later in `Settings`.

After onboarding:

1. Leave `Nationwide` visible if you want access to national forecast discussions; hide it later if you do not use it.
2. If you skipped adding a location during onboarding, add one with `Location > Add Location` or `Ctrl+L`.
3. Leave `Settings > Data Sources > Weather Data Source` on `Automatic` unless you have a specific reason to force one provider.
4. Refresh weather if the app has not already done it for you.

If you want to force the onboarding wizard to appear again later, start AccessiWeather with:

```bash
accessiweather --wizard
```

## Adding and Managing Locations

Use `Location > Add Location` to add places to your saved list.

The add-location dialog works like this:

1. Type a friendly name in `Location Name`.
2. Search by city name or ZIP/postal code.
3. Select one of the search results.
4. Save the location.

Important details:

- The location name must be unique in your saved list.
- You cannot save a location until you search and select a result.
- Double-clicking a search result also saves it.
- `Nationwide` is a built-in pseudo-location, not a normal city.

Use `Location > Remove Location` or `Ctrl+D` to remove the currently selected saved location. The app will not let you remove your last remaining location.

## Main Window

The main window is not just a read-only weather display. It also includes a row of quick-action buttons so you do not have to open the menu bar for common tasks.

### Quick-Action Buttons

The main window includes these buttons:

- `Add`: open the add-location dialog
- `Remove`: remove the currently selected saved location
- `Refresh`: refresh the selected location now
- `Explain`: open a one-shot AI explanation of the current weather
- `Discussion`: open the forecast discussion for the current location
- `Settings`: open the Settings dialog
- `View Alert Details`: open the full text of the selected alert when alerts are present

### Location Selector

The location drop-down at the top picks which saved location the app should show. When you switch locations, AccessiWeather may show cached data first and then refresh in the background.

### Current Conditions

This section shows the latest current weather. Depending on source availability and your display settings, it can include:

- Temperature
- Feels-like temperature
- Wind
- Humidity
- Dew point
- Visibility
- UV index
- Pressure trend
- Air quality
- Pollen

If Pirate Weather minutely data is available, current conditions can also include a short precipitation outlook such as rain starting or stopping soon.

### Daily Forecast

This section shows the multi-day forecast. The number of days depends on your `Forecast duration` setting and the source data available.

### Hourly Forecast

This section shows the short-range hourly forecast. You choose how many hours it includes in `Settings > Display > Hourly forecast hours`.

### Weather Alerts

This section shows active alerts for the selected location. Select an alert and choose `View Alert Details`, or press Enter or Space on the selected alert, to open the full text.

Between refreshes, alerts may be tagged with lifecycle labels such as:

- `New`
- `Updated`
- `Escalated`
- `Extended`

Cancelled alerts can still generate notifications even after they are no longer in the active list.

## Weather Sources

AccessiWeather does not treat all weather sources the same. Choosing the right source matters.

### Automatic

`Automatic` is the default. It fetches from all available sources it can use and merges the results.

What `Automatic` does:

- Always fetches Open-Meteo because it works globally and does not need a key.
- Fetches NWS for US locations.
- Fetches Visual Crossing only if you have a Visual Crossing key.
- Fetches Pirate Weather only if you have a Pirate Weather key.
- Merges current conditions, daily forecast, and hourly forecast using your source-priority choices.

What `Automatic` does not do:

- It does not merge alerts from every source equally.
- For US locations, it intentionally uses NWS alerts only.
- For non-US locations, it prefers Pirate Weather alerts and falls back to Visual Crossing alerts if Pirate Weather is not available.

Why most users should keep it on:

- It fills gaps better than any one provider alone.
- It keeps US alerts on the most detailed source.
- It can add Pirate Weather minutely precipitation when you have a Pirate Weather key.

### National Weather Service (NWS)

Best for:

- US forecasts
- US alerts
- Forecast discussions
- NOAA Weather Radio use with US locations

Important limitations:

- US only
- Outside the US, NWS-specific features such as area forecast discussions do not apply

### Open-Meteo

Best for:

- Global coverage
- No-key use
- Fast baseline forecast data
- Open-Meteo model selection

Important limitations:

- No weather alerts in AccessiWeather
- No NWS forecast discussions

### Visual Crossing

Best for:

- Weather history enrichment
- Extra global forecast coverage
- Some alert coverage outside the US

Important limitations:

- Requires an API key
- For US alerts, AccessiWeather still treats NWS as the authoritative source
- Visual Crossing alerts are less detailed than NWS in the current app

### Pirate Weather

Best for:

- Worldwide alerts
- Minutely precipitation guidance
- Dark Sky-style daily summaries
- Non-US alert coverage

Important limitations:

- Requires an API key
- Alerts can be broader regional alerts rather than highly specific local targeting
- Minutely precipitation depends on Pirate Weather data being available for that location and time

## How Alerts Behave

Alert behavior depends on both source and location.

### US Locations

- In `Automatic`, AccessiWeather uses NWS alerts only.
- Visual Crossing and Pirate Weather alerts are ignored there to avoid duplicates and weaker metadata.
- `Alert Area` applies to NWS alert targeting only.

### Non-US Locations

- NWS alerts do not apply.
- If Pirate Weather is configured and returns alerts, AccessiWeather prefers those.
- If Pirate Weather is not available, AccessiWeather can use Visual Crossing alerts where supported.

### Why Alerts Can Feel Different Between Sources

NWS alerts usually include stronger metadata such as severity, urgency, certainty, and more precise targeting. Pirate Weather alerts are useful for worldwide coverage, but they can be broader. Visual Crossing can help in some regions, but it is not the strongest alert source in the app.

## Forecast Discussions

You can open forecast discussions either from the main window `Discussion` button or from `View > Forecast Discussion...`.

`View > Forecast Discussion...` behaves differently depending on the selected location:

- For a normal US location, it opens the local NWS Area Forecast Discussion.
- For `Nationwide`, it opens national discussion products instead of a local office discussion.
- Outside NWS coverage, forecast discussion may simply not be available.

The discussion window also has an `Explain with AI` button when you have an OpenRouter key configured.

## Weather History

`View > Weather History` shows comparison text built from the current weather payload, including:

- Recent daily history when available
- Trend insights when available
- A simple today-versus-yesterday comparison when the data supports it

Important caveat:

- The app has a `Enable weather history comparisons` setting, but the menu item is still present either way. Turning the setting off stops the deferred weather-history service from being initialized, so history features may be more limited or unavailable.

## Air Quality and UV Index

Use the `View` menu to open dedicated dialogs for air quality and UV details.

Air quality can show:

- Current AQI
- AQI category
- Dominant pollutant
- Hourly air-quality forecast
- Pollutant detail values

UV can show:

- Current UV index
- UV category
- Hourly UV forecast
- Sun-safety guidance

These dialogs depend on environmental data being available for the selected location. If the source data is missing, the dialog will say so directly.

## Aviation Weather

Use `View > Aviation Weather...` to fetch decoded TAF information by four-letter ICAO airport code such as `KJFK`.

How it works:

- Enter a four-letter ICAO code.
- Press Enter or choose `Get Aviation Data`.
- The dialog shows both the raw TAF and a decoded version.
- It can also show aviation advisories.

About the optional AVWX key:

- You enter it in the aviation dialog itself, not in the main Settings dialog.
- It is mainly for better international airport support.
- US airports use the NWS/AWC path by default.
- The AVWX hint in the app explicitly calls out enhanced translations, flight rules, and screen-reader-friendly speech for international airports.

## NOAA Weather Radio

Use `View > NOAA Weather Radio...` to open the radio player for the current location.

What the dialog does:

- Finds nearby stations based on the current location
- Lists up to 10 nearby stations that have known online streams
- Lets you play, stop, try the next stream, change volume, and mark a stream as preferred

Important caveats:

- Not every NOAA Weather Radio station has an online stream.
- The dialog is non-modal, so you can leave it open while using the main window.
- This feature is oriented around NOAA Weather Radio stations, so it is most useful in NOAA coverage areas.

## AI Features

AccessiWeather has two separate AI features. Both require an OpenRouter API key.

### Explain Weather

You can open this from the main window `Explain` button or from `View > Explain Weather`.

`View > Explain Weather` generates a one-shot explanation of the currently loaded weather.

The explanation dialog shows:

- The generated explanation text
- The model used
- Token count
- Estimated cost
- Whether the result came from cache

You can regenerate the explanation from inside the dialog.

### Weather Assistant

`View > Weather Assistant...` opens a chat window. It is a multi-turn tool, not just a one-shot summary.

The assistant can use the app's live weather tools, including:

- Current weather
- Forecasts
- Alerts
- Location search
- Saved locations
- Open-Meteo variable queries
- Forecast discussions and national outlook products

Use it when you want follow-up questions, not just a quick summary.

## Optional API Keys

AccessiWeather works without paid services, but some features require optional keys.

### Pirate Weather

Needed for:

- Pirate Weather as a direct source
- Worldwide non-NWS alerts in many regions
- Minutely precipitation guidance
- Dark Sky-style summary text

Where to enter it:

- `Settings > Data Sources`

### Visual Crossing

Needed for:

- Visual Crossing as a direct source
- Weather history enrichment
- Some forecast and alert fallback coverage

Where to enter it:

- `Settings > Data Sources`

### OpenRouter

Needed for:

- `Explain Weather`
- `Weather Assistant`
- `Explain with AI` in the discussion dialog

Where to enter it:

- `Settings > AI`

### AVWX

Needed for:

- Better international aviation weather handling

Where to enter it:

- `View > Aviation Weather...`

## Settings Guide

This section explains every tab and control in the current settings dialog.

### General

#### Update Interval (minutes)

How often the app refreshes weather automatically in the background.

Change it when:

- You want fresher data more often
- You want fewer background refreshes

Tradeoff:

- Shorter intervals can mean more network activity and more opportunities for alerts and status changes to be detected quickly.

#### Show Nationwide location (requires Auto or NWS data source)

Shows or hides the built-in `Nationwide` location.

Turn it on when:

- You want quick access to national forecast discussion products

Turn it off when:

- You never use nationwide products and want a shorter location list

Important caveat:

- The checkbox is disabled unless your source is `Automatic` or `National Weather Service`.

#### Show weather text on tray icon

Lets AccessiWeather replace the plain tray tooltip with live weather text.

Turn it on when:

- You want the notification area tooltip to say more than just `AccessiWeather`

Turn it off when:

- You prefer a simpler tray icon with no changing weather text

#### Update tray text dynamically

Lets the tray text formatter adapt to live weather data and formatting rules.

Turn it on when:

- You want the tray text to update as weather changes

Turn it off when:

- You want a fixed custom format without dynamic behavior changing the result

#### Current tray text format / Edit Format...

Shows the current format string and opens the tray-format editor.

Use it when:

- You want to control exactly which values appear in tray text

The editor includes:

- A live preview
- A list of supported placeholders such as `{temp}`, `{condition}`, `{feels_like}`, `{humidity}`, `{wind}`, `{high}`, and `{low}`

Important caveat:

- Invalid format strings with unbalanced braces fall back to the default tray text.

### Display

#### Temperature Display

Choices:

- `Auto (based on location)`
- `Imperial (°F)`
- `Metric (°C)`
- `Both (°F and °C)`

Change it when:

- You want one unit system everywhere
- You want the app to follow location defaults automatically
- You want both systems spoken or shown together

#### Show dewpoint

Adds dew point to current conditions when available.

Turn it on when:

- You want a better sense of muggy or dry air

#### Show visibility

Adds visibility to current conditions when available.

Useful for:

- Fog
- Smoke
- Driving conditions
- Aviation awareness

#### Show UV index

Adds UV index to current conditions when available.

Useful for:

- Outdoor planning
- Sun-safety awareness

#### Show pressure trend

Adds pressure-trend information when available.

Useful for:

- Users who track changing weather systems closely

#### Show values as whole numbers (no decimals)

Rounds many displayed values.

Turn it on when:

- You want cleaner, faster-to-hear speech output

Turn it off when:

- You want more precise values

#### Show detailed forecast information

Controls how much detail the forecast text includes.

Turn it on when:

- You want fuller forecast text

Turn it off when:

- You want quicker summaries

#### Forecast duration

Choices in the current UI:

- 3 days
- 5 days
- 7 days
- 10 days
- 14 days
- 15 days

Change it when:

- You want a shorter or longer daily forecast

Important caveat:

- The app can request up to 15 days in the UI, but what you actually get still depends on source support.

#### Hourly forecast hours

How many hours the hourly section should show.

Change it when:

- You want a quick near-term look
- You want a longer hour-by-hour view

#### Forecast time display

Choices:

- `Location's timezone`
- `My local timezone`

Use location time when:

- You want the forecast as locals would read it

Use your local time when:

- You are monitoring weather somewhere else from home

#### Time zone display

Choices:

- `Local time only`
- `UTC time only`
- `Both (Local and UTC)`

Useful when:

- You work with UTC regularly
- You want both local and UTC for clarity

#### Use 12-hour time format

Switches between 12-hour and 24-hour style for displayed times.

#### Show timezone abbreviations

Adds suffixes such as `EST` or `UTC` where the display supports them.

Turn it on when:

- You want less ambiguity in spoken or read times

#### Verbosity level

Choices:

- `Minimal`
- `Standard`
- `Detailed`

This controls how much information AccessiWeather prioritizes in presentation.

Use:

- `Minimal` for shorter output
- `Standard` for most users
- `Detailed` for maximum available detail

#### Automatically prioritize severe weather info

Moves severe weather information higher in importance when conditions warrant it.

Turn it on when:

- You want dangerous weather surfaced more aggressively

### Data Sources

#### Weather Data Source

Choices:

- `Automatic`
- `National Weather Service`
- `Open-Meteo`
- `Visual Crossing`
- `Pirate Weather`

Use:

- `Automatic` for most users
- `NWS` if you only care about US weather and alerts
- `Open-Meteo` if you want a no-key global source
- `Visual Crossing` if you want to force that source and already have a key
- `Pirate Weather` if you want to force worldwide alerts/minutely support and already have a key

Important caveats:

- `Visual Crossing` and `Pirate Weather` require keys when chosen directly.
- `Open-Meteo` has no alerts.
- `NWS` is US-only.

#### Visual Crossing API Key / Get Free API Key / Validate API Key

Use these controls to add and test your Visual Crossing key.

Use Visual Crossing when:

- You want history enrichment
- You want another fallback source in Automatic mode
- You want to force Visual Crossing directly

#### Pirate Weather API Key / Get Free API Key / Validate API Key

Use these controls to add and test your Pirate Weather key.

Use Pirate Weather when:

- You want worldwide alert support
- You want minutely precipitation start/stop guidance
- You want Pirate Weather as a direct source

#### US Locations Priority

Controls the merge order used by `Automatic` for US locations.

Current choices:

- `NWS → Open-Meteo → Visual Crossing`
- `NWS → Visual Crossing → Open-Meteo`
- `Open-Meteo → NWS → Visual Crossing`

Change it when:

- You want Open-Meteo or Visual Crossing to win more often for current/forecast values

Important caveat:

- This affects data merging, not US alert authority. US alerts still come from NWS only.

#### International Locations Priority

Controls the merge order used by `Automatic` for non-US locations.

Current choices:

- `Open-Meteo → Visual Crossing`
- `Visual Crossing → Open-Meteo`

Important caveat:

- Internally, Pirate Weather can still participate in Automatic mode when you have a Pirate Weather key. The UI only exposes two priority presets here, so this setting is simpler than the actual full internal source list.

#### Open-Meteo Weather Model

Choices in the current UI:

- `Best Match`
- `ICON Seamless`
- `ICON Global`
- `ICON EU`
- `ICON D2`
- `GFS Seamless`
- `GFS Global`
- `ECMWF IFS`
- `Météo-France`
- `GEM`
- `JMA`

What it does:

- Chooses which Open-Meteo model AccessiWeather asks for

When to leave it on `Best Match`:

- Almost always, unless you have a reason to prefer a specific regional model

When to change it:

- You know a specific regional model usually performs better for your area
- You want to compare how Open-Meteo-based output changes

Practical guidance:

- `ICON` variants are most relevant for Europe and Germany
- `GFS` is NOAA-based and broadly useful for the Americas and global coverage
- `ECMWF IFS` is a global model many users prefer for general forecasting
- `GEM` is Canada/North America oriented
- `JMA` is Japan/Asia oriented

Important caveat:

- This only affects Open-Meteo requests. It matters most when Open-Meteo is your direct source or when Automatic mode is using Open-Meteo data to fill gaps or win a merge.

#### NWS Station Selection (Current Conditions)

Controls how AccessiWeather chooses an NWS observation station for current conditions.

Choices:

- `Hybrid default`
- `Nearest station`
- `Major airport preferred`
- `Freshest observation`

Use:

- `Hybrid default` if you want the safest general choice
- `Nearest station` if local distance matters most to you
- `Major airport preferred` if you trust staffed airport observations more
- `Freshest observation` if recency matters more than distance

Important caveat:

- This applies to NWS current conditions only.
- In `Automatic`, it matters when NWS is selected for current conditions or used as fallback.

### Notifications

#### Enable weather alerts

Turns weather-alert handling on or off in the app.

Turn it off when:

- You do not want alerts at all

#### Enable alert notifications

Controls desktop alert pop-ups separately from alert handling itself.

Turn it off when:

- You still want to read alerts in the app, but do not want pop-up notifications

#### Alert Area

Choices:

- `County`
- `Point`
- `Zone`
- `State`

What it does:

- Chooses how NWS alert matching should work

Use:

- `County` for the least noisy local NWS targeting
- `Point` for the narrowest location match, with the risk of missing some alerts
- `Zone` for a somewhat broader NWS area
- `State` only if you want very broad alert coverage

Important caveat:

- This is an NWS setting. It does not make Pirate Weather or Visual Crossing alerts more precise.

#### Severity checkboxes

Choices:

- `Extreme`
- `Severe`
- `Moderate`
- `Minor`
- `Unknown`

What they do:

- Decide which severities can notify you

Typical use:

- Leave `Extreme`, `Severe`, and `Moderate` on for important alerts
- Turn on `Minor` only if you want more low-impact notifications
- Turn on `Unknown` only if you would rather risk extra noise than miss poorly categorized alerts

#### Notify when Area Forecast Discussion is updated

Alerts you when the NWS Area Forecast Discussion issuance time changes.

Useful when:

- You follow forecaster reasoning closely

Important caveat:

- NWS US only

#### Notify when severe weather risk level changes

Alerts you when the severe-weather risk category changes.

Important caveat:

- Visual Crossing only

#### Notify when precipitation is expected to start soon

Uses Pirate Weather minutely data to notify you when the app detects a dry-to-wet transition.

Useful when:

- You want a heads-up before rain, snow, sleet, or other precipitation starts

Important caveat:

- Requires Pirate Weather and available minutely data

#### Notify when precipitation is expected to stop soon

Uses Pirate Weather minutely data to notify you when the app detects a wet-to-dry transition.

Useful when:

- You want to know when precipitation is about to end

#### Global cooldown (minutes)

Sets a broad cooldown between notifications.

Raise it when:

- You want fewer notifications overall

#### Per-alert cooldown (minutes)

Limits how often the same alert can notify you again.

Raise it when:

- Repeated updates for the same alert feel too noisy

#### Alert freshness window (minutes)

Controls how new an alert must be to count as fresh for notification purposes.

Lower it when:

- You only want very recent alerts

Raise it when:

- You would rather hear about slightly older alerts than miss them

#### Maximum notifications per hour

Caps the total number of notifications the app can send in one hour.

Lower it when:

- You want a hard limit during active weather

### Audio

#### Play notification sounds

Master switch for app sounds.

Turn it off when:

- You want visual notifications only

#### Sound pack

Chooses which installed sound pack is active.

Change it when:

- You prefer a different alert style
- You have installed community or custom packs

#### Test Sound

Plays a quick sample using the active sound setup.

Use it when:

- You want to confirm your current sound pack works

#### Manage Sound Packs...

Opens the sound pack manager.

Use it when:

- You want to install, remove, preview, or manage packs

#### Event sound summary

Shows how many sound-capable events are currently enabled.

#### Configure Event Sounds...

Opens a detailed sound-event chooser.

What you can control there:

- Core app sounds such as refresh complete or refresh failed
- Discussion-update and severe-risk-change sounds
- Startup and exit sounds
- Severity fallback sounds
- Generic warning/watch/advisory/statement sounds
- Many specific alert-event sounds such as tornado, flood, winter, wind, tropical, marine, fog, fire, and air-quality events

Use it when:

- You want sounds for only a few events
- You want to mute less important events without muting everything

### Updates

#### Check for updates automatically

Turns scheduled update checks on or off.

Turn it off when:

- You prefer to check manually

Important caveat:

- Update checking is only available in installed builds. If you run from source, manual update checking tells you to update with `git pull` instead.

#### Update Channel

Current choices:

- `Stable`
- `Development`

Use `Stable` when:

- You want production releases only

Use `Development` when:

- You want newer features sooner and accept more instability

#### Check Interval (hours)

How often automatic update checks run.

#### Check for Updates Now

Runs a manual update check immediately.

#### Update status

Shows the current update-check state inside the settings window.

### AI

#### OpenRouter API Key / Validate API Key

Required for all AI features in the current app, including free models.

Use `Validate API Key` when:

- You want to confirm the key works before closing settings

#### Model Preference

Current built-in choices:

- `Free Router (Auto, Free)`
- `Llama 3.3 70B (Free)`
- `Auto Router (Paid)`

What they mean:

- `Free Router` uses OpenRouter's free routing path
- `Llama 3.3 70B (Free)` forces that specific free model
- `Auto Router (Paid)` lets OpenRouter choose among paid options

Use:

- A free option if you want zero-cost explanations and can accept free-tier limits
- `Auto Router (Paid)` if you want broader model routing and are comfortable with usage costs

#### Browse Models...

Lets you choose a specific OpenRouter model beyond the built-in presets.

Use it when:

- You want to lock the app to a particular model

#### Explanation Style

Choices:

- `Brief`
- `Standard`
- `Detailed`

Applies to AI-generated explanations.

Use:

- `Brief` for fast summaries
- `Standard` for general use
- `Detailed` for fuller explanations

#### Custom System Prompt

Overrides the default system prompt used for AI explanations.

Use it only when:

- You know exactly how you want the explanation behavior changed

Important caveat:

- This is powerful, but it can make AI output worse or less predictable if overused.

#### Reset to Default

Clears your custom system prompt back to the app default.

#### Custom Instructions

Adds extra instructions on top of the normal AI prompt.

Good use cases:

- Keep responses short
- Focus on outdoor activity impact
- Prefer plainer language

#### Cost Information

The AI tab also shows a simple reminder that free models have no direct cost and paid models vary by model.

### Advanced

#### Minimize to notification area when closing

Changes the close behavior so closing the main window hides it to the tray instead of exiting.

Turn it on when:

- You want AccessiWeather running in the background

#### Start minimized to notification area

Starts the app hidden in the tray.

Turn it on when:

- You want AccessiWeather available at startup without opening a window

Important caveat:

- This control is only enabled when `Minimize to notification area when closing` is on.
- It also depends on a working tray icon on your platform.

#### Launch automatically at startup

Tries to launch AccessiWeather when you sign in.

Turn it on when:

- You want background weather updates and alerts without manually opening the app every time

#### Enable weather history comparisons

Allows the app to initialize its deferred weather-history service.

Turn it off when:

- You do not care about history/trend comparisons and want a slightly simpler startup path

Important caveat:

- The `Weather History` menu item still exists even when this is off.

#### Reset all settings to defaults

Resets settings back to default values.

Use it when:

- You want to undo many setting changes quickly

#### Reset all app data (settings, locations, caches)

Wipes settings, locations, cache files, and alert state.

Use it when:

- You want a true clean start

Important caveat:

- This is much broader than resetting settings alone.

#### Open current config directory

Opens the config directory the running app is currently using.

Useful for:

- Backups
- Troubleshooting
- Portable-mode inspection

#### Open installed config directory (source)

Opens the standard installed config directory.

Most useful when:

- You are in portable mode and need to compare or copy data

#### Copy installed config to portable

Only shown in portable mode.

Use it when:

- You want to migrate an existing installed config into your portable setup

#### Export Settings...

Exports app settings and saved locations.

Important caveat:

- API keys are not included in normal settings export.

#### Import Settings...

Imports a previously exported settings file.

#### Export API keys (encrypted)

Creates an encrypted bundle of saved API keys for transfer to another machine.

Use it when:

- You are moving to another computer
- You want a safer backup than plain text

#### Import API keys (encrypted)

Imports an encrypted API-key bundle and stores the keys in this machine's secure storage.

#### Open sound packs folder

Opens the folder where sound packs live.

Use it when:

- You want to manually add, inspect, or remove pack files

## Menus and Workflows

### File

- `Settings`: opens the settings dialog
- `Exit`: quits the app

### Location

- `Add Location`: search and save a new location
- `Remove Location`: removes the selected saved location

### View

- `Refresh`
- `Explain Weather`
- `Weather History`
- `Forecast Discussion`
- `Aviation Weather`
- `Air Quality`
- `UV Index`
- `NOAA Weather Radio`
- `Weather Assistant`

### Tools

- `Soundpack Manager`

### Help

- `Check for Updates`
- `Report Issue`
- `About`

## Keyboard Shortcuts

The current code binds these global shortcuts:

- `Ctrl+R` or `F5`: Refresh weather
- `Ctrl+L`: Add location
- `Ctrl+D`: Remove selected location
- `Ctrl+H`: Open Weather History
- `Ctrl+S`: Open Settings
- `Ctrl+Q`: Quit
- `Ctrl+E`: Explain Weather
- `Ctrl+T`: Open Weather Assistant
- `Ctrl+Shift+R`: Open NOAA Weather Radio

## Config and Portability

AccessiWeather stores normal settings in the standard per-user config area unless you run in portable mode.

Regular settings export/import:

- Includes settings and saved locations
- Does not include API keys

Encrypted API-key transfer:

1. Open `Settings > Advanced`.
2. Choose `Export API keys (encrypted)`.
3. Save the bundle and remember the passphrase.
4. On the other machine, choose `Import API keys (encrypted)`.
5. Enter the same passphrase.

## Troubleshooting

### I am not seeing alerts

Check these first:

- `Open-Meteo` does not provide alerts in AccessiWeather.
- For US locations, use `Automatic` or `National Weather Service`.
- For non-US locations, add a Pirate Weather key if you want the best alert coverage the app currently supports.
- In `Settings > Notifications`, make sure `Enable weather alerts` and `Enable alert notifications` are set the way you expect.

### Alerts feel too broad outside the US

That can be normal. Pirate Weather alerts can be regional WMO-style alerts rather than tightly targeted county-style alerts.

### I want rain-start or rain-stop notifications

You need:

- A Pirate Weather API key
- Pirate Weather minutely data to be available for the location
- The matching notification setting turned on in `Settings > Notifications`

### Forecast times look wrong for a remote city

Check:

- `Forecast time display`
- `Time zone display`
- `Use 12-hour time format`
- `Show timezone abbreviations`

### Explain Weather or Weather Assistant does not work

Check:

- A valid OpenRouter key is saved in `Settings > AI`
- The selected model still exists on OpenRouter
- You have weather data loaded for the current location

### Forecast Discussion says it is unavailable

That can happen when:

- The selected location is outside NWS coverage
- No recent NWS discussion was issued
- NWS is temporarily unavailable

### NOAA Weather Radio says no stream is available

That can be normal. The app only lists stations with known online streams, and not every NOAA Weather Radio station has one.
