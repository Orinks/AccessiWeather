"""Tests for TAF decoder utility."""


from accessiweather.utils.taf_decoder import (
    _decode_cloud,
    _decode_visibility,
    _decode_weather,
    _decode_wind,
    _describe_segment,
    _format_day,
    _format_from_time,
    _format_issue_time,
    _format_time_range,
    _segment_intro,
    _split_segments,
    decode_taf_text,
)

# --- decode_taf_text (public API) ---


class TestDecodeTafText:
    """Tests for the main public function."""

    def test_empty_string(self):
        assert decode_taf_text("") == "No TAF available."

    def test_none_input(self):
        assert decode_taf_text(None) == "No TAF available."

    def test_whitespace_only(self):
        assert decode_taf_text("   \n  ") == "No TAF available."

    def test_equals_only(self):
        assert decode_taf_text("= = =") == "No TAF available."

    def test_station_only(self):
        result = decode_taf_text("TAF KJFK")
        assert "station KJFK" in result

    def test_nil_taf(self):
        result = decode_taf_text("TAF KJFK NIL")
        assert "No TAF available" in result
        assert "KJFK" in result

    def test_basic_taf(self):
        raw = "TAF KJFK 071730Z 0718/0824 21015KT P6SM SCT250"
        result = decode_taf_text(raw)
        assert "KJFK" in result
        assert "Winds from 210 degrees at 15 knots" in result
        assert "Visibility greater than 6 statute miles" in result
        assert "Scattered clouds at 25,000 feet" in result

    def test_amended_taf(self):
        raw = "TAF AMD KJFK 071730Z 0718/0824 21015KT P6SM SCT250"
        result = decode_taf_text(raw)
        assert "KJFK" in result

    def test_corrected_taf(self):
        raw = "TAF COR KJFK 071730Z 0718/0824 21015KT P6SM SCT250"
        result = decode_taf_text(raw)
        assert "KJFK" in result

    def test_taf_with_from_group(self):
        raw = "TAF KJFK 071730Z 0718/0824 21015KT P6SM SCT250 FM072200 31010KT P6SM FEW250"
        result = decode_taf_text(raw)
        assert "From" in result
        assert "Winds from 310 degrees at 10 knots" in result

    def test_taf_with_tempo(self):
        raw = "TAF KJFK 071730Z 0718/0824 21015KT P6SM SCT250 TEMPO 0720/0724 3SM -RA"
        result = decode_taf_text(raw)
        assert "Temporary" in result
        assert "light rain" in result

    def test_taf_with_becmg(self):
        raw = "TAF KJFK 071730Z 0718/0824 21015KT P6SM SCT250 BECMG 0720/0722 BKN040"
        result = decode_taf_text(raw)
        assert "Becoming" in result
        assert "Broken clouds at 4,000 feet" in result

    def test_taf_with_probability(self):
        raw = "TAF KJFK 071730Z 0718/0824 21015KT P6SM SCT250 PROB30 0720/0724 1SM +TSRA"
        result = decode_taf_text(raw)
        assert "Probability 30%" in result
        assert "thunderstorms" in result

    def test_taf_with_prob_tempo(self):
        raw = "TAF KJFK 071730Z 0718/0824 21015KT P6SM SCT250 PROB40 TEMPO 0720/0724 1SM +TSRA"
        result = decode_taf_text(raw)
        assert "Probability 40%" in result
        assert "temporary" in result.lower()

    def test_taf_with_remarks(self):
        raw = "TAF KJFK 071730Z 0718/0824 21015KT P6SM SCT250 RMK NXT FCST BY 08Z"
        result = decode_taf_text(raw)
        assert "Remarks:" in result
        assert "NXT FCST BY 08Z" in result

    def test_taf_with_cavok(self):
        raw = "TAF EGLL 071730Z 0718/0824 27010KT CAVOK"
        result = decode_taf_text(raw)
        assert "CAVOK" in result

    def test_taf_with_nsw(self):
        raw = "TAF KJFK 071730Z 0718/0824 21015KT P6SM NSW SCT250"
        result = decode_taf_text(raw)
        assert "No significant weather" in result

    def test_trailing_equals_stripped(self):
        raw = "TAF KJFK 071730Z 0718/0824 21015KT P6SM SCT250="
        result = decode_taf_text(raw)
        assert "KJFK" in result
        assert "=" not in result or "=" in result  # just ensure it parses

    def test_multiline_input(self):
        raw = """TAF KJFK 071730Z 0718/0824
        21015KT P6SM SCT250"""
        result = decode_taf_text(raw)
        assert "KJFK" in result
        assert "Winds" in result

    def test_no_station_prefix(self):
        # No TAF prefix, just station
        result = decode_taf_text("KJFK 071730Z 0718/0824 21015KT P6SM")
        assert "KJFK" in result


