"""Simple data models for AccessiWeather.

This module provides simple dataclasses for weather information,
replacing the complex service layer architecture with straightforward data structures.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class Location:
    """Simple location data."""
    name: str
    latitude: float
    longitude: float
    
    def __str__(self) -> str:
        return self.name


@dataclass
class CurrentConditions:
    """Current weather conditions."""
    temperature_f: Optional[float] = None
    temperature_c: Optional[float] = None
    condition: Optional[str] = None
    humidity: Optional[int] = None
    wind_speed_mph: Optional[float] = None
    wind_speed_kph: Optional[float] = None
    wind_direction: Optional[str] = None
    pressure_in: Optional[float] = None
    pressure_mb: Optional[float] = None
    feels_like_f: Optional[float] = None
    feels_like_c: Optional[float] = None
    visibility_miles: Optional[float] = None
    visibility_km: Optional[float] = None
    uv_index: Optional[float] = None
    last_updated: Optional[datetime] = None
    
    def has_data(self) -> bool:
        """Check if we have any meaningful weather data."""
        return any([
            self.temperature_f is not None,
            self.temperature_c is not None,
            self.condition is not None
        ])


@dataclass
class ForecastPeriod:
    """Single forecast period."""
    name: str
    temperature: Optional[float] = None
    temperature_unit: str = "F"
    short_forecast: Optional[str] = None
    detailed_forecast: Optional[str] = None
    wind_speed: Optional[str] = None
    wind_direction: Optional[str] = None
    icon: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


@dataclass
class Forecast:
    """Weather forecast data."""
    periods: List[ForecastPeriod]
    generated_at: Optional[datetime] = None
    
    def has_data(self) -> bool:
        """Check if we have any forecast data."""
        return len(self.periods) > 0


@dataclass
class WeatherAlert:
    """Weather alert/warning."""
    title: str
    description: str
    severity: str = "Unknown"
    urgency: str = "Unknown"
    certainty: str = "Unknown"
    event: Optional[str] = None
    headline: Optional[str] = None
    instruction: Optional[str] = None
    onset: Optional[datetime] = None
    expires: Optional[datetime] = None
    areas: List[str] = None
    
    def __post_init__(self):
        if self.areas is None:
            self.areas = []


@dataclass
class WeatherAlerts:
    """Collection of weather alerts."""
    alerts: List[WeatherAlert]
    
    def has_alerts(self) -> bool:
        """Check if we have any active alerts."""
        return len(self.alerts) > 0
    
    def get_active_alerts(self) -> List[WeatherAlert]:
        """Get alerts that haven't expired."""
        now = datetime.now()
        active = []
        
        for alert in self.alerts:
            if alert.expires is None or alert.expires > now:
                active.append(alert)
        
        return active


@dataclass
class WeatherData:
    """Complete weather data for a location."""
    location: Location
    current: Optional[CurrentConditions] = None
    forecast: Optional[Forecast] = None
    discussion: Optional[str] = None
    alerts: Optional[WeatherAlerts] = None
    last_updated: Optional[datetime] = None
    
    def has_any_data(self) -> bool:
        """Check if we have any weather data."""
        return any([
            self.current and self.current.has_data(),
            self.forecast and self.forecast.has_data(),
            self.alerts and self.alerts.has_alerts()
        ])


@dataclass
class ApiError:
    """API error information."""
    message: str
    code: Optional[str] = None
    details: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


# Configuration data structures
@dataclass
class AppSettings:
    """Application settings."""
    temperature_unit: str = "both"  # "f", "c", or "both"
    update_interval_minutes: int = 10
    show_detailed_forecast: bool = True
    enable_alerts: bool = True
    minimize_to_tray: bool = True
    data_source: str = "auto"  # "nws", "openmeteo", or "auto"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "temperature_unit": self.temperature_unit,
            "update_interval_minutes": self.update_interval_minutes,
            "show_detailed_forecast": self.show_detailed_forecast,
            "enable_alerts": self.enable_alerts,
            "minimize_to_tray": self.minimize_to_tray,
            "data_source": self.data_source,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        """Create from dictionary."""
        return cls(
            temperature_unit=data.get("temperature_unit", "both"),
            update_interval_minutes=data.get("update_interval_minutes", 10),
            show_detailed_forecast=data.get("show_detailed_forecast", True),
            enable_alerts=data.get("enable_alerts", True),
            minimize_to_tray=data.get("minimize_to_tray", True),
            data_source=data.get("data_source", "auto"),
        )


@dataclass
class AppConfig:
    """Application configuration."""
    settings: AppSettings
    locations: List[Location]
    current_location: Optional[Location] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "settings": self.settings.to_dict(),
            "locations": [
                {
                    "name": loc.name,
                    "latitude": loc.latitude,
                    "longitude": loc.longitude,
                }
                for loc in self.locations
            ],
            "current_location": {
                "name": self.current_location.name,
                "latitude": self.current_location.latitude,
                "longitude": self.current_location.longitude,
            } if self.current_location else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        """Create from dictionary."""
        settings = AppSettings.from_dict(data.get("settings", {}))
        
        locations = []
        for loc_data in data.get("locations", []):
            locations.append(Location(
                name=loc_data["name"],
                latitude=loc_data["latitude"],
                longitude=loc_data["longitude"],
            ))
        
        current_location = None
        if data.get("current_location"):
            loc_data = data["current_location"]
            current_location = Location(
                name=loc_data["name"],
                latitude=loc_data["latitude"],
                longitude=loc_data["longitude"],
            )
        
        return cls(
            settings=settings,
            locations=locations,
            current_location=current_location,
        )
    
    @classmethod
    def default(cls) -> "AppConfig":
        """Create default configuration."""
        return cls(
            settings=AppSettings(),
            locations=[],
            current_location=None,
        )
