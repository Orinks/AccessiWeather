"""Pytest plugin to handle service class mocking.

This plugin provides a hook to handle mocking of service classes
to avoid conflicts between different test modules when using unittest.mock.MagicMock.
"""

import pytest
from unittest.mock import patch


def pytest_configure(config):
    """Register the plugin."""
    config.pluginmanager.register(ServiceClassesPlugin(), "service_classes_plugin")


class ServiceClassesPlugin:
    """Plugin to handle service classes mocking."""

    def pytest_sessionstart(self, session):
        """Set up mocking for the session."""
        # Import here to avoid circular imports
        from accessiweather.services.weather_service import WeatherService
        from accessiweather.services.location_service import LocationService
        from accessiweather.api_client import NoaaApiClient
        from accessiweather.notifications import WeatherNotifier
        
        # Store the original __new__ methods
        self._originals = {}
        
        # List of classes to patch
        classes_to_patch = [
            WeatherService,
            LocationService,
            NoaaApiClient,
            WeatherNotifier
        ]
        
        # Patch each class
        for cls in classes_to_patch:
            self._originals[cls] = cls.__new__
            
            # Create a closure to capture the current class
            def make_patched_new(target_cls):
                def patched_new(cls, *args, **kwargs):
                    if cls is target_cls:
                        return object.__new__(cls)
                    return self._originals[target_cls](cls, *args, **kwargs)
                return patched_new
            
            # Apply the patch
            cls.__new__ = make_patched_new(cls)

    def pytest_sessionfinish(self, session, exitstatus):
        """Clean up mocking after the session."""
        # Restore the original __new__ methods
        for cls, original_new in self._originals.items():
            cls.__new__ = original_new
