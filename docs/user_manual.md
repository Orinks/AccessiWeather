# AccessiWeather User Manual

## 1. Introduction

AccessiWeather is an accessible desktop weather application for Windows, macOS, and Linux. It is designed to work well with screen readers, keyboard navigation, desktop notifications, and clear text layouts.

Instead of mixing everything into one long report, AccessiWeather separates weather into practical sections:

- Current Conditions
- Daily Forecast
- Hourly Forecast
- Weather Alerts

The app can also provide forecast discussions, air quality details, UV details, aviation weather, NOAA Weather Radio access, AI weather explanations, Weather Assistant chat, and optional notification sounds.

This manual explains how to install the app, add locations, read the weather, choose weather sources, manage alerts and notifications, and adjust settings.

## 2. Installing and starting AccessiWeather

### Downloading a build

Prebuilt downloads are available from:

- https://orinks.net/accessiweather
- https://github.com/Orinks/AccessiWeather/releases

Typical download options are:

- Windows: MSI installer or portable ZIP
- macOS: DMG
- Linux: run from source

### Running from source

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

### Portable mode

Portable mode keeps AccessiWeather's configuration next to the app instead of storing it in your normal user profile.

Use portable mode when:

- you want to carry the app on removable storage
- you want the app and its settings to travel together
- you do not want this installation to use your usual per-user config location

Start portable mode with:

```bash
accessiweather --portable
```

In portable mode, encrypted API key bundles are used instead of normal keyring storage.

## 3. First-time setup

When you start AccessiWeather for the first time, it shows a short onboarding wizard.

The wizard walks you through these steps:

1. Add your first location, or skip it for now.
2. Enter an OpenRouter API key if you want AI features.
3. Enter a Visual Crossing API key if you want that provider.
4. Enter a Pirate Weather API key if you want that provider.
5. In portable mode, choose a passphrase to save entered keys into an encrypted portable bundle.

At the end, AccessiWeather shows a readiness summary.

You can safely skip any optional key step. The app works without paid services, and you can add keys later in Settings.

To run the onboarding wizard again manually, start the app with:

```bash
accessiweather --wizard
```

### Recommended first setup

For the smoothest first experience, do the following:

1. Add at least one location.
2. Leave the weather source set to Automatic unless you have a reason to force one provider.
3. Refresh weather if the app has not already done so.
4. Open Settings only after you have seen the basic forecast once.

## 4. Everyday tasks

### Add your first location

To add a location:

1. Open Location > Add Location, or press Ctrl+L.
2. Enter a friendly name in Location Name.
3. Search by city name or ZIP or postal code.
4. Select one result from the results list.
5. Save the location.

Important things to know:

- The name must be unique in your saved list.
- You cannot save the location until you choose a search result.
- Double-clicking a search result also saves it.

### Switch locations

Use the location selector near the top of the main window to switch between saved places.

When you switch locations, AccessiWeather may show cached weather first and then refresh in the background.

### Refresh weather now

To refresh the selected location immediately:

- press F5
- press Ctrl+R
- choose View > Refresh
- use the Refresh button in the main window

### Remove a location

To remove the current location:

- choose Location > Remove Location
- or press Ctrl+D
- or use the Remove button

AccessiWeather will not let you remove your last remaining location.

### Open the forecast discussion

To open a forecast discussion:

- use the Discussion button
- or choose View > Forecast Discussion

For normal US locations, this opens the local NWS Area Forecast Discussion.

If Nationwide is selected, AccessiWeather opens national discussion products instead.

If your current source or location does not support forecast discussions, the discussion may be unavailable.

### View alert details

To read the full text of an alert:

1. Move to the Weather Alerts section.
2. Select the alert you want.
3. Choose View Alert Details, or press Enter or Space on the selected alert.

### Open Settings

To open Settings:

- press Ctrl+S
- choose File > Settings
- use the Settings button

## 5. Understanding the main window

The main window is designed for quick keyboard and screen-reader use.

### Quick-action buttons

The button row provides common actions without requiring the menu bar:

- Add
- Remove
- Refresh
- Explain
- Discussion
- Settings
- View Alert Details

### Location selector

The location selector chooses which saved place is currently shown.

### Current Conditions

This section shows the latest current weather report. Depending on source availability and your display settings, it may include:

- temperature
- feels-like temperature
- wind
- humidity
- dew point
- visibility
- UV index
- pressure trend
- air quality
- pollen or impact summaries when available

