"""A client library for accessing Open-Meteo Forecast & Archive API (AccessiWeather Sketch)"""

from .client import AuthenticatedClient, Client

__all__ = (
    "AuthenticatedClient",
    "Client",
)
