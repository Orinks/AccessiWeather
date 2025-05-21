from enum import Enum


class AlertCategory(str, Enum):
    CBRNE = "CBRNE"
    ENV = "Env"
    FIRE = "Fire"
    GEO = "Geo"
    HEALTH = "Health"
    INFRA = "Infra"
    MET = "Met"
    OTHER = "Other"
    RESCUE = "Rescue"
    SAFETY = "Safety"
    SECURITY = "Security"
    TRANSPORT = "Transport"

    def __str__(self) -> str:
        return str(self.value)
