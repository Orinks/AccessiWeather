"""Tests for the geocoding service"""

from unittest.mock import MagicMock, patch

from geopy.exc import GeocoderServiceError, GeocoderTimedOut

from accessiweather.geocoding import GeocodingService


class TestGeocodingService:
    """Test suite for GeocodingService"""

    @patch("accessiweather.geocoding.Nominatim")
    def test_init(self, mock_nominatim):
        """Test initialization"""
        # Create a service
        service = GeocodingService(user_agent="Test App", timeout=20)

        # Check that Nominatim was initialized correctly
        mock_nominatim.assert_called_once_with(user_agent="Test App", timeout=20)
        assert service.geolocator == mock_nominatim.return_value

    @patch("accessiweather.geocoding.Nominatim")
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

    def test_is_zip_code(self):
        """Test ZIP code detection"""
        service = GeocodingService()

        # Test valid ZIP codes
        assert service.is_zip_code("12345") is True
        assert service.is_zip_code("12345-6789") is True

        # Test invalid ZIP codes
        assert service.is_zip_code("1234") is False  # Too short
        assert service.is_zip_code("123456") is False  # Too long
        assert service.is_zip_code("abcde") is False  # Not digits
        assert service.is_zip_code("12345-") is False  # Incomplete ZIP+4
        assert service.is_zip_code("12345-67") is False  # Incomplete ZIP+4
        assert service.is_zip_code("New York") is False  # Not a ZIP code

    def test_format_zip_code(self):
        """Test ZIP code formatting"""
        service = GeocodingService()

        # Test 5-digit ZIP code
        assert service.format_zip_code("12345") == "12345, USA"

        # Test ZIP+4 code (should extract the 5-digit base)
        assert service.format_zip_code("12345-6789") == "12345, USA"

    @patch("accessiweather.geocoding.Nominatim")
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

    @patch("accessiweather.geocoding.Nominatim")
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

    @patch("accessiweather.geocoding.Nominatim")
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

    @patch("accessiweather.geocoding.Nominatim")
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

    @patch("accessiweather.geocoding.Nominatim")
    def test_geocode_zip_plus_4(self, mock_nominatim):
        """Test geocoding a ZIP+4 code"""
        # Set up mock
        mock_location = MagicMock()
        mock_location.latitude = 35.0
        mock_location.longitude = -80.0
        mock_location.address = "City, State 12345, USA"

        mock_geolocator = MagicMock()
        mock_geolocator.geocode.return_value = mock_location
        mock_nominatim.return_value = mock_geolocator

        # Create a service and geocode a ZIP+4 code
        service = GeocodingService()
        result = service.geocode_address("12345-6789")

        # Check that geocode was called with just the 5-digit base and USA suffix
        mock_geolocator.geocode.assert_called_once_with("12345, USA")

        # Check result
        assert result == (35.0, -80.0, "City, State 12345, USA")

    @patch("accessiweather.geocoding.Nominatim")
    def test_suggest_locations_with_zip_code(self, mock_nominatim):
        """Test location suggestions with a ZIP code"""
        # Set up mock locations
        mock_location1 = MagicMock()
        mock_location1.address = "City1, State 12345, USA"

        mock_location2 = MagicMock()
        mock_location2.address = "City2, State 12345, USA"

        mock_geolocator = MagicMock()
        mock_geolocator.geocode.return_value = [mock_location1, mock_location2]
        mock_nominatim.return_value = mock_geolocator

        # Create a service and get suggestions for a ZIP code
        service = GeocodingService()
        suggestions = service.suggest_locations("12345")

        # Check that geocode was called with USA suffix for ZIP codes
        mock_geolocator.geocode.assert_called_once_with("12345, USA", exactly_one=False, limit=5)

        # Check suggestions
        assert suggestions == ["City1, State 12345, USA", "City2, State 12345, USA"]
