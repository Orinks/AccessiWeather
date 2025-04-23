# AccessiWeather Knowledge Base

## Project Overview
AccessiWeather: Accessible weather app using NOAA data. Focus on screen reader support and keyboard navigation.

## Key Architecture Points
- GUI and CLI interfaces available (main.py handles both)
- Service-based architecture with clear separation of concerns
- Portable mode support - detects if running from non-standard location
- Single instance enforcement - only one instance can run
- System tray integration with configurable minimize/close behavior
- Fresh installations start with only Nationwide location in memory (no locations.json created until user adds a location)

## Development Guidelines

### Code Style
- Follow PEP 8, 100 char line length
- Use Black, isort, flake8, mypy
- Type hints required
- Docstrings for all public items

### Testing
- TDD required
- Run tests after changes: `python -m pytest tests/`
- Test with screen readers (NVDA, JAWS, VoiceOver)

#### Mock Configuration
- Configure location_service.is_nationwide_location to return False for testing regular locations
- This ensures API client is used directly instead of weather service
- Critical for testing API headers and request patterns

#### API Testing
- Mock responses should include proper error simulation
- Test all error paths: network errors, HTTP errors, JSON parsing errors
- Verify error logging using assertLogs
- Use side_effect for dynamic mock responses
- Test fallback behavior for location-based endpoints

#### Async Fetcher Tests
- Expect "Application context not available" warnings in tests
- These warnings are normal when testing async fetchers without a full wx event loop
- Use side_effect lambdas with **kwargs to handle optional parameters in mocks

#### wxPython Testing
- Use wx_app_isolated fixture for tests that create new frames/windows
- This ensures a fresh wx.App instance for each test
- Prevents state leakage between tests
- Required when creating top-level windows or frames
- For UI event tests:
  - Use wx.CallAfter for UI updates from threads
  - Process events with wx.SafeYield() after UI changes
  - Add small delays (wx.MilliSleep) between operations
  - Clean up resources in finally blocks
  - Stop threads before destroying windows
  - Prefer direct method calls over complex threading in tests

#### Exit Handling Tests
- Mock fetchers need both cancel() method and _stop_event
- cancel() method should set _stop_event when called
- Timer mocks need both Stop() method and IsRunning() property
- Stop() should update IsRunning() state
- Taskbar icon needs both RemoveIcon() and Destroy() methods
- Test both normal exit and error cases
- Critical cleanup sequence:
  1. Verify UI cleanup (timer, taskbar icon) before ExitHandler runs
  2. Run ExitHandler for thread cleanup
  3. Verify thread cleanup after ExitHandler completes
  4. Only set attributes to None after verification
  5. Process events between steps with wx.SafeYield()

### Exit Handling
- ExitHandler.cleanup_app() returns False if any part of cleanup fails
- Cleanup continues even after failures to ensure maximum resource cleanup
- Thread cleanup happens in two phases:
  1. Try cancel() method first
  2. Fall back to manual stop_event/join if cancel fails
- Failed thread cleanup should not prevent other cleanup operations
- Timer handling during exit:
  1. Minimize to tray: Stop timer before hiding, restart after hidden
  2. Force close: Stop timer permanently before cleanup
- Force close behavior:
  1. Can be triggered by force_close parameter in OnClose
  2. Can be set via _force_close instance flag
  3. Takes precedence over taskbar icon minimize behavior

### Accessibility Requirements
- All UI elements need proper screen reader labels
- Full keyboard navigation required
- Focus management must be clear
- High contrast colors for visibility

### Git Workflow
1. Create feature branch
2. Write tests first
3. Implement feature
4. Update docs
5. Submit PR

## Configuration
- Default: `~/.accessiweather/` or `%APPDATA%\.accessiweather`
- Portable mode: Uses `config/` in app directory
- Settings include:
  - API contact info
  - Update intervals
  - Alert radius
  - Minimize/close behavior
  - Cache settings

## Key Components
- WeatherApp (main window)
- UIManager (handles UI updates)
- Services:
  - WeatherService
  - LocationService
  - NotificationService
- SingleInstanceChecker (ensures one instance)
- TaskBarIcon (system tray support)

## Best Practices
- Minimal edits to accomplish changes
- Preserve existing comments exactly
- Test accessibility after UI changes
- Run type checks after changes
- Handle errors gracefully
- Clean up resources on exit

## Dependencies
- Python 3.7+ (3.11 recommended)
- wxPython 4.2.2
- Internet for NOAA API access

## Common Issues
- wxPython installation may need system packages
- Config directory permissions in portable mode
- Screen reader compatibility testing needed
- Lock file cleanup on abnormal exit
- System tray icon cleanup on exit