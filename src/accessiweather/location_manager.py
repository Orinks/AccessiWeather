"""
Simple location management for AccessiWeather.

This module provides simple location management functionality,
replacing the complex location service with direct operations.
"""

import logging

import httpx

from .models import Location
from .utils.retry_utils import (
    RETRYABLE_EXCEPTIONS,
    async_retry_with_backoff,
    is_retryable_http_error,
)

logger = logging.getLogger(__name__)


class LocationManager:
    """Simple location manager with geocoding support via Open-Meteo."""

    def __init__(self):
        """Initialize the instance."""
        self.timeout = 10.0
        self.geocoding_base_url = "https://geocoding-api.open-meteo.com/v1"

    @async_retry_with_backoff(max_attempts=3, base_delay=1.0, timeout=15.0)
    async def search_locations(self, query: str, limit: int = 5) -> list[Location]:
        """Search for locations using Open-Meteo geocoding API."""
        logger.info(f"Searching for locations: {query}")

        # Open-Meteo requires at least 2 characters
        if len(query.strip()) < 2:
            logger.info("Query too short for geocoding")
            return []

        try:
            url = f"{self.geocoding_base_url}/search"
            params = {
                "name": query,
                "count": min(limit, 100),  # Open-Meteo max is 100
                "language": "en",
                "format": "json",
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                if not results:
                    logger.info(f"No locations found for query: {query}")
                    return []

                # Sort by population (higher first) for better relevance
                results.sort(key=lambda x: x.get("population", 0) or 0, reverse=True)

                # Parse and deduplicate results
                unique_locations: dict[str, Location] = {}
                for item in results:
                    location = self._parse_geocoding_result(item)
                    if location:
                        key = location.name.lower()
                        if key not in unique_locations:
                            unique_locations[key] = location
                        if len(unique_locations) >= limit:
                            break

                locations = list(unique_locations.values())
                logger.info(f"Found {len(locations)} locations for query: {query}")
                return locations

        except Exception as e:
            logger.error(f"Failed to search locations: {e}")
            if isinstance(e, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(e):
                raise
            return []

    def _parse_geocoding_result(self, data: dict) -> Location | None:
        """Parse Open-Meteo geocoding API result into Location object."""
        try:
            lat = float(data.get("latitude", 0))
            lon = float(data.get("longitude", 0))

            # Build location name from available fields
            name = data.get("name", "")
            admin1 = data.get("admin1", "")  # State/province
            country = data.get("country", "")
            country_code = data.get("country_code", "")

            # Build a nice display name
            name_parts = [name] if name else []

            # Add state/province for context
            if admin1 and admin1 != name:
                name_parts.append(admin1)

            # Add country if not US (to avoid redundancy for US locations)
            if country and country not in ("United States", "United States of America"):
                name_parts.append(country)

            display_name = ", ".join(name_parts) if name_parts else "Unknown Location"

            return Location(
                name=display_name,
                latitude=lat,
                longitude=lon,
                country_code=country_code.upper() if country_code else None,
            )

        except Exception as e:
            logger.error(f"Failed to parse geocoding result: {e}")
            return None

    def validate_coordinates(self, latitude: float, longitude: float) -> bool:
        """Validate that coordinates are within valid ranges."""
        return (-90 <= latitude <= 90) and (-180 <= longitude <= 180)

    def calculate_distance(self, loc1: Location, loc2: Location) -> float:
        """Calculate distance between two locations in miles using Haversine formula."""
        import math

        # Convert to radians
        lat1_rad = math.radians(loc1.latitude)
        lon1_rad = math.radians(loc1.longitude)
        lat2_rad = math.radians(loc2.latitude)
        lon2_rad = math.radians(loc2.longitude)

        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))

        # Earth's radius in miles
        earth_radius_miles = 3959

        return earth_radius_miles * c

    def get_us_state_from_coordinates(self, latitude: float, longitude: float) -> str | None:
        """Get US state abbreviation from coordinates (simplified lookup)."""
        # This is a very simplified state lookup based on rough coordinate ranges
        # For production use, you'd want a proper geospatial library or service

        state_bounds = {
            "FL": {"lat_min": 24.5, "lat_max": 31.0, "lon_min": -87.6, "lon_max": -80.0},
            "CA": {"lat_min": 32.5, "lat_max": 42.0, "lon_min": -124.4, "lon_max": -114.1},
            "TX": {"lat_min": 25.8, "lat_max": 36.5, "lon_min": -106.6, "lon_max": -93.5},
            "NY": {"lat_min": 40.5, "lat_max": 45.0, "lon_min": -79.8, "lon_max": -71.9},
            "PA": {"lat_min": 39.7, "lat_max": 42.3, "lon_min": -80.5, "lon_max": -74.7},
            # Add more states as needed
        }

        for state, bounds in state_bounds.items():
            if (
                bounds["lat_min"] <= latitude <= bounds["lat_max"]
                and bounds["lon_min"] <= longitude <= bounds["lon_max"]
            ):
                return state

        return None

    def is_us_location(self, location: Location) -> bool:
        """Check if location is within the United States (rough approximation)."""
        # Continental US bounds (approximate)
        us_bounds = {
            "lat_min": 24.0,  # Southern tip of Florida
            "lat_max": 49.0,  # Northern border
            "lon_min": -125.0,  # West coast
            "lon_max": -66.0,  # East coast
        }

        return (
            us_bounds["lat_min"] <= location.latitude <= us_bounds["lat_max"]
            and us_bounds["lon_min"] <= location.longitude <= us_bounds["lon_max"]
        )

    def format_coordinates(self, latitude: float, longitude: float, precision: int = 4) -> str:
        """Format coordinates as a readable string."""
        lat_dir = "N" if latitude >= 0 else "S"
        lon_dir = "E" if longitude >= 0 else "W"

        return f"{abs(latitude):.{precision}f}°{lat_dir}, {abs(longitude):.{precision}f}°{lon_dir}"

    def parse_coordinates(self, coord_string: str) -> tuple[float, float] | None:
        """Parse coordinate string into latitude, longitude tuple."""
        try:
            # Handle various coordinate formats
            coord_string = coord_string.strip()

            # Remove degree symbols and direction letters for parsing
            clean_string = (
                coord_string.replace("°", "")
                .replace("N", "")
                .replace("S", "")
                .replace("E", "")
                .replace("W", "")
            )

            # Split on comma
            parts = [part.strip() for part in clean_string.split(",")]
            if len(parts) != 2:
                return None

            lat = float(parts[0])
            lon = float(parts[1])

            # Apply direction signs if present in original string
            if "S" in coord_string.upper():
                lat = -abs(lat)
            if "W" in coord_string.upper():
                lon = -abs(lon)

            # Validate
            if self.validate_coordinates(lat, lon):
                return (lat, lon)
            return None

        except Exception as e:
            logger.error(f"Failed to parse coordinates '{coord_string}': {e}")
            return None

    def get_common_locations(self) -> list[Location]:
        """Get a list of common/popular locations for quick selection."""
        return [
            Location("New York, NY", 40.7128, -74.0060),
            Location("Los Angeles, CA", 34.0522, -118.2437),
            Location("Chicago, IL", 41.8781, -87.6298),
            Location("Houston, TX", 29.7604, -95.3698),
            Location("Phoenix, AZ", 33.4484, -112.0740),
            Location("Philadelphia, PA", 39.9526, -75.1652),
            Location("San Antonio, TX", 29.4241, -98.4936),
            Location("San Diego, CA", 32.7157, -117.1611),
            Location("Dallas, TX", 32.7767, -96.7970),
            Location("San Jose, CA", 37.3382, -121.8863),
            Location("Miami, FL", 25.7617, -80.1918),
            Location("Atlanta, GA", 33.7490, -84.3880),
            Location("Boston, MA", 42.3601, -71.0589),
            Location("Seattle, WA", 47.6062, -122.3321),
            Location("Denver, CO", 39.7392, -104.9903),
        ]

    @async_retry_with_backoff(max_attempts=2, base_delay=0.5, timeout=12.0)
    async def get_current_location_from_ip(self) -> Location | None:
        """Get approximate location from IP address (for initial setup)."""
        try:
            # Use a simple IP geolocation service
            url = "http://ip-api.com/json/"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                if data.get("status") == "success":
                    city = data.get("city", "")
                    region = data.get("regionName", "")
                    country = data.get("country", "")

                    # Build location name
                    name_parts = [city, region] if city and region else [city or region]
                    if country and country != "United States":
                        name_parts.append(country)

                    name = ", ".join(name_parts) if name_parts else "Current Location"

                    location = Location(
                        name=name,
                        latitude=data.get("lat", 0.0),
                        longitude=data.get("lon", 0.0),
                        country_code=(data.get("countryCode") or "").upper() or None,
                    )

                    logger.info(f"Detected location from IP: {location.name}")
                    return location

        except Exception as e:
            logger.error(f"Failed to get location from IP: {e}")
            if isinstance(e, RETRYABLE_EXCEPTIONS) or is_retryable_http_error(e):
                raise

        return None
