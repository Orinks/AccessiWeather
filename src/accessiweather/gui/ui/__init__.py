"""UI package for AccessiWeather.

This package contains modular UI components extracted from the original
large ui_manager.py file for better maintainability and separation of concerns.
"""

from .alerts_manager import AlertsDisplayManager
from .data_extractors import WeatherDataExtractor
from .data_formatters import WeatherDataFormatter
from .display_managers import WeatherDisplayManager
from .event_handlers import EventHandlers
from .ui_utils import (
    convert_wind_direction_to_cardinal,
    create_standardized_taskbar_data,
    format_combined_wind,
    is_weatherapi_data,
    safe_get_location_name,
)
from .weather_source_manager import WeatherSourceManager
from .widget_factory import WidgetFactory

__all__ = [
    "AlertsDisplayManager",
    "WeatherDataExtractor",
    "WeatherDataFormatter",
    "WeatherDisplayManager",
    "EventHandlers",
    "WeatherSourceManager",
    "WidgetFactory",
    "convert_wind_direction_to_cardinal",
    "create_standardized_taskbar_data",
    "format_combined_wind",
    "is_weatherapi_data",
    "safe_get_location_name",
]
