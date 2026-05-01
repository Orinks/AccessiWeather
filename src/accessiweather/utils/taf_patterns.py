"""Shared regex patterns and code maps for TAF decoding."""

from __future__ import annotations

import re

ISSUE_TIME_RE = re.compile(r"^\d{6}Z$")
TIME_RANGE_RE = re.compile(r"^\d{4}/\d{4}$")
FM_TIME_RE = re.compile(r"^FM\d{6}$")
PROB_RE = re.compile(r"^PROB(?P<prob>\d{2})(?P<period>\d{4}/\d{4})?$")
TEMPO_RE = re.compile(r"^TEMPO(?P<period>\d{4}/\d{4})?$")
BECMG_RE = re.compile(r"^BECMG(?P<period>\d{4}/\d{4})?$")
WIND_RE = re.compile(
    r"^(?P<dir>\d{3}|VRB)(?P<speed>\d{2,3})(?P<gust>G\d{2,3})?(?P<unit>KT|MPS|KMH)$"
)
CLOUD_RE = re.compile(r"^(FEW|SCT|BKN|OVC|NSC|SKC|CLR|VV)(\d{3}|///)?(CB|TCU|///)?$")

DESCRIPTORS = {
    "MI": "shallow",
    "PR": "partial",
    "BC": "patches of",
    "DR": "low drifting",
    "BL": "blowing",
    "SH": "showers of",
    "TS": "thunderstorms with",
    "FZ": "freezing",
    "RE": "recent",
}

PHENOMENA = {
    "DZ": "drizzle",
    "RA": "rain",
    "SN": "snow",
    "SG": "snow grains",
    "IC": "ice crystals",
    "PL": "ice pellets",
    "GR": "hail",
    "GS": "small hail",
    "UP": "unknown precipitation",
    "BR": "mist",
    "FG": "fog",
    "FU": "smoke",
    "VA": "volcanic ash",
    "DU": "dust",
    "SA": "sand",
    "HZ": "haze",
    "PY": "spray",
    "PO": "dust/sand whirls",
    "SQ": "squalls",
    "FC": "funnel clouds",
    "SS": "sandstorm",
    "DS": "dust storm",
    "SH": "showers",
    "TS": "thunderstorms",
}

INTENSITY = {"+": "heavy", "-": "light"}
KNOWN_PRECIP_CODES = {"DZ", "RA", "SN", "SG", "IC", "PL", "GR", "GS"}
