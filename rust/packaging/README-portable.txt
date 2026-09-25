AccessiWeather (native Rust edition)

Run the executable to start. Settings and saved locations are stored in your
user profile and are shared with the Python edition of AccessiWeather.

To keep everything next to the program instead (USB stick, etc.), start it
with --portable; a "config" folder will be created beside the executable.

Command line:
  --portable        Store configuration next to the executable
  --config-dir DIR  Use a specific configuration folder
  --offline         Use bundled sample data (no network)
  --print-paths     Show where configuration is stored
  --debug           Enable debug logging
  --version         Show the version

Keyboard shortcuts:
  F5 / Ctrl+R       Refresh weather
  Ctrl+L            Add location
  F2                Edit the selected location
  Ctrl+D            Remove location
  Ctrl+S            Open Settings
  Ctrl+H            Open Weather History
  Ctrl+E            Explain Weather
  Ctrl+T            Open Weather Assistant
  Ctrl+N            Open NOAA Weather Radio
  Ctrl+1 .. Ctrl+5  Current Conditions, Hourly Forecast, Daily Forecast,
                    Weather Alerts, Event Center
  F6                Cycle through the visible sections
  Ctrl+Q            Quit
