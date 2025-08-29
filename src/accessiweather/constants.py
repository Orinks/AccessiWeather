"""Constants and configuration values for AccessiWeather.

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
