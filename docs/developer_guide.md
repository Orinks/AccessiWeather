# NOAA Weather App - Developer Guide

## Architecture Overview

The AccessiWeather App follows a modular design with clear separation of concerns:

```
accessiweather/
├── api_client.py                # NOAA API interaction
├── notifications.py             # Alert notifications
├── constants.py                 # Shared constants and configurations
├── location.py                  # Location management
├── main.py                      # Application entry point (starts GUI or CLI)
├── cli.py                       # Command-line interface logic
├── national_forecast_fetcher.py # Fetches national forecast data
├── utils/
│   ├── __init__.py
│   └── thread_manager.py        # Thread management utility
├── services/
│   ├── __init__.py
│   ├── location_service.py      # Location service
│   ├── weather_service.py       # Weather service
│   └── national_discussion_scraper.py # Scrapes national discussions
└── gui/
    ├── __init__.py
    ├── app.py                   # Main application class
    ├── weather_app.py           # Main application window/frame
    ├── ui_manager.py            # Manages UI elements and updates
    ├── dialogs.py               # Dialog windows
    ├── handlers/                # Event handlers
    │   ├── __init__.py
    │   ├── location_handlers.py # Location-related handlers
    │   ├── discussion_handlers.py # Discussion-related handlers
    │   └── system_handlers.py   # System-related handlers
    └── async_fetchers.py        # Handles background data fetching
```

The application can be run either as a command-line tool (`cli.py`) or a graphical application (`gui/`). The `main.py` script serves as the entry point, directing execution based on arguments. Core logic like API interaction (`api_client.py`) and notifications (`notifications.py`) are shared. The GUI components are organized within the `gui` package.

## Module Descriptions

### API Client (`api_client.py`)

Responsible for all interactions with the NOAA Weather API, including:
- Retrieving point metadata
- Fetching forecasts
- Getting active alerts
- Accessing forecast discussions

### Notifications (`notifications.py`)

Handles processing and displaying weather alerts:
- Processes alert data from the API
- Displays desktop notifications (platform-dependent)
- Sorts alerts by priority
- Manages active alert state

### Constants (`constants.py`)

Defines shared constants, configurations (like API endpoints or default settings), and potentially enum types used across the application to ensure consistency and ease of modification.

### Main Entry Point (`main.py`)

The primary script to launch the application. It parses command-line arguments to determine whether to start the graphical user interface or the command-line interface.

### Command-Line Interface (`cli.py`)

Provides a text-based interface for accessing weather information. It utilizes the `api_client` and other core modules to fetch and display data in the terminal.

### GUI Package (`gui/`)

Contains all modules related to the graphical user interface.

#### Main Application Frame (`gui/weather_app.py`)

Implements the main graphical user interface window (e.g., using wxPython). This class sets up the overall structure of the application window and hosts the various UI panels and controls.

#### UI Manager (`gui/ui_manager.py`)

Responsible for creating, arranging, updating, and managing the state of the various UI components (like forecast displays, alert lists, input fields) within the `WeatherApp` frame. It acts as a coordinator between the data fetching logic and the UI presentation.

#### Async Fetchers (`gui/async_fetchers.py`)

Provides functions to perform potentially long-running operations, primarily network requests to the NOAA API, asynchronously. This prevents the GUI from freezing while waiting for data and ensures a responsive user experience. It typically uses background threads or asynchronous programming techniques.

### Location Management (`location.py`)

Manages saved locations and their coordinates:
- Stores and retrieves location data
- Handles the special Nationwide location
- Provides methods for adding, removing, and updating locations

### National Forecast Fetcher (`national_forecast_fetcher.py`)

Fetches national forecast data asynchronously:
- Retrieves data from various NOAA/NWS centers
- Handles threading and cancellation
- Processes national forecast discussions

### Thread Manager (`utils/thread_manager.py`)

