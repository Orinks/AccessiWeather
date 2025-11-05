# Changelog

All notable changes to AccessiWeather will be documented in this file.

## [Unreleased]

### Performance
- **Weather data fetch optimizations**: Comprehensive improvements reducing API calls and latency
  - Request deduplication: Concurrent requests for same location now coalesce into single API call (10x reduction)
  - Enhanced caching: 180-minute TTL cache with early freshness checking reduces redundant fetches by 80%+
  - Cache pre-warming: Background pre-fetching of weather data for faster initial display
  - Connection pooling: Optimized HTTP connection pool (30 max connections, 15 keepalive) for faster parallel fetches
  - Parallel enrichment: Alerts, discussions, and sunrise/sunset data fetched simultaneously
  - Smart timeouts: Configurable connect (5s) and read (10s) timeouts with exponential backoff retry
  - Performance instrumentation: Comprehensive timing measurements for monitoring fetch operations
- **Test coverage**: 31 performance tests (23 unit + 8 end-to-end) validating real-world scenarios
  - App startup with multiple locations (<2s for 5 locations)
  - Rapid location switching with cache hits (<1s for 5 requests)
  - Concurrent request handling (<0.2s for 10 coalesced requests)
  - Cache effectiveness (<10ms for cache hits vs 50ms+ fresh fetches)
  - Load testing (20 concurrent requests with intelligent deduplication)

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
