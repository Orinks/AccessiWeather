# AccessiWeather Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed
- Forecaster Notes now hides Hazardous Weather Outlook and Special Weather Statement tabs when NWS confirms there is no matching product for the selected office.
- Nightly builds now report the dev package version consistently instead of using stale generated build metadata.

## [0.6.0] - 2026-04-24

### Added
- You can now grab the whole alert — headline, details, instructions, timestamps — in one click with the new **Copy to clipboard** button in the alert dialog. Works the same whether you use separate fields or the combined view.
- **Edit Location** — a new "Edit Location" button and menu item in the Location menu let you toggle Marine Mode on existing locations without having to remove and re-add them
- **NOAA radio station count chooser** — the NOAA Weather Radio dialog now lets you pick how many nearby stations to load (10, 25, 50, 100, or All) without digging through the main Settings window
- **Precipitation timeline dialog** — View > Precipitation Timeline now opens a dedicated Pirate Weather minutely precipitation timeline with a quick summary and minute-by-minute plain-text breakdown
- **Faster Pirate Weather rain checks are opt-in** — a new notification setting lets you check minutely precipitation more often when rain is likely, while the default cadence stays closer to Pirate Weather's recommended update window
- **Single combined alert view** — pick "Single combined view" in Settings > Display > Alert display to read the whole alert (headline, description, instruction, Issued, and Expires) in one scrollable edit box with a Close button. The original separate-fields layout is still the default
- **Configurable date format** — choose how dates are shown: ISO (2026-04-18), US short (04/18/2026), US long (April 18, 2026), or EU (18/04/2026). Applies to timestamps in the new combined alert view for now
- **Pressure outlook for fishing and planning** — pressure trends now say when a barometric pressure drop or rise is predicted, and Settings > Display lets you choose the pressure outlook range from 1 hour to 7 days

### Fixed
- **Pirate Weather minutely precipitation units** — rain-start notifications now evaluate Pirate Weather minutely intensity in consistent mm/hr units, and the timeline shows the unit plus uncertainty when Pirate Weather provides it
- **NOAA radio station count now sticks** — your nearby-station limit is saved with NOAA radio preferences and reused the next time you open the dialog, while preferred stream choices keep working as before
- **Automatic update checks now fire on long-running sessions** — the 24-hour update check used a single long wxTimer that could silently skip its tick after the computer slept or hibernated, so users who left the app open had to check manually. The scheduler now polls every 15 minutes and uses wall-clock elapsed time, so checks run on schedule even across sleep/wake cycles
- **Adaptive Pirate Weather minutely polling** — minutely precipitation checks now stay near Pirate Weather's recommended cadence by default, with an opt-in faster check cadence when the hourly forecast suggests rain is likely soon (#565)

## [0.4.5] - 2026-03-26