If Pirate Weather minutely precipitation data is available, this section can also mention near-term precipitation start or stop timing.

### Daily Forecast

This section shows the multi-day forecast. The number of days depends on your Display settings and on what the source can provide.

### Hourly Forecast

This section shows the short-range hourly forecast. You can choose how many hours appear in Settings > Display.

### Weather Alerts

This section lists active alerts for the selected location.

When alerts change between refreshes, you may hear or read labels such as:

- New
- Updated
- Escalated
- Extended

Cancelled alerts may still trigger notifications even after they leave the active list.

## 6. Weather sources and Automatic mode

AccessiWeather can use multiple weather providers. You can force a single provider, but most users will get the best results from Automatic mode.

### Weather providers at a glance

#### National Weather Service (NWS)

Best for:

- US forecasts
- US alerts
- US forecast discussions
- NOAA Weather Radio features

Important limits:

- US only
- not available for international locations

#### Open-Meteo

Best for:

- global forecast coverage
- no-key setup
- strong baseline forecast coverage

Important limits:

- no weather alerts in AccessiWeather
- no forecast discussion support

#### Pirate Weather

Best for:

- global forecast coverage with an API key
- worldwide alert coverage in many regions
- minutely precipitation guidance
- Dark Sky-style summary text

Important limits:

- requires an API key
- alerts may be broader than local US NWS targeting
- minutely precipitation is only available where Pirate Weather provides it

#### Visual Crossing

Best for:

- global forecast enrichment with an API key
- weather history support
- some alert coverage outside the US

Important limits:

- requires an API key
- not the authoritative US alert source in AccessiWeather

### What Automatic mode means now

Automatic mode is the default weather-source choice.

Its default behavior is fusion-first using the Max coverage budget. In plain language, that means AccessiWeather tries every enabled source it can use for your region, then merges the results so one provider can fill gaps left by another.

Automatic mode is not limited to one built-in fetch order. It follows the source order you save in the Automatic mode configuration.

Automatic mode also keeps separate source lists for:

- US locations
- international locations

This lets you choose a different preferred order for domestic and international use.

### Automatic mode budgets

AccessiWeather provides three Automatic mode API budget choices.

#### Max coverage

This is the default.

Use this when:

- you want the richest merged result
- you want Automatic mode to behave in its full fusion-first form
- you want the best chance of filling forecast gaps from multiple sources

What it does:

- fans out to every enabled source that is available for the current location
- merges current conditions, daily forecast, and hourly forecast from those results
- uses your saved source order when deciding how to merge overlapping data

#### Economy

This is an opt-in reduced-call mode.

Use this when:

- you want to minimize API usage
- you are trying to stay within optional-provider quotas
- you prefer a simpler, lower-call Automatic mode

What it does:

- starts with your first enabled source for the region
- only adds limited fallback behavior when needed
- keeps call volume lower than Max coverage

#### Balanced

This is also an opt-in reduced-call mode.

Use this when:

- you want fewer API calls than Max coverage
- but you still want one useful fallback in more situations than Economy

What it does:

- starts with your first enabled source for the region
- allows one additional fallback source when Automatic mode needs it
- offers a middle ground between Economy and Max coverage

### Separate US and international source lists

Automatic mode uses separate saved source lists for US and international locations.

Default order:

- US: NWS, Open-Meteo, Visual Crossing, Pirate Weather
- International: Open-Meteo, Pirate Weather, Visual Crossing

You can change these lists in Settings > Data Sources > Configure automatic mode budget and sources.

The staged fetch order follows the source order you save.

### Alerts in Automatic mode

Automatic mode does not treat every alert source equally.

#### US locations

For US locations, NWS alerts are authoritative when NWS is available.

That means:

- AccessiWeather uses NWS alerts as the official alert feed in Automatic mode
- Pirate Weather and Visual Crossing alerts are not used as equal co-authorities for US alerts
- the Alert Area setting applies to NWS-style US alert targeting

#### International locations

For international locations:

- NWS alerts do not apply
- Pirate Weather alerts are preferred when available
- Visual Crossing is used as the fallback alert source when Pirate Weather is unavailable

### Forecast discussion behavior in Automatic mode

Forecast discussions come from NWS.

That means:

