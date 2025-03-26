"""Tests for the geocoding service"""

import pytest
from unittest.mock import patch, MagicMock

from accessiweather.geocoding import GeocodingService
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


class TestGeocodingService:
    """Test suite for GeocodingService"""

    @patch('accessiweather.geocoding.Nominatim')
    def test_init(self, mock_nominatim):
        """Test initialization"""
        # Create a service
        service = GeocodingService(user_agent="Test App")
        
        # Check that Nominatim was initialized correctly
        mock_nominatim.assert_called_once_with(user_agent="Test App")
        assert service.geolocator == mock_nominatim.return_value

    @patch('accessiweather.geocoding.Nominatim')
    def test_geocode_address_success(self, mock_nominatim):
        """Test successful geocoding of an address"""
        # Set up mock
        mock_location = MagicMock()
        mock_location.latitude = 35.0
        mock_location.longitude = -80.0
        mock_location.address = "123 Main St, City, State"
        
        mock_geolocator = MagicMock()
        mock_geolocator.geocode.return_value = mock_location
        mock_nominatim.return_value = mock_geolocator
        
        # Create a service and geocode an address
        service = GeocodingService()
        result = service.geocode_address("123 Main St")
        
        # Check that geocode was called
        mock_geolocator.geocode.assert_called_once_with("123 Main St")
        
        # Check result
        assert result == (35.0, -80.0, "123 Main St, City, State")
    
    @patch('accessiweather.geocoding.Nominatim')
    def test_geocode_zip_code(self, mock_nominatim):
        """Test geocoding a zip code"""
        # Set up mock
        mock_location = MagicMock()
        mock_location.latitude = 35.0
        mock_location.longitude = -80.0
        mock_location.address = "City, State 12345, USA"
        
        mock_geolocator = MagicMock()
        mock_geolocator.geocode.return_value = mock_location
        mock_nominatim.return_value = mock_geolocator
        
        # Create a service and geocode a zip code
        service = GeocodingService()
        result = service.geocode_address("12345")
        
        # Check that geocode was called with USA suffix for zip codes
        mock_geolocator.geocode.assert_called_once_with("12345, USA")
        
        # Check result
        assert result == (35.0, -80.0, "City, State 12345, USA")
    
    @patch('accessiweather.geocoding.Nominatim')
    def test_geocode_address_not_found(self, mock_nominatim):
        """Test geocoding an address that isn't found"""
        # Set up mock
        mock_geolocator = MagicMock()
        mock_geolocator.geocode.return_value = None
        mock_nominatim.return_value = mock_geolocator
        
        # Create a service and try to geocode a nonexistent address
        service = GeocodingService()
        result = service.geocode_address("Nonexistent Address")
        
        # Check that geocode was called
        mock_geolocator.geocode.assert_called_once_with("Nonexistent Address")
        
        # Check result
        assert result is None
    
    @patch('accessiweather.geocoding.Nominatim')
    def test_geocode_address_timeout(self, mock_nominatim):
        """Test handling of geocoder timeout"""
        # Set up mock
        mock_geolocator = MagicMock()
        mock_geolocator.geocode.side_effect = GeocoderTimedOut("Timeout")
        mock_nominatim.return_value = mock_geolocator
        
        # Create a service and try to geocode an address
        service = GeocodingService()
        result = service.geocode_address("123 Main St")
        
        # Check that geocode was called
        mock_geolocator.geocode.assert_called_once_with("123 Main St")
        
        # Check result
        assert result is None

    @patch('accessiweather.geocoding.Nominatim')
    def test_geocode_address_service_error(self, mock_nominatim):
        """Test handling of geocoder service error"""
        # Set up mock
        mock_geolocator = MagicMock()
        mock_geolocator.geocode.side_effect = GeocoderServiceError("Service Error")
        mock_nominatim.return_value = mock_geolocator
        
        # Create a service and try to geocode an address
        service = GeocodingService()
        result = service.geocode_address("123 Main St")
        
        # Check that geocode was called
        mock_geolocator.geocode.assert_called_once_with("123 Main St")
        
        # Check result
        assert result is None
