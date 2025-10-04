"""Display modules for AccessiWeather Simple.

WeatherPresenter remains the public entry point. Additional presentation helpers now
live in internal submodules that organize current conditions, forecasts, and alerts
logic while preserving this import surface.
"""

from .weather_presenter import WeatherPresenter

__all__ = [
    "WeatherPresenter",
]
