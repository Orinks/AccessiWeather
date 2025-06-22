"""System tray functionality for AccessiWeather.

This module provides backward compatibility imports for the refactored
system tray functionality. The actual implementation has been split into
focused modules for better maintainability.
"""

# Import the main TaskBarIcon class from the new module structure
from .system_tray_modules import TaskBarIcon

# Export for backward compatibility
__all__ = ["TaskBarIcon"]
