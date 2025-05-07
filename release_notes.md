# AccessiWeather v0.9.1

## Added
- System tray functionality with minimize to tray option
- Escape key shortcut to hide app to system tray
- Extended 7-day forecast display (all 14 periods)
- Current conditions integration with temperature, humidity, wind, and pressure
- Hourly forecast integration for detailed short-term predictions
- Debug mode CLI flag for testing and development

## Changed
- Consolidated update mechanism for better performance
- Enhanced weather discussion reader with improved formatting

## Fixed
- Alert update interval setting issues
- Weather discussion fetching and display problems
- Loading dialog cleanup
- Various accessibility improvements for screen readers

## Known Issues
- Screen readers parse Nationwide discussions oddly and read them incorrectly, even though the data is being fetched correctly
