# Test Fixes Plan

## Issues to Address
1. Mock Configuration
- Ensure location_service.is_nationwide_location returns False for testing
- Verify API client is used directly instead of weather service
- Check API headers and request patterns

2. Async Fetcher Tests
- Handle "Application context not available" warnings
- Implement proper async test patterns
- Add side_effect lambdas with **kwargs for mocks

3. wxPython Testing
- Use wx_app_isolated fixture for frame/window tests
- Implement proper event processing
- Add cleanup in finally blocks
- Stop threads before destroying windows

4. Exit Handling Tests
- Add both cancel() and _stop_event to mock fetchers
- Implement Stop() and IsRunning() for timer mocks
- Add RemoveIcon() and Destroy() to taskbar icon mocks
- Test normal and error exit cases

## Implementation Steps
1. Fix mock configuration in conftest.py
2. Update async fetcher test patterns
3. Implement proper wxPython test cleanup
4. Add comprehensive exit handling test coverage
5. Run tests and verify fixes

## Success Criteria
- All tests pass
- No resource leaks
- Proper error handling
- Clean exit behavior