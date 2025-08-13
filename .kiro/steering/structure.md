# Project Structure & Organization

## Root Directory Layout
```
accessiweather/
├── src/accessiweather/          # Main source code
├── tests/                       # Test suite
├── docs/                        # Documentation
├── config/                      # Runtime configuration files
├── installer/                   # Windows installer scripts
├── scripts/                     # Utility scripts
├── logs/                        # Application logs
├── build/                       # Build artifacts (generated)
├── dist/                        # Distribution files (generated)
└── temp_backup/                 # Temporary backups
```

## Source Code Structure (`src/accessiweather/`)
```
src/accessiweather/
├── __init__.py                  # Package initialization
├── __main__.py                  # Module entry point
├── main.py                      # Application entry point
├── cli.py                       # Command-line interface
├── app.py                       # Main application class
├── version.py                   # Version information
├── constants.py                 # Application constants
├── config_utils.py              # Configuration utilities
├── logging_config.py            # Logging setup
├── cache.py                     # Data caching
├── location.py                  # Location management
├── geocoding.py                 # Geocoding services
├── api_client.py                # Legacy API client
├── api_wrapper.py               # API wrapper utilities
├── notifications.py             # Notification system
├── format_string_parser.py      # String formatting
├── national_forecast_fetcher.py # National forecast data
├── openmeteo_client.py          # Open-Meteo API client
├── openmeteo_mapper.py          # Open-Meteo data mapping
├── weather_condition_analyzer.py # Weather analysis
├── api/                         # API layer
├── api_client/                  # API client implementations
├── gui/                         # GUI components (wxPython/Toga)
├── simple/                      # Simplified UI components
├── services/                    # Business logic services
├── utils/                       # Utility modules
├── notifications/               # Notification implementations
├── soundpacks/                  # Audio resources
├── weather_gov_api_client/      # Auto-generated NWS API client
└── weatherapi_client/           # Auto-generated WeatherAPI client
```

## Key Architectural Patterns

### Modular Design
- **Separation of concerns**: GUI, API, services, and utilities are separate
- **Service layer**: Business logic isolated in `services/` directory
- **API abstraction**: Multiple weather providers through unified interface
- **Utility modules**: Shared functionality in `utils/` directory

### GUI Architecture
- **Dual framework support**: Both Toga (modern) and wxPython (legacy)
- **Component organization**: UI components grouped by functionality
- **Event handling**: Centralized handlers in `gui/handlers/`
- **Async operations**: Background data fetching with `async_fetchers.py`

### Configuration Management
- **Runtime config**: `config/` directory for user settings
- **Environment detection**: Automatic portable mode detection
- **Settings persistence**: JSON-based configuration storage
- **Multi-location support**: Saved locations with metadata

## File Naming Conventions
- **Snake_case**: All Python files and directories
- **Descriptive names**: Clear purpose indication (e.g., `weather_service.py`)
- **Service suffix**: Service classes end with `_service.py`
- **Handler suffix**: Event handlers end with `_handlers.py`
- **Client suffix**: API clients end with `_client.py`
- **Fetcher suffix**: Data fetchers end with `_fetcher.py`

## Directory Purposes

### `/src/accessiweather/`
Main application source code with entry points and core modules.

### `/src/accessiweather/gui/`
All GUI-related code including windows, dialogs, and event handlers.

### `/src/accessiweather/services/`
Business logic services that coordinate between data sources and UI.

### `/src/accessiweather/utils/`
Shared utility functions and classes used across the application.

### `/src/accessiweather/api/` & `/src/accessiweather/api_client/`
API interaction layers for different weather data providers.

### `/tests/`
Comprehensive test suite with unit, integration, and accessibility tests.

### `/docs/`
Project documentation including user manual and developer guide.

### `/config/`
Runtime configuration files (locations, settings, state).

### `/installer/`
Windows-specific installer scripts and Inno Setup configuration.

## Import Conventions
- **Absolute imports**: Use full module paths from `accessiweather`
- **Service imports**: Import services at module level
- **Lazy imports**: Heavy dependencies imported when needed
- **API client imports**: Auto-generated clients imported with aliases

## Code Organization Principles
- **Single responsibility**: Each module has one clear purpose
- **Dependency injection**: Services receive dependencies as parameters
- **Interface segregation**: Small, focused interfaces over large ones
- **Accessibility first**: All UI code considers screen reader compatibility
- **Error handling**: Comprehensive error handling with user-friendly messages
