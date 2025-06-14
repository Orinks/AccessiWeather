"""Shared test fixtures for AccessiWeather integration tests.

This module imports all fixtures from the fixtures package to make them
available to all tests. The fixtures are organized into logical modules:

- config_fixtures: Configuration and temporary directory fixtures
- client_fixtures: Mock client fixtures for API testing
- geocoding_fixtures: Geocoding service mocks and location fixtures
- service_fixtures: Service layer fixtures (LocationManager, WeatherService, etc.)
- sample_data_fixtures: Sample API response data for testing
- coordinate_fixtures: Test coordinate sets for different scenarios
- gui_fixtures: GUI testing fixtures and mocks
- performance_fixtures: Performance testing utilities
- api_mock_fixtures: Comprehensive API mocking for integration tests
"""

import sys
from pathlib import Path

# Add src to path before importing project modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import all fixtures to make them available to tests
# These imports make the fixtures available via pytest's fixture discovery
# flake8: noqa: E402
from tests.fixtures.api_mock_fixtures import *  # noqa: F401, F403
from tests.fixtures.client_fixtures import *  # noqa: F401, F403
from tests.fixtures.config_fixtures import *  # noqa: F401, F403
from tests.fixtures.coordinate_fixtures import *  # noqa: F401, F403
from tests.fixtures.geocoding_fixtures import *  # noqa: F401, F403
from tests.fixtures.gui_fixtures import *  # noqa: F401, F403
from tests.fixtures.performance_fixtures import *  # noqa: F401, F403
from tests.fixtures.sample_data_fixtures import *  # noqa: F401, F403
from tests.fixtures.service_fixtures import *  # noqa: F401, F403
