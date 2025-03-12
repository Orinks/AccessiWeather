# NOAA Weather App - Developer Guide

## Architecture Overview

The NOAA Weather App follows a modular design with clear separation of concerns:

```
noaa_weather_app/
├── api_client.py   # NOAA API interaction
├── notifications.py # Alert notifications
├── location.py     # Location management
├── gui.py          # Main GUI components
├── accessible_widgets.py # Accessibility-enhanced widgets
├── main.py         # Application entry point
├── cli.py          # Command-line interface
```

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
- Displays desktop notifications
- Sorts alerts by priority
- Manages active alert state

### Location Manager (`location.py`)

Manages user-defined locations:
- Saves and loads locations from disk
- Adds, removes, and updates locations
- Tracks the current selected location

### GUI (`gui.py`)

Implements the main user interface:
- Main application window
- Location management dialogs
- Weather data display
- Alert listing and details
- Forecast discussion viewer

### Accessible Widgets (`accessible_widgets.py`)

Provides enhanced wxPython widgets with accessibility features:
- Screen reader support
- Keyboard navigation
- ARIA roles and properties

## Development Workflow

### Test-Driven Development

This project follows test-driven development (TDD) practices:

1. Write a test that defines expected behavior
2. Run the test and verify it fails
3. Write the minimum code necessary to make the test pass
4. Refactor code while ensuring tests still pass
5. Repeat for each new feature

### Running Tests

Use the `run_tests.py` script to execute all tests:

```
python run_tests.py
```

Or use pytest directly:

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

1. All UI elements must have proper labels and descriptions
2. Ensure keyboard navigation works for all features
3. Implement proper focus management
4. Use high-contrast color schemes
5. Test with screen readers (e.g., NVDA, JAWS)

## Adding New Features

1. Start by adding tests in the appropriate test module
2. Implement the feature in the relevant application module
3. Ensure all tests pass before committing
4. Update documentation to reflect the new feature

## Code Style

This project follows PEP 8 guidelines for Python code style. Key points:

- Use 4 spaces for indentation
- Maximum line length of 79 characters
- Add docstrings to all modules, classes, and functions
- Use type hints for function parameters and return values
