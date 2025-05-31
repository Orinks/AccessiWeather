# Coverage Improvement Plan

## Current Status
- **Current Coverage**: 53%
- **Approach**: Informational reporting to guide testing priorities
- **Focus**: High-value testing of critical business logic

## Analysis of Coverage Gaps

Based on the coverage report, here are the files with the lowest coverage that have high business value:

### Critical Files Needing Attention

1. **api_wrapper.py** (31% coverage)
   - **Priority**: High
   - **Current**: 290/423 lines uncovered
   - **Focus**: Core API wrapper functionality, error handling

2. **weather_service.py** (59% coverage)
   - **Priority**: High
   - **Current**: 94/229 lines uncovered
   - **Focus**: Service layer logic, API selection, fallback mechanisms

3. **config_utils.py** (73% coverage)
   - **Priority**: High
   - **Current**: 14/52 lines uncovered
   - **Focus**: Configuration management, portable mode detection

4. **gui/weather_app.py** (34% coverage)
   - **Priority**: Medium
   - **Current**: 235/355 lines uncovered
   - **Focus**: Non-GUI business logic only

## Phase 1: Core Business Logic (Target: 2 weeks)

### api_wrapper.py Improvements
**Target**: Increase from 31% to 75%

**Missing Test Areas**:
- Rate limiting functionality
- Retry mechanisms with backoff
- Cache integration
- Error handling for different HTTP status codes
- Request/response transformation

**Suggested Tests**:
```python
# tests/test_api_wrapper_comprehensive.py
def test_rate_limiting_enforcement()
def test_retry_mechanism_with_backoff()
def test_cache_hit_and_miss_scenarios()
def test_error_handling_for_http_errors()
def test_request_transformation()
```

### weather_service.py Improvements
**Target**: Increase from 59% to 85%

**Missing Test Areas**:
- API selection logic (NWS vs Open-Meteo vs Auto)
- Fallback mechanisms when primary API fails
- Configuration-based behavior
- Error propagation and logging

**Suggested Tests**:
```python
# tests/services/test_weather_service_comprehensive.py
def test_api_selection_based_on_location()
def test_fallback_when_primary_api_fails()
def test_configuration_driven_behavior()
def test_error_handling_and_logging()
```

### config_utils.py Improvements
**Target**: Increase from 73% to 90%

**Missing Test Areas**:
- Portable mode detection logic
- Configuration migration
- Directory creation and permissions
- Error handling for file operations

**Suggested Tests**:
```python
# tests/test_config_utils_comprehensive.py
def test_portable_mode_detection()
def test_config_migration_scenarios()
def test_directory_creation_permissions()
def test_file_operation_error_handling()
```

## Phase 2: Service Layer (Target: 3 weeks)

### openmeteo_client.py Improvements
**Target**: Maintain 96% (already good)

### notifications.py Improvements
**Target**: Maintain 90% (already good)

### location.py Improvements
**Target**: Increase from 77% to 85%

**Missing Test Areas**:
- Location validation edge cases
- Coordinate parsing and validation
- Location persistence and retrieval

## Phase 3: GUI Logic (Target: 4 weeks)

### settings_dialog.py Improvements
**Target**: Maintain 88% (already good)

### ui_manager.py Improvements
**Target**: Increase from 51% to 70%

**Focus**: Data formatting and display logic (not GUI widgets)

## Implementation Strategy

### Week 1-2: API Layer
1. **api_wrapper.py**: Add comprehensive tests for rate limiting, retries, caching
2. **api_client.py**: Improve error handling test coverage

### Week 3-4: Service Layer
1. **weather_service.py**: Test API selection logic and fallback mechanisms
2. **config_utils.py**: Test portable mode and configuration management

### Week 5-6: Integration & Polish
1. **location.py**: Edge cases and validation
2. **ui_manager.py**: Data formatting logic
3. **Integration tests**: Cross-component interactions

## Quick Wins (Can be done immediately)

### Add pragma: no cover to untestable code
```python
# In GUI event handlers
def on_button_click(self, event):  # pragma: no cover
    self.handle_button_click()

# In platform-specific code
if sys.platform == "win32":  # pragma: no cover
    # Windows-specific code
```

### Test utility functions (easy coverage gains)
- `temperature_utils.py` (97% - already good)
- `unit_utils.py` (100% - already good)
- `format_string_parser.py` (95% - add 2 missing lines)

## Specific Test Files to Create/Enhance

### New Test Files Needed
1. `tests/test_api_wrapper_comprehensive.py`
2. `tests/test_config_utils_comprehensive.py`
3. `tests/services/test_weather_service_fallback.py`
4. `tests/test_location_edge_cases.py`

### Existing Files to Enhance
1. `tests/test_api_client.py` - Add error handling tests
2. `tests/services/test_weather_service.py` - Add configuration tests
3. `tests/test_config_utils.py` - Add portable mode tests

## Coverage Monitoring

### Daily Checks
```bash
# Run coverage and check progress
python -m pytest --cov=src/accessiweather --cov-report=term-missing | grep "TOTAL"
```

### Weekly Reports
- Generate HTML coverage reports
- Identify new gaps introduced by code changes
- Update this plan based on progress

## Success Metrics

### Phase 1 Success (2 weeks)
- Comprehensive testing of core API functionality
- api_wrapper.py: Improved error handling and retry logic coverage
- weather_service.py: Better API selection and fallback testing
- config_utils.py: Enhanced configuration management testing

### Phase 2 Success (3 weeks)
- Service layer reliability improvements
- location.py: Better validation and edge case coverage
- Additional service layer robustness

### Phase 3 Success (4 weeks)
- ui_manager.py: Improved data formatting logic testing
- All critical business logic well-tested
- Focus on quality over quantity

## Notes

- Focus on testing business logic, not GUI widgets
- Use mocks extensively for external dependencies
- Prioritize error handling and edge cases
- Add `pragma: no cover` for truly untestable code
- Maintain test quality over coverage quantity
