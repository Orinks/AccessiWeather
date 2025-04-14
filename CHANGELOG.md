# Changelog

All notable changes to AccessiWeather will be documented in this file.

## [0.9.0] - 2024-06-01 (Beta Release)

### Added
- Complete NOAA weather API integration
- Location management with multiple saved locations
- Detailed weather forecasts with temperature and conditions
- Active weather alerts, watches, and warnings
- Weather discussion reader for in-depth analysis
- Desktop notifications for weather alerts
- Precise location alerts (county/township level)
- Statewide alert toggle
- Accessible UI with screen reader compatibility
- Keyboard navigation support
- Configuration persistence

### Changed
- Removed autocomplete from location search for better accessibility
- Improved error handling and user feedback
- Enhanced thread safety in wxPython components

### Fixed
- Thread safety issues in UI updates
- Segmentation faults in some test scenarios
- API error handling and recovery

## [0.1.0] - 2024-01-01 (Initial Development)

- Initial project structure
- Basic wxPython UI framework
- NOAA API client implementation