Centralized utility for managing background threads:
- Registers and tracks all background threads
- Provides methods to stop threads gracefully
- Ensures clean application shutdown
- Replaces the previous ExitHandler utility

### National Discussion Scraper (`services/national_discussion_scraper.py`)

Scrapes and processes national forecast discussions:
- Fetches discussions from WPC and SPC websites
- Extracts and formats discussion text
- Implements rate limiting to avoid overloading NOAA servers
- Provides both summary and full discussion text

### Location Service (`services/location_service.py`)

Provides higher-level location management functionality:
- Interfaces with the LocationManager
- Handles the Nationwide location visibility setting
- Provides location validation and geocoding

### Weather Service (`services/weather_service.py`)

Coordinates weather data retrieval:
- Interfaces with the NoaaApiClient
- Manages caching of weather data
- Handles error conditions and retries
- Provides access to national forecast data

### Event Handlers (`gui/handlers/`)

Organized event handlers for the GUI:
- `location_handlers.py`: Handles location-related events
- `discussion_handlers.py`: Handles forecast discussion events, including nationwide discussions
- `system_handlers.py`: Handles system events like application close

## Development Workflow

### Test-Driven Development

This project follows test-driven development (TDD) practices:

1. Write a test that defines expected behavior
2. Run the test and verify it fails
3. Write the minimum code necessary to make the test pass
4. Refactor code while ensuring tests still pass
5. Repeat for each new feature

### Running Tests

Use pytest directly:

```
python -m pytest tests/
```

### Git Workflow

1. Create a feature branch: `git checkout -b feature/new-feature`
2. Implement tests and code following TDD
3. Commit changes when tests pass
4. Create a pull request for review

## Accessibility Guidelines

When developing the UI, follow these accessibility guidelines:

1. All UI elements must have proper labels and descriptions accessible to assistive technologies.
2. Ensure full keyboard navigation works for all interactive elements and features.
3. Implement proper focus management, indicating the currently focused element clearly.
4. Use high-contrast color schemes suitable for users with visual impairments.
5. Test with screen readers (e.g., NVDA, JAWS, VoiceOver) to ensure usability.

## Key Features

### Nationwide View

The Nationwide view provides a comprehensive overview of the national weather situation:

- Implementation details:
  - Special "Nationwide" location that cannot be removed
  - Fetches data from multiple NOAA/NWS centers (WPC, SPC, NHC, CPC)
  - Displays national forecast discussions in a tabbed interface
  - Can be hidden/shown via settings
  - Uses web scraping to retrieve discussion text from NOAA websites

- Components involved:
  - `location.py`: Defines the Nationwide location constants and special handling
  - `national_forecast_fetcher.py`: Fetches national forecast data asynchronously
  - `services/national_discussion_scraper.py`: Scrapes national discussions from NOAA websites
  - `gui/dialogs.py`: Contains the `NationalDiscussionDialog` for displaying discussions
  - `gui/handlers/discussion_handlers.py`: Handles viewing nationwide discussions

### Thread Management

The application uses a centralized thread management system:

- The `ThreadManager` utility (in `utils/thread_manager.py`) replaces the previous `ExitHandler`
- All background threads register with the ThreadManager
- The ThreadManager provides methods to stop threads gracefully
- The application's exit process uses ThreadManager to ensure clean shutdown
- Each fetcher class registers its threads with the ThreadManager

## Adding New Features

1. Start by adding tests in the appropriate test module (e.g., `tests/test_gui.py`, `tests/test_cli.py`).
2. Implement the feature in the relevant application module(s).
3. Ensure all tests pass before committing.
4. Update documentation (like this guide) to reflect the new feature or changes.

## Code Style

This project follows PEP 8 guidelines for Python code style. Key points:

- Use 4 spaces for indentation
- Aim for a maximum line length of ~88-100 characters (aligned with tools like Black/Ruff).
- Add docstrings to all public modules, classes, and functions.
- Use type hints for function parameters and return values.