### Added
- **Optional in-app alert detail popups** — while AccessiWeather is already running, you can now choose to open newly eligible alert details immediately instead of only getting toast notifications (#578)
- **Pirate Weather full integration** — Pirate Weather is now a first-class data source with alerts, hourly and minutely forecasts, and automatic fusion alongside NWS and Open-Meteo (#479)
- **AVWX aviation source** — TAF and METAR data from AVWX for international locations (#480)
- **All Locations summary view** — see a compact weather overview for all your saved locations at once (#518)
- **ScreenReaderAnnouncer** — new dynamic announcement system for status changes, ensuring NVDA and other screen readers get timely updates without polluting the status bar (#525)
- **Configurable auto mode source list** — choose which sources are eligible when using Smart Auto mode (#531)
- **All Locations tray placeholder** — `{alert}` tray text placeholder shows the most severe active alert across all locations (#519)
- **Whole-numbers display setting** — global option to round all displayed values to whole numbers (#476)
- **Auto unit preference** — units default to metric or imperial based on the detected country of the selected location (#490)
- **Improved geocoding** — international locations with special characters (accents, non-ASCII) now resolve correctly (#491)
- **Humidity and dewpoint in hourly forecasts** (#499)
- **Pirate Weather hourly/minutely summaries** surfaced in auto mode (#498)
- **AFD section extraction** — Area Forecast Discussion change notifications now summarize the relevant changed sections (#453)
- **Version shown in About dialog** (#451)
- **Alert timing controls moved to Advanced dialog** — declutters the main Settings window (#524)
- **Separate daily and hourly forecast sections** — navigable independently with screen readers (#501)

### Changed
- **Open-Meteo now handles extended forecasts** — replaces the previous NWS+OM stitching approach for cleaner multi-day data (#484)
- **Default soundpack converted from WAV to OGG** — smaller file size, same quality (#542)
- **Status bar replaces custom status label** — NVDA End-key navigation now works correctly in the main window (#539)
- **Redundant US/international priority combo boxes removed** from Settings (#535)
- **Minimum Python version bumped to 3.11**
- **Parallel fetch timeout is now configurable**
- Runtime alert and notification state migrated to normalized storage roots (#468)

### Fixed
- **Action Center notification clicks now reopen AccessiWeather** — clicking a weather alert or discussion update restores the running app and opens the matching dialog instead of doing nothing (#573)
- **Forecast timezone labels now honor the location timezone consistently** — daily generated times and hourly forecast labels use named zones like BST when available instead of falling back to UTC/GMT offsets (#572)
- **Permanent refresh freeze** — weather updates no longer stop indefinitely when a location is added or removed while a background fetch is in progress (#545)
- **stop_all_sounds() now works** — was silently doing nothing; now properly stops all active audio streams (#545)
- **Announcer cleanup on exit** — ScreenReaderAnnouncer is now shut down properly when the window closes (#545)
- **Auto-source checkboxes update immediately** when a VC/PW API key is entered or cleared in Settings (#545)
- **Routine status bar calls removed** — NVDA no longer announces every background weather refresh as a status change (#543)
- **NWS detailed forecast text restored** — was accidentally hidden by a removed setting (#537)
- **Data source is now strictly respected** — selecting a specific source no longer silently falls back to NWS (#530)
- **Fields hidden when not provided by source** — no more blank or stale values from a previous source showing through (#528)
- **Visibility capped at 10 statute miles** in Open-Meteo output (#532)
- **UV index uses real-time value** in Open-Meteo current conditions, not the daily maximum (#533)
- **API key portable bundle** now applies to the weather client on startup and refreshes when settings change (#523)
- **severe_weather_override defaults to False** — was accidentally opt-in on fresh installs
- **Pirate Weather source preference preserved** across restarts (#512)
- **Pirate Weather alert cancellation stabilized** — no more false cancellation announcements when an alert briefly disappears upstream (#503)
- **Pirate Weather WMO alerts treated as regional** — correctly labeled, not matched to county/zone (#504)
- **Duplicate NWS discussion notifications prevented** (#notifications)
- **Pirate Weather keyring resolution retried on startup** — fixes missing PW data after first launch (#515)
- **Tray wind direction** now displays as cardinal (N/NE/etc.) instead of raw degrees (#511)
- **Tray text format configuration improved** (#460)
- **AFD update notifications** now use cleaner, more informative text (#462)
- **Visual Crossing timeline API path corrected** (#465)
- **Canadian border city detection fixed** — cities near the US/Canada border now resolve to the correct country
- **Open-Meteo overnight lows** now display correctly (#497)
- **Auto-select newly added location** (#516)
- **UTC fallback crash, weather code messages, and expired alert display** fixed in combined bug hunt pass (#522)
- **Accessibility audit fixes** — button order, accessible labels, and keyboard focus corrected throughout (#520)

---

## [0.4.2] - 2025-12-16

### Added
- AI weather explanations and model browser - get AI-generated insights about your weather, and pick specific OpenRouter models instead of just "Auto (Free)" or "Auto (Paid)". Hit "Browse Models..." in the AI tab to search through all available models, filter by free/paid, and see context lengths and pricing
- HTML-based weather display with optional semantic HTML rendering for better accessibility
- Smart Auto Source with seasonal weather display - automatically picks the best weather source (NWS for US, Open-Meteo internationally) and shows you which source each piece of data came from
- Air Quality Dialog - dedicated view for detailed air quality and pollutant information accessible from the View menu
- Hourly air quality forecasts - see pollutant levels and AQI predictions for the coming hours
- Dynamic taskbar icon text - shows current weather conditions (temperature and conditions) in the taskbar on Windows 11+
- Weather history trends and pollen display - compare weather against yesterday and last week, with detailed pollen count forecasts
- Precipitation probability, snowfall, and UV index in forecasts - see detailed precipitation chance, expected snowfall amounts, and UV intensity in your forecast

### Changed
- Forecast display now uses WebView with optional semantic HTML rendering for faster performance

### Fixed
- API keys now persist in secure storage regardless of selected data source, fixing auto mode's ability to use Visual Crossing when configured
- System tray tooltip now shows actual weather data (like "45F Clear") instead of just "AccessiWeather" on Windows 11
- Hourly forecast times now display correctly in your location's timezone for all data sources (NWS and Visual Crossing were showing UTC times, causing incorrect displays like "0:00 AM" for midnight UTC)
- Forecast periods no longer appear twice - the app now picks the best single source (NWS for US, Open-Meteo internationally) instead of merging forecasts from multiple sources with different naming conventions
- Snow depth and snowfall values now display correctly - Open-Meteo was returning data in metric units (cm/meters) but the code treated them as imperial (inches/feet), causing values to be 2-3x too high

---

## [0.4.1] - 2025-11-20

### Highlights
- **Secure API Key Storage**: Integrated system keyring for safer storage of API credentials on Windows, macOS, and Linux—no more plain-text keys in config files.
- **Moon Phase Data**: Visual Crossing moon phase information now displays in the current conditions, showing lunar phase with readable descriptions.
- **Flexible Time Display**: Standardized time format controls across the app—choose between local time, UTC, or both, with 12/24-hour and timezone label toggles to suit your preferences.
- **Performance Improvements**: Implemented cache-first design with background enrichment updates, reducing unnecessary API calls by 80%+ and improving app responsiveness on slower connections.

### Added
- Secure API Key Storage via system keyring (Windows, macOS, Linux)
- Moon Phase Data integration from Visual Crossing (API integration complete; UI display pending)
- Flexible time display preferences (local/UTC toggle, 12/24-hour format, timezone labels)
- Fine-grained alert notification settings for alert type filtering
- Automatic weather refresh when app window returns to foreground

### Changed
- Time format preferences now consistently apply to all displayed timestamps (sunrise/sunset, forecasts, alerts, weather history)
- Cache-first architecture pre-warms forecasts in the background while serving cached data instantly to the user
- Alert notification settings UI for better accessibility and control
- Modernized sound pack manager and community browser interface
- Improved NWS observation station selection to prioritize quality data
- Enhanced international Open-Meteo support with better location search scoring

### Fixed
- Timezone display bug for sunrise/sunset times—now properly respects location timezone instead of shifting by local offset
- NWS temperature unit normalization inconsistencies
- Improved weather data coverage and aviation handling to reduce missing data gaps
- Sound pack manager async race conditions during import/delete
- NWS 'Last updated' timestamps now convert to location's timezone based on user display preferences
- Keyring now gracefully handles missing system integration without crashing
- Location search now returns correct results when adding locations

### Known Issues
- **Moon Phase Data (UI Not Displaying)**: Visual Crossing moon phase API calls are working correctly, but the UI is not yet displaying the retrieved moon phase information. The data is being fetched and cached successfully; this is a presentation-layer issue that will be resolved in a future patch.

### Upgrade Notes
- **API Keys**: Add your API keys through Settings > Data Sources. Keys are now stored securely in your system's keyring (Windows Credential Manager, macOS Keychain, Linux Secret Service) instead of plain text.
- Portable Windows builds should remove any legacy `config` folders next to the executable before extracting the new ZIP to ensure clean asset refresh.
- Need a fresh start? Use Settings > Advanced > Reset Application to clear your config and start fresh. Your config is stored in `%APPDATA%\.accessiweather` on Windows and `~/.accessiweather` on macOS/Linux.

---

## [0.4.0] - 2025-10-12 [YANKED]

⚠️ **Security Warning**: This release stored API keys in plain text in `accessiweather.json`. Upgrade to v0.4.1+ immediately.

### Added
- Desktop app rebuilt on BeeWare's Toga toolkit for native UI across Windows, macOS, Linux
- Weather History comparisons against yesterday and last week using Open-Meteo archive
- Auto mode with enriched forecasts (sunrise/sunset, NWS discussions, Visual Crossing alerts)
- Sound pack manager with modular interface, mapping previews, creation wizard, community integration
- Update center with stable/beta/dev channels and checksum-verified downloads
- Expanded current conditions view (sunrise/sunset, UV, air-quality, pollen metrics)
- Universal Remove shortcut (Ctrl/Cmd+D) for locations and sound packs
- Startup management for automatic launch on Windows, macOS, Linux
- Accessible Weather History dialog with forecast discussion reader layout

### Changed
- Refined settings dialog with accessible dropdowns for temperature units and data sources
- Refactored codebase into modular packages (app shell, presenters, weather client, updater)
- Streamlined CI/CD with make.py-driven builds, nightly smoketests, checksum validation

### Fixed
- Normalized Open-Meteo timestamps for international forecasts
- Restored legacy `current` weather accessor compatibility
- Prevented duplicate application launches
- Removed unstable text-to-speech override controls

### Removed
- wxPython-based UI and related dependencies
- Unstable text-to-speech override functionality

---

## [0.3.1] and earlier

See git history for detailed changes prior to v0.4.0.
