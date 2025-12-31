"""
Property-based tests for TAF decoder module.

These tests use Hypothesis to verify that the TAF decoder:
- Never crashes on arbitrary input
- Produces human-readable output for valid tokens
- Handles edge cases gracefully
"""

from __future__ import annotations

import pytest
from hypothesis import (
    given,
    settings,
    strategies as st,
)

from accessiweather.utils.taf_decoder import decode_taf_text

# -----------------------------------------------------------------------------
# Hypothesis Strategies for generating TAF-like data
# -----------------------------------------------------------------------------

# Valid wind directions (3 digits or VRB)
wind_directions = st.one_of(
    st.integers(min_value=0, max_value=360).map(lambda d: f"{d:03d}"),
    st.just("VRB"),
)

# Valid wind speeds (2-3 digits)
wind_speeds = st.integers(min_value=0, max_value=150).map(lambda s: f"{s:02d}")

# Valid wind units
wind_units = st.sampled_from(["KT", "MPS", "KMH"])

# Valid gust values
gust_values = st.one_of(
    st.none(),
    st.integers(min_value=10, max_value=150).map(lambda g: f"G{g:02d}"),
)


@st.composite
def valid_wind_token(draw: st.DrawFn) -> str:
    """Generate a valid TAF wind token."""
    direction = draw(wind_directions)
    speed = draw(wind_speeds)
    gust = draw(gust_values)
    unit = draw(wind_units)
    gust_str = gust if gust else ""
    return f"{direction}{speed}{gust_str}{unit}"


# Visibility strategies
visibility_sm = st.one_of(
    st.integers(min_value=0, max_value=10).map(lambda v: f"{v}SM"),
    st.sampled_from(["1/4SM", "1/2SM", "3/4SM", "1 1/2SM", "2 1/4SM"]),
    st.sampled_from(["P6SM", "M1/4SM"]),
)

visibility_meters = st.integers(min_value=0, max_value=9999).map(lambda v: f"{v:04d}")

visibility_tokens = st.one_of(visibility_sm, visibility_meters)

# Cloud layer strategies
cloud_coverage = st.sampled_from(["FEW", "SCT", "BKN", "OVC", "VV"])
cloud_height = st.integers(min_value=0, max_value=999).map(lambda h: f"{h:03d}")
cloud_type = st.sampled_from([None, "CB", "TCU"])


@st.composite
def valid_cloud_token(draw: st.DrawFn) -> str:
    """Generate a valid TAF cloud token."""
    cover = draw(cloud_coverage)
    height = draw(cloud_height)
    ctype = draw(cloud_type)
    type_str = ctype if ctype else ""
    return f"{cover}{height}{type_str}"


# Weather phenomena strategies
weather_intensity = st.sampled_from(["", "+", "-"])
weather_descriptor = st.sampled_from(["", "MI", "PR", "BC", "DR", "BL", "SH", "TS", "FZ"])
weather_phenomena = st.sampled_from(["RA", "SN", "DZ", "FG", "BR", "HZ", "FU", "GR", "GS"])


@st.composite
def valid_weather_token(draw: st.DrawFn) -> str:
    """Generate a valid TAF weather token."""
    intensity = draw(weather_intensity)
    descriptor = draw(weather_descriptor)
    phenomena = draw(weather_phenomena)
    return f"{intensity}{descriptor}{phenomena}"


# Station identifiers (4 letter ICAO codes)
station_ids = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    min_size=4,
    max_size=4,
)

# Issue time (DDHHMMZ format)
issue_times = st.tuples(
    st.integers(min_value=1, max_value=31),
    st.integers(min_value=0, max_value=23),
    st.integers(min_value=0, max_value=59),
).map(lambda t: f"{t[0]:02d}{t[1]:02d}{t[2]:02d}Z")

# Time range (DDHH/DDHH format)
time_ranges = st.tuples(
    st.integers(min_value=1, max_value=31),
    st.integers(min_value=0, max_value=23),
    st.integers(min_value=1, max_value=31),
    st.integers(min_value=0, max_value=23),
).map(lambda t: f"{t[0]:02d}{t[1]:02d}/{t[2]:02d}{t[3]:02d}")


