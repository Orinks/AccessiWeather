# AccessiWeather Beta Release (v0.9.0)

Thank you for trying the AccessiWeather beta release! This package contains both an installer and a portable version of the application.

## Installation Options

### Option 1: Installer (Recommended)

Run `AccessiWeather_Setup_v0.9.0.exe` to install the application. This will:
- Install the application to your Program Files directory
- Create start menu shortcuts
- Optionally create a desktop shortcut
- Set up the configuration directory automatically

### Option 2: Portable Version

Extract `AccessiWeather_Portable_v0.9.0.zip` to any location and run `AccessiWeather.exe`.

Note: The portable version will still create a configuration directory at `%USERPROFILE%\.accessiweather` to store your settings and location data.

## First-Time Setup

When you first run the application, you'll be prompted to enter your contact information for the NOAA API. This is required by the NOAA API terms of service and helps them contact you if there are issues with your usage.

## Known Issues

- The geocoding service may find locations outside the United States that the National Weather Service does not support
- The application has been primarily tested on Windows; Linux support is experimental

## Feedback and Issues

Please report any issues or feedback on our GitHub repository:
https://github.com/Orinks/AccessiWeather/issues

See the included `BETA_RELEASE.md` file for more information about this beta release.

## Documentation

- `README.md` - General information about the application
- `INSTALL.md` - Detailed installation instructions
- `BETA_RELEASE.md` - Information specific to this beta release