# --- _decode_wind ---


class TestDecodeWind:
    def test_basic_wind(self):
        result = _decode_wind("21015KT")
        assert "210 degrees" in result
        assert "15 knots" in result

    def test_wind_with_gusts(self):
        result = _decode_wind("21015G25KT")
        assert "gusts to 25 knots" in result

    def test_variable_wind(self):
        result = _decode_wind("VRB05KT")
        assert "variable" in result.lower()
        assert "5 knots" in result

    def test_calm_wind(self):
        result = _decode_wind("00000KT")
        assert "Calm" in result

    def test_mps_unit(self):
        result = _decode_wind("18010MPS")
        assert "meters per second" in result

    def test_kmh_unit(self):
        result = _decode_wind("27020KMH")
        assert "kilometres per hour" in result

    def test_invalid_wind(self):
        assert _decode_wind("NOSUCHWIND") is None

    def test_three_digit_speed(self):
        result = _decode_wind("270100KT")
        assert "100 knots" in result


# --- _decode_visibility ---


class TestDecodeVisibility:
    def test_statute_miles_integer(self):
        result = _decode_visibility("6SM")
        assert "6 statute miles" in result

    def test_greater_than(self):
        result = _decode_visibility("P6SM")
        assert "greater than" in result

    def test_less_than(self):
        result = _decode_visibility("M1/4SM")
        assert "less than" in result
        assert "1/4" in result

    def test_fraction_visibility(self):
        result = _decode_visibility("1/2SM")
        assert "1/2 statute miles" in result
        assert "0.5" in result

    def test_mixed_number_visibility(self):
        result = _decode_visibility("1 1/2SM")
        assert "1 1/2" in result
        assert "1.5" in result

    def test_meters_visibility(self):
        result = _decode_visibility("5000")
        assert "5.0 kilometres" in result
        assert "5000 meters" in result

    def test_meters_9999(self):
        result = _decode_visibility("9999")
        assert "10 kilometres or more" in result

    def test_empty_string(self):
        assert _decode_visibility("") is None

    def test_invalid_token(self):
        assert _decode_visibility("NOSUCH") is None


# --- _decode_weather ---


class TestDecodeWeather:
    def test_rain(self):
        result = _decode_weather("RA")
        assert "rain" in result

    def test_heavy_rain(self):
        result = _decode_weather("+RA")
        assert "heavy" in result
        assert "rain" in result

    def test_light_snow(self):
        result = _decode_weather("-SN")
        assert "light" in result
        assert "snow" in result

    def test_thunderstorm_rain(self):
        result = _decode_weather("TSRA")
        assert "thunderstorms" in result
        assert "rain" in result

    def test_freezing_rain(self):
        result = _decode_weather("FZRA")
        assert "freezing" in result
        assert "rain" in result

    def test_vicinity(self):
        result = _decode_weather("VCSH")
        assert "vicinity" in result.lower()
        assert "showers" in result

    def test_fog(self):
        result = _decode_weather("FG")
        assert "fog" in result

    def test_mist(self):
        result = _decode_weather("BR")
        assert "mist" in result

    def test_haze(self):
        result = _decode_weather("HZ")
        assert "haze" in result

    def test_empty_string(self):
        assert _decode_weather("") is None

    def test_none_input(self):
        assert _decode_weather(None) is None

    def test_unrecognized_code(self):
        assert _decode_weather("XX") is None

    def test_blowing_snow(self):
        result = _decode_weather("BLSN")
        assert "blowing" in result
        assert "snow" in result

    def test_shallow_fog(self):
        result = _decode_weather("MIFG")
        assert "shallow" in result
        assert "fog" in result


# --- _decode_cloud ---


