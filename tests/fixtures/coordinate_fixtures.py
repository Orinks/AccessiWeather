"""Coordinate-related test fixtures."""

import pytest


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
