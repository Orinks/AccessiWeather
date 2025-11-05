# Changelog

All notable changes to AccessiWeather will be documented in this file.

## [Unreleased]

### Added
- Intelligent alert notification system with rate limiting and cooldowns
  - Global cooldown (default: 5 min) prevents notification spam across all alerts
  - Per-alert cooldown (default: 60 min) prevents duplicate notifications
  - Escalation override (default: 15 min) allows high-severity alerts to bypass cooldowns
  - Hourly notification cap (default: 10) prevents excessive notifications
- Severity-based alert filtering
  - Configure which alert severities trigger notifications (Extreme, Severe, Moderate, Minor, Unknown)
  - Minor severity alerts disabled by default to reduce noise
- Alert notification history tracking
  - Bounded history (max 500 notifications) prevents memory growth
  - Tracks notification timestamps and severities for rate limiting decisions
- Comprehensive test coverage for alert system (104 tests)
  - Constants validation tests (19 tests)
  - Alert state history tests (26 tests)
  - Token bucket rate limiting tests (14 tests)
  - Accessibility formatting tests (18 tests)
  - UI accessibility audit tests (15 tests)
  - Configuration migration tests (12 tests)

### Changed
- Alert notification settings now persist in configuration
- AlertManager reconfigurable at runtime without restart
- Improved screen reader accessibility for notification settings UI
  - All controls have proper aria_label and aria_description attributes
  - Logical keyboard navigation order
  - Clear focus indicators and descriptive labels

### Fixed
- Eliminated magic numbers in alert notification code
- Improved testability with dependency injection patterns
- Enhanced configuration migration backward compatibility

## [0.9.1] - 2025-05-07

### Added
- System tray functionality with minimize to tray option
- Escape key shortcut to hide app to system tray
- Extended 7-day forecast display (all 14 periods)
- Current conditions integration with temperature, humidity, wind, and pressure
- Hourly forecast integration for detailed short-term predictions
- Debug mode CLI flag for testing and development

### Changed
- Consolidated update mechanism for better performance
- Enhanced weather discussion reader with improved formatting

### Fixed
- Alert update interval setting issues
- Weather discussion fetching and display problems
- Loading dialog cleanup
- Various accessibility improvements for screen readers

### Known Issues
- Screen readers parse Nationwide discussions oddly and read them incorrectly, even though the data is being fetched correctly
- Escape key for minimizing is currently busted.
## [0.9.0] - 2025-04-14 (Beta Release)

### Added
- Complete NOAA weather API integration
- Location management with multiple saved locations
- Search by address or ZIP code
- Manual coordinate entry support
- Detailed weather forecasts with temperature and conditions
- Active weather alerts, watches, and warnings
- Weather discussion reader
- Desktop notifications for weather alerts
- Precise location alerts (county/township level)
- Statewide alert toggle
- Alert details dialog to display alert statements
- Accessible UI with screen reader compatibility
- Keyboard navigation support
- Configuration persistence
- True portable mode with local configuration storage

### Changed
- Removed autocomplete from location search for better accessibility
- Improved error handling and user feedback
- Enhanced thread safety in wxPython components
- Enhanced location display with full address information
- Standardized configuration directory location

### Fixed
- Thread safety issues in UI updates
- Segmentation faults in some test scenarios
- API error handling and recovery
- Location search crash by making geocoding asynchronous
- ZIP code search functionality
- Precise location alerts setting persistence

## [0.1.0] - 2024-01-01 (Initial Development)

- Initial project structure
- Basic wxPython UI framework
- NOAA API client implementation
