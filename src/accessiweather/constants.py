"""
Constants and configuration values for AccessiWeather.

This module centralizes all settings keys, default values, and configuration
constants used throughout the application.
"""

from .utils.temperature_utils import TemperatureUnit

# General settings keys
UPDATE_INTERVAL_KEY = "update_interval_minutes"
ALERT_RADIUS_KEY = "alert_radius_miles"
PRECISE_LOCATION_ALERTS_KEY = "precise_location_alerts"
SHOW_NATIONWIDE_KEY = "show_nationwide_location"
AUTO_REFRESH_NATIONAL_KEY = "auto_refresh_national"

# Advanced settings keys
CACHE_ENABLED_KEY = "cache_enabled"
CACHE_TTL_KEY = "cache_ttl"

# System tray settings
MINIMIZE_ON_STARTUP_KEY = "minimize_on_startup"
MINIMIZE_TO_TRAY_KEY = "minimize_to_tray"

# Update settings keys
AUTO_UPDATE_CHECK_KEY = "auto_update_check_enabled"
UPDATE_CHECK_INTERVAL_KEY = "update_check_interval_hours"
UPDATE_CHANNEL_KEY = "update_channel"

# Update defaults
DEFAULT_AUTO_UPDATE_CHECK = True
DEFAULT_UPDATE_CHECK_INTERVAL = 24
DEFAULT_UPDATE_CHANNEL = "stable"

# Display settings keys
TASKBAR_ICON_TEXT_ENABLED_KEY = "taskbar_icon_text_enabled"
TASKBAR_ICON_TEXT_FORMAT_KEY = "taskbar_icon_text_format"
TASKBAR_ICON_DYNAMIC_ENABLED_KEY = "taskbar_icon_dynamic_enabled"
TEMPERATURE_UNIT_KEY = "temperature_unit"
DEFAULT_TEMPERATURE_UNIT = TemperatureUnit.FAHRENHEIT.value

# Data source constants
DATA_SOURCE_KEY = "data_source"
API_KEYS_SECTION = "api_keys"

# Valid data source values
DATA_SOURCE_NWS = "nws"
DATA_SOURCE_OPENMETEO = "openmeteo"
DATA_SOURCE_VISUALCROSSING = "visualcrossing"
DATA_SOURCE_AUTO = "auto"
VALID_DATA_SOURCES = [
    DATA_SOURCE_NWS,
    DATA_SOURCE_OPENMETEO,
    DATA_SOURCE_VISUALCROSSING,
    DATA_SOURCE_AUTO,
]

# Default values
DEFAULT_DATA_SOURCE = DATA_SOURCE_AUTO

# UI Configuration
DEFAULT_TASKBAR_FORMAT = "{temp} {condition}"

# Default values for intervals
UPDATE_INTERVAL = 15  # Default update interval in minutes

# Validation limits
MIN_UPDATE_INTERVAL = 1
MIN_ALERT_RADIUS = 1
MIN_CACHE_TTL = 60
MIN_UPDATE_CHECK_INTERVAL = 1
MAX_UPDATE_CHECK_INTERVAL = 168  # 1 week in hours

# Tab names for notebook
TAB_GENERAL = "General"
TAB_DISPLAY = "Display"
TAB_ADVANCED = "Advanced"
TAB_UPDATES = "Updates"


# GitHub App configuration constants
GITHUB_APP_ID_KEY = "github_app_id"
GITHUB_APP_PRIVATE_KEY_KEY = "github_app_private_key"
GITHUB_APP_INSTALLATION_ID_KEY = "github_app_installation_id"
DEFAULT_GITHUB_APP_ID = ""
DEFAULT_GITHUB_APP_PRIVATE_KEY = ""
DEFAULT_GITHUB_APP_INSTALLATION_ID = ""
GITHUB_API_BASE_URL = "https://api.github.com"

# GitHub App validation constants
GITHUB_APP_MIN_ID_LENGTH = 1
GITHUB_APP_PRIVATE_KEY_HEADER = "-----BEGIN RSA PRIVATE KEY-----"
GITHUB_APP_PRIVATE_KEY_FOOTER = "-----END RSA PRIVATE KEY-----"
GITHUB_APP_PKCS8_PRIVATE_KEY_HEADER = "-----BEGIN PRIVATE KEY-----"
GITHUB_APP_PKCS8_PRIVATE_KEY_FOOTER = "-----END PRIVATE KEY-----"

# GitHub repository constants for community soundpack repository
COMMUNITY_REPO_OWNER = "orinks"
COMMUNITY_REPO_NAME = "accessiweather-soundpacks"


# =============================================================================
# Alert System Constants
# =============================================================================

# Severity Priority System (1-5 scale, higher = more severe)
SEVERITY_PRIORITY_UNKNOWN = 1
SEVERITY_PRIORITY_MINOR = 2
SEVERITY_PRIORITY_MODERATE = 3
SEVERITY_PRIORITY_SEVERE = 4
SEVERITY_PRIORITY_EXTREME = 5

# Mapping from severity string to numeric priority
SEVERITY_PRIORITY_MAP: dict[str, int] = {
    "unknown": SEVERITY_PRIORITY_UNKNOWN,
    "minor": SEVERITY_PRIORITY_MINOR,
    "moderate": SEVERITY_PRIORITY_MODERATE,
    "severe": SEVERITY_PRIORITY_SEVERE,
    "extreme": SEVERITY_PRIORITY_EXTREME,
}

# Alert Notification Cooldown Periods (in minutes)
# Global cooldown: minimum time between any notifications
DEFAULT_GLOBAL_COOLDOWN_MINUTES = 5

# Per-alert cooldown: minimum time before re-notifying about same alert
DEFAULT_PER_ALERT_COOLDOWN_MINUTES = 60

# Escalation cooldown: reduced cooldown when alert severity increases
DEFAULT_ESCALATION_COOLDOWN_MINUTES = 15

# Rate Limiting Configuration
# Maximum number of alert notifications allowed per hour
DEFAULT_MAX_NOTIFICATIONS_PER_HOUR = 10

# Time conversion constant for rate limit calculations
SECONDS_PER_HOUR = 3600

# Notification Formatting Limits
# Maximum length of alert description in notification message (truncated with "...")
MAX_NOTIFICATION_DESCRIPTION_LENGTH = 100

# Maximum number of affected areas to display (additional areas shown as count)
MAX_DISPLAYED_AREAS = 2

# Default timeout for desktop notifications (in seconds)
NOTIFICATION_TIMEOUT_SECONDS = 15

# Alert State Management
# Number of days to retain alert state history before cleanup
ALERT_STATE_RETENTION_DAYS = 7

# Maximum number of historical content hashes to track per alert
# (for change detection and escalation tracking)
ALERT_HISTORY_MAX_LENGTH = 5

# Default Alert Settings
# Default minimum severity level to trigger notifications
# (2 = minor and above, 3 = moderate and above, etc.)
DEFAULT_MIN_SEVERITY_PRIORITY = SEVERITY_PRIORITY_MINOR

# Default enabled state for alert notifications
DEFAULT_NOTIFICATIONS_ENABLED = True

# Default enabled state for notification sounds
DEFAULT_SOUND_ENABLED = True
