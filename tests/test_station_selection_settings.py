from accessiweather.models import AppSettings


def test_station_selection_strategy_defaults_for_legacy_config():
    settings = AppSettings.from_dict({"data_source": "nws"})
    assert settings.station_selection_strategy == "hybrid_default"


def test_station_selection_strategy_invalid_value_is_safely_corrected():
    settings = AppSettings.from_dict({"station_selection_strategy": "weird"})
    settings.validate_on_access("station_selection_strategy")
    assert settings.station_selection_strategy == "hybrid_default"
