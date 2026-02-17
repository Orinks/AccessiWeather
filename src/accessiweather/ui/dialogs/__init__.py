"""wxPython dialogs for AccessiWeather."""

import importlib as _importlib

__all__ = [
    "show_add_location_dialog",
    "show_air_quality_dialog",
    "show_alert_dialog",
    "show_aviation_dialog",
    "show_discussion_dialog",
    "show_explanation_dialog",
    "show_nationwide_discussion_dialog",
    "show_settings_dialog",
    "show_soundpack_manager_dialog",
    "show_uv_index_dialog",
    "show_weather_assistant_dialog",
    "show_weather_history_dialog",
    "NOAARadioDialog",
    "show_noaa_radio_dialog",
    "SoundPackWizardDialog",
]

_LAZY_IMPORTS = {
    "show_air_quality_dialog": ".air_quality_dialog",
    "show_alert_dialog": ".alert_dialog",
    "show_aviation_dialog": ".aviation_dialog",
    "show_discussion_dialog": ".discussion_dialog",
    "show_explanation_dialog": ".explanation_dialog",
    "show_add_location_dialog": ".location_dialog",
    "show_nationwide_discussion_dialog": ".nationwide_discussion_dialog",
    "NOAARadioDialog": ".noaa_radio_dialog",
    "show_noaa_radio_dialog": ".noaa_radio_dialog",
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
