"""
Simple location management for AccessiWeather.

This module provides simple location management functionality,
replacing the complex location service with direct operations.
"""

import logging

import httpx

from .models import Location

logger = logging.getLogger(__name__)


class LocationManager:
    """Simple location manager with geocoding support."""

    def __init__(self):
        """Initialize the instance."""
        self.timeout = 10.0
        self.geocoding_base_url = "https://nominatim.openstreetmap.org"

    async def search_locations(self, query: str, limit: int = 5) -> list[Location]:
        """Search for locations using geocoding service."""
        logger.info(f"Searching for locations: {query}")

        try:
            url = f"{self.geocoding_base_url}/search"
            params = {
                "q": query,
                "format": "json",
                "limit": limit,
                "addressdetails": 1,
                "extratags": 1,
            }

            headers = {
                "User-Agent": "AccessiWeather/1.0 (https://github.com/Orinks/AccessiWeather)"
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()

                candidates: list[tuple[float, Location]] = []
                fallbacks: list[tuple[float, Location]] = []
                for item in data:
                    score = self._score_geocoding_result(item)
                    location = self._parse_geocoding_result(item)
                    if location:
                        if score > 0:
                            candidates.append((score, location))
                        else:
                            fallbacks.append((score, location))

                if not candidates and not fallbacks:
                    logger.info(f"No suitable locations found for query: {query}")
                    return []

                # Sort by score (highest first) and deduplicate by name to keep results tidy.
                primary_pool = candidates if candidates else fallbacks
                primary_pool.sort(key=lambda entry: entry[0], reverse=True)
                unique_locations: dict[str, Location] = {}

                def add_from_pool(pool: list[tuple[float, Location]]) -> None:
                    for _, location in pool:
                        key = location.name.lower()
                        if key not in unique_locations:
                            unique_locations[key] = location
                        if len(unique_locations) >= limit:
                            break

                add_from_pool(primary_pool)

                if candidates and fallbacks and len(unique_locations) < limit:
                    fallbacks.sort(key=lambda entry: entry[0], reverse=True)
                    add_from_pool(fallbacks)

                locations = list(unique_locations.values())
                logger.info(f"Found {len(locations)} locations for query: {query}")
                return locations

        except Exception as e:
            logger.error(f"Failed to search locations: {e}")
            return []

    async def reverse_geocode(self, latitude: float, longitude: float) -> Location | None:
        """Get location name from coordinates."""
        logger.info(f"Reverse geocoding: {latitude}, {longitude}")

        try:
            url = f"{self.geocoding_base_url}/reverse"
            params = {
                "lat": latitude,
                "lon": longitude,
                "format": "json",
                "addressdetails": 1,
            }

            headers = {
                "User-Agent": "AccessiWeather/1.0 (https://github.com/Orinks/AccessiWeather)"
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()

                location = self._parse_geocoding_result(data)
                if location:
                    logger.info(f"Reverse geocoded to: {location.name}")
                    return location
                logger.warning("No location found for coordinates")
                return None

        except Exception as e:
            logger.error(f"Failed to reverse geocode: {e}")
            return None

    def _parse_geocoding_result(self, data: dict) -> Location | None:
        """Parse geocoding API result into Location object."""
        try:
            # Get coordinates
            lat = float(data.get("lat", 0))
            lon = float(data.get("lon", 0))

            # Build location name from address components
            address = data.get("address", {})
            display_name = data.get("display_name", "")

            # Try to build a nice name from address components
            name_parts = []

            # Add city/town/village/county - prioritize more specific locations
            location_found = False
            for key in ["city", "town", "village", "hamlet"]:
                if key in address:
                    name_parts.append(address[key])
                    location_found = True
                    break

            # If no city/town found, check for county
            if not location_found and "county" in address:
                name_parts.append(address["county"])

            # Add state/province
            for key in ["state", "province", "region"]:
                if key in address:
                    name_parts.append(address[key])
                    break

            # Add country if not US (to avoid redundancy)
            country = address.get("country", "")
            if country and country != "United States":
                name_parts.append(country)

            country_code = address.get("country_code")
            if country_code:
                country_code = country_code.upper()

            # Use constructed name or fall back to display name
            if name_parts:
                name = ", ".join(name_parts)
            else:
                # Fallback to display name, but truncate if too long
                name = display_name
                if len(name) > 50:
                    name = name[:47] + "..."

            return Location(name=name, latitude=lat, longitude=lon, country_code=country_code)

        except Exception as e:
            logger.error(f"Failed to parse geocoding result: {e}")
            return None

    def _score_geocoding_result(self, data: dict) -> float:
        """
        Compute a relevance score for a geocoding result.

        We prefer populated places (city/town/village) and de-prioritize large
        administrative boundaries (province/country) that tend to have coarse centroids.
        """
        addresstype = (data.get("addresstype") or "").lower()
        result_class = (data.get("class") or "").lower()
        extratags = data.get("extratags") or {}

        priority_map = {
            "city": 120,
            "town": 110,
            "village": 100,
            "hamlet": 90,
            "municipality": 85,
            "suburb": 80,
            "borough": 75,
            "county": 60,
            "state_district": 40,
            "state": 35,
            "province": 25,
            "region": 20,
            "country": 10,
        }

        score = priority_map.get(addresstype, 0)

        # Favor explicit place classifications over administrative boundaries.
        if result_class == "place":
            score += 15
        elif result_class == "boundary":
            score -= 10

        # Extratags often carry a more precise "place" hint; use it if present.
        place_hint = (extratags.get("place") or "").lower()
        if place_hint in {"city", "town", "village", "hamlet", "municipality"}:
            score += 20
        elif place_hint in {"province", "state", "region"}:
            score -= 15

        # Higher place_rank indicates finer-grained features.
        try:
            place_rank = float(data.get("place_rank", 0))
        except (TypeError, ValueError):
            place_rank = 0.0
        score += place_rank * 0.5

        # Importance ranges roughly 0-1; boost slightly to break ties.
        try:
            importance = float(data.get("importance", 0.0))
        except (TypeError, ValueError):
            importance = 0.0
        score += importance * 5

        # Discard extremely coarse matches (province/country) unless nothing else is available.
        if score <= 25 and addresstype in {"country", "province", "state", "region"}:
            return 0.0

        return score

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

        return None
