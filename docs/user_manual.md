# NOAA Weather App - User Manual

## Overview

The NOAA Weather App is a desktop application that provides weather information from the National Oceanic and Atmospheric Administration (NOAA). It features real-time weather alerts, forecast data, and detailed weather discussions with full accessibility support for screen readers.

## Installation

### Prerequisites
- Python 3.7 or higher
- Internet connection for accessing NOAA weather data

### Installing from Source
1. Clone the repository or download the source code
2. Navigate to the project directory
3. Install the application:
   ```
   pip install -e .
   ```

## Features

### Location Management

The application allows you to save multiple locations to check weather conditions:

- **Adding a Location**: Click the "Add Location" button and provide a name, latitude, and longitude.
- **Removing a Location**: Select a location from the dropdown and click "Remove Location".
- **Switching Locations**: Select a different location from the dropdown to view its weather data.
- **Nationwide View**: A special "Nationwide" location is available that provides national weather information and discussions from various NOAA/NWS centers. This location cannot be removed but can be hidden in settings.

### Weather Data

The application displays the following weather information:

- **Forecast**: View current and upcoming weather forecasts for your selected location.
- **Weather Alerts**: See active alerts, watches, and warnings for your location.
- **Forecast Discussion**: Read detailed weather discussions from meteorologists by clicking the "View Forecast Discussion" button.
- **National Forecast Discussions**: When the Nationwide location is selected, you can view discussions from the Weather Prediction Center (WPC) and Storm Prediction Center (SPC) by clicking the "View Forecast Discussion" button. These discussions provide a comprehensive overview of the national weather situation.

### Notifications

The application will automatically notify you of important weather alerts:

- Desktop notifications appear for new alerts, watches, and warnings.
- Alerts are prioritized by severity (Extreme, Severe, Moderate, Minor).
- Click on an alert in the list to view detailed information.

## Accessibility Features

The NOAA Weather App is fully accessible with screen readers:

- All UI elements have appropriate screen reader labels and descriptions.
- Keyboard navigation is fully supported throughout the application.
- Weather alerts and discussions can be read aloud by screen readers.

## Settings

You can customize the application behavior through the Settings dialog:

- **Update Interval**: Set how often the application refreshes weather data (in minutes).
- **Alert Radius**: Set the radius around your location to receive alerts for (in miles).
- **Precise Location Alerts**: Enable/disable precise location alerts (county/township level).
- **Show Nationwide**: Show or hide the Nationwide location in the locations dropdown.

To access settings, click the "Settings" button in the main application window.

## Keyboard Shortcuts

- **F5**: Refresh weather data
- **Tab**: Navigate between UI elements
- **Enter/Space**: Activate buttons and controls

## Troubleshooting

### Common Issues

- **No Weather Data**: Ensure you have an active internet connection and have added at least one location.
- **Location Not Found**: Verify that the latitude and longitude coordinates are correct.
- **No Alerts Displayed**: There may not be any active alerts for your location.
- **National Discussions Unavailable**: The national discussions may be temporarily unavailable due to NOAA server maintenance. Try again later.
- **Nationwide Location Missing**: If you don't see the Nationwide location in the dropdown, check your settings to ensure it's not hidden.

### Log Files

Log files are stored in the `~/.noaa_weather_app/` directory. These can be helpful for diagnosing issues.

## Support

If you encounter any issues or have questions about the application, please submit an issue on our GitHub repository.
