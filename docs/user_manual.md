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

You can change your preferred data source in Settings → Data Sources → Weather Data Source.

### Weather Models

When using Open-Meteo or Automatic mode, you can choose which weather forecast model to use. Weather models are sophisticated computer simulations that meteorological agencies run to predict future weather conditions. Different models have different strengths depending on your location and what you need.

#### What is a Weather Model?

A weather model (also called a numerical weather prediction model) is a computer program that uses mathematical equations to simulate the atmosphere. These models take current observations from weather stations, satellites, and weather balloons, then calculate how the atmosphere will evolve over time.

Different meteorological agencies around the world run their own models, each with unique characteristics:
- **Resolution**: How detailed the predictions are (smaller grid = more local detail)
- **Coverage**: Geographic area the model covers well
- **Update Frequency**: How often the model runs with fresh data
- **Forecast Length**: How far into the future predictions extend

#### Available Models

| Model | Provider | Best For | Resolution |
|-------|----------|----------|------------|
| **Best Match (Automatic)** | Open-Meteo | General use - automatically picks the best model for your location | Varies |
| **ICON Seamless** | DWD (Germany) | Europe and global forecasts with smooth blending between resolutions | 2-13 km |
| **ICON Global** | DWD (Germany) | Worldwide coverage, good baseline accuracy | 13 km |
| **ICON EU** | DWD (Germany) | European locations - higher detail for Europe | 6.5 km |
| **ICON D2** | DWD (Germany) | Germany and nearby regions - very high detail | 2 km |
| **GFS Seamless** | NOAA (USA) | Americas and global, good for North America | 3-28 km |
| **GFS Global** | NOAA (USA) | Worldwide coverage, reliable US government model | 28 km |
| **ECMWF IFS** | ECMWF (Europe) | Highest accuracy worldwide, considered the gold standard | 9 km |
| **Météo-France** | Météo-France | France and Europe - excellent for Western Europe | Varies |
| **GEM** | Canada | North America, especially Canada | Varies |
| **JMA** | Japan | Japan and East Asia | Varies |

#### Choosing the Right Model

**For most users**: Start with "Best Match (Automatic)" - Open-Meteo will intelligently select the best model for your location.

**For specific needs**:
- **US locations**: GFS Seamless or Best Match work well
- **European locations**: ICON Seamless, ICON EU, or ECMWF IFS
- **Germany**: ICON D2 for maximum local detail
- **Canada**: GEM for optimized Canadian forecasts
- **Japan/East Asia**: JMA for regional expertise
- **Maximum accuracy**: ECMWF IFS is widely considered the most accurate global model

#### Tips for Model Selection

1. **Try different models**: Weather models can have different biases for your specific location. If one model consistently over- or under-predicts, try another.

2. **Consider your use case**:
   - For general daily planning, Best Match is usually sufficient
   - For outdoor activities or events, try a higher-resolution regional model
   - For travel planning, stick with global models like GFS or ECMWF

3. **Regional models are limited**: High-resolution regional models (like ICON D2) only cover specific areas. If you select one for a location outside its coverage, forecasts may be less accurate.

4. **Model updates vary**: Some models update every hour, others every 6 hours. More frequent updates mean fresher predictions but don't necessarily mean better accuracy.

To change your weather model: Settings → Data Sources → Open-Meteo Weather Model

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

### Environmental Information Dialogs

AccessiWeather provides specialized dialogs for detailed environmental data:

#### UV Index Dialog

Access comprehensive UV index information through View → UV Index in the menu bar.

**What You'll See:**
- **Current UV Index**: Real-time UV index value with EPA/WHO category rating
- **Health Guidance**: Context-specific health recommendations based on current UV level
- **Hourly Forecast**: 24-hour UV index forecast with trend analysis
- **Peak Times**: Identifies when UV levels are highest for activity planning
- **Sun Safety Recommendations**: Detailed protection guidance including:
  - Sunscreen SPF recommendations and reapplication schedule
  - Protective clothing suggestions (hats, sunglasses, long sleeves)
  - Shade-seeking guidance and timing recommendations
  - Safe outdoor activity windows

**UV Index Categories:**
- **Low (0-2)**: No protection needed for most people
- **Moderate (3-5)**: Take precautions - wear sunscreen and hat
- **High (6-7)**: Protection essential - use SPF 30+, protective clothing
- **Very High (8-10)**: Extra protection required - SPF 50+, minimize midday exposure
- **Extreme (11+)**: Take all precautions - avoid sun exposure 10 AM to 4 PM

**When to Check UV Index:**
- Planning outdoor activities or sports
- Before spending extended time outside
- When traveling to locations with different sun exposure
- For managing sun-sensitive health conditions
- During summer months or at high elevations

**Accessibility Features:**
- Full screen reader compatibility with descriptive labels
- Keyboard navigation support
- Clear section headers for easy scanning
- Detailed ARIA descriptions for all information panels

**Note:** UV index data availability depends on your weather data source. Open-Meteo provides comprehensive UV index data for both US and international locations, including hourly forecasts.

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
AccessiWeather's standout feature is intelligent taskbar icon text customization with dynamic format switching:

- **Dynamic Format Switching**: Automatically changes display format based on weather conditions
- **Custom Text Display**: Show weather information directly in the taskbar
- **Format Strings**: Use variables like `{temp}`, `{condition}`, `{location}`, `{humidity}`
- **Real-time Updates**: Taskbar text updates automatically with weather data
- **Weather-Aware Display**: Different formats for normal, severe, and extreme conditions

#### Dynamic Format Examples
When dynamic switching is enabled, the taskbar automatically shows contextually relevant information:

- **Normal conditions**: `"San Francisco, CA 72°F Clear • 55%"`
- **Severe weather**: `"🌩️ New York, NY Thunderstorms 68°F • NW 25.0 mph"`
- **Temperature extremes**: `"🌡️ Phoenix, AZ 105°F (feels 115°F) • Sunny"`
- **High winds**: `"💨 Chicago, IL NW 35.0 mph • Partly Cloudy 45°F"`
- **Precipitation expected**: `"🌧️ Seattle, WA Cloudy 58°F • 80% chance"`
- **Low visibility**: `"🌫️ San Francisco, CA Fog 55°F • Visibility 0.5 mi"`

#### System Tray Keyboard Shortcuts
- **Enter**: Focus application or show context menu
- **Applications Key**: Show context menu (screen reader compatible)
- **Shift+F10**: Alternative context menu access
- **Escape**: Hide application to tray (when minimize to tray is enabled)

## Settings Configuration

AccessiWeather provides extensive customization through a five-tab settings dialog:

### General Tab
Core application settings:
- **Temperature Units**: Imperial, Metric, or Both
- **Update Interval**: How often to refresh weather data (1-1440 minutes)
- **Detailed Forecast**: Enable/disable detailed forecast information
- **Alert Settings**: Configure weather alert preferences

### Data Sources Tab
Weather API configuration:
- **Weather Data Source**:
  - **National Weather Service**: US locations only, includes weather alerts
  - **Open-Meteo**: International locations, free service, no alerts
  - **Automatic**: Best of both - NWS for US, Open-Meteo for international (recommended)