- US users can open discussions when NWS is part of the active path
- Nationwide can open national discussion products
- if Automatic mode does not use NWS for the current weather path, forecast discussion may be unavailable
- Open-Meteo, Pirate Weather, and Visual Crossing do not provide forecast discussions in AccessiWeather

### Minutely precipitation

Minutely precipitation guidance depends on Pirate Weather.

When Pirate Weather minutely data is available, AccessiWeather can:

- include near-term precipitation timing in current conditions
- notify you when precipitation is expected to start soon
- notify you when precipitation is expected to stop soon

If Pirate Weather is not configured, or if minutely data is unavailable for the location, those features will not appear.

## 7. Alerts and notifications

Alerts and notifications are related, but they are not the same thing.

- Alerts are the weather hazards AccessiWeather receives from a source.
- Notifications are the desktop popups and optional sounds AccessiWeather sends when something changes.

### Standard alert monitoring

You can choose whether AccessiWeather should:

- monitor alerts at all
- send alert notifications
- open alert details immediately while the app is running

### Alert area

For NWS-based US alerts, the Alert Area setting controls how broad the targeting should be.

Choices are:

- County: recommended for most users
- Point: exact coordinate, but may miss nearby alerts
- Zone: somewhat broader than county
- State: broadest and noisiest

Use smaller areas when you want fewer notifications. Use broader areas when you do not want to miss alerts that affect a wider region.

### Severity filters

You can choose which alert severities are allowed to notify you:

- Extreme
- Severe
- Moderate
- Minor
- Uncategorized

A severity being turned off means the alert can still exist in the weather data, but AccessiWeather will not notify you for that level.

### Extra weather event notifications

In addition to standard alerts, AccessiWeather can notify you about:

- Area Forecast Discussion updates for NWS US locations
- severe weather risk changes from Visual Crossing
- minutely precipitation start soon from Pirate Weather
- minutely precipitation stop soon from Pirate Weather

These are optional and should be turned on only if you want those extra updates.

### Cooldowns and notification limits

Cooldown settings help prevent repeated notifications from becoming overwhelming.

In user terms:

- global cooldown is the minimum time between any alert notifications
- per-alert cooldown is how long AccessiWeather waits before repeating the same alert
- freshness window limits notifications to recently issued alerts
- maximum notifications per hour puts an upper cap on how noisy the app can be

Use these controls when you want fewer repeat notifications without turning alerts off completely.

## 8. Settings reference

The Settings dialog is organized in this order:

1. General
2. Display
3. Alerts
4. Audio
5. Data Sources
6. AI
7. Updates
8. Advanced

### General

Use the General tab for everyday app behavior.

#### Refresh weather every (minutes)

Controls how often AccessiWeather refreshes weather automatically.

Use a shorter interval when you want faster background updates. Use a longer interval when you prefer less network activity.

#### Show the Nationwide location when a supported data source is selected

Shows or hides the built-in Nationwide location.

Nationwide is available when your weather source is set to Automatic or NWS.

Use this when you want quick access to national discussion products.

#### Tray icon text options

The General tab also includes tray text controls:

- Show weather text on the tray icon
- Update tray text as conditions change
- Current tray text format
- Edit tray text format

Use these options when you want the notification-area icon to show a short live weather summary instead of a plain app name.

### Display

Use the Display tab to control units, detail level, and forecast layout.

#### Temperature units

Choices are:

- Auto based on location
- Imperial (Fahrenheit)
- Metric (Celsius)
- Both

You can also choose to show values as whole numbers when possible.

#### Forecast range

The Display tab lets you choose:

- Daily forecast range: 3, 5, 7, 10, 14, or 15 days
- Hourly forecast range: 1 to 168 hours

#### Extra weather details

You can turn these details on or off:

- dew point
- visibility
- UV index
- pressure trend
- impact summaries for outdoor, driving, and allergy conditions

#### Time display

Time controls include:

- whether forecast times follow the location timezone or your own local timezone
- whether times are shown as local only, UTC only, or both
- 12-hour time format
- timezone abbreviations

#### Reading priority

You can choose:

- Minimal verbosity
- Standard verbosity
- Detailed verbosity
- Automatically prioritize severe weather details

Use these controls to make the forecast shorter or more detailed.

### Alerts

Use the Alerts tab to control alert handling, event notifications, and rate limiting.

#### Alert delivery

Controls include:

- Monitor weather alerts
- Send alert notifications
- Open alert details immediately while AccessiWeather is running

#### Coverage and severity

Controls include:

