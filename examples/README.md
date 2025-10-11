# AccessiWeather Examples

This directory contains example scripts and demonstrations of AccessiWeather features.

## Available Examples

### weather_history_demo.py

Demonstrates the Weather History Tracker feature that allows tracking and comparing weather conditions over time.

**Features shown:**
- Initializing the weather history tracker
- Adding weather history entries
- Saving and loading history from file
- Comparing current weather with past days (yesterday, last week)
- Generating accessible summaries for screen readers
- Automatic cleanup of old entries

**Running the demo:**
```bash
cd /path/to/AccessiWeather
python3 examples/weather_history_demo.py
```

**Sample output:**
```
======================================================================
Weather History Tracker Demo
======================================================================

1. Initializing Weather History Tracker...
   ✓ Tracker created with 30-day retention

2. Creating location...
   ✓ Location: New York City

...

7. Comparing with Yesterday:
   Temperature: 8.0 degrees warmer
   Condition: Changed
   Previous: Partly Cloudy

   Accessible Summary:
   "Compared to yesterday: 8.0 degrees warmer. Changed from Partly Cloudy to Sunny."
```

## Creating New Examples

When adding new example scripts:

1. Create a standalone Python file in this directory
2. Include docstrings explaining what the example demonstrates
3. Make the script executable: `chmod +x your_example.py`
4. Add a shebang line: `#!/usr/bin/env python3`
5. Add error handling and cleanup code
6. Update this README with usage instructions

## Requirements

Examples should be self-contained and work with minimal dependencies. Mock any unavailable modules (like Toga) if needed.

## Testing Examples

Before committing:

1. Run the example script to ensure it works
2. Verify output is clear and helpful
3. Check for Python syntax errors: `python3 -m py_compile your_example.py`
4. Ensure proper cleanup of temporary files

## License

All examples are part of AccessiWeather and licensed under the MIT License.
