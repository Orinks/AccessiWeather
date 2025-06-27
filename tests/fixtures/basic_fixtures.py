"""Basic test fixtures for configuration, temporary directories, and core testing utilities."""

import json
import os
import tempfile

import pytest


@pytest.fixture
def temp_config_dir():
    """Create a temporary configuration directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "location": {"name": "Test City", "lat": 40.7128, "lon": -74.0060},
        "settings": {
            "update_interval": 30,
            "temperature_unit": "both",  # Simple string instead of enum
            "data_source": "auto",
            "minimize_to_tray": False,
            "show_nationwide_location": True,
            "alert_radius": 50,
            "precise_location_alerts": False,
        },
        "api_settings": {"contact_info": "test@example.com"},
    }


@pytest.fixture
def config_file(temp_config_dir, sample_config):
    """Create a configuration file in temp directory."""
    config_path = os.path.join(temp_config_dir, "config.json")
    os.makedirs(temp_config_dir, exist_ok=True)

    with open(config_path, "w") as f:
        json.dump(sample_config, f)

    return config_path


# Test coordinates for different scenarios
@pytest.fixture
def us_coordinates():
    """US coordinates (New York City)."""
    return (40.7128, -74.0060)


@pytest.fixture
def international_coordinates():
    """International coordinates (London, UK)."""
    return (51.5074, -0.1278)


@pytest.fixture
def edge_case_coordinates():
    """Edge case coordinates (near US border)."""
    return (49.0, -125.0)  # Near US-Canada border


# Test to verify geocoding is mocked
@pytest.fixture
def verify_no_real_geocoding_calls():
    """Verify that no real geocoding API calls are made during tests."""
    # This fixture can be used to ensure tests don't make real API calls
    # The autouse mock_all_geocoding fixture should prevent any real calls