- Alert Area
- Extreme severity alerts
- Severe severity alerts
- Moderate severity alerts
- Minor severity alerts
- Uncategorized alerts

#### Extra weather event notifications

Controls include:

- discussion update notifications
- severe risk change notifications
- minutely precipitation start notifications
- minutely precipitation stop notifications

#### Rate limiting and advanced timing

Controls include:

- Maximum notifications per hour
- Advanced timing dialog for global cooldown, per-alert cooldown, and freshness window

Use these controls when you want to keep notifications useful without letting them repeat too often.

### Audio

Use the Audio tab to control sounds.

#### Playback

Controls include:

- Play notification sounds
- Sound pack
- Play sample sound
- Manage sound packs

#### When sounds play

Audio also includes event-sound controls so you can decide which event types are allowed to make noise.

Use this when:

- you want sounds for major alerts but not for routine updates
- you want to keep audio on without making every event noisy

### Data Sources

Use the Data Sources tab to choose the weather provider and configure Automatic mode.

#### Weather source

Choices are:

- Automatic
- National Weather Service
- Open-Meteo
- Visual Crossing
- Pirate Weather

Choose a single source when you want predictable provider-specific behavior. Choose Automatic when you want merged results and source fallbacks.

#### Automatic mode summary and configuration

The Data Sources tab shows a plain-language summary of your current Automatic mode settings, including:

- Automatic mode budget
- US automatic sources
- International automatic sources
- NWS station strategy

Use Configure automatic mode budget and sources to change:

- Max coverage, Economy, or Balanced
- separate US automatic source order
- separate international automatic source order
- the station strategy used when NWS chooses a current-conditions station

#### NWS station strategy

The available strategies are:

- Hybrid default
- Nearest station
- Major airport preferred
- Freshest observation

Use this when you want to influence which NWS observation station is preferred for current conditions.

#### Provider API keys

The Data Sources tab includes API key fields and validation actions for:

- Visual Crossing
- Pirate Weather

Each provider includes:

- an API key field
- a button to get a key
- a button to validate the key

Stored keys remain in secure storage unless you explicitly export them.

### AI

Use the AI tab if you want Explain Weather or Weather Assistant.

#### OpenRouter access

Controls include:

- OpenRouter API key
- Validate OpenRouter key

#### Model and explanation style

Controls include:

- model preference
- Browse OpenRouter models
- explanation style: brief, standard, or detailed

#### Custom prompts

Optional fields include:

- custom system prompt
- custom instructions
- Reset prompt to default

Leave these blank unless you want to change the AI's tone or focus.

### Updates

Use the Updates tab to control release checks.

Controls include:

- Check for updates automatically
- Release channel: Stable or Development
- Check every (hours)
- Check for updates now

Use Stable for everyday use. Use Development only if you want newer changes sooner and are comfortable with more risk.

### Advanced

Use the Advanced tab for startup behavior, backup tools, file locations, and reset actions.

#### Startup and window behavior

Controls include:

- Minimize to the notification area when closing
- Start minimized to the notification area
- Launch automatically at startup
- Enable weather history comparisons

#### Backup and transfer

Tools include:

- Export settings
- Import settings
- Export API keys (encrypted)
- Import API keys (encrypted)

This is the place to move settings between machines and to transfer API keys securely.

#### Folders and files

Tools include:

- Open current config folder
- Open installed config folder (source)
- Open sound packs folder
- Copy installed config to portable, when running in portable mode

Use these tools when you need to inspect, back up, or migrate AccessiWeather files.

#### Reset and maintenance

Tools include:

- Reset settings to defaults
- Reset all app data (settings, locations, caches)

Reset all app data is a major cleanup action. Use it only when normal troubleshooting has not solved the problem.

## 9. Keyboard shortcuts

These shortcuts are available in the current app:

- F5 or Ctrl+R: Refresh weather
- Ctrl+L: Add location
- Ctrl+D: Remove location
- Ctrl+S: Open Settings
- Ctrl+H: Open Weather History
- Ctrl+E: Explain Weather
- Ctrl+T: Open Weather Assistant
- Ctrl+Shift+R: Open NOAA Weather Radio
- Ctrl+Q: Quit

## 10. Troubleshooting

### Problem: No weather data appears

What it usually means:

- the selected source failed
- your network connection is unavailable
- the location has not refreshed yet
- an API-key-based source is selected without a working key