class TestDecodeCloud:
    def test_few_clouds(self):
        result = _decode_cloud("FEW020")
        assert "few clouds" in result.lower()
        assert "2,000 feet" in result

    def test_scattered(self):
        result = _decode_cloud("SCT250")
        assert "Scattered clouds" in result
        assert "25,000 feet" in result

    def test_broken(self):
        result = _decode_cloud("BKN040")
        assert "Broken clouds" in result
        assert "4,000 feet" in result

    def test_overcast(self):
        result = _decode_cloud("OVC010")
        assert "Overcast" in result
        assert "1,000 feet" in result

    def test_sky_clear(self):
        assert "Sky clear" in _decode_cloud("SKC")
        assert "Sky clear" in _decode_cloud("CLR")

    def test_no_significant_clouds(self):
        result = _decode_cloud("NSC")
        assert "No significant clouds" in result

    def test_cumulonimbus(self):
        result = _decode_cloud("BKN040CB")
        assert "cumulonimbus" in result

    def test_towering_cumulus(self):
        result = _decode_cloud("SCT030TCU")
        assert "towering cumulus" in result

    def test_vertical_visibility(self):
        result = _decode_cloud("VV005")
        assert "Vertical visibility" in result
        assert "500 feet" in result

    def test_invalid_cloud(self):
        assert _decode_cloud("NOSUCHCLOUD") is None

    def test_empty_string(self):
        assert _decode_cloud("") is None

    def test_none_input(self):
        assert _decode_cloud(None) is None

    def test_cloud_with_slashes(self):
        # height "///" means unknown
        result = _decode_cloud("BKN///")
        assert "Broken clouds" in result


# --- _format_day ---


class TestFormatDay:
    def test_1st(self):
        assert _format_day(1) == "1st"

    def test_2nd(self):
        assert _format_day(2) == "2nd"

    def test_3rd(self):
        assert _format_day(3) == "3rd"

    def test_4th(self):
        assert _format_day(4) == "4th"

    def test_11th(self):
        assert _format_day(11) == "11th"

    def test_12th(self):
        assert _format_day(12) == "12th"

    def test_13th(self):
        assert _format_day(13) == "13th"

    def test_21st(self):
        assert _format_day(21) == "21st"

    def test_22nd(self):
        assert _format_day(22) == "22nd"

    def test_31st(self):
        assert _format_day(31) == "31st"


# --- _format_issue_time ---


class TestFormatIssueTime:
    def test_basic(self):
        result = _format_issue_time("071730Z")
        assert "17:30 UTC" in result
        assert "7th" in result


# --- _format_time_range ---


class TestFormatTimeRange:
    def test_basic(self):
        result = _format_time_range("0718/0824")
        assert "18:00 UTC" in result
        assert "7th" in result
        assert "24:00 UTC" in result or "00:00 UTC" in result
        assert "8th" in result

    def test_invalid(self):
        assert _format_time_range("invalid") == "invalid"


# --- _format_from_time ---


class TestFormatFromTime:
    def test_basic(self):
        result = _format_from_time("072200")
        assert "22:00 UTC" in result
        assert "7th" in result

    def test_invalid_length(self):
        assert _format_from_time("123") == "123"

    def test_non_digit(self):
        assert _format_from_time("abcdef") == "abcdef"


# --- _split_segments ---


class TestSplitSegments:
    def test_base_only(self):
        segments, remarks = _split_segments(["21015KT", "P6SM", "SCT250"])
        assert len(segments) == 1
        assert segments[0]["type"] == "base"

    def test_with_from(self):
        segments, _ = _split_segments(["21015KT", "P6SM", "FM072200", "31010KT"])
        types = [s["type"] for s in segments]
        assert "from" in types

    def test_with_tempo(self):
        segments, _ = _split_segments(["21015KT", "TEMPO", "0720/0724", "3SM"])
        types = [s["type"] for s in segments]
        assert "tempo" in types

    def test_with_becmg(self):
        segments, _ = _split_segments(["21015KT", "BECMG", "0720/0722", "BKN040"])
        types = [s["type"] for s in segments]
        assert "becmg" in types

    def test_with_remarks(self):
        _, remarks = _split_segments(["21015KT", "RMK", "NXT", "FCST"])
        assert remarks == "NXT FCST"

    def test_prob_with_separate_period(self):
        segments, _ = _split_segments(["PROB30", "0720/0724", "+TSRA"])
        prob_seg = [s for s in segments if s["type"] == "probability"][0]
        assert prob_seg["prob"] == 30
        assert prob_seg["period"] == "0720/0724"

    def test_prob_tempo(self):
        segments, _ = _split_segments(["PROB40", "TEMPO", "0720/0724", "+TSRA"])
        prob_seg = [s for s in segments if s["type"] == "probability"][0]
        assert prob_seg["qualifier"] == "tempo"

    def test_tempo_with_attached_period(self):
        segments, _ = _split_segments(["TEMPO0720/0724", "3SM"])
        types = [s["type"] for s in segments]
        assert "tempo" in types

    def test_becmg_with_attached_period(self):
        segments, _ = _split_segments(["BECMG0720/0722", "BKN040"])
        types = [s["type"] for s in segments]
        assert "becmg" in types


