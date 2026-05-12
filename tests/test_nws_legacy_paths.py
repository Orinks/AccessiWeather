"""Regression tests for legacy NWS wrapper paths."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from accessiweather.api.nws import NwsApiWrapper
from accessiweather.api_client import NoaaApiClient
from accessiweather.api_wrapper import NoaaApiWrapper


def test_legacy_precise_alerts_use_point_query_not_zone():
    client = NoaaApiClient()
    client.identify_location_type = MagicMock(return_value=("county", "NYC061"))  # type: ignore[method-assign]
    client._make_request = MagicMock(return_value={"features": []})  # type: ignore[method-assign]

    assert client.get_alerts(40.7128, -74.006, precise_location=True) == {"features": []}

    client.identify_location_type.assert_not_called()
    client._make_request.assert_called_once_with(
        "alerts/active",
        params={"point": "40.7128,-74.006"},
        force_refresh=False,
    )


def test_legacy_alert_fallback_omits_unsupported_radius_parameter():
    client = NoaaApiClient()
    client.identify_location_type = MagicMock(return_value=(None, None))  # type: ignore[method-assign]
    client._make_request = MagicMock(return_value={"features": []})  # type: ignore[method-assign]

    assert client.get_alerts(40.7128, -74.006, precise_location=False, radius=50) == {
        "features": []
    }

    client._make_request.assert_called_once_with(
        "alerts/active",
        params={"point": "40.7128,-74.006"},
        force_refresh=False,
    )


def test_nws_wrapper_alert_fallback_omits_unsupported_radius_parameter():
    wrapper = NwsApiWrapper(min_request_interval=0)
    wrapper.point_location.identify_location_type = MagicMock(return_value=(None, None))

    with (
        patch.object(wrapper, "_get_cached_or_fetch", side_effect=lambda _key, fn, _force: fn()),
        patch("accessiweather.api.nws.alerts_discussions.httpx") as mock_httpx,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"features": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_httpx.Client.return_value = mock_client
        mock_httpx.Timeout = MagicMock()

        wrapper.get_alerts(40.7128, -74.006, precise_location=False, radius=50)

    requested_url = mock_client.get.call_args.args[0]
    assert requested_url == "https://api.weather.gov/alerts/active?point=40.7128,-74.006"


def test_nws_point_transform_preserves_problem_detail_errors():
    wrapper = NwsApiWrapper(min_request_interval=0)
    problem = SimpleNamespace(
        to_dict=lambda: {
            "status": 404,
            "title": "Data Unavailable For Requested Point",
            "detail": "Unable to provide data for requested point",
        }
    )

    result = wrapper.point_location._transform_point_data(problem)

    assert result["status"] == 404
    assert result["title"] == "Data Unavailable For Requested Point"


def test_nws_wrapper_national_aliases_use_iem_afos_instead_of_weather_gov_product_types():
    wrapper = NwsApiWrapper(min_request_interval=0)

    with (
        patch(
            "accessiweather.api.nws.alerts_discussions.fetch_iem_national_product",
            return_value="WPC short range text",
        ) as mock_iem,
        patch.object(wrapper, "_fetch_url") as mock_weather_gov,
    ):
        result = wrapper.get_national_product("FXUS01", "KWNH", force_refresh=True)

    assert result == "WPC short range text"
    mock_iem.assert_called_once()
    mock_weather_gov.assert_not_called()


def test_legacy_national_aliases_use_iem_afos_instead_of_weather_gov_product_types():
    client = NoaaApiClient()

    with (
        patch(
            "accessiweather.api_client.alerts_and_products.fetch_iem_national_product",
            return_value="SPC day one text",
        ) as mock_iem,
        patch.object(client, "_make_request") as mock_weather_gov,
    ):
        result = client.get_national_product("ACUS01", "KWNS", force_refresh=True)

    assert result == "SPC day one text"
    mock_iem.assert_called_once()
    mock_weather_gov.assert_not_called()


def test_nws_national_product_helper_maps_to_iem_afos():
    with patch(
        "accessiweather.nws_national_products.fetch_iem_afos_text_sync",
        return_value=SimpleNamespace(product_text="NHC outlook"),
    ) as mock_iem:
        from accessiweather.nws_national_products import fetch_iem_national_product

        result = fetch_iem_national_product("MIATWOAT", "KNHC")

    assert result == "NHC outlook"
    mock_iem.assert_called_once()
    assert mock_iem.call_args.args[0] == "TWOAT"


def test_auto_provider_selects_nws_for_alaska_hawaii_and_puerto_rico():
    wrapper = NoaaApiWrapper(min_request_interval=0, preferred_provider="auto")

    assert wrapper.get_active_provider(61.2181, -149.9003) == "nws"
    assert wrapper.get_active_provider(21.3069, -157.8583) == "nws"
    assert wrapper.get_active_provider(18.4655, -66.1057) == "nws"
    assert wrapper.get_active_provider(51.5074, -0.1278) == "openmeteo"