What to try:

1. Press F5 to refresh.
2. Switch the weather source to Automatic.
3. Confirm the location is valid and still selected.
4. If using Visual Crossing or Pirate Weather directly, validate the API key in Settings > Data Sources.
5. Try another saved location to see whether the issue is location-specific.

### Problem: Alerts are missing or seem different between sources

What it usually means:

- different providers do not offer the same alert coverage
- US alerts and international alerts follow different authority rules
- your Alert Area or severity filters are too narrow

What to try:

1. Check whether the location is in the US or outside it.
2. For US locations, remember that NWS is the authoritative alert source in Automatic mode.
3. For international locations, add a Pirate Weather key if you want broader alert coverage.
4. Review Alert Area and severity settings in Settings > Alerts.
5. Make sure alert monitoring and alert notifications are enabled.

### Problem: Forecast discussion is unavailable

What it usually means:

- the current location is outside NWS coverage
- the current provider does not support discussions
- Automatic mode did not use NWS for the current path

What to try:

1. Switch to a US location.
2. Use Automatic or NWS as the weather source.
3. If you need national products, enable and select Nationwide.
4. Refresh and try again.

### Problem: AI features are unavailable

What it usually means:

- no OpenRouter key is configured
- the key is invalid
- the selected model is unavailable or rate limited

What to try:

1. Open Settings > AI.
2. Enter or validate your OpenRouter API key.
3. Try a free model first.
4. If responses are empty, switch models and try again.

### Problem: API key validation fails

What it usually means:

- the key was entered incorrectly
- the provider account is not active yet
- the provider site is temporarily unavailable

What to try:

1. Paste the key again carefully.
2. Make sure there are no extra spaces before or after it.
3. Confirm you copied the correct provider's key.
4. Wait a few minutes and validate again if the key was just created.

### Problem: Portable mode behavior is confusing

What it usually means:

- portable mode stores configuration differently from a standard install
- keys are expected to live in the encrypted bundle, not your normal keyring

What to try:

1. Confirm you actually started the app with --portable.
2. Use Settings > Advanced to export or import encrypted API keys.
3. If needed, use Copy installed config to portable while running in portable mode.
4. Remember that blank or skipped bundle setup means keys may not persist.

### Problem: Update checks are not happening when expected

What it usually means:

- automatic update checks are disabled
- the check interval is longer than you expected
- you are on a different update channel than you intended

What to try:

1. Open Settings > Updates.
2. Confirm automatic checking is enabled.
3. Review the release channel.
4. Use Check for updates now to test immediately.

### Problem: Automatic mode did not use the source I expected

What it usually means:

- your saved US or international source order is different from what you remember
- the provider you expected is not currently available
- you selected Economy or Balanced instead of Max coverage

What to try:

1. Open Settings > Data Sources.
2. Review the Automatic mode summary.
3. Open Configure automatic mode budget and sources.
4. Check whether you are looking at the US list or the international list.
5. If you want full fusion-first behavior, choose Max coverage.
6. Confirm any required API key is present and valid.

## 11. Additional features

### Weather History

Use View > Weather History to compare current conditions with recent history when that data is available.

This feature can be turned on or off in Settings > Advanced.

### Air Quality and UV details

Use the View menu to open dedicated air quality and UV windows.

These windows can show current values, categories, forecasts, and guidance when the underlying weather data includes them.

### Aviation Weather

Use View > Aviation Weather to fetch decoded aviation weather by four-letter ICAO airport code, such as KJFK.

This is useful when you want raw and decoded TAF information and related advisories.

An optional AVWX key can improve international aviation support.

### NOAA Weather Radio

Use View > NOAA Weather Radio to open the radio player for the current location.

This feature is most useful in NOAA coverage areas and depends on online station streams being available.

### Explain Weather

Explain Weather gives you a one-shot AI explanation of the current weather.

Use it when you want a quick plain-language summary.

### Weather Assistant

Weather Assistant is the chat-style AI tool.

Use it when you want follow-up questions, practical advice, or a longer conversation about the current weather and forecast.

## 12. Where to get help

If you need help, updates, or downloads, use these resources:

- Project website: https://orinks.net/accessiweather
- GitHub issues: https://github.com/Orinks/AccessiWeather/issues
- GitHub discussions: https://github.com/Orinks/AccessiWeather/discussions
- GitHub releases: https://github.com/Orinks/AccessiWeather/releases
