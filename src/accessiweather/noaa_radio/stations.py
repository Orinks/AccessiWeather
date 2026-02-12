"""NOAA Weather Radio station data model."""

from dataclasses import dataclass


@dataclass
class Station:
    """
    Represents a NOAA Weather Radio station.

    Attributes:
        call_sign: FCC call sign (e.g., 'KEC49').
        frequency: Broadcast frequency in MHz (e.g., 162.550).
        name: Human-readable station/transmitter name.
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
        state: US state abbreviation.

    """

    call_sign: str
    frequency: float
    name: str
    lat: float
    lon: float
    state: str