- **Open-Meteo Weather Model**: Choose which forecast model to use (see [Weather Models](#weather-models) below)
- **Visual Crossing API**: Setup and configuration for Visual Crossing weather service

### Audio Tab
Sound notification settings:
- **Sound Enabled**: Enable/disable sound notifications
- **Sound Pack Selection**: Choose from available sound packs
- **Manage Sound Packs**: Add, remove, or configure sound packs

### Updates Tab
Update configuration:
- **Auto-update**: Enable automatic update checking
- **Channel Selection**: Choose Stable, Beta, or Development releases
- **Check Interval**: How often to check for updates
- **Manual Check**: Check for updates immediately

### Advanced Tab
Power user settings:
- **Minimize to Tray**: Hide to system tray instead of closing
- **Debug Mode**: Enable detailed logging for troubleshooting

#### Taskbar Icon Customization
- **Enable Taskbar Text**: Show weather information in the taskbar icon
- **Dynamic Format Switching**: Automatically adapt display format based on weather conditions
- **Custom Format String**: Define what information to display (used as default/fallback when dynamic switching is enabled)

#### Dynamic Format Switching
When enabled, AccessiWeather intelligently selects the most appropriate format based on current conditions:

- **Automatic Context Switching**: Changes format based on weather severity and type
- **Visual Weather Indicators**: Uses emojis (🌩️, 🌡️, 💨, 🌧️, 🌫️) to quickly identify conditions
- **Relevant Information Priority**: Shows the most important data for each weather scenario
- **Fallback Protection**: Uses your custom format if dynamic switching encounters issues

#### Available Format Variables
All variables respect your temperature unit preference (Imperial/Metric/Both):

- `{temp}` - Current temperature (formatted with units)
- `{temp_f}` - Temperature in Fahrenheit only
- `{temp_c}` - Temperature in Celsius only
- `{condition}` - Weather condition (e.g., "Sunny", "Partly Cloudy")
- `{location}` - Location name
- `{humidity}` - Humidity percentage (number only, % symbol added by template)
- `{wind_speed}` - Wind speed (formatted with units)
- `{wind_dir}` - Wind direction (e.g., "NW", "SE")
- `{feels_like}` - Feels-like temperature (formatted with units)
- `{pressure}` - Atmospheric pressure (formatted with units)
- `{visibility}` - Visibility distance (formatted with units)
- `{precip}` - Precipitation amount (formatted with units)
- `{precip_chance}` - Chance of precipitation (number only, % symbol added by template)
- `{uv}` - UV index
- `{high}` - Today's high temperature (formatted with units)
- `{low}` - Today's low temperature (formatted with units)

#### Custom Format Examples
- `{location} {temp} {condition}` → "New York, NY 72°F Sunny"
- `{temp} • {humidity}% humidity` → "72°F • 45% humidity"
- `{location}: {temp} (feels {feels_like})` → "Phoenix: 95°F (feels 105°F)"
- `{condition} {temp} • {wind_dir} {wind_speed}` → "Partly Cloudy 68°F • NW 12.0 mph"

### Advanced Tab

#### System Behavior
- **Minimize to Tray**: Hide to system tray instead of closing when X is clicked
- **Cache Settings**: Enable/disable API response caching
- **Cache TTL**: How long to cache weather data (60-3600 seconds)

## Understanding Dynamic Format Switching

Dynamic format switching is AccessiWeather's intelligent feature that automatically adapts the taskbar display based on current weather conditions. This ensures you always see the most relevant information at a glance.

### How Dynamic Switching Works

The system analyzes current weather data and selects the most appropriate format template:

1. **Weather Condition Analysis**: Evaluates temperature, wind speed, precipitation, visibility, and alerts
2. **Priority Assessment**: Determines which weather factors are most important to display
3. **Format Selection**: Chooses the best template for the current conditions
4. **Automatic Updates**: Switches formats as weather conditions change throughout the day

### Dynamic Format Types

#### Default Format
**Used for**: Normal, pleasant weather conditions
**Shows**: Location, temperature, condition, and humidity
**Example**: `"San Francisco, CA 75°F Partly Cloudy • 68%"`

#### Severe Weather Format
**Used for**: Thunderstorms, severe weather warnings
**Shows**: Storm emoji, location, condition, temperature, and wind information
**Example**: `"🌩️ Miami, FL Thunderstorms 82°F • SW 28.0 mph"`

#### Temperature Extreme Format
**Used for**: Very hot or very cold conditions (based on feels-like temperature)
**Shows**: Temperature emoji, location, actual and feels-like temperatures
**Example**: `"🌡️ Phoenix, AZ 108°F (feels 118°F) • Sunny"`

#### Wind Warning Format
**Used for**: High wind conditions
**Shows**: Wind emoji, location, wind details, condition, and temperature
**Example**: `"💨 Chicago, IL NW 42.0 mph • Clear 38°F"`

#### Precipitation Format
**Used for**: When rain, snow, or other precipitation is likely
**Shows**: Rain emoji, location, condition, temperature, and precipitation chance
**Example**: `"🌧️ Seattle, WA Overcast 52°F • 85% chance"`

#### Fog/Low Visibility Format
**Used for**: Foggy conditions or low visibility
**Shows**: Fog emoji, location, condition, temperature, and visibility distance
**Example**: `"🌫️ San Francisco, CA Fog 58°F • Visibility 0.3 mi"`

#### Alert Format
**Used for**: Active weather alerts and warnings
**Shows**: Warning emoji, location, alert type, and severity
**Example**: `"⚠️ Dallas, TX: Tornado Warning (Extreme)"`

### Benefits of Dynamic Switching

- **Contextual Relevance**: Always shows the most important information for current conditions
- **Quick Recognition**: Visual emojis help identify weather situations at a glance
- **Automatic Adaptation**: No manual configuration needed as weather changes
- **Comprehensive Coverage**: Handles all types of weather scenarios intelligently
- **Accessibility**: Maintains screen reader compatibility while providing rich visual information

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
- **Delete**: Remove selected item (locations, sound packs)

### System Tray Shortcuts
- **Enter**: Focus application or show context menu
- **Applications Key**: Show context menu
- **Shift+F10**: Alternative context menu access

### List and Text Navigation
- **Home / End**: Move to beginning/end of lists or text
- **Page Up / Page Down**: Scroll through long content
- **Ctrl+A**: Select all text in text controls

### Context-Specific Shortcuts
- **Delete on Location Selection**: Remove the currently selected location (requires at least one location to remain)
- **Delete on Sound Pack List**: Remove the selected sound pack (cannot delete the default pack)

## Usage Tips and Best Practices

### Getting Started
1. **Start with Automatic Data Source**: The automatic weather source selection provides the best experience
2. **Add Local Location First**: Add your primary location before exploring other features
3. **Enable Dynamic Format Switching**: Turn on dynamic format switching for the best taskbar experience
4. **Configure Alerts**: Set appropriate alert radius and precision for your needs
5. **Enable System Tray**: Use minimize to tray for convenient background operation

### Taskbar Customization Tips
- **Try Dynamic Switching First**: Enable dynamic format switching to see intelligent format changes
- **Create Custom Fallback**: Design a custom format string as backup when dynamic switching is enabled
- **Test Different Conditions**: Observe how the format changes during different weather conditions
- **Consider Screen Space**: Longer formats may be truncated on smaller screens
- **Use Relevant Variables**: Include variables that matter most for your location and preferences

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
- **Dynamic Switching**: If enabled, format changes automatically based on weather conditions

#### Dynamic Format Issues
- **Format Not Changing**: Dynamic switching requires varying weather conditions to demonstrate different formats
- **Missing Emojis**: Ensure your system supports Unicode emoji display
- **Unexpected Format**: Dynamic switching overrides custom format; disable it to use only your custom format
- **Fallback Behavior**: If dynamic switching fails, it automatically uses your custom format string

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
