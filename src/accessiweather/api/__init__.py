"""API package for AccessiWeather.

This package contains modular API components extracted from the original
large api_wrapper.py file for better maintainability and separation of concerns.
"""

from .base_wrapper import BaseApiWrapper
from .nws import NwsApiWrapper
from .openmeteo_wrapper import OpenMeteoApiWrapper

__all__ = [
    "BaseApiWrapper",
    "NwsApiWrapper",
    "OpenMeteoApiWrapper",
]
