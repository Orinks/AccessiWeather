"""Display Managers for AccessiWeather UI.

This module provides classes for managing the display of weather data
in various UI components.

This module has been refactored for better maintainability. The actual
implementation is now in the display_managers package.
"""

# Import from the new modular structure for backward compatibility
from .display_managers import WeatherDisplayManager

__all__ = ["WeatherDisplayManager"]
