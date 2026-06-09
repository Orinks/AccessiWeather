# AccessiWeather Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed
- AccessiWeather can now automatically tune NOAA Weather Radio for qualifying alerts that use Specific Area Message Encoding (SAME) when you turn on the opt-in setting on the Alerts tab, then stop after the duration you choose when a reliable station match is available.
- NOAA Weather Radio now opens independently of saved weather locations and keeps playing after you close the player until you press Stop or exit the app.
- The NOAA Weather Radio Station Finder now has clearer modes for searching all stations, browsing by full state or territory name, and finding nearby stations by coordinates.
- NOAA Weather Radio stations can now be saved as favorites, with a Favorites finder mode and optional nearby-station lookup from your saved AccessiWeather locations.

### Fixed
- Unknown or uncategorized weather alerts now have a mappable default sound, and missing custom-pack event sounds fall back to the matching default sound before generic notification audio.
- NOAA Weather Radio Station Finder now repopulates stations when leaving an empty Favorites view, so you no longer need to reopen the radio dialog.
- Feels-like temperatures now keep showing in tray text when only one temperature unit is available, instead of falling back to `N/A`.

## [0.7.2] - 2026-05-30

### Added
- You can now choose "Use my current location" when adding or updating a saved location. AccessiWeather asks the OS once, only after you press the button, and keeps manual search available if location access is denied or unavailable.
- Alert updates can now use their own mappable sound in sound packs.
- Settings > Audio can now enable specific-alert sounds per sound pack, so packs with sounds like `tornado_watch` and `tornado_warning` keep working while severity-only packs stay simple.
- First-run setup can now import existing settings and encrypted API keys from the wizard, or exit with Escape at any wizard step when you want to configure everything yourself.
- You can now search for a US street address when adding or editing a location, so AccessiWeather can save coordinates for that specific address instead of the nearest city or ZIP result.
- Saved locations now stay sorted alphabetically in the location list (#667).
- You can now choose to sort saved locations alphabetically or nearest to the current location.
- **Daily Climate Reports in Forecaster Notes** — You can now read the latest NWS Daily Climate Report for supported US climate stations, with station-aware lookup, cached refreshes, history through Advanced Lookup, and optional update notifications.
- **National Products in Forecaster Notes** — Forecaster Notes now opens a dedicated National Products dialog for SPC, WPC, NHC, CPC, and other national NWS text products. The new view replaces the old Nationwide Discussions scraper with IEM AFOS plain-text products while keeping the existing Advanced Lookup path available for direct product searches (#641).
- **Guided Advanced Lookup in Forecaster Notes** — Advanced Lookup now organizes NWS and IEM text products into product groups with clearer product choices, office selection, date presets, result limits, sort order, source selection, aviation AFD, center, WMO, and text-match filters.

### Changed
- Linux downloads now ship as `.tar.gz` tarballs instead of ZIP files.
- Alert sounds and sound-pack creation now focus on alert severity instead of a long list of specific alert names, while existing packs can keep their older mappings.

### Fixed
- Edit Location and Settings > AI prompt fields now expose their visible labels correctly to screen readers.
- Reliability fixes now prevent several update, notification, tray tooltip, dialog, NOAA radio, and alert-refresh edge cases from interrupting normal use.
- Detected current locations outside the US now get an editable place name when reverse geocoding can identify the coordinates.
- Editing a location after using "Use my current location" now refreshes the editable name and saved US metadata for the detected point, so locations don't quietly fall back to metric defaults.
- Notification sounds now recover after Windows sleep or hibernation, so update
  notifications don't fall back to only the generic Windows toast sound.
- Plain Language Summary now shows and speaks which OpenRouter model it is trying, when it falls back from a busy free model, and why the final model was used.
- Forecaster Notes AI summaries now use the same default prompt for every text product unless you've set custom AI prompt options.
- Default AI summaries now stay grounded in the provided weather text or data, so they are less likely to invent forecast details when summarizing reports.
- Relaunching AccessiWeather on Windows now reliably restores the already-running window from desktop shortcuts, direct EXE launches, and portable copies without relying on the window title.
- Restoring the running AccessiWeather window on relaunch, and bringing it to the front from a notification, now work reliably on 64-bit Windows instead of leaving the window in the background.
- Relaunching AccessiWeather no longer briefly activates the already-running window twice in rare fallback cases.
- Alt+F4 now stays routed through the normal close-to-tray behavior after switching between All Locations and saved locations.
- Automatic Windows startup now stays in the background when AccessiWeather is already running, and startup shortcuts are recreated with a stable AccessiWeather target for portable copies.
- The Windows installer now closes running AccessiWeather copies automatically before installing, then can launch the updated app normally when setup exits.
- Alt+F4 now respects "Minimize to the notification area when closing" again, so keyboard users can send AccessiWeather to the background without exiting.
- Launching AccessiWeather no longer focuses a browser tab whose title starts with "AccessiWeather" instead of opening the app.
- Open-Meteo location searches now handle common city/state or city/country entries like "New York, NY" and "London, UK" when adding locations.
- The Windows installer now waits for any running AccessiWeather copy before replacing files, including portable copies launched from a folder.
- Plain Language Summary now works for Daily Climate Reports and other Forecaster Notes text products, not just AFD, HWO, and SPS.
- Weather Assistant now avoids a removed OpenRouter free model, so automatic free mode no longer fails with a 404 before answering.
- Opening AccessiWeather no longer sends catch-up notifications for older Forecaster Notes updates; text-product notifications now start from the current session, and HWO/SPS checks run after their latest products are loaded.
- Default soundpack now includes specific sounds for mapped weather alert types.
- Pirate Weather minute-by-minute precipitation notifications now wait until start/stop changes are near-term and no longer count down repeatedly for the same rain event.
- Saving Settings no longer waits on the Windows startup shortcut check unless you actually change the launch-at-startup checkbox.
- Settings now opens without waiting on the Windows startup shortcut check.
- The weather-refresh completion sound is now off by default, and switching to a cached location no longer plays it before the real refresh finishes.
- Open-Meteo forecasts now keep unit-aware wind, visibility, snow depth, pressure, and freezing-level details instead of misreading feet, meters, or kilometers in some payloads.
- Open-Meteo daily forecasts now include low temperatures and wind details when the API provides them.
- Weather history comparisons now skip incomplete Open-Meteo archive responses instead of comparing against placeholder zero values.
- Pressure outlooks no longer show unrealistic swings when current conditions and hourly forecasts use mixed pressure reference levels.
- NWS and Pirate Weather data handling is more accurate: NWS alert lookups now avoid rejected radius parameters and stale cross-location alert caches, while Pirate Weather no longer treats precipitation rate as accumulated amount or reuses US units for international minutely precipitation checks.
- NWS forecasts now pair daytime highs with following nighttime lows when NWS provides day/night forecast periods.
- Smart Auto mode now keeps the NWS forecaster discussion from its main NWS fetch, avoids a duplicate follow-up request when it already has that discussion, and chooses Open-Meteo for extended US forecasts even if Pirate Weather is listed first.
- Smart Auto mode now fills in current condition text from Open-Meteo or Pirate Weather when NWS reports an empty or unknown condition.
- Canadian locations near the border no longer try NWS in Automatic mode when an older/manual location is missing a saved country code.
- IEM text-product lookup errors no longer appear as if they were valid forecaster text.
- Alerts now honor your selected alert area during regular refreshes, including state and zone alert modes.
- Zone alert mode now checks both county and forecast zones so county-based watches and warnings are less likely to be missed.
- The "Launch automatically at startup" setting now updates the system startup entry instead of only saving the checkbox.
- Repeated checks of unchanged alerts no longer use up notification rate-limit capacity before newer alerts are handled.
- The update dialog now shows release notes as screen-reader-friendly plain text instead of raw Markdown.
- Linux packages now include the files needed for notification sounds.
- Linux packages now avoid a startup compatibility issue on some systems.
- Forecaster Notes now starts with NWS discussion tabs only and adds IEM-backed tabs only when active SPC/WPC products apply to your selected location.
- Pirate Weather now requests API v2 data and carries v2 precipitation types like freezing rain and wintry mix into current, daily, and hourly forecasts.
- Forecaster Notes now hides Hazardous Weather Outlook and Special Weather Statement tabs when NWS confirms there is no matching product for the selected office.

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
