"""Golden outputs for weather history comparisons and anomaly callouts.

Writes rust/testdata/golden/history/*.json.
"""

from __future__ import annotations

import json
from datetime import date

from common import write

import accessiweather.weather_anomaly as weather_anomaly
from accessiweather.models.weather import CurrentConditions
from accessiweather.weather_history import (
    HistoricalWeatherData,
    WeatherComparison,
    WeatherHistoryService,
)


def comparisons():
    hist = HistoricalWeatherData(
        date=date(2026, 7, 14),
        temperature_max=80.0,
        temperature_min=60.0,
        temperature_mean=70.0,
        condition="Clear sky",
        humidity=None,
        wind_speed=10.0,
        wind_direction=180,
        pressure=None,
    )
    cases = [
        ("same", CurrentConditions(temperature=70.5, condition="Clear sky"), 1),
        ("warmer", CurrentConditions(temperature=75.25, condition="Clear sky"), 1),
        ("cooler_changed", CurrentConditions(temperature=62.0, condition="Rain"), 7),
        ("no_condition", CurrentConditions(temperature=69.0), 3),
        ("exactly_one_degree", CurrentConditions(temperature=71.0, condition="Fog"), 30),
    ]
    out = []
    for name, current, days_ago in cases:
        comparison = WeatherComparison.compare(current, hist, days_ago=days_ago)
        out.append(
            {
                "name": name,
                "current": current,
                "historical": hist,
                "days_ago": days_ago,
                "comparison": comparison,
                "summary": comparison.get_accessible_summary(),
            }
        )
    write("history", "comparisons", out)


class FakeArchiveClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def _make_request(self, endpoint, params, use_archive=False):
        self.calls.append((endpoint, params, use_archive))
        if isinstance(self.response, Exception):
            raise self.response
        if callable(self.response):
            return self.response(params)
        return self.response

    @staticmethod
    def get_weather_description(code):
        return f"code {json.dumps(code)}"


def archive_parsing():
    target = date(2026, 7, 14)
    full = {
        "time": ["2026-07-14"],
        "weather_code": [3],
        "temperature_2m_max": [81.5],
        "temperature_2m_min": [62],
        "temperature_2m_mean": ["71.2"],
        "wind_speed_10m_max": [12.3],
        "wind_direction_10m_dominant": [185.7],
    }
    cases = [
        ("full", {"daily": full}),
        ("no_daily", {"hourly": {}}),
        ("empty_time", {"daily": {**full, "time": []}}),
        ("missing_mean", {"daily": {k: v for k, v in full.items() if k != "temperature_2m_mean"}}),
        ("null_code", {"daily": {**full, "weather_code": [None]}}),
        ("null_direction", {"daily": {**full, "wind_direction_10m_dominant": [None]}}),
        ("no_direction", {"daily": {k: v for k, v in full.items() if k != "wind_direction_10m_dominant"}}),
        ("bad_number", {"daily": {**full, "temperature_2m_max": ["hot"]}}),
        ("float_code", {"daily": {**full, "weather_code": [61.0]}}),
    ]
    out = []
    for name, response in cases:
        service = WeatherHistoryService(openmeteo_client=FakeArchiveClient(response))
        result = service.get_historical_weather(40.0, -75.0, target)
        out.append({"name": name, "date": target, "response": response, "result": result})
    write("history", "archive_parsing", out)


def anomaly():
    def responder(means_by_year):
        def respond(params):
            year = int(params["start_date"][:4])
            value = means_by_year.get(year)
            if value is None:
                return None
            return {"daily": {"temperature_2m_mean": value}}

        return respond

    cases = [
        ("five_years", 75.0, date(2026, 7, 15), date(2026, 7, 15), {
            2025: [70.0, 71.0, None], 2024: [72.0], 2023: [68.5, 69.5], 2022: [71.0], 2021: [70.0]}),
        ("insufficient", 75.0, date(2026, 7, 15), date(2026, 7, 15), {2025: [70.0], 2024: [72.0]}),
        ("empty_lists_skipped", 60.0, date(2026, 7, 15), date(2026, 7, 15), {
            2025: [], 2024: [None], 2023: [59.0], 2022: [60.2], 2021: [60.1]}),
        ("leap_day", 40.0, date(2028, 2, 29), date(2028, 2, 29), {
            2027: [45.0], 2026: [44.0], 2025: [46.0], 2024: [43.0], 2023: [47.0]}),
        ("recent_window_clamped", 50.0, date(2026, 7, 15), date(2025, 7, 20), {
            2025: [49.0], 2024: [48.0], 2023: [47.0], 2022: [51.0], 2021: [52.0]}),
    ]
    out = []
    for name, temp, current_date, today, means in cases:
        weather_anomaly.date = type(
            "FrozenDate", (date,), {"today": classmethod(lambda cls, t=today: t)}
        )
        client = FakeArchiveClient(responder(means))
        result = weather_anomaly.compute_anomaly(40.0, -75.0, temp, current_date, client)
        requests = [f"{p['start_date']}/{p['end_date']}" for _, p, _ in client.calls]
        responses = {}
        for _, params, _ in client.calls:
            responses[f"{params['start_date']}/{params['end_date']}"] = responder(means)(params)
        out.append(
            {
                "name": name,
                "current_temp_f": temp,
                "current_date": current_date,
                "today": today,
                "responses": responses,
                "requests": requests,
                "result": result,
            }
        )
    write("history", "anomaly", out)


if __name__ == "__main__":
    comparisons()
    archive_parsing()
    anomaly()
