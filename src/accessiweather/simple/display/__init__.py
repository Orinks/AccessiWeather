"""Display modules for AccessiWeather Simple.

This package provides display components and formatters that match the wx version's
output exactly while being organized into clean, modular components.
"""

from .wx_style_formatter import WxStyleWeatherFormatter

__all__ = [
    "WxStyleWeatherFormatter",
]
