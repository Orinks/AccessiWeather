"""Tests for AVWX REST API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.api.avwx_client import (
    AVWX_BASE_URL,
    AvwxApiError,
    _build_aviation_data,
    _build_decoded_taf,
    _format_avwx_time,
    _format_period,
    fetch_avwx_taf,
    is_us_station,
)
from accessiweather.models.weather import AviationData

# ---------------------------------------------------------------------------
# is_us_station
# ---------------------------------------------------------------------------


class TestIsUsStation:
    def test_k_prefix_is_us(self):
        assert is_us_station("KJFK") is True

    def test_k_prefix_any_case(self):
        assert is_us_station("kjfk") is True

    def test_alaska_pa_prefix(self):
        assert is_us_station("PANC") is True

    def test_hawaii_ph_prefix(self):
        assert is_us_station("PHNL") is True

    def test_guam_pg_prefix(self):
        assert is_us_station("PGUM") is True

    def test_international_eg_is_not_us(self):
        assert is_us_station("EGLL") is False

    def test_international_rj_is_not_us(self):
        assert is_us_station("RJTT") is False

    def test_international_ys_is_not_us(self):
        assert is_us_station("YSSY") is False

    def test_international_lf_is_not_us(self):
        assert is_us_station("LFPG") is False

    def test_empty_string(self):
        assert is_us_station("") is False

    def test_none_coerced(self):
        assert is_us_station(None) is False


# ---------------------------------------------------------------------------
# _format_avwx_time
# ---------------------------------------------------------------------------


class TestFormatAvwxTime:
    def test_none_returns_none(self):
        assert _format_avwx_time(None) is None

    def test_string_passthrough(self):
        assert _format_avwx_time("1812/1912") == "1812/1912"

    def test_dict_with_dt_iso(self):
        time_data = {"dt": "2024-01-07T18:00:00+00:00", "repr": "0718/0918"}
        result = _format_avwx_time(time_data)
        assert result is not None
        assert "18:00Z" in result
        assert "7th" in result

    def test_dict_with_repr_fallback(self):
        time_data = {"repr": "0718/0918"}
        result = _format_avwx_time(time_data)
        assert result == "0718/0918"

    def test_dict_empty(self):
        assert _format_avwx_time({}) is None

    def test_invalid_dt_falls_back_to_repr(self):
        time_data = {"dt": "not-a-date", "repr": "0718/0918"}
        result = _format_avwx_time(time_data)
        assert result == "0718/0918"


# ---------------------------------------------------------------------------
# _format_period
# ---------------------------------------------------------------------------


class TestFormatPeriod:
    def test_from_period_with_speech(self):
        period = {
            "type": "FM",
            "start_time": {"repr": "0718"},
            "speech": "Winds from the west at 15kt.",
        }
        lines = _format_period(period, None)
        assert any("From" in line for line in lines)
        assert any("Winds from the west" in line for line in lines)

    def test_tempo_period(self):
        period = {
            "type": "TEMPO",
            "start_time": {"repr": "0720"},
            "end_time": {"repr": "0724"},
        }
        trans = {"wind": "Variable winds", "visibility": "3 miles", "wx_codes": "rain"}
        lines = _format_period(period, trans)
        assert any("Temporary" in line for line in lines)
        assert any("Variable winds" in line for line in lines)
        assert any("3 miles" in line for line in lines)

    def test_becmg_period(self):
        period = {"type": "BECMG", "start_time": {"repr": "0802"}}
        lines = _format_period(period, None)
        assert any("Becoming" in line for line in lines)

    def test_prob_period(self):
        period = {
            "type": "PROB",
            "probability": {"value": 30},
            "start_time": {"repr": "0806"},
        }
        lines = _format_period(period, None)
        header = next(line for line in lines if "Probability" in line or "30%" in line)
        assert header is not None

    def test_flight_rules_included(self):
        period = {
            "type": "FM",
            "flight_rules": "VFR",
            "start_time": {"repr": "0718"},
        }
        trans = {"wind": "10kt"}
        lines = _format_period(period, trans)
        assert any("VFR" in line for line in lines)

    def test_raw_fallback_when_no_trans_no_speech(self):
        period = {
            "type": "FM",
            "raw": "27010KT 9999 FEW020",
            "start_time": {"repr": "0718"},
        }
        lines = _format_period(period, None)
        assert any("27010KT" in line for line in lines)


# ---------------------------------------------------------------------------
# _build_decoded_taf
# ---------------------------------------------------------------------------


class TestBuildDecodedTaf:
    def test_uses_top_level_speech_when_available(self):
        data = {
            "speech": "Terminal Aerodrome Forecast for London Heathrow.",
            "forecast": [],
        }
        result = _build_decoded_taf("EGLL", data, {"name": "London Heathrow Airport"})
        assert result == "Terminal Aerodrome Forecast for London Heathrow."

    def test_builds_from_periods_when_no_speech(self):
        data = {
            "speech": "",
            "start_time": {"repr": "0718/0918"},
            "end_time": {"repr": "0718/0918"},
            "forecast": [
                {
                    "type": "FM",
                    "speech": "Winds 270 at 10kt.",
                    "start_time": {"repr": "0718"},
                }
            ],
        }
        result = _build_decoded_taf("EGLL", data, {"name": "London Heathrow Airport"})
        assert "London Heathrow Airport" in result
        assert "Winds 270 at 10kt." in result

    def test_station_fallback_when_no_info(self):
        data = {"speech": "", "forecast": []}
        result = _build_decoded_taf("RJTT", data, {})
        assert "RJTT" in result


# ---------------------------------------------------------------------------
# _build_aviation_data
# ---------------------------------------------------------------------------


class TestBuildAviationData:
    def test_basic_structure(self):
        data = {
            "raw": "TAF EGLL 071730Z 0718/0824 27010KT 9999 FEW020",
            "speech": "Terminal Aerodrome Forecast for London Heathrow.",
            "info": {"name": "London Heathrow Airport"},
            "forecast": [],
        }
        result = _build_aviation_data("EGLL", data)
        assert isinstance(result, AviationData)
        assert result.station_id == "EGLL"
        assert result.airport_name == "London Heathrow Airport"
        assert result.raw_taf is not None
        assert "EGLL" in result.raw_taf
        assert result.decoded_taf == "Terminal Aerodrome Forecast for London Heathrow."

    def test_missing_raw_taf(self):
        data = {
            "speech": "No data.",
            "info": {},
            "forecast": [],
        }
        result = _build_aviation_data("RJTT", data)
        assert result.raw_taf is None

    def test_city_fallback_for_airport_name(self):
        data = {
            "info": {"city": "Tokyo"},
            "forecast": [],
        }
        result = _build_aviation_data("RJTT", data)
        assert result.airport_name == "Tokyo"


# ---------------------------------------------------------------------------
# fetch_avwx_taf (async, mocked HTTP)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFetchAvwxTaf:
    def _make_response(self, status_code: int, json_data: dict) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_data
        return mock_resp

    async def test_successful_fetch(self):
        payload = {
            "raw": "TAF EGLL 071730Z 0718/0824 27010KT 9999 FEW020",
            "speech": "TAF for London Heathrow.",
            "info": {"name": "London Heathrow Airport"},
            "forecast": [],
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=self._make_response(200, payload))

        result = await fetch_avwx_taf("EGLL", "test-key", http_client=mock_client)

        assert result.station_id == "EGLL"
        assert result.airport_name == "London Heathrow Airport"
        assert result.decoded_taf == "TAF for London Heathrow."
        assert result.raw_taf is not None

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert f"{AVWX_BASE_URL}/taf/EGLL" in call_args[0][0]
        assert call_args[1]["params"]["token"] == "test-key"

    async def test_station_uppercased(self):
        payload = {
            "raw": "TAF EGLL ...",
            "speech": "TAF for EGLL.",
            "info": {},
            "forecast": [],
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=self._make_response(200, payload))

        result = await fetch_avwx_taf("egll", "key", http_client=mock_client)
        assert result.station_id == "EGLL"

    async def test_401_raises_avwx_error(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=self._make_response(401, {}))

        with pytest.raises(AvwxApiError, match="invalid or expired"):
            await fetch_avwx_taf("EGLL", "bad-key", http_client=mock_client)

    async def test_404_raises_avwx_error(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=self._make_response(404, {}))

        with pytest.raises(AvwxApiError, match="not found"):
            await fetch_avwx_taf("ZZZZ", "key", http_client=mock_client)

    async def test_500_raises_avwx_error(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=self._make_response(500, {}))

        with pytest.raises(AvwxApiError, match="HTTP 500"):
            await fetch_avwx_taf("EGLL", "key", http_client=mock_client)

    async def test_empty_station_raises_value_error(self):
        mock_client = AsyncMock()
        with pytest.raises(ValueError, match="non-empty"):
            await fetch_avwx_taf("", "key", http_client=mock_client)

    async def test_creates_own_client_when_none_provided(self):
        """When no http_client is given, the function creates and closes its own."""
        payload = {
            "raw": "TAF EGLL 071730Z 0718/0824 27010KT 9999",
            "speech": "",
            "info": {},
            "forecast": [],
        }
        mock_resp = self._make_response(200, payload)

        async def fake_get(*args, **kwargs):
            return mock_resp

        mock_internal_client = AsyncMock()
        mock_internal_client.get = AsyncMock(side_effect=fake_get)
        mock_internal_client.aclose = AsyncMock()

        with patch(
            "accessiweather.api.avwx_client.httpx.AsyncClient",
            return_value=mock_internal_client,
        ):
            result = await fetch_avwx_taf("EGLL", "key")

        mock_internal_client.aclose.assert_called_once()
        assert result.station_id == "EGLL"
