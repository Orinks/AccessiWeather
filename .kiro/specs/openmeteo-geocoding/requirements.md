# Requirements Document

## Introduction

This feature migrates AccessiWeather's geocoding functionality from the current Nominatim/geopy implementation to Open-Meteo's Geocoding API. The Open-Meteo Geocoding API provides free, no-API-key-required geocoding that aligns with the existing Open-Meteo weather data integration. This migration simplifies dependencies, improves consistency across the application, and provides additional useful data like timezone and elevation information.

## Glossary

- **Geocoding**: The process of converting a place name, address, or ZIP code into geographic coordinates (latitude/longitude)
- **Reverse Geocoding**: The process of converting geographic coordinates into a human-readable location name
- **Open-Meteo Geocoding API**: A free geocoding service at `https://geocoding-api.open-meteo.com/v1/search` that returns location data including coordinates, timezone, country, and elevation
- **GeocodingService**: The existing AccessiWeather class that provides geocoding functionality to the application
- **OpenMeteoGeocodingClient**: The new client class that will communicate with the Open-Meteo Geocoding API
- **NWS**: National Weather Service, which only covers US locations
- **ZIP Code**: US postal code in 5-digit (XXXXX) or ZIP+4 (XXXXX-XXXX) format

## Requirements

### Requirement 1

**User Story:** As a user, I want to search for locations by name or address, so that I can add them to my weather locations list.

#### Acceptance Criteria

1. WHEN a user enters a location search query THEN the OpenMeteoGeocodingClient SHALL send a request to the Open-Meteo Geocoding API and return matching locations
2. WHEN the Open-Meteo Geocoding API returns results THEN the GeocodingService SHALL parse the response and extract latitude, longitude, display name, timezone, and country information
3. WHEN a user searches for a US ZIP code THEN the GeocodingService SHALL format the query appropriately and return matching US locations
4. WHEN the Open-Meteo Geocoding API returns no results THEN the GeocodingService SHALL return an empty result set without raising an exception
5. WHEN the Open-Meteo Geocoding API returns an error THEN the GeocodingService SHALL log the error and return None or an empty result set

### Requirement 2

**User Story:** As a user, I want location suggestions as I type, so that I can quickly find and select the location I'm looking for.

#### Acceptance Criteria

1. WHEN a user types a partial location name THEN the GeocodingService SHALL return up to a configurable number of location suggestions
2. WHEN suggesting locations THEN the GeocodingService SHALL include the location name, administrative region, and country in the display text
3. WHEN the data source is set to NWS THEN the GeocodingService SHALL filter suggestions to only include US locations
4. WHEN the data source is set to auto or a non-NWS source THEN the GeocodingService SHALL return worldwide location suggestions

### Requirement 3

**User Story:** As a developer, I want the geocoding client to follow the same patterns as the existing Open-Meteo weather client, so that the codebase remains consistent and maintainable.

#### Acceptance Criteria

1. THE OpenMeteoGeocodingClient SHALL use the httpx library for HTTP requests, consistent with OpenMeteoApiClient
2. THE OpenMeteoGeocodingClient SHALL implement retry logic with configurable max retries and retry delay
3. THE OpenMeteoGeocodingClient SHALL raise specific exception types (OpenMeteoGeocodingError, OpenMeteoGeocodingNetworkError) for different error conditions
4. THE OpenMeteoGeocodingClient SHALL accept configurable timeout, user agent, max retries, and retry delay parameters

### Requirement 4

**User Story:** As a user, I want my coordinates validated before adding a location, so that I don't accidentally add invalid locations.

#### Acceptance Criteria

1. WHEN validating coordinates THEN the GeocodingService SHALL verify latitude is between -90 and 90 degrees
2. WHEN validating coordinates THEN the GeocodingService SHALL verify longitude is between -180 and 180 degrees
3. WHEN the data source is NWS and coordinates are outside the US THEN the GeocodingService SHALL reject the coordinates
4. WHEN the data source is auto or non-NWS THEN the GeocodingService SHALL accept any valid global coordinates

### Requirement 5

**User Story:** As a developer, I want to remove the geopy dependency, so that the application has fewer external dependencies to maintain.

#### Acceptance Criteria

1. WHEN the migration is complete THEN the GeocodingService SHALL use OpenMeteoGeocodingClient instead of geopy's Nominatim
2. WHEN the migration is complete THEN the geopy package SHALL be removed from requirements.txt and pyproject.toml
3. THE GeocodingService SHALL maintain backward compatibility with existing callers (same method signatures and return types)

### Requirement 6

**User Story:** As a user, I want geocoding to work reliably even when the network is slow or unstable, so that I can still add locations under poor network conditions.

#### Acceptance Criteria

1. WHEN a network timeout occurs THEN the OpenMeteoGeocodingClient SHALL retry the request up to the configured maximum retries
2. WHEN all retries are exhausted THEN the OpenMeteoGeocodingClient SHALL raise an OpenMeteoGeocodingNetworkError with a descriptive message
3. WHEN the API returns a rate limit error (HTTP 429) THEN the OpenMeteoGeocodingClient SHALL raise an OpenMeteoGeocodingError indicating rate limiting

### Requirement 7

**User Story:** As a developer, I want comprehensive tests for the geocoding functionality, so that I can be confident the migration doesn't break existing functionality.

#### Acceptance Criteria

1. THE test suite SHALL include property-based tests for ZIP code validation using the same patterns as existing tests
2. THE test suite SHALL include property-based tests for coordinate validation
3. THE test suite SHALL include unit tests for the OpenMeteoGeocodingClient request/response handling
4. THE test suite SHALL include integration tests that can be run against the real Open-Meteo Geocoding API (marked to skip in CI)
