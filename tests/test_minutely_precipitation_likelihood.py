"""Tests for probability-based precipitation likelihood detection."""

from __future__ import annotations

from accessiweather.notifications.minutely_precipitation import (
    NO_LIKELIHOOD_SIGNATURE,
    MinutelyPrecipitationLikelihood,
    _probability_band,
    build_minutely_likelihood_signature,
    detect_minutely_precipitation_likelihood,
    parse_pirate_weather_minutely_block,
)


class TestProbabilityBand:
    """Tests for the _probability_band helper."""

    def test_band_50_70(self):
        assert _probability_band(0.5) == "50-70%"
        assert _probability_band(0.6) == "50-70%"
        assert _probability_band(0.69) == "50-70%"

    def test_band_70_90(self):
        assert _probability_band(0.7) == "70-90%"
        assert _probability_band(0.8) == "70-90%"
        assert _probability_band(0.89) == "70-90%"

    def test_band_90_plus(self):
        assert _probability_band(0.9) == "90%+"
        assert _probability_band(0.95) == "90%+"
        assert _probability_band(1.0) == "90%+"


class TestDetectMinutelyPrecipitationLikelihood:
    """Tests for detect_minutely_precipitation_likelihood."""

    def test_returns_none_for_none_forecast(self):
        assert detect_minutely_precipitation_likelihood(None) is None

    def test_returns_none_when_currently_wet(self):
        forecast = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0.05, "precipType": "rain"},
                    {
                        "time": 1768917660,
                        "precipIntensity": 0,
                        "precipProbability": 0.8,
                        "precipType": "rain",
                    },
                ]
            }
        )
        assert detect_minutely_precipitation_likelihood(forecast) is None

    def test_returns_none_when_all_below_threshold(self):
        forecast = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0, "precipProbability": 0},
                    {"time": 1768917660, "precipIntensity": 0, "precipProbability": 0.3},
                    {"time": 1768917720, "precipIntensity": 0, "precipProbability": 0.4},
                ]
            }
        )
        assert detect_minutely_precipitation_likelihood(forecast, threshold=0.5) is None

    def test_detects_likelihood_above_threshold(self):
        forecast = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0, "precipProbability": 0},
                    {
                        "time": 1768917660,
                        "precipIntensity": 0,
                        "precipProbability": 0.7,
                        "precipType": "rain",
                    },
                    {
                        "time": 1768917720,
                        "precipIntensity": 0,
                        "precipProbability": 0.5,
                        "precipType": "rain",
                    },
                ]
            }
        )
        result = detect_minutely_precipitation_likelihood(forecast, threshold=0.5)
        assert result is not None
        assert result.max_probability == 0.7
        assert result.precipitation_type == "rain"
        assert result.probability_band == "70-90%"

    def test_uses_max_probability(self):
        forecast = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0, "precipProbability": 0},
                    {
                        "time": 1768917660,
                        "precipIntensity": 0,
                        "precipProbability": 0.6,
                        "precipType": "rain",
                    },
                    {
                        "time": 1768917720,
                        "precipIntensity": 0,
                        "precipProbability": 0.95,
                        "precipType": "snow",
                    },
                ]
            }
        )
        result = detect_minutely_precipitation_likelihood(forecast, threshold=0.5)
        assert result is not None
        assert result.max_probability == 0.95
        assert result.precipitation_type == "snow"
        assert result.probability_band == "90%+"

    def test_custom_threshold(self):
        forecast = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0, "precipProbability": 0},
                    {
                        "time": 1768917660,
                        "precipIntensity": 0,
                        "precipProbability": 0.65,
                        "precipType": "rain",
                    },
                ]
            }
        )
        # With default threshold 0.5, should detect
        assert detect_minutely_precipitation_likelihood(forecast, threshold=0.5) is not None
        # With higher threshold 0.7, should not detect
        assert detect_minutely_precipitation_likelihood(forecast, threshold=0.7) is None


class TestMinutelyPrecipitationLikelihood:
    """Tests for the MinutelyPrecipitationLikelihood dataclass."""

    def test_event_type(self):
        likelihood = MinutelyPrecipitationLikelihood(
            max_probability=0.7, precipitation_type="rain", probability_band="70-90%"
        )
        assert likelihood.event_type == "minutely_precipitation_likelihood"

    def test_title_with_rain(self):
        likelihood = MinutelyPrecipitationLikelihood(
            max_probability=0.7, precipitation_type="rain", probability_band="70-90%"
        )
        assert likelihood.title == "Rain likely in the next hour (70% chance)"

    def test_title_with_snow(self):
        likelihood = MinutelyPrecipitationLikelihood(
            max_probability=0.95, precipitation_type="snow", probability_band="90%+"
        )
        assert likelihood.title == "Snow likely in the next hour (95% chance)"

    def test_title_without_type(self):
        likelihood = MinutelyPrecipitationLikelihood(
            max_probability=0.6, precipitation_type=None, probability_band="50-70%"
        )
        assert likelihood.title == "Precipitation likely in the next hour (60% chance)"


class TestBuildMinutelyLikelihoodSignature:
    """Tests for build_minutely_likelihood_signature."""

    def test_returns_none_for_none_forecast(self):
        assert build_minutely_likelihood_signature(None) is None

    def test_returns_no_likelihood_when_below_threshold(self):
        forecast = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0, "precipProbability": 0},
                    {"time": 1768917660, "precipIntensity": 0, "precipProbability": 0.3},
                ]
            }
        )
        assert build_minutely_likelihood_signature(forecast) == NO_LIKELIHOOD_SIGNATURE

    def test_returns_signature_with_band_and_type(self):
        forecast = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0, "precipProbability": 0},
                    {
                        "time": 1768917660,
                        "precipIntensity": 0,
                        "precipProbability": 0.8,
                        "precipType": "rain",
                    },
                ]
            }
        )
        sig = build_minutely_likelihood_signature(forecast)
        assert sig == "likelihood:70-90%:rain"

    def test_returns_signature_with_default_type(self):
        forecast = parse_pirate_weather_minutely_block(
            {
                "data": [
                    {"time": 1768917600, "precipIntensity": 0, "precipProbability": 0},
                    {"time": 1768917660, "precipIntensity": 0, "precipProbability": 0.6},
                ]
            }
        )
        sig = build_minutely_likelihood_signature(forecast)
        assert sig == "likelihood:50-70%:precipitation"

    def test_different_bands_produce_different_signatures(self):
        data_70 = {
            "data": [
                {"time": 1768917600, "precipIntensity": 0, "precipProbability": 0},
                {
                    "time": 1768917660,
                    "precipIntensity": 0,
                    "precipProbability": 0.75,
                    "precipType": "rain",
                },
            ]
        }
        data_95 = {
            "data": [
                {"time": 1768917600, "precipIntensity": 0, "precipProbability": 0},
                {
                    "time": 1768917660,
                    "precipIntensity": 0,
                    "precipProbability": 0.95,
                    "precipType": "rain",
                },
            ]
        }
        sig1 = build_minutely_likelihood_signature(parse_pirate_weather_minutely_block(data_70))
        sig2 = build_minutely_likelihood_signature(parse_pirate_weather_minutely_block(data_95))
        assert sig1 != sig2
        assert sig1 == "likelihood:70-90%:rain"
        assert sig2 == "likelihood:90%+:rain"
