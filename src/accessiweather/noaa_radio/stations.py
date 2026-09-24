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
        status: Operational status reported by the station directory
            (e.g. 'NORMAL' or 'OUT OF SERVICE'); empty when unknown.

    """

    call_sign: str
    frequency: float
    name: str
    lat: float
    lon: float
    state: str
    status: str = ""

    @property
    def is_out_of_service(self) -> bool:
        """Return True when the directory reports the transmitter as out of service."""
        return self.status.strip().upper() == "OUT OF SERVICE"
