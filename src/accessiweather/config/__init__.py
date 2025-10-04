"""Configuration helpers and manager for AccessiWeather.

This package exposes :class:`ConfigManager` while housing focused helper modules
that implement specific groups of configuration operations.
"""

from .config_manager import ConfigManager, logger

__all__ = ["ConfigManager", "logger"]
