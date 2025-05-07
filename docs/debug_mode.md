# AccessiWeather Debug Mode

AccessiWeather includes a debug mode that can be used to test various features of the application, particularly the alert system. This document explains how to use the debug mode.

## Command Line Arguments

The following command line arguments are available for debug mode:

### Basic Debug Mode

```
python -m accessiweather.cli --debug
```

This enables debug logging, which provides more detailed information in the console and log files.

### Enhanced Debug Mode

```
python -m accessiweather.cli --debug --debug-mode test-alert
```

This enables the test alert feature, which allows you to manually trigger test alerts.

```
python -m accessiweather.cli --debug --debug-mode verify-interval
```

This enables the interval verification feature, which allows you to verify that the alert update interval is working correctly.

### Debug Mode Options

The following options can be used with the enhanced debug mode:

```
--alert-severity {Extreme,Severe,Moderate,Minor}
```

Specifies the severity level for test alerts (default: Moderate).

```
--alert-event "Custom Alert Name"
```

Specifies the event name for test alerts (default: "Test Alert").

## Test Alert Mode

When running in test alert mode, the application will automatically trigger a test alert when it starts. The test alert will appear in the Alerts tab and will also trigger a desktop notification.

Test alerts are clearly marked with "DEBUG TEST:" in the headline to distinguish them from real alerts.

Example:

```
python -m accessiweather.cli --debug --debug-mode test-alert --alert-severity Severe --alert-event "Tornado Warning"
```

This will trigger a test alert with severity "Severe" and event name "Tornado Warning".

## Interval Verification Mode

When running in interval verification mode, the application will:

1. Set the alert update interval to 10 seconds (1/6 of a minute)
2. Trigger an initial test alert
3. Log detailed information about the alert update interval checks

This mode is useful for verifying that the alert update interval setting is working correctly. You should see log messages indicating that the alerts are being updated every 10 seconds.

Example:

```
python -m accessiweather.cli --debug --debug-mode verify-interval
```

## Logging

When running in debug mode, detailed logging information is written to the console and log files. The log files are located in the following directory:

- Windows: `%APPDATA%\AccessiWeather\logs`
- Linux/macOS: `~/.accessiweather/logs`

The log files include information about alert updates, timer checks, and other events that can help diagnose issues with the application.
