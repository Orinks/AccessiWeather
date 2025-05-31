# Test Coverage Strategy

## Overview

AccessiWeather generates test coverage reports for unit tests to help identify areas that may need additional testing. This document outlines our coverage strategy, focusing on high-value testing rather than just hitting coverage numbers.

## Coverage Configuration

### Current Settings (.coveragerc)

- **Target**: Coverage reporting for unit tests (no minimum threshold enforced)
- **Scope**: `src/accessiweather` (excludes generated API client code)
- **Exclusions**: Test files, generated code, and untestable patterns

### Smart Exclusions

The following patterns are excluded from coverage requirements:

```ini
# Core exclusions
pragma: no cover
def __repr__
if self.debug:
if settings.DEBUG
raise AssertionError
raise NotImplementedError

# Type checking and imports
if TYPE_CHECKING:
except ImportError:
except ModuleNotFoundError:

# Platform-specific code
if sys.platform
if platform.system

# GUI event handlers (hard to test)
def on_.*\(self, event\):

# Cleanup methods
def __del__
```

## High-Value Coverage Areas

### Priority 1: Core Business Logic (Target: 90%+)

1. **Weather Data Processing**
   - `openmeteo_client.py` - API client logic
   - `openmeteo_mapper.py` - Data transformation
   - `api_client.py` - NOAA API integration

2. **Configuration Management**
   - `config_utils.py` - Settings persistence
   - `location.py` - Location management
   - `cache.py` - Data caching

3. **Utility Functions**
   - `temperature_utils.py` - Temperature conversions
   - `unit_utils.py` - Unit formatting
   - `format_string_parser.py` - String parsing

### Priority 2: Service Layer (Target: 80%+)

1. **Weather Service**
   - `services/weather_service.py` - Main weather logic
   - `services/location_service.py` - Location operations

2. **Notification System**
   - `notifications.py` - Alert processing
   - `services/notification_service.py` - Notification delivery

### Priority 3: GUI Logic (Target: 60%+)

Focus on testable business logic within GUI components:

1. **Settings Management**
   - `gui/settings_dialog.py` - Configuration UI logic
   - Data validation and transformation

2. **Data Display Logic**
   - `gui/ui_manager.py` - Data formatting for display
   - Non-GUI-dependent formatting functions

### Lower Priority: GUI Event Handlers (Target: 40%+)

- Event handlers are often excluded or have lower coverage requirements
- Focus on testing the underlying logic they call
- Use integration tests for full GUI workflows

## Coverage Quality Guidelines

### What Makes Good Coverage

1. **Test Critical Paths**: Focus on main user workflows
2. **Test Error Conditions**: Ensure graceful error handling
3. **Test Edge Cases**: Boundary conditions and unusual inputs
4. **Test Public APIs**: All public methods should be tested

### What to Avoid

1. **Testing Implementation Details**: Don't test private methods directly
2. **Trivial Tests**: Avoid tests that just call getters/setters
3. **GUI Widget Creation**: Focus on logic, not widget instantiation
4. **External API Calls**: Mock external dependencies

## Monitoring Coverage

### CI Pipeline

- Coverage reports are generated for each PR for informational purposes
- No minimum coverage threshold is enforced
- Trends can be tracked over time

### Local Development

```bash
# Run tests with coverage
python -m pytest --cov=src/accessiweather --cov-report=html

# View detailed report
open htmlcov/index.html
```

### Coverage Analysis

1. **Review uncovered lines** in coverage reports
2. **Identify high-value missing tests** 
3. **Add `pragma: no cover` for untestable code**
4. **Focus on business logic over boilerplate**

## Current Status

- **Current Coverage**: ~53%
- **Approach**: Informational reporting without enforced thresholds

### Improvement Plan

1. **Phase 1**: Core business logic (weather data, config, utils)
2. **Phase 2**: Service layer (weather service, notifications)
3. **Phase 3**: Testable GUI logic (settings, data formatting)

## Best Practices

### Writing Testable Code

1. **Separate business logic from GUI code**
2. **Use dependency injection for external services**
3. **Keep functions small and focused**
4. **Avoid global state when possible**

### Test Organization

1. **Unit tests**: Fast, isolated, high coverage
2. **Integration tests**: Component interactions
3. **GUI tests**: User workflows (lower coverage requirements)
4. **E2E tests**: Full application scenarios

### Pragmatic Approach

- **Coverage is informational, not a gate**
- **Focus on meaningful tests over coverage numbers**
- **Use `pragma: no cover` judiciously for untestable code**
- **Prioritize testing based on user impact and complexity**

## Conclusion

Coverage reporting helps AccessiWeather maintain high reliability standards while allowing flexibility for GUI code and edge cases. Focus on testing core business logic and user-critical paths rather than achieving coverage through trivial tests.
