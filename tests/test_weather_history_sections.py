"""Wording of the Today vs Yesterday section in the weather history dialog."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from accessiweather.ui.dialogs.weather_history_dialog import _build_history_sections


def _weather_double(current_temp_f: float, yesterday_temp: float) -> SimpleNamespace:
    yesterday = SimpleNamespace(
        name="Yesterday",
        start_time=None,
        temperature=yesterday_temp,
        short_forecast="Sunny",
    )
    return SimpleNamespace(
        daily_history=[yesterday],
        trend_insights=None,
        current=SimpleNamespace(temperature_f=current_temp_f),
    )


def test_equal_temperatures_read_naturally():
    sections = dict(_build_history_sections(MagicMock(), _weather_double(70.0, 70.0)))

    assert "Today vs Yesterday" in sections
    text = sections["Today vs Yesterday"]
    assert "is about the same as yesterday" in text
    assert "warmer" not in text
    assert "cooler" not in text


def test_warmer_temperature_reports_difference():
    sections = dict(_build_history_sections(MagicMock(), _weather_double(75.0, 70.0)))

    text = sections["Today vs Yesterday"]
    assert "5.0°F warmer" in text


def test_cooler_temperature_reports_difference():
    sections = dict(_build_history_sections(MagicMock(), _weather_double(65.0, 70.0)))

    text = sections["Today vs Yesterday"]
    assert "5.0°F cooler" in text
