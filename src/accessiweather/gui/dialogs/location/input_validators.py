"""
Input validation utilities for location dialog components.

This module provides validation functions and error handling for location
input fields, coordinate validation, and user feedback mechanisms.
"""

import logging
from typing import Optional, Tuple

import wx

from .constants import (
    EMPTY_NAME_ERROR,
    INVALID_NUMBERS_ERROR,
    LATITUDE_RANGE_ERROR,
    LONGITUDE_RANGE_ERROR,
    MAX_LATITUDE,
    MAX_LONGITUDE,
    MIN_LATITUDE,
    MIN_LONGITUDE,
    NO_COORDINATES_ERROR,
    VALIDATION_ERROR_TITLE,
)

logger = logging.getLogger(__name__)


class CoordinateValidator:
    """Validator for latitude and longitude coordinates."""

    @staticmethod
    def validate_coordinate_range(lat: float, lon: float) -> Tuple[bool, Optional[str]]:
        """
        Validate that coordinates are within valid ranges.

        Args:
            lat: Latitude value
            lon: Longitude value

        Returns:
            Tuple of (is_valid, error_message)
        """
        if lat < MIN_LATITUDE or lat > MAX_LATITUDE:
            return False, LATITUDE_RANGE_ERROR

        if lon < MIN_LONGITUDE or lon > MAX_LONGITUDE:
            return False, LONGITUDE_RANGE_ERROR

        return True, None

    @staticmethod
    def parse_coordinates(
        lat_str: str, lon_str: str
    ) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """
        Parse coordinate strings into float values.

        Args:
            lat_str: Latitude string
            lon_str: Longitude string

        Returns:
            Tuple of (latitude, longitude, error_message)
        """
        try:
            lat = float(lat_str)
            lon = float(lon_str)
            return lat, lon, None
        except ValueError:
            return None, None, INVALID_NUMBERS_ERROR

    @staticmethod
    def validate_coordinates(
        lat_str: str, lon_str: str
    ) -> Tuple[bool, Optional[float], Optional[float], Optional[str]]:
        """
        Complete coordinate validation including parsing and range checking.

        Args:
            lat_str: Latitude string
            lon_str: Longitude string

        Returns:
            Tuple of (is_valid, latitude, longitude, error_message)
        """
        # Parse coordinates
        lat, lon, parse_error = CoordinateValidator.parse_coordinates(lat_str, lon_str)
        if parse_error:
            return False, None, None, parse_error

        # Validate range (only if we have valid coordinates)
        if lat is not None and lon is not None:
            is_valid, range_error = CoordinateValidator.validate_coordinate_range(lat, lon)
            if not is_valid:
                return False, lat, lon, range_error

        return True, lat, lon, None


class LocationInputValidator:
    """Validator for location dialog input fields."""

    @staticmethod
    def validate_location_name(name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate location name input.

        Args:
            name: Location name string

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not name.strip():
            return False, EMPTY_NAME_ERROR
        return True, None

    @staticmethod
    def validate_coordinates_exist(
        latitude: Optional[float], longitude: Optional[float]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that coordinates have been set.

        Args:
            latitude: Latitude value or None
            longitude: Longitude value or None

        Returns:
            Tuple of (is_valid, error_message)
        """
        if latitude is None or longitude is None:
            return False, NO_COORDINATES_ERROR
        return True, None

    @staticmethod
    def validate_search_query(query: str) -> Tuple[bool, Optional[str]]:
        """
        Validate search query input.

        Args:
            query: Search query string

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not query.strip():
            return False, "Please enter an address, city, or ZIP code to search"
        return True, None


class ValidationErrorHandler:
    """Handler for displaying validation errors to users."""

    @staticmethod
    def show_validation_error(
        parent: wx.Window, message: str, title: str = VALIDATION_ERROR_TITLE
    ) -> None:
        """
        Display a validation error message box.

        Args:
            parent: Parent window for the message box
            message: Error message to display
            title: Title for the message box
        """
        wx.MessageBox(message, title, wx.OK | wx.ICON_ERROR)

    @staticmethod
    def show_search_error(parent: wx.Window, message: str, title: str = "Search Error") -> None:
        """
        Display a search error message box.

        Args:
            parent: Parent window for the message box
            message: Error message to display
            title: Title for the message box
        """
        wx.MessageBox(message, title, wx.OK | wx.ICON_ERROR)


class AdvancedDialogValidator:
    """Specialized validator for the advanced location dialog."""

    def __init__(self, lat_ctrl: wx.TextCtrl, lon_ctrl: wx.TextCtrl):
        """
        Initialize the validator with text controls.

        Args:
            lat_ctrl: Latitude text control
            lon_ctrl: Longitude text control
        """
        self.lat_ctrl = lat_ctrl
        self.lon_ctrl = lon_ctrl

    def validate_and_get_coordinates(self) -> Tuple[bool, Optional[float], Optional[float]]:
        """
        Validate the current input and return coordinates if valid.

        Returns:
            Tuple of (is_valid, latitude, longitude)
        """
        lat_str = self.lat_ctrl.GetValue()
        lon_str = self.lon_ctrl.GetValue()

        is_valid, lat, lon, error_msg = CoordinateValidator.validate_coordinates(lat_str, lon_str)

        if not is_valid and error_msg:
            ValidationErrorHandler.show_validation_error(self.lat_ctrl.GetParent(), error_msg)

        return is_valid, lat, lon

    def get_coordinates_safe(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Get coordinates without validation, returning None for invalid values.

        Returns:
            Tuple of (latitude, longitude) or (None, None) if invalid
        """
        try:
            lat = float(self.lat_ctrl.GetValue())
            lon = float(self.lon_ctrl.GetValue())
            return lat, lon
        except ValueError:
            return None, None


class LocationDialogValidator:
    """Specialized validator for the main location dialog."""

    def __init__(
        self, name_ctrl: wx.TextCtrl, latitude: Optional[float], longitude: Optional[float]
    ):
        """
        Initialize the validator with dialog state.

        Args:
            name_ctrl: Location name text control
            latitude: Current latitude value
            longitude: Current longitude value
        """
        self.name_ctrl = name_ctrl
        self.latitude = latitude
        self.longitude = longitude

    def validate_for_save(self) -> bool:
        """
        Validate all required fields for saving the location.

        Returns:
            True if all validation passes, False otherwise
        """
        # Validate location name
        name = self.name_ctrl.GetValue().strip()
        is_name_valid, name_error = LocationInputValidator.validate_location_name(name)
        if not is_name_valid and name_error:
            ValidationErrorHandler.show_validation_error(self.name_ctrl.GetParent(), name_error)
            return False

        # Validate coordinates exist
        coords_valid, coords_error = LocationInputValidator.validate_coordinates_exist(
            self.latitude, self.longitude
        )
        if not coords_valid and coords_error:
            ValidationErrorHandler.show_validation_error(self.name_ctrl.GetParent(), coords_error)
            return False

        return True

    def update_coordinates(self, latitude: Optional[float], longitude: Optional[float]) -> None:
        """
        Update the stored coordinate values.

        Args:
            latitude: New latitude value
            longitude: New longitude value
        """
        self.latitude = latitude
        self.longitude = longitude
