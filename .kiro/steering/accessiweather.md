# AccessiWeather Development Steering

## Architecture Quick Reference

### App Structure
- Main app class: `AccessiWeatherApp(toga.App)` in `src/accessiweather/app.py`
- Config manager: `app.config_manager` (not `app.config`)
- Settings access: `app.config_manager.get_config().settings` returns `AppSettings`
- Config model: `AppConfig` contains `settings: AppSettings` and `locations: list[Location]`

### Key Patterns

#### Accessing Configuration
```python
# CORRECT - get AppSettings from config_manager
settings = app.config_manager.get_config().settings

# WRONG - config_manager doesn't have settings directly
# settings = app.config_manager.settings  # AttributeError!
# settings = app.config.settings  # AttributeError - no 'config' attribute!
```

#### Cross-Platform Path Handling
When dealing with Windows paths in code that may run on Linux (e.g., CI tests):
```python
# Use ntpath for Windows path operations
import ntpath
app_dir = ntpath.dirname(sys.executable)  # Works on Linux too
normalized = ntpath.normpath(path).lower()

# DON'T use os.path for Windows paths on Linux
# os.path.dirname("c:\\path\\file.exe")  # Returns "" on Linux!
```

### Test Markers
- `@pytest.mark.unit` - Fast, isolated tests (run in CI)
- `@pytest.mark.integration` - Tests with real API calls (skipped in CI)
- CI uses `-m "not integration"` to skip integration tests

### Common Gotchas
1. `os.path` functions are platform-dependent - use `ntpath` for Windows paths
2. ConfigManager uses `get_config()` method, not direct attribute access
3. Integration tests make real API calls - mark them properly to skip in CI
