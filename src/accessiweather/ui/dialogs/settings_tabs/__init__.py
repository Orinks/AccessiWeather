"""Per-tab modules for the Settings dialog."""

from .advanced import AdvancedTab
from .ai import AITab
from .audio import AudioTab
from .data_sources import DataSourcesTab
from .display import DisplayTab
from .general import GeneralTab
from .notifications import NotificationsTab
from .updates import UpdatesTab

__all__ = [
    "GeneralTab",
    "DisplayTab",
    "DataSourcesTab",
    "NotificationsTab",
    "AudioTab",
    "UpdatesTab",
    "AITab",
    "AdvancedTab",
]
