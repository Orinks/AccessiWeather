# NOAA Weather App - Developer Guide

## Architecture Overview

The AccessiWeather App follows a modular design with clear separation of concerns:

```
accessiweather/
├── api_client.py      # NOAA API interaction
├── notifications.py   # Alert notifications
├── constants.py       # Shared constants and configurations
├── main.py            # Application entry point (starts GUI or CLI)
├── cli.py             # Command-line interface logic
└── gui/
    ├── __init__.py
    ├── weather_app.py   # Main application window/frame
    ├── ui_manager.py    # Manages UI elements and updates
    └── async_fetchers.py # Handles background data fetching
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
