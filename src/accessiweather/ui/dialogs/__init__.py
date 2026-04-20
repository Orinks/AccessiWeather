import importlib as _importlib

from .air_quality_dialog import show_air_quality_dialog
from .alert_dialog import show_alert_dialog
from .alerts_summary_dialog import show_alerts_summary_dialog
from .aviation_dialog import show_aviation_dialog
from .discussion_dialog import show_discussion_dialog
from .explanation_dialog import show_explanation_dialog
from .forecast_products_dialog import show_forecast_products_dialog
from .location_dialog import show_add_location_dialog, show_edit_location_dialog
from .nationwide_discussion_dialog import show_nationwide_discussion_dialog
from .noaa_radio_dialog import NOAARadioDialog, show_noaa_radio_dialog
from .precipitation_timeline_dialog import show_precipitation_timeline_dialog
from .settings_dialog import show_settings_dialog
from .soundpack_manager_dialog import show_soundpack_manager_dialog
from .soundpack_wizard_dialog import SoundPackWizardDialog
from .uv_index_dialog import show_uv_index_dialog
from .weather_assistant_dialog import show_weather_assistant_dialog
from .weather_history_dialog import show_weather_history_dialog

__all__ = [
    "show_add_location_dialog",
    "show_edit_location_dialog",
    "show_air_quality_dialog",
    "show_alert_dialog",
    "show_alerts_summary_dialog",
    "show_aviation_dialog",
    "show_discussion_dialog",
    "show_explanation_dialog",
    "show_forecast_products_dialog",
    "show_nationwide_discussion_dialog",
    "show_settings_dialog",
    "show_soundpack_manager_dialog",
    "show_uv_index_dialog",
    "show_weather_assistant_dialog",
    "show_weather_history_dialog",
    "NOAARadioDialog",
    "show_noaa_radio_dialog",
    "show_precipitation_timeline_dialog",
    "SoundPackWizardDialog",
]

_LAZY_IMPORTS = {
    "show_air_quality_dialog": ".air_quality_dialog",
    "show_alert_dialog": ".alert_dialog",
    "show_alerts_summary_dialog": ".alerts_summary_dialog",
    "show_aviation_dialog": ".aviation_dialog",
    "show_discussion_dialog": ".discussion_dialog",
    "show_explanation_dialog": ".explanation_dialog",
    "show_forecast_products_dialog": ".forecast_products_dialog",
    "show_add_location_dialog": ".location_dialog",
    "show_edit_location_dialog": ".location_dialog",
    "show_nationwide_discussion_dialog": ".nationwide_discussion_dialog",
    "NOAARadioDialog": ".noaa_radio_dialog",
    "show_noaa_radio_dialog": ".noaa_radio_dialog",
    "show_precipitation_timeline_dialog": ".precipitation_timeline_dialog",
    "show_settings_dialog": ".settings_dialog",
    "show_soundpack_manager_dialog": ".soundpack_manager_dialog",
    "SoundPackWizardDialog": ".soundpack_wizard_dialog",
    "show_uv_index_dialog": ".uv_index_dialog",
    "show_weather_assistant_dialog": ".weather_assistant_dialog",
    "show_weather_history_dialog": ".weather_history_dialog",
}


def __getattr__(name):
    if name in _LAZY_IMPORTS:
        module = _importlib.import_module(_LAZY_IMPORTS[name], __name__)
        return getattr(module, name)
    # Allow submodule access
    try:
        return _importlib.import_module(f".{name}", __name__)
    except ImportError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
