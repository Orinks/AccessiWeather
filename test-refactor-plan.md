Test Refactoring Plan

1. Consolidate Mock Fixtures
- Move common mock fixtures to conftest.py
- Create base fixtures for:
  - API client mocks
  - Weather service mocks
  - Location service mocks
  - Notification service mocks
  - Common test data

2. Consolidate Duplicate Tests
- Merge test_weather_app.py and test_weather_app_refactored.py
- Merge test_gui.py and test_gui_loading_improved.py
- Consolidate location-related tests into test_location_service.py

3. Standardize Test Structure
- Use pytest fixtures consistently instead of mixing unittest
- Use consistent naming conventions
- Add proper docstrings and comments
- Use consistent assertion styles

4. Improve Test Organization
- Group related tests together
- Create test classes for logical grouping
- Use descriptive test names
- Add setup/teardown where appropriate

5. Improve Mock Usage
- Use proper mock specifications
- Avoid redundant mocks
- Use context managers for patches
- Add proper cleanup

6. Add Missing Test Coverage
- Add edge cases
- Add error cases
- Add boundary conditions
- Add integration tests where needed

Implementation Steps:

1. First consolidate fixtures in conftest.py
2. Then merge duplicate test files
3. Then standardize test structure
4. Finally add missing coverage

The goal is to make the tests:
- More maintainable
- More readable 
- More reliable
- More complete
- Less redundant

While preserving all existing test coverage.