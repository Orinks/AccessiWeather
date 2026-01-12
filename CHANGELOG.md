# AccessiWeather Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Added
- Settings export and import - backup your preferences to a file and restore them on another machine, perfect for keeping your setup in sync across devices. Find it in Settings > Advanced. Your API keys stay secure in your system keyring and aren't included in the export file
- Config file protection on Windows - your configuration file now has Windows-equivalent permissions (user-only access), matching the existing protection on macOS and Linux. This adds defense-in-depth for your location data and preferences
- UV Index Dialog - dedicated view for detailed UV index information and sun protection recommendations accessible from the View menu

### Changed
-

### Fixed
-

### Removed
-

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
