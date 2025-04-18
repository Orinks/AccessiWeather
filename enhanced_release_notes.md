# AccessiWeather Beta Release (v0.9.0)

We're excited to announce the beta release of AccessiWeather, an accessible weather application using NOAA data with a focus on screen reader compatibility!

## What's Included in the Beta

This beta release includes all core functionality:

- Complete NOAA weather API integration
- Location management with multiple saved locations
- Search by address or ZIP code
- Manual coordinate entry support
- Detailed weather forecasts with temperature and conditions
- Active weather alerts, watches, and warnings
- Weather discussion reader for in-depth analysis
- Desktop notifications for weather alerts
- Precise location alerts (county/township level)
- Statewide alert toggle
- Accessible UI with screen reader compatibility
- Keyboard navigation support
- Configuration persistence

## Installation Options

### Option 1: Installer (Recommended)

Download and run `AccessiWeather_Setup_v0.9.0.exe` to install the application. This will:
- Install the application to your Program Files directory
- Create start menu shortcuts
- Optionally create a desktop shortcut
- Set up the configuration directory automatically

### Option 2: Portable Version

Download and extract `AccessiWeather_Portable_v0.9.0.zip` to any location and run `AccessiWeather.exe`.

Note: The portable version will store your settings and location data in a `config` folder within the application directory, making it fully portable.

## First-Time Setup

When you first run the application, you'll be prompted to enter your contact information for the NOAA API. This is required by the NOAA API terms of service and helps them contact you if there are issues with your usage.

## Recent Changes

- Added true portable mode support with local configuration storage
- Standardized configuration directory location
- Improved wxPython dialog patching to prevent segmentation faults
- Added precise location alerts functionality
- Added settings dialog, loading feedback, and first-time setup prompt
- Fixed ModuleNotFoundError for logging_config
- Refined mocks and logging patches to clean up test output
- Added service layer, alert system enhancements, and location search fixes

## Known Issues

- The geocoding service may find locations outside the United States that the National Weather Service does not support
- The application has been primarily tested on Windows; Linux support is experimental

## Feedback Requested

We're particularly interested in feedback on:

1. Accessibility with screen readers
2. UI/UX improvements
3. Weather data accuracy and presentation
4. Performance on different systems
5. Installation and setup experience

## Reporting Issues

Please report any issues you encounter on the [GitHub Issues page](https://github.com/Orinks/AccessiWeather/issues).

## What's Next

After the beta testing phase, we plan to:

1. Address feedback and fix reported issues
2. Fix geocoding to filter out unsupported international locations
3. Enhance documentation
4. Release version 1.0.0

Thank you for helping test AccessiWeather!