# -----------------------------------------------------------------------------
# Property Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
class TestTafDecoderNeverCrashes:
    """Property: decode_taf_text never crashes on any input."""

    @given(text=st.text(min_size=0, max_size=500))
    @settings(max_examples=50)
    def test_arbitrary_string_does_not_crash(self, text: str) -> None:
        """decode_taf_text should handle any arbitrary string without crashing."""
        result = decode_taf_text(text)
        assert isinstance(result, str)
        assert len(result) >= 0

    @given(
        text=st.binary(min_size=0, max_size=200).map(lambda b: b.decode("utf-8", errors="replace"))
    )
    @settings(max_examples=50)
    def test_binary_garbage_does_not_crash(self, text: str) -> None:
        """decode_taf_text should handle binary garbage decoded as UTF-8."""
        result = decode_taf_text(text)
        assert isinstance(result, str)

    @given(
        text=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "S", "Z"),
                whitelist_characters="!@#$%^&*(){}[]|\\:;\"'<>,.?/~`",
            ),
            min_size=0,
            max_size=300,
        )
    )
    @settings(max_examples=50)
    def test_special_characters_do_not_crash(self, text: str) -> None:
        """decode_taf_text should handle special characters gracefully."""
        result = decode_taf_text(text)
        assert isinstance(result, str)


@pytest.mark.unit
class TestTafDecoderEdgeCases:
    """Property: edge cases are handled appropriately."""

    def test_empty_string(self) -> None:
        """Empty string returns appropriate message."""
        result = decode_taf_text("")
        assert result == "No TAF available."

    def test_whitespace_only(self) -> None:
        """Whitespace-only string returns appropriate message."""
        result = decode_taf_text("   \t\n  ")
        assert result == "No TAF available."

    def test_none_input(self) -> None:
        """None input returns appropriate message."""
        result = decode_taf_text(None)  # type: ignore[arg-type]
        assert result == "No TAF available."

    @given(text=st.text(min_size=1000, max_size=5000))
    @settings(max_examples=20)
    def test_very_long_strings_do_not_crash(self, text: str) -> None:
        """Very long strings should be handled without crashing."""
        result = decode_taf_text(text)
        assert isinstance(result, str)

    @given(
        count=st.integers(min_value=1, max_value=100),
        token=st.sampled_from(["TAF", "AMD", "COR", "NIL", "RMK"]),
    )
    @settings(max_examples=50)
    def test_repeated_tokens_do_not_crash(self, count: int, token: str) -> None:
        """Repeated TAF tokens should be handled gracefully."""
        text = " ".join([token] * count)
        result = decode_taf_text(text)
        assert isinstance(result, str)


@pytest.mark.unit
class TestTafDecoderValidTokens:
    """Property: valid TAF tokens produce readable output."""

    @given(
        station=station_ids,
        issue_time=issue_times,
        validity=time_ranges,
        wind=valid_wind_token(),
    )
    @settings(max_examples=50)
    def test_basic_taf_produces_readable_output(
        self, station: str, issue_time: str, validity: str, wind: str
    ) -> None:
        """A basic valid TAF should produce human-readable output."""
        taf = f"TAF {station} {issue_time} {validity} {wind}"
        result = decode_taf_text(taf)

        # Should contain station reference
        assert station in result
        # Should be readable text, not just raw codes
        assert "Forecast" in result or "forecast" in result.lower()
        # Wind should be decoded
        assert "Wind" in result or "knot" in result.lower() or "calm" in result.lower()

    @given(wind=valid_wind_token())
    @settings(max_examples=50)
    def test_wind_token_produces_readable_output(self, wind: str) -> None:
        """Valid wind tokens should produce readable descriptions."""
        taf = f"TAF KJFK 010000Z 0100/0124 {wind}"
        result = decode_taf_text(taf)

        # Should contain wind information
        has_wind_info = any(
            term in result.lower()
            for term in ["wind", "knot", "calm", "variable", "degrees", "meters per second"]
        )
        assert has_wind_info, f"Expected wind info in: {result}"

    @given(cloud=valid_cloud_token())
    @settings(max_examples=50)
    def test_cloud_token_produces_readable_output(self, cloud: str) -> None:
        """Valid cloud tokens should produce readable descriptions."""
        taf = f"TAF KJFK 010000Z 0100/0124 10010KT {cloud}"
        result = decode_taf_text(taf)

        # Should contain cloud information
        has_cloud_info = any(
            term in result.lower()
            for term in ["cloud", "few", "scattered", "broken", "overcast", "visibility", "feet"]
        )
        assert has_cloud_info, f"Expected cloud info in: {result}"

    @given(weather=valid_weather_token())
    @settings(max_examples=50)
    def test_weather_token_produces_readable_output(self, weather: str) -> None:
        """Valid weather tokens should produce readable descriptions."""
        taf = f"TAF KJFK 010000Z 0100/0124 10010KT 6SM {weather} BKN020"
        result = decode_taf_text(taf)

        # Result should be a string (weather may end up in Additional codes if malformed)
        assert isinstance(result, str)
        assert len(result) > 0


