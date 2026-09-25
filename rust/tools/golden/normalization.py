"""Golden outputs for the shared unit/normalization helpers
(weather_client_parsers, provider_normalization, thermal_comfort and the
Open-Meteo unit helpers).

    cd C:\\Users\\joshu\\accessiweather
    uv run python <worktree>\\rust\\tools\\golden\\normalization.py

Writes rust/testdata/golden/normalization/helpers.json.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import provider_golden_common as common  # noqa: E402

from accessiweather import (
    provider_normalization as pn,  # noqa: E402
    weather_client_openmeteo_units as omu,  # noqa: E402
    weather_client_parsers as wcp,  # noqa: E402
)
from accessiweather.thermal_comfort import sanitize_thermal_comfort_readings  # noqa: E402

UNITS = [None, "", "°F", "°C", "wmoUnit:degC", "wmoUnit:degF", "fahrenheit", "celsius", "K"]
SPEED_UNITS = [
    None,
    "",
    "mph",
    "mp/h",
    "km/h",
    "kmh",
    "kph",
    "m/s",
    "wmoUnit:m_s-1",
    "wmoUnit:km_h-1",
    "kn",
    "kt",
    "knots",
    "furlongs",
]
PRESSURE_UNITS = [None, "", "hPa", "mb", "Pa", "wmoUnit:Pa", "inHg", "inch", "in", "psi"]
LENGTH_UNITS = [
    None,
    "",
    "m",
    "km",
    "ft",
    "feet",
    "mi",
    "miles",
    "mm",
    "cm",
    "inch",
    "in",
    "kilo metre",
]


def main() -> None:
    common.reset("normalization")
    thermal = []
    for temp, humidity, feels, chill, heat in itertools.product(
        [None, 20.0, 45.0, 79.0, 85.0, 95.0],
        [None, 15, 45, 90],
        [None, 10.0, 44.0, 86.0, 89.0, 100.0, 120.0],
        [None, 15.0, 50.0],
        [None, 90.0, 104.0],
    ):
        readings = sanitize_thermal_comfort_readings(
            temperature_f=temp,
            humidity=humidity,
            feels_like_f=feels,
            wind_chill_f=chill,
            heat_index_f=heat,
        )
        thermal.append([[temp, humidity, feels, chill, heat], readings])
    thermal_celsius = [
        [
            [c, h, fc],
            sanitize_thermal_comfort_readings(
                temperature_f=None, temperature_c=c, humidity=h, feels_like_c=fc
            ),
        ]
        for c, h, fc in [(30.0, 70, 38.0), (0.0, 50, -6.0), (None, 50, 20.0), (35.0, 10, 41.0)]
    ]
    values = [None, 0.0, 12.5, -3.25, 1013.25]
    common.write(
        "normalization",
        "helpers",
        {
            "thermal": thermal,
            "thermal_celsius": thermal_celsius,
            "temperature": [[v, u, wcp.normalize_temperature(v, u)] for v in values for u in UNITS],
            "speed": [
                [v, u, wcp.convert_wind_speed_to_mph_and_kph(v, u)]
                for v in values
                for u in SPEED_UNITS
            ],
            "speed_pair": [
                [v, u, pn.normalize_speed_pair(v, u)] for v in values for u in SPEED_UNITS
            ],
            "pressure": [
                [v, u, wcp.normalize_pressure(v, u)] for v in values for u in PRESSURE_UNITS
            ],
            "pascals": [
                [v, u, pn.normalize_pressure_to_pascals(v, u)]
                for v in values
                for u in PRESSURE_UNITS
            ],
            "visibility": [
                [v, u, cap, pn.normalize_visibility_pair(v, u, cap_miles=cap)]
                for v in [None, 0.0, 1609.344, 16.0, 52800.0]
                for u in LENGTH_UNITS
                for cap in [None, 10.0]
            ],
            "snow_depth": [
                [v, u, omu.normalize_snow_depth_to_inches_and_cm(v, u)]
                for v in values
                for u in LENGTH_UNITS
            ],
            "precipitation": [
                [v, u, omu.normalize_precipitation_to_inches_and_mm(v, u)]
                for v in values
                for u in LENGTH_UNITS
            ],
            "height": [
                [v, u, omu.normalize_height_to_feet(v, u)] for v in values for u in LENGTH_UNITS
            ],
            "humidity": [
                [v, f, pn.normalize_humidity_percent(v, fraction=f)]
                for v in [None, 0.5, 0.655, 0.125, 72.5, 73.5, 100]
                for f in [False, True]
            ],
            "dewpoint": [
                [
                    d,
                    u,
                    t,
                    h,
                    pn.normalize_dewpoint_pair(d, u, fallback_temperature_f=t, humidity_percent=h),
                ]
                for d, u, t, h in [
                    (10.0, "C", 70.0, 50),
                    (None, "F", 70.0, 50),
                    (None, "F", 70.0, 0),
                    (None, "F", None, 50),
                    (50.0, "F", None, None),
                    (None, None, 5.0, 100),
                ]
            ],
            "format_speed": [
                [v, u, pn.format_speed(v, u)]
                for v in [None, 0.4, 0.5, 1.5, 2.5, 10.49, -0.5]
                for u in ["mph", "km/h"]
            ],
            "cardinal": [
                [d, wcp.degrees_to_cardinal(d)]
                for d in [
                    None,
                    0,
                    11.25,
                    11.26,
                    22.5,
                    33.75,
                    45,
                    90,
                    180,
                    270,
                    348.75,
                    359,
                    360,
                    720.5,
                    -22.5,
                    -90,
                ]
            ],
            "weather_code": [
                [c, wcp.weather_code_to_description(c)]
                for c in [
                    None,
                    0,
                    1,
                    2,
                    3,
                    45,
                    48,
                    51,
                    61,
                    71,
                    77,
                    80,
                    95,
                    99,
                    4,
                    100,
                    "3",
                    "abc",
                    2.7,
                ]
            ],
            "moon_phase": [
                [v, wcp.describe_moon_phase(v)]
                for v in [
                    None,
                    0,
                    0.06,
                    0.0625,
                    0.25,
                    0.5,
                    0.74,
                    0.9375,
                    0.99,
                    1.0,
                    1.3,
                    -0.25,
                    "0.5",
                    "x",
                ]
            ],
            "date_name": [
                [d, i, wcp.format_date_name(d, i)]
                for d, i in [
                    ("2025-01-15", 0),
                    ("2025-01-16", 1),
                    ("2025-01-17", 2),
                    ("2025-01-18T12:00", 3),
                    ("bad", 4),
                    ("2024-02-29", 6),
                ]
            ],
            "apparent": [
                [t, a, c, pn.classify_apparent_temperature(t, a, c)]
                for t, a, c in [
                    (None, 10.0, None),
                    (50.0, None, None),
                    (50.0, 40.0, 4.4),
                    (50.0, 60.0, 15.5),
                    (50.0, 50.0, 10.0),
                ]
            ],
        },
    )


if __name__ == "__main__":
    main()
