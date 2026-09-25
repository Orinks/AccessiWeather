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
  --version         Show the version

Keyboard shortcuts:
  F5 / Ctrl+R       Refresh weather
  Alt+A             Add a location
  Ctrl+,            Settings
  Ctrl+D            Forecast discussion
  Ctrl+Shift+S      Read current conditions aloud (Escape stops speech)
  Ctrl+1 .. Ctrl+5  Jump to location, current, hourly, daily, alerts
  Ctrl+Q            Quit
