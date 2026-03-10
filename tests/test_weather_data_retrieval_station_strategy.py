from types import SimpleNamespace

from accessiweather.services.weather_service.weather_data_retrieval import WeatherDataRetrieval


def test_get_current_conditions_passes_station_strategy_to_nws_client():
    calls = {}

    def _get_current_conditions(lat: float, lon: float, **kwargs):
        calls["kwargs"] = kwargs
        return {"ok": True}

    nws_client = SimpleNamespace(get_current_conditions=_get_current_conditions)
    api_client_manager = SimpleNamespace(
        _should_use_openmeteo=lambda lat, lon: False,
        config={"settings": {"station_selection_strategy": "freshest_observation"}},
    )
    fallback_handler = SimpleNamespace(try_fallback_api=lambda *args, **kwargs: None)

    retrieval = WeatherDataRetrieval(nws_client, api_client_manager, fallback_handler)
    result = retrieval.get_current_conditions(40.0, -86.0, force_refresh=True)

    assert result == {"ok": True}
    assert calls["kwargs"]["station_selection_strategy"] == "freshest_observation"
    assert calls["kwargs"]["force_refresh"] is True
