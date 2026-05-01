"""Top-level application configuration dataclass."""

from __future__ import annotations

from dataclasses import dataclass

from .config_settings import AppSettings
from .weather import Location


@dataclass
class AppConfig:
    """Application configuration."""

    settings: AppSettings
    locations: list[Location]
    current_location: Location | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "settings": self.settings.to_dict(),
            "locations": [
                {
                    "name": loc.name,
                    "latitude": loc.latitude,
                    "longitude": loc.longitude,
                    **({"country_code": loc.country_code} if loc.country_code else {}),
                    **({"marine_mode": True} if loc.marine_mode else {}),
                    **({"timezone": loc.timezone} if loc.timezone else {}),
                    **({"forecast_zone_id": loc.forecast_zone_id} if loc.forecast_zone_id else {}),
                    **({"cwa_office": loc.cwa_office} if loc.cwa_office else {}),
                    **({"county_zone_id": loc.county_zone_id} if loc.county_zone_id else {}),
                    **({"fire_zone_id": loc.fire_zone_id} if loc.fire_zone_id else {}),
                    **({"radar_station": loc.radar_station} if loc.radar_station else {}),
                }
                for loc in self.locations
            ],
            "current_location": {
                "name": self.current_location.name,
                "latitude": self.current_location.latitude,
                "longitude": self.current_location.longitude,
                **(
                    {"country_code": self.current_location.country_code}
                    if self.current_location.country_code
                    else {}
                ),
                **({"marine_mode": True} if self.current_location.marine_mode else {}),
                **(
                    {"timezone": self.current_location.timezone}
                    if self.current_location.timezone
                    else {}
                ),
                **(
                    {"forecast_zone_id": self.current_location.forecast_zone_id}
                    if self.current_location.forecast_zone_id
                    else {}
                ),
                **(
                    {"cwa_office": self.current_location.cwa_office}
                    if self.current_location.cwa_office
                    else {}
                ),
                **(
                    {"county_zone_id": self.current_location.county_zone_id}
                    if self.current_location.county_zone_id
                    else {}
                ),
                **(
                    {"fire_zone_id": self.current_location.fire_zone_id}
                    if self.current_location.fire_zone_id
                    else {}
                ),
                **(
                    {"radar_station": self.current_location.radar_station}
                    if self.current_location.radar_station
                    else {}
                ),
            }
            if self.current_location
            else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AppConfig:
        """Create from dictionary."""
        settings = AppSettings.from_dict(data.get("settings", {}))

        locations = []
        for loc_data in data.get("locations", []):
            locations.append(
                Location(
                    name=loc_data["name"],
                    latitude=loc_data["latitude"],
                    longitude=loc_data["longitude"],
                    timezone=loc_data.get("timezone"),
                    country_code=loc_data.get("country_code"),
                    marine_mode=bool(loc_data.get("marine_mode", False)),
                    forecast_zone_id=loc_data.get("forecast_zone_id"),
                    cwa_office=loc_data.get("cwa_office"),
                    county_zone_id=loc_data.get("county_zone_id"),
                    fire_zone_id=loc_data.get("fire_zone_id"),
                    radar_station=loc_data.get("radar_station"),
                )
            )

        current_location = None
        if data.get("current_location"):
            loc_data = data["current_location"]
            current_location = Location(
                name=loc_data["name"],
                latitude=loc_data["latitude"],
                longitude=loc_data["longitude"],
                timezone=loc_data.get("timezone"),
                country_code=loc_data.get("country_code"),
                marine_mode=bool(loc_data.get("marine_mode", False)),
                forecast_zone_id=loc_data.get("forecast_zone_id"),
                cwa_office=loc_data.get("cwa_office"),
                county_zone_id=loc_data.get("county_zone_id"),
                fire_zone_id=loc_data.get("fire_zone_id"),
                radar_station=loc_data.get("radar_station"),
            )

        return cls(
            settings=settings,
            locations=locations,
            current_location=current_location,
        )

    @classmethod
    def default(cls) -> AppConfig:
        """Create default configuration."""
        return cls(
            settings=AppSettings(),
            locations=[],
            current_location=None,
        )
