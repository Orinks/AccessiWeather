### Welcome to AccessiWeather

AccessiWeather is a desktop weather application designed from the ground up to be accessible and user-friendly, especially for those who use screen readers like NVDA and JAWS. It provides detailed, real-time weather information right on your desktop, with a focus on keyboard navigation and clarity.

### Quick Start Guide

Getting started with AccessiWeather is straightforward.

**1. Installation**
For the easiest setup, it is recommended to use the Windows installer. Users who prefer package managers can also check for its availability through tools like Chocolatey or winget.

* Go to the AccessiWeather releases page on GitHub.
* Download the latest installer (`.exe` file).
* Run the installer and follow the on-screen instructions.
* You can then launch AccessiWeather from your Start Menu or desktop.

For users who prefer not to install software, a portable version is also available. Simply download the `.zip` file, extract it, and run `accessiweather.exe`. Your settings will be saved in the same folder.

**2. First-Time Setup**
When you first open the app:

* **Add Your Location**: The app starts with a "Nationwide" view. Click "Add Location" and search by city or ZIP code to get your local forecast.
* **Explore Settings**: Open the Settings dialog, access via the settings button in the main user interface. Here you can customize everything from measurement units to how often the weather updates.
* **Enable System Tray**: For convenience, go to the "Advanced" tab in settings and enable "Minimize to Tray." Alternatively, press escape or the "Minimize to Tray" button in the main user interface window. This keeps the app running in the background.


### Exploring Your Weather

AccessiWeather puts comprehensive weather data at your fingertips.

* **Forecasts at a Glance**: View current conditions, detailed multi-day forecasts, and hour-by-hour predictions for precise planning.
* **Stay Safe with Weather Alerts**: For locations within the United States, AccessiWeather provides real-time weather alerts from the National Weather Service (NWS). You can receive notifications for watches, warnings, and advisories, and customize the alert radius to fit your needs. International locations are supported for weather data via Open-Meteo, but without alerts.
* **Go Deeper with Weather Discussions**: For those who want more than just the numbers, AccessiWeather provides access to in-depth meteorological discussions, offering professional insights directly from forecasters.
    * **Nationwide Discussions**: The application includes a "Nationwide" view by default, which provides broad discussions from the Weather Prediction Center (WPC) and Storm Prediction Center (SPC). This gives you a comprehensive overview of weather patterns across the United States. If you prefer to focus only on your local spots, this Nationwide view can be hidden in the General settings.
    * **Local Area Forecast Discussions (AFD)**: When you add any location within the United States, you can also access its local Area Forecast Discussion. An AFD is a detailed narrative written by the meteorologists at the local National Weather Service office that explains the reasoning, models, and uncertainties behind their official forecast. This provides a valuable behind-the-scenes look at how your weather is predicted. These discussions are particularly useful for weather enthusiasts and those with weather-sensitive hobbies, like flight simulation, as they can clarify the nuances behind official aviation forecasts.


### A Smarter Taskbar Icon

A key feature of AccessiWeather is its ability to display live weather information directly in your taskbar icon. This feature is highly customizable and can automatically change to show you the most important information based on current conditions.

**Dynamic Format Switching**
When you enable "Dynamic Format Switching" in the Display settings, the taskbar text adapts to the weather. This means you don't have to open the app to know if conditions are changing.

Here’s how it works:

* **Normal Weather**: Shows a general overview.
    * `"San Francisco, CA 72°F Clear - 55%"`
* **Severe Weather**: Highlights storms and wind.
    * `"🌩️ New York, NY Thunderstorms 68°F - NW 25.0 mph"`
* **Temperature Extremes**: Warns you about heat or cold.
    * `"🌡️ Phoenix, AZ 105°F (feels 115°F) - Sunny"`
* **Precipitation**: Tells you the chance of rain or snow.
    * `"🌧️ Seattle, WA Cloudy 58°F - 80% chance"`
* **Active Alerts**: Displays official warnings.
    * `"⚠️ Dallas, TX: Tornado Warning (Extreme)"`

You can also create your own custom display format using variables like `{temp}`, `{condition}`, and `{location}`. This custom format will be used as a fallback if dynamic switching is disabled or unavailable.

### Essential Keyboard Commands

AccessiWeather is fully navigable with a keyboard. While standard keys like `Tab` and the arrow keys work as expected, here are the shortcuts specific to the application:

* **F5**: Refresh the weather data immediately.
* **Escape**: Minimize the application to the system tray (if enabled in settings).
* **Applications Key** or **Shift+F10**: Open the context menu when focused on the system tray icon.


### Tips for a Better Experience

* **Use the "Automatic" Data Source**: In Settings, the "Automatic" weather source is recommended. It intelligently uses the NWS for US locations (to provide alerts) and Open-Meteo for international locations.
* **Adjust Update Intervals**: Set a short interval (e.g., 10-15 minutes) for active monitoring or a longer one to save resources if you only need occasional updates.
* **Customize Alerts**: In the General settings, you can choose between "Precise Location Alerts" for your specific area or "State-wide Alerts" for broader coverage.


### Troubleshooting and Support

If you encounter issues, detailed logs are created to help diagnose the problem. For support, bug reports, and feature requests, the community and developers can be reached through the project's GitHub Issues page. To check your app version, navigate to `Help > About` in the application menu.
