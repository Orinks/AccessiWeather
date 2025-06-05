# AccessiWeather - User Manual

## Overview

AccessiWeather is a desktop weather application that provides comprehensive weather information with robust accessibility features and international weather support. Built using wxPython with a focus on screen reader compatibility and keyboard navigation, AccessiWeather offers weather data from multiple sources including the National Weather Service (NWS) and Open-Meteo.

## Installation

AccessiWeather offers multiple installation options to suit different user needs:

### Option 1: Download Pre-built Installer (Recommended)
1. Visit the [AccessiWeather releases page](https://github.com/Orinks/AccessiWeather/releases)
2. Download the latest Windows installer (.exe file)
3. Run the installer and follow the setup wizard
4. Launch AccessiWeather from the Start Menu or desktop shortcut

### Option 2: Portable Version
1. Download the portable version from the releases page
2. Extract the ZIP file to your desired location
3. Run `accessiweather.exe` directly from the extracted folder
4. Configuration files will be saved in the same folder as the application

### Option 3: Install from Source
1. Ensure you have Python 3.8 or higher installed
2. Clone the repository or download the source code:
   ```bash
   git clone https://github.com/Orinks/AccessiWeather.git
   cd AccessiWeather
   ```
3. Install the application:
   ```bash
   pip install -e .
   ```
4. Run the application:
   ```bash
   accessiweather
   ```

### Option 4: Force Portable Mode
If you want to run AccessiWeather in portable mode (saving configuration to the application directory), use:
```bash
accessiweather --portable
```

## First-Time Setup

When you first run AccessiWeather:

1. **Initial Configuration**: The application will create a configuration directory and start with the Nationwide location pre-loaded
2. **Add Your Location**: Click "Add Location" to add your local weather location
3. **Configure Settings**: Access Settings to customize weather data sources, update intervals, and display preferences
4. **System Tray Setup**: If desired, enable "Minimize to Tray" in Advanced settings for background operation

## Core Features

### Weather Data Sources

AccessiWeather supports multiple weather data providers:

- **National Weather Service (NWS)**: Provides weather data for US locations with full alert support
- **Open-Meteo**: Free international weather service covering worldwide locations (no alerts)
- **Automatic Selection**: Intelligently uses NWS for US locations and Open-Meteo for international locations (recommended)

You can change your preferred data source in Settings → General → Weather Data Source.

### Location Management

AccessiWeather allows you to manage multiple weather locations:

#### Adding Locations
1. **Simple Search**: Click "Add Location" and search by city name or ZIP code
2. **Advanced Entry**: Use "Advanced (Lat/Lon)" for precise coordinates
3. **International Locations**: Supported through Open-Meteo integration

#### Managing Locations
- **Switch Locations**: Use the dropdown menu to select different saved locations
- **Remove Locations**: Select a location and click "Remove Location"
- **Nationwide View**: Special location providing national weather overview (US only)

#### Nationwide Location
The Nationwide location provides:
- National weather discussions from Weather Prediction Center (WPC)
- Storm Prediction Center (SPC) discussions
- Comprehensive overview of US weather patterns
- Cannot be removed but can be hidden in settings

### Weather Information Display

AccessiWeather presents comprehensive weather data:

#### Current Conditions
- Real-time temperature and weather conditions
- Humidity, wind speed, and atmospheric pressure
- "Feels like" temperature and visibility

#### Forecasts
- **Detailed Forecasts**: Multi-day weather predictions with descriptions
- **Hourly Forecasts**: Hour-by-hour weather data for precise planning
- **Extended Outlook**: Long-range weather trends

#### Weather Alerts
- **Real-time Alerts**: Watches, warnings, and advisories
- **Severity Levels**: Extreme, Severe, Moderate, and Minor classifications
- **Geographic Targeting**: Precise location or state-wide alert options
- **Alert Details**: Click any alert for comprehensive information

#### Weather Discussions
- **Local Discussions**: Detailed meteorological analysis for your area
- **National Discussions**: WPC and SPC professional weather analysis
- **Technical Insights**: In-depth weather pattern explanations

### Notifications and Alerts

AccessiWeather provides intelligent alert management:

#### Desktop Notifications
- Automatic notifications for new weather alerts
- Severity-based prioritization
- Non-intrusive notification system
- Customizable alert radius (5-100 miles)

#### Alert Configuration
- **Precise Location Alerts**: County/township-level targeting
- **State-wide Alerts**: Broader geographic coverage
- **Alert Radius**: Customizable distance for alert monitoring
- **Alert Types**: Watches, warnings, advisories, and statements

### System Tray and Taskbar Customization

AccessiWeather offers advanced system tray integration:

#### System Tray Features
- **Minimize to Tray**: Hide the application to the system tray instead of closing
- **Taskbar Icon**: Persistent system tray icon for quick access
- **Context Menu**: Right-click the tray icon for quick actions
- **Keyboard Accessibility**: Full keyboard support for tray icon interaction

#### Taskbar Icon Customization
AccessiWeather's standout feature is dynamic taskbar icon text customization:

- **Custom Text Display**: Show weather information directly in the taskbar
- **Format Strings**: Use variables like `{temp}`, `{condition}`, `{humidity}`
- **Real-time Updates**: Taskbar text updates automatically with weather data
- **Examples**:
  - `{temp}°F {condition}` → "72°F Sunny"
  - `{temp}° {humidity}%` → "72° 45%"
  - `{location}: {temp}°` → "New York: 72°"

#### System Tray Keyboard Shortcuts
- **Enter**: Focus application or show context menu
- **Applications Key**: Show context menu (screen reader compatible)
- **Shift+F10**: Alternative context menu access
- **Escape**: Hide application to tray (when minimize to tray is enabled)

## Settings Configuration

AccessiWeather provides extensive customization through a three-tab settings dialog:

### General Tab

#### Weather Data Source
- **National Weather Service**: US locations only, includes weather alerts
- **Open-Meteo**: International locations, free service, no alerts
- **Automatic**: Best of both - NWS for US, Open-Meteo for international (recommended)

#### Update and Alert Settings
- **Update Interval**: How often to refresh weather data (1-1440 minutes)
- **Alert Radius**: Distance for monitoring weather alerts (5-100 miles)
- **Precise Location Alerts**: County/township level vs. state-wide alerts
- **Show Nationwide Location**: Display or hide the Nationwide weather view
- **Auto-refresh National**: Automatically update national discussions

### Display Tab

#### Measurement Units
- **Imperial**: Fahrenheit temperatures, miles, inches
- **Metric**: Celsius temperatures, kilometers, millimeters
- **Both**: Display both imperial and metric values

#### Taskbar Icon Customization
- **Enable Taskbar Text**: Show weather information in the taskbar icon
- **Custom Format String**: Define what information to display
- **Available Variables**:
  - `{temp}` - Current temperature
  - `{condition}` - Weather condition (e.g., "Sunny", "Cloudy")
  - `{humidity}` - Humidity percentage
  - `{location}` - Location name
  - `{wind_speed}` - Wind speed
  - `{pressure}` - Atmospheric pressure

### Advanced Tab

#### System Behavior
- **Minimize to Tray**: Hide to system tray instead of closing when X is clicked
- **Cache Settings**: Enable/disable API response caching
- **Cache TTL**: How long to cache weather data (60-3600 seconds)

## Accessibility Features

AccessiWeather is designed with comprehensive accessibility support:

### Screen Reader Compatibility
- **Full NVDA Support**: Tested extensively with NVDA screen reader
- **JAWS Compatibility**: Works with JAWS screen reader
- **Accessible Labels**: All UI elements have proper screen reader labels
- **Role Definitions**: Proper ARIA roles for complex interface elements

### Keyboard Navigation
- **Complete Keyboard Access**: Every feature accessible via keyboard
- **Logical Tab Order**: Intuitive navigation flow through interface
- **Focus Indicators**: Clear visual focus indicators for sighted users
- **Keyboard Shortcuts**: Comprehensive shortcut system

### Accessible UI Components
- **Custom Accessible Controls**: Enhanced wxPython controls with better screen reader support
- **Proper Event Handling**: Keyboard events properly handled for accessibility
- **Character Navigation**: Support for character-by-character text navigation
- **Context Menus**: Accessible via keyboard shortcuts

## Keyboard Shortcuts

### Global Shortcuts
- **F5**: Refresh weather data
- **Ctrl+S**: Open settings dialog
- **Escape**: Minimize to system tray (when enabled)
- **Alt+F4**: Exit application

### Navigation Shortcuts
- **Tab / Shift+Tab**: Navigate between UI elements
- **Arrow Keys**: Navigate lists, dropdowns, and text
- **Enter / Space**: Activate buttons and controls
- **Alt+Down**: Open dropdown menus

### System Tray Shortcuts
- **Enter**: Focus application or show context menu
- **Applications Key**: Show context menu
- **Shift+F10**: Alternative context menu access

### List and Text Navigation
- **Home / End**: Move to beginning/end of lists or text
- **Page Up / Page Down**: Scroll through long content
- **Ctrl+A**: Select all text in text controls

## Usage Tips and Best Practices

### Getting Started
1. **Start with Automatic Data Source**: The automatic weather source selection provides the best experience
2. **Add Local Location First**: Add your primary location before exploring other features
3. **Configure Alerts**: Set appropriate alert radius and precision for your needs
4. **Enable System Tray**: Use minimize to tray for convenient background operation

### Optimizing Performance
- **Reasonable Update Intervals**: Use 10-15 minute intervals for active monitoring, longer for background use
- **Enable Caching**: Keep API caching enabled to reduce network requests
- **Manage Locations**: Remove unused locations to improve performance

### Accessibility Best Practices
- **Use Keyboard Navigation**: Take advantage of comprehensive keyboard shortcuts
- **Configure Screen Reader**: Ensure your screen reader is properly configured for wxPython applications
- **Adjust Update Intervals**: Longer intervals reduce interruptions from automatic updates

## Portable Mode

AccessiWeather supports portable operation for users who need to run the application from removable media or without installation:

### Automatic Portable Detection
AccessiWeather automatically detects portable mode when:
- Running from a location outside Program Files
- The application directory is writable
- No standard installation is detected

### Manual Portable Mode
Force portable mode using the command line:
```bash
accessiweather --portable
```

### Portable Mode Features
- **Self-contained**: All configuration files stored in application directory
- **No Registry Changes**: No system modifications required
- **Removable Media**: Run from USB drives or network locations
- **Multiple Instances**: Different portable installations can have separate configurations

## Troubleshooting

### Installation Issues

#### Windows Installation Problems
- **Installer Won't Run**: Right-click installer and select "Run as Administrator"
- **Antivirus Blocking**: Temporarily disable antivirus or add exception for AccessiWeather
- **Missing Dependencies**: Ensure Windows is up to date with latest Visual C++ redistributables

#### Portable Version Issues
- **Won't Start**: Ensure the folder has write permissions
- **Configuration Lost**: Check that the application directory is writable
- **Multiple Instances**: Each portable installation maintains separate settings

### Weather Data Issues

#### No Weather Data Displayed
1. **Check Internet Connection**: Ensure stable internet connectivity
2. **Verify Location**: Confirm location coordinates are correct
3. **Try Different Data Source**: Switch between NWS, Open-Meteo, or Automatic
4. **Check API Status**: Weather services may experience temporary outages

#### Inaccurate Weather Information
- **Location Precision**: Use more precise coordinates for better accuracy
- **Data Source Selection**: NWS provides more accurate data for US locations
- **Update Frequency**: Increase update frequency for more current data

#### Missing Weather Alerts
- **US Locations Only**: Weather alerts are only available for US locations via NWS
- **Alert Radius**: Increase alert radius to capture more distant alerts
- **Precise vs. State-wide**: Try switching between precise and state-wide alert modes

### System Tray Issues

#### Tray Icon Not Appearing
- **Windows Settings**: Check Windows notification area settings
- **Restart Application**: Close and restart AccessiWeather
- **System Tray Overflow**: Check the hidden icons area in the system tray

#### Taskbar Text Not Updating
- **Enable Feature**: Ensure taskbar text is enabled in Display settings
- **Format String**: Verify the format string syntax is correct
- **Data Availability**: Some variables may not be available for all locations

### Performance Issues

#### Slow Application Response
- **Reduce Update Frequency**: Increase update interval to reduce API calls
- **Disable Caching**: Try disabling cache if experiencing issues
- **Close Other Applications**: Free up system resources

#### High Memory Usage
- **Restart Application**: Restart AccessiWeather periodically
- **Reduce Locations**: Remove unused weather locations
- **Update Application**: Ensure you're running the latest version

### Accessibility Issues

#### Screen Reader Problems
- **Update Screen Reader**: Ensure your screen reader software is current
- **wxPython Compatibility**: Some screen readers may need specific wxPython configurations
- **Alternative Navigation**: Use keyboard shortcuts if mouse navigation isn't working

#### Keyboard Navigation Issues
- **Focus Problems**: Use Tab key to restore proper focus
- **Stuck Focus**: Press Escape to reset focus to main window
- **Menu Access**: Use Alt key to access menu bar

### Configuration Issues

#### Settings Not Saving
- **File Permissions**: Ensure configuration directory is writable
- **Portable Mode**: Check if running in portable mode affects save location
- **Disk Space**: Verify sufficient disk space for configuration files

#### Lost Configuration
- **Backup Settings**: Regularly backup your configuration directory
- **Default Settings**: Reset to defaults if configuration becomes corrupted
- **Multiple Installations**: Ensure you're running the correct installation

### Getting Help

#### Log Files
Log files are stored in:
- **Standard Installation**: `%APPDATA%\.accessiweather\logs\`
- **Portable Mode**: `[Application Directory]\.accessiweather\logs\`

#### Debug Mode
Run AccessiWeather with debug mode for detailed logging:
```bash
accessiweather --debug
```

#### Reporting Issues
When reporting issues, please include:
- AccessiWeather version number
- Operating system version
- Steps to reproduce the problem
- Relevant log file entries
- Screenshots (if applicable)

## Support and Community

### Getting Support
- **GitHub Issues**: Report bugs and request features at [GitHub Issues](https://github.com/Orinks/AccessiWeather/issues)
- **Documentation**: Check this manual and other documentation in the `docs/` folder
- **Community**: Engage with other users through GitHub discussions

### Contributing
AccessiWeather is open source and welcomes contributions:
- **Bug Reports**: Help improve the application by reporting issues
- **Feature Requests**: Suggest new features and improvements
- **Code Contributions**: Submit pull requests for bug fixes and enhancements
- **Documentation**: Help improve documentation and user guides

### Version Information
To check your AccessiWeather version:
1. Open AccessiWeather
2. Go to Help → About
3. Version information is displayed in the About dialog

For the latest version and release notes, visit the [GitHub releases page](https://github.com/Orinks/AccessiWeather/releases).