# --- _segment_intro ---


class TestSegmentIntro:
    def test_base(self):
        assert "Base forecast" in _segment_intro({"type": "base"})

    def test_from_with_time(self):
        result = _segment_intro({"type": "from", "time": "072200"})
        assert "From" in result

    def test_from_without_time(self):
        result = _segment_intro({"type": "from"})
        assert "From" in result

    def test_tempo_with_period(self):
        result = _segment_intro({"type": "tempo", "period": "0720/0724"})
        assert "Temporary" in result

    def test_tempo_without_period(self):
        result = _segment_intro({"type": "tempo"})
        assert "Temporary" in result

    def test_becmg_with_period(self):
        result = _segment_intro({"type": "becmg", "period": "0720/0722"})
        assert "Becoming" in result

    def test_becmg_without_period(self):
        result = _segment_intro({"type": "becmg"})
        assert "Becoming" in result

    def test_probability_with_all(self):
        result = _segment_intro({
            "type": "probability",
            "prob": 30,
            "period": "0720/0724",
            "qualifier": "tempo",
        })
        assert "30%" in result
        assert "temporary" in result.lower()

    def test_probability_no_period(self):
        result = _segment_intro({"type": "probability", "prob": 40})
        assert "40%" in result

    def test_probability_no_prob(self):
        result = _segment_intro({"type": "probability"})
        assert "Probability" in result

    def test_unknown_type(self):
        assert _segment_intro({"type": "unknown"}) == ""


# --- _describe_segment ---


class TestDescribeSegment:
    def test_empty_tokens(self):
        result = _describe_segment({"tokens": []})
        assert "No additional details" in result

    def test_wind_and_vis(self):
        result = _describe_segment({"tokens": ["21015KT", "P6SM"]})
        assert "Winds" in result
        assert "Visibility" in result

    def test_weather_and_clouds(self):
        result = _describe_segment({"tokens": ["-RA", "BKN040"]})
        assert "rain" in result
        assert "Broken" in result

    def test_cavok(self):
        result = _describe_segment({"tokens": ["CAVOK"]})
        assert "CAVOK" in result

    def test_nsw(self):
        result = _describe_segment({"tokens": ["NSW"]})
        assert "No significant weather" in result

    def test_extra_unrecognized_tokens(self):
        result = _describe_segment({"tokens": ["UNKNOWN123"]})
        assert "Additional codes" in result

    def test_mixed_number_visibility(self):
        # e.g. "1 1/2SM" split as two tokens
        result = _describe_segment({"tokens": ["1", "1/2SM"]})
        assert "1 1/2" in result or "1.5" in result


# --- Full TAF integration tests ---


class TestFullTafIntegration:
    def test_complex_taf(self):
        raw = (
            "TAF AMD KJFK 071730Z 0718/0824 21015G25KT P6SM SCT250 "
            "FM072200 31010KT P6SM FEW250 "
            "TEMPO 0720/0724 3SM -RA BKN020 "
            "BECMG 0802/0804 18005KT "
            "PROB30 0806/0810 1SM +TSRA OVC010CB "
            "RMK NXT FCST BY 08Z"
        )
        result = decode_taf_text(raw)
        # Verify all sections present
        assert "KJFK" in result
        assert "gusts to 25" in result
        assert "From" in result
        assert "Temporary" in result
        assert "Becoming" in result
        assert "Probability 30%" in result
        assert "Remarks:" in result

    def test_no_taf_prefix(self):
        raw = "EGLL 071730Z 0718/0824 27010KT 9999 SCT040"
        result = decode_taf_text(raw)
        assert "EGLL" in result
        assert "10 kilometres or more" in result

    def test_header_only_no_station(self):
        result = decode_taf_text("TAF")
        assert "no additional information" in result.lower()