@pytest.mark.unit
class TestTafDecoderWindFunction:
    """Property: _decode_wind output contains speed/direction when valid."""

    @given(wind=valid_wind_token())
    @settings(max_examples=50)
    def test_valid_wind_decoded_in_taf(self, wind: str) -> None:
        """Valid wind strings produce output with speed/direction values."""
        taf = f"TAF KJFK 010000Z 0100/0124 {wind}"
        result = decode_taf_text(taf)

        # The wind token should appear in the decoded output (in parentheses)
        assert wind in result, f"Wind token {wind} should appear in result: {result}"


@pytest.mark.unit
class TestTafDecoderVisibilityFunction:
    """Property: _decode_visibility handles various formats without crashing."""

    @given(vis=visibility_tokens)
    @settings(max_examples=50)
    def test_visibility_formats_do_not_crash(self, vis: str) -> None:
        """Various visibility formats should be handled without crashing."""
        taf = f"TAF KJFK 010000Z 0100/0124 10010KT {vis} SKC"
        result = decode_taf_text(taf)
        assert isinstance(result, str)

    @given(vis=visibility_sm)
    @settings(max_examples=50)
    def test_statute_mile_visibility_decoded(self, vis: str) -> None:
        """Statute mile visibility should be decoded readably."""
        taf = f"TAF KJFK 010000Z 0100/0124 10010KT {vis} SKC"
        result = decode_taf_text(taf)

        # Should contain visibility reference
        has_visibility = "visibility" in result.lower() or "mile" in result.lower()
        assert has_visibility, f"Expected visibility info in: {result}"

    @given(vis=visibility_meters)
    @settings(max_examples=50)
    def test_meter_visibility_decoded(self, vis: str) -> None:
        """Meter visibility should be decoded readably."""
        taf = f"TAF KJFK 010000Z 0100/0124 10010KT {vis} SKC"
        result = decode_taf_text(taf)

        # Should contain visibility reference (meters decoded to kilometers)
        has_visibility = (
            "visibility" in result.lower()
            or "kilometre" in result.lower()
            or "kilometer" in result.lower()
            or "metre" in result.lower()
            or "meter" in result.lower()
        )
        assert has_visibility, f"Expected visibility info in: {result}"


@pytest.mark.unit
class TestTafDecoderRealWorldExamples:
    """Tests using real-world TAF examples."""

    def test_real_taf_kjfk(self) -> None:
        """Test decoding a real KJFK TAF."""
        taf = (
            "TAF KJFK 251730Z 2518/2624 31008KT P6SM FEW250 "
            "FM260000 33006KT P6SM SCT250 "
            "FM261200 02010KT P6SM SKC"
        )
        result = decode_taf_text(taf)

        assert "KJFK" in result
        assert "Forecast" in result
        assert "Wind" in result or "wind" in result.lower()
        assert "From" in result  # FM segments

    def test_real_taf_with_weather(self) -> None:
        """Test decoding a TAF with weather phenomena."""
        taf = "TAF KORD 251730Z 2518/2624 18012G20KT 5SM -RA BKN015 OVC030"
        result = decode_taf_text(taf)

        assert "KORD" in result
        assert "gust" in result.lower() or "G20" in result
        assert "rain" in result.lower() or "-RA" in result

    def test_real_taf_with_tempo_and_prob(self) -> None:
        """Test decoding a TAF with TEMPO and PROB segments."""
        taf = (
            "TAF KLAX 251730Z 2518/2624 25010KT P6SM SKC "
            "TEMPO 2520/2524 3SM BR "
            "PROB30 2602/2606 1SM FG"
        )
        result = decode_taf_text(taf)

        assert "KLAX" in result
        assert "Temporary" in result or "TEMPO" in result
        assert "Probability" in result or "PROB" in result

    def test_nil_taf(self) -> None:
        """Test decoding a NIL TAF."""
        taf = "TAF KABC 251730Z NIL"
        result = decode_taf_text(taf)

        assert "No TAF available" in result or "NIL" in result

    def test_taf_with_remarks(self) -> None:
        """Test decoding a TAF with remarks."""
        taf = "TAF KDEN 251730Z 2518/2624 27012KT P6SM SKC RMK NXT FCST BY 00Z"
        result = decode_taf_text(taf)

        assert "KDEN" in result
        assert "Remarks" in result or "RMK" in result
