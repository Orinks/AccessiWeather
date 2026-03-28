"""
Regression tests for daily forecast timezone handling.

Covers the bug where non-UTC locations (e.g. UTC+1 BST) could see a calendar
day skipped or duplicated in the 7-day forecast window because
parse_openmeteo_forecast did not forward utc_offset_seconds to
_parse_iso_datetime, and _select_periods_by_day_window could choke when
comparing tz-aware and naive start_time values.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from accessiweather.display.presentation.forecast import _select_periods_by_day_window
from accessiweather.models.weather import Forecast, ForecastPeriod
from accessiweather.weather_client_openmeteo import parse_openmeteo_forecast

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BST = timezone(timedelta(hours=1))  # UTC+1 (British Summer Time)
_IST = timezone(timedelta(hours=5, minutes=30))  # UTC+5:30 (India)
_NZDT = timezone(timedelta(hours=13))  # UTC+13 (NZ Daylight Time)
_ART = timezone(timedelta(hours=-3))  # UTC-3 (Argentina)


def _make_openmeteo_payload(
    start_date: str,
    n_days: int,
    utc_offset_seconds: int | None,
) -> dict:
    """Build a minimal Open-Meteo daily forecast payload."""
    from datetime import date as _date

    base = _date.fromisoformat(start_date)
    dates = [(base + timedelta(days=i)).isoformat() for i in range(n_days)]
    return {
        "utc_offset_seconds": utc_offset_seconds,
        "daily": {
            "time": dates,
            "temperature_2m_max": [20.0 + i for i in range(n_days)],
            "weather_code": [1] * n_days,
        },
    }


# ---------------------------------------------------------------------------
# parse_openmeteo_forecast — utc_offset_seconds forwarding
# ---------------------------------------------------------------------------


class TestParseOpenmeteoForecastTimezone:
    def test_utc_location_sets_utc_tz(self):
        """start_time for UTC location should be UTC-aware."""
        payload = _make_openmeteo_payload("2026-03-27", 7, utc_offset_seconds=0)
        forecast = parse_openmeteo_forecast(payload)
        for p in forecast.periods:
            assert p.start_time is not None
            assert p.start_time.tzinfo is not None
            assert p.start_time.utcoffset() == timedelta(0)

    def test_bst_location_sets_plus1_tz(self):
        """start_time for UTC+1 (BST) location should have +01:00 offset."""
        payload = _make_openmeteo_payload("2026-03-27", 7, utc_offset_seconds=3600)
        forecast = parse_openmeteo_forecast(payload)
        for p in forecast.periods:
            assert p.start_time is not None
            assert p.start_time.tzinfo is not None
            assert p.start_time.utcoffset() == timedelta(hours=1)

    def test_bst_start_times_are_noon_local(self):
        """Each start_time should represent noon local (12:00) in the local tz."""
        payload = _make_openmeteo_payload("2026-03-27", 7, utc_offset_seconds=3600)
        forecast = parse_openmeteo_forecast(payload)
        for p in forecast.periods:
            assert p.start_time is not None
            assert p.start_time.hour == 12

    def test_bst_local_dates_match_open_meteo_dates(self):
        """The calendar date of each period must match the date Open-Meteo provided."""
        from datetime import date as _date

        payload = _make_openmeteo_payload("2026-03-27", 7, utc_offset_seconds=3600)
        forecast = parse_openmeteo_forecast(payload)
        base = _date(2026, 3, 27)
        for i, p in enumerate(forecast.periods):
            expected_date = base + timedelta(days=i)
            assert p.start_time is not None
            assert p.start_time.date() == expected_date, (
                f"Period {i}: expected {expected_date}, got {p.start_time.date()}"
            )

    def test_no_utc_offset_still_has_tzinfo(self):
        """When utc_offset_seconds is absent the fallback should still be tz-aware."""
        payload = _make_openmeteo_payload("2026-03-27", 7, utc_offset_seconds=None)
        del payload["utc_offset_seconds"]
        forecast = parse_openmeteo_forecast(payload)
        for p in forecast.periods:
            assert p.start_time is not None
            # fallback: _parse_iso_datetime attaches UTC when no offset is given
            assert p.start_time.tzinfo is not None

    def test_india_offset_correct_dates(self):
        """UTC+5:30 (India) — all 7 local dates must be present."""
        from datetime import date as _date

        payload = _make_openmeteo_payload("2026-04-01", 7, utc_offset_seconds=19800)
        forecast = parse_openmeteo_forecast(payload)
        base = _date(2026, 4, 1)
        for i, p in enumerate(forecast.periods):
            expected = base + timedelta(days=i)
            assert p.start_time is not None
            assert p.start_time.date() == expected

    def test_nzdt_offset_correct_dates(self):
        """UTC+13 (NZ Daylight Time) — local dates must match even at large positive offset."""
        from datetime import date as _date

        payload = _make_openmeteo_payload("2026-01-10", 7, utc_offset_seconds=46800)
        forecast = parse_openmeteo_forecast(payload)
        base = _date(2026, 1, 10)
        for i, p in enumerate(forecast.periods):
            expected = base + timedelta(days=i)
            assert p.start_time is not None
            assert p.start_time.date() == expected


# ---------------------------------------------------------------------------
# _select_periods_by_day_window — no gaps, no duplicates, UTC+1
# ---------------------------------------------------------------------------


class TestSelectPeriodsNoGapsUTC1:
    def _make_forecast(self, start_date: str, n_days: int, tz: timezone) -> Forecast:
        """Build a Forecast where every period has a tz-aware noon start_time."""
        from datetime import date as _date

        base = _date.fromisoformat(start_date)
        periods = []
        for i in range(n_days):
            d = base + timedelta(days=i)
            st = datetime(d.year, d.month, d.day, 12, tzinfo=tz)
            periods.append(
                ForecastPeriod(
                    name="Today" if i == 0 else "Tomorrow" if i == 1 else d.strftime("%A"),
                    temperature=20.0 + i,
                    start_time=st,
                )
            )
        return Forecast(periods=periods)

    def test_7_days_bst_no_gap(self):
        """7 UTC+1 periods → _select_periods_by_day_window returns all 7, no gap."""
        forecast = self._make_forecast("2026-03-27", 7, _BST)
        result = _select_periods_by_day_window(forecast, 7)
        assert len(result) == 7

    def test_7_days_bst_all_distinct_dates(self):
        """Returned periods must cover 7 distinct calendar dates."""
        forecast = self._make_forecast("2026-03-27", 7, _BST)
        result = _select_periods_by_day_window(forecast, 7)
        dates = [p.start_time.date() for p in result]
        assert len(set(dates)) == 7, f"Duplicate dates found: {dates}"

    def test_7_days_bst_dates_are_consecutive(self):
        """Returned calendar dates must be consecutive — no day skipped."""
        forecast = self._make_forecast("2026-03-27", 7, _BST)
        result = _select_periods_by_day_window(forecast, 7)
        dates = sorted(p.start_time.date() for p in result)
        for i in range(1, len(dates)):
            assert dates[i] - dates[i - 1] == timedelta(days=1), (
                f"Gap between {dates[i - 1]} and {dates[i]}"
            )

    def test_14_days_bst_truncated_to_7(self):
        """14-day Open-Meteo payload → only first 7 days selected."""
        forecast = self._make_forecast("2026-03-27", 14, _BST)
        result = _select_periods_by_day_window(forecast, 7)
        assert len(result) == 7

    def test_sat_present_in_fri_start_7day_window(self):
        """Specifically: Friday start, 7 days → Saturday must appear at index 1."""
        from datetime import date as _date

        forecast = self._make_forecast("2026-03-27", 7, _BST)  # 2026-03-27 is a Friday
        result = _select_periods_by_day_window(forecast, 7)
        dates = [p.start_time.date() for p in result]
        saturday = _date(2026, 3, 28)
        assert saturday in dates, f"Saturday missing from {dates}"

    def test_mixed_naive_aware_sorts_without_error(self):
        """
        No crash when naive fallback datetimes are present alongside tz-aware ones.

        _select_periods_by_day_window must handle mixed-tzinfo lists gracefully.
        """
        from datetime import date as _date

        base = _date(2026, 3, 27)
        periods = []
        for i in range(5):
            d = base + timedelta(days=i)
            # Alternate: 0,2,4 are UTC-aware, 1,3 are naive
            if i % 2 == 0:
                st = datetime(d.year, d.month, d.day, 12, tzinfo=_BST)
            else:
                st = datetime(d.year, d.month, d.day, 12)  # naive
            periods.append(ForecastPeriod(name=f"Day{i}", temperature=20.0, start_time=st))
        forecast = Forecast(periods=periods)
        result = _select_periods_by_day_window(forecast, 5)
        assert len(result) == 5

    def test_nzdt_no_gap_utc13(self):
        """UTC+13 (large positive offset) — no day skipped or duplicated."""
        forecast = self._make_forecast("2026-01-10", 7, _NZDT)
        result = _select_periods_by_day_window(forecast, 7)
        dates = sorted(p.start_time.date() for p in result)
        assert len(dates) == 7
        for i in range(1, len(dates)):
            assert dates[i] - dates[i - 1] == timedelta(days=1)

    def test_argentina_no_gap_utc_minus3(self):
        """UTC-3 (negative offset) — no day skipped or duplicated."""
        forecast = self._make_forecast("2026-03-27", 7, _ART)
        result = _select_periods_by_day_window(forecast, 7)
        dates = sorted(p.start_time.date() for p in result)
        assert len(dates) == 7
        for i in range(1, len(dates)):
            assert dates[i] - dates[i - 1] == timedelta(days=1)


# ---------------------------------------------------------------------------
# End-to-end: parse then select — simulating Preston, England (UTC+1 BST)
# ---------------------------------------------------------------------------


class TestPreston7DayForecastNoGap:
    """Full pipeline: parse_openmeteo_forecast + _select_periods_by_day_window."""

    def test_preston_7day_all_days_present(self):
        """For a 7-day BST payload, _select_periods_by_day_window returns all 7 days."""
        payload = _make_openmeteo_payload("2026-03-27", 7, utc_offset_seconds=3600)
        forecast = parse_openmeteo_forecast(payload)
        result = _select_periods_by_day_window(forecast, 7)
        assert len(result) == 7

    def test_preston_7day_saturday_present(self):
        """Saturday (index 1 for a Friday start) must appear in the result."""
        from datetime import date as _date

        payload = _make_openmeteo_payload("2026-03-27", 7, utc_offset_seconds=3600)
        forecast = parse_openmeteo_forecast(payload)
        result = _select_periods_by_day_window(forecast, 7)
        dates = {p.start_time.date() for p in result}
        assert _date(2026, 3, 28) in dates, f"Saturday missing; dates found: {sorted(dates)}"

    def test_preston_7day_consecutive(self):
        """All 7 returned dates must be consecutive — no gaps."""
        payload = _make_openmeteo_payload("2026-03-27", 7, utc_offset_seconds=3600)
        forecast = parse_openmeteo_forecast(payload)
        result = _select_periods_by_day_window(forecast, 7)
        dates = sorted(p.start_time.date() for p in result)
        for i in range(1, len(dates)):
            assert dates[i] - dates[i - 1] == timedelta(days=1), f"Gap: {dates[i - 1]} → {dates[i]}"

    def test_preston_16day_truncates_to_7(self):
        """16-day payload for BST → only first 7 days returned."""
        payload = _make_openmeteo_payload("2026-03-27", 16, utc_offset_seconds=3600)
        forecast = parse_openmeteo_forecast(payload)
        result = _select_periods_by_day_window(forecast, 7)
        assert len(result) == 7

    def test_preston_no_duplicate_dates(self):
        """No date should appear twice in the returned periods."""
        payload = _make_openmeteo_payload("2026-03-27", 7, utc_offset_seconds=3600)
        forecast = parse_openmeteo_forecast(payload)
        result = _select_periods_by_day_window(forecast, 7)
        dates = [p.start_time.date() for p in result]
        assert len(dates) == len(set(dates)), f"Duplicates found: {dates}"
