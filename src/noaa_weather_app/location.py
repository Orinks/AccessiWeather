"""Location handling for NOAA weather app

This module handles location storage and retrieval.
"""

import json
import os
from typing import Dict, Tuple, List, Optional
import logging

logger = logging.getLogger(__name__)

class LocationManager:
    """Manager for handling saved locations"""
    
    def __init__(self, config_dir: str = None):
        """Initialize the location manager
        
        Args:
            config_dir: Directory for config files, defaults to user's home directory
        """
        if config_dir is None:
            self.config_dir = os.path.expanduser("~/.noaa_weather_app")
        else:
            self.config_dir = config_dir
            
        self.locations_file = os.path.join(self.config_dir, "locations.json")
        self.current_location = None
        self.saved_locations = {}
        
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Load saved locations
        self._load_locations()
    
    def _load_locations(self) -> None:
        """Load saved locations from file"""
        try:
            if os.path.exists(self.locations_file):
                with open(self.locations_file, 'r') as f:
                    data = json.load(f)
                    self.saved_locations = data.get("locations", {})
                    
                    # Set current location if available
                    current = data.get("current")
                    if current and current in self.saved_locations:
                        self.current_location = current
        except Exception as e:
            logger.error(f"Failed to load locations: {str(e)}")
            self.saved_locations = {}
            self.current_location = None
    
    def _save_locations(self) -> None:
        """Save locations to file"""
        try:
            data = {
                "locations": self.saved_locations,
                "current": self.current_location
            }
            
            with open(self.locations_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save locations: {str(e)}")
    
    def add_location(self, name: str, lat: float, lon: float) -> None:
        """Add a new location
        
        Args:
            name: Location name
            lat: Latitude
            lon: Longitude
        """
        self.saved_locations[name] = {"lat": lat, "lon": lon}
        
        # If this is the first location, make it current
        if self.current_location is None:
            self.current_location = name
            
        self._save_locations()
    
    def remove_location(self, name: str) -> bool:
        """Remove a location
        
        Args:
            name: Location name to remove
            
        Returns:
            True if location was removed, False otherwise
        """
        if name in self.saved_locations:
            del self.saved_locations[name]
            
            # If we removed the current location, update it
            if self.current_location == name:
                self.current_location = next(iter(self.saved_locations)) if self.saved_locations else None
                
            self._save_locations()
            return True
        
        return False
    
    def set_current_location(self, name: str) -> bool:
        """Set the current location
        
        Args:
            name: Location name
            
        Returns:
            True if successful, False if location doesn't exist
        """
        if name in self.saved_locations:
            self.current_location = name
            self._save_locations()
            return True
        
        return False
    
    def get_current_location(self) -> Optional[Tuple[str, float, float]]:
        """Get the current location
        
        Returns:
            Tuple of (name, lat, lon) if current location exists, None otherwise
        """
        if self.current_location and self.current_location in self.saved_locations:
            loc = self.saved_locations[self.current_location]
            return (self.current_location, loc["lat"], loc["lon"])
        
        return None
    
    def get_all_locations(self) -> List[str]:
        """Get all saved location names
        
        Returns:
            List of location names
        """
        return list(self.saved_locations.keys())
