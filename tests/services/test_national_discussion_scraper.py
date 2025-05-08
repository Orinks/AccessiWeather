"""Tests for national discussion scraper."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from accessiweather.services.national_discussion_scraper import (
    fetch_spc_day1,
    fetch_wpc_short_range,
    get_national_discussion_summaries,
)

# --- Test Data ---

SAMPLE_WPC_HTML = """
<html>
<body>
<pre>
Short-Range Forecast Discussion
NWS Weather Prediction Center College Park MD
1030 AM EDT Thu Apr 18 2024

A strong cold front will bring rain and thunderstorms to the eastern U.S.
Some storms may be severe with damaging winds and hail.
Behind the front, much cooler temperatures are expected.
</pre>
</body>
</html>
"""

SAMPLE_SPC_HTML = """
<html>
<body>
<pre>
Day 1 Convective Outlook
NWS Storm Prediction Center Norman OK
1030 AM EDT Thu Apr 18 2024

...THERE IS A SLIGHT RISK OF SEVERE THUNDERSTORMS ACROSS PORTIONS OF
THE EASTERN U.S...

...SUMMARY...
A potent upper-level system will support severe thunderstorms.
Large hail and damaging winds are the primary threats.
Isolated tornadoes are also possible in some areas.

...REGIONAL DETAIL...
More details for a specific region.

...MAX PROBS...
</pre>
</body>
</html>
"""

SAMPLE_WPC_TEXT = """Short-Range Forecast Discussion
NWS Weather Prediction Center College Park MD
1030 AM EDT Thu Apr 18 2024

A strong cold front will bring rain and thunderstorms to the eastern U.S.
Some storms may be severe with damaging winds and hail.
Behind the front, much cooler temperatures are expected."""

EXPECTED_WPC_SUMMARY = """Short-Range Forecast Discussion
NWS Weather Prediction Center College Park MD
1030 AM EDT Thu Apr 18 2024
A strong cold front will bring rain and thunderstorms to the eastern U.S.
Some storms may be severe with damaging winds and hail.
Behind the front, much cooler temperatures are expected."""

SAMPLE_SPC_PRE_TEXT = """Day 1 Convective Outlook
NWS Storm Prediction Center Norman OK
1030 AM EDT Thu Apr 18 2024

...THERE IS A SLIGHT RISK OF SEVERE THUNDERSTORMS ACROSS PORTIONS OF
THE EASTERN U.S...

...SUMMARY...
A potent upper-level system will support severe thunderstorms.
Large hail and damaging winds are the primary threats.
Isolated tornadoes are also possible in some areas.

...REGIONAL DETAIL...
More details for a specific region.

...MAX PROBS..."""

SAMPLE_SPC_TEXT = """A potent upper-level system will support severe thunderstorms.
Large hail and damaging winds are the primary threats.
Isolated tornadoes are also possible in some areas.

...REGIONAL DETAIL...
More details for a specific region.

...MAX PROBS..."""

EXPECTED_SPC_SUMMARY = """A potent upper-level system will support severe thunderstorms.
Large hail and damaging winds are the primary threats.
Isolated tornadoes are also possible in some areas.
...REGIONAL DETAIL...
More details for a specific region.
...MAX PROBS..."""

# --- Fixtures ---


@pytest.fixture
def mock_requests():
    """Mock requests.get."""
    with patch("requests.get") as mock:
        response = MagicMock()
        response.raise_for_status = MagicMock()
        mock.return_value = response
        yield mock


@pytest.fixture
def mock_bs4():
    """Mock BeautifulSoup."""
    with patch("bs4.BeautifulSoup") as mock:
        soup = MagicMock()
        mock.return_value = soup
        yield mock, soup


@pytest.fixture
def mock_sleep():
    """Mock time.sleep."""
    with patch("time.sleep") as mock:
        yield mock


@pytest.fixture
def mock_time():
    """Mock time.time."""
    with patch("time.time") as mock:
        mock.return_value = 1000.0  # Fixed timestamp for most tests
        yield mock


@pytest.fixture
def clean_last_request_time():
    """Clear the _last_request_time dictionary."""
    with patch.dict(
        "accessiweather.services.national_discussion_scraper._last_request_time", clear=True
    ):
        yield


# --- WPC Tests ---


def test_fetch_wpc_success(mock_requests, mock_bs4, mock_sleep):  # noqa: ARG001
    """Test successful WPC discussion fetch."""
    mock_requests.return_value.text = SAMPLE_WPC_HTML
    mock_bs4[1].find.return_value.get_text.return_value = SAMPLE_WPC_TEXT

    result = fetch_wpc_short_range()

    assert result == SAMPLE_WPC_TEXT
    mock_requests.assert_called_once_with(
        "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdspd",
        headers={"User-Agent": "AccessiWeatherBot/1.0 (contact: youremail@example.com)"},
        timeout=10,
    )


def test_fetch_wpc_no_pre_tag(mock_requests, mock_bs4, mock_sleep):  # noqa: ARG001
    """Test WPC fetch when pre tag is missing."""
    mock_requests.return_value.text = "<html><body>No pre tag here</body></html>"
    mock_bs4[1].find.return_value = None

    result = fetch_wpc_short_range()

    assert result == "No discussion found. (WPC)"


def test_fetch_wpc_request_error(mock_requests, mock_sleep):  # noqa: ARG001
    """Test WPC fetch when request fails."""
    mock_requests.side_effect = requests.exceptions.RequestException("Connection error")

    # We need to modify the test to match the actual implementation
    result = fetch_wpc_short_range()
    assert result == "No discussion found. (WPC)"


def test_fetch_wpc_rate_limit(
    mock_requests, mock_bs4, mock_sleep, mock_time, clean_last_request_time  # noqa: ARG001
):
    """Test WPC rate limiting."""
    mock_requests.return_value.text = SAMPLE_WPC_HTML
    mock_bs4[1].find.return_value.get_text.return_value = SAMPLE_WPC_TEXT

    # First call at t=1000.0
    mock_time.return_value = 1000.0
    fetch_wpc_short_range()
    mock_sleep.assert_not_called()

    # Second call at t=1001.0 (9 seconds after first call)
    mock_time.return_value = 1001.0
    fetch_wpc_short_range()
    mock_sleep.assert_called_once_with(9.0)


# --- SPC Tests ---


def test_fetch_spc_success_with_summary(mock_requests, mock_bs4, mock_sleep):  # noqa: ARG001
    """Test successful SPC discussion fetch with ...SUMMARY... marker."""
    mock_requests.return_value.text = SAMPLE_SPC_HTML
    pre_mock = MagicMock()
    pre_mock.get_text.return_value = SAMPLE_SPC_PRE_TEXT
    mock_bs4[1].find.return_value = pre_mock

    result = fetch_spc_day1()
    print(f"Result: {repr(result)}")  # Debug print
    print(f"Expected: {repr(SAMPLE_SPC_TEXT)}")  # Debug print

    assert result == SAMPLE_SPC_TEXT
    mock_requests.assert_called_once_with(
        "https://www.spc.noaa.gov/products/outlook/day1otlk.html",
        headers={"User-Agent": "AccessiWeatherBot/1.0 (contact: youremail@example.com)"},
        timeout=10,
    )


def test_fetch_spc_success_no_summary_marker(mock_requests, mock_bs4, mock_sleep):  # noqa: ARG001
    """Test successful SPC discussion fetch without ...SUMMARY... marker."""
    mock_requests.return_value.text = (
        "<html><body><pre>Full text without marker</pre></body></html>"
    )
    mock_bs4[1].find.return_value.get_text.return_value = "Full text without marker"

    result = fetch_spc_day1()

    assert result == "Full text without marker"


def test_fetch_spc_no_pre_tag(mock_requests, mock_bs4, mock_sleep):  # noqa: ARG001
    """Test SPC fetch when pre tag is missing."""
    mock_requests.return_value.text = "<html><body>No pre tag here</body></html>"
    mock_bs4[1].find.return_value = None

    result = fetch_spc_day1()

    assert result == "No discussion found. (SPC)"


def test_fetch_spc_request_error(mock_requests, mock_sleep):  # noqa: ARG001
    """Test SPC fetch when request fails."""
    mock_requests.side_effect = requests.exceptions.RequestException("Connection error")

    result = fetch_spc_day1()

    assert result == "No discussion found. (SPC)"


def test_fetch_spc_rate_limit(
    mock_requests, mock_bs4, mock_sleep, mock_time, clean_last_request_time  # noqa: ARG001
):
    """Test SPC rate limiting."""
    mock_requests.return_value.text = SAMPLE_SPC_HTML
    mock_bs4[1].find.return_value.get_text.return_value = SAMPLE_SPC_TEXT

    # First call at t=1000.0
    mock_time.return_value = 1000.0
    fetch_spc_day1()
    mock_sleep.assert_not_called()

    # Second call at t=1001.0 (9 seconds after first call)
    mock_time.return_value = 1001.0
    fetch_spc_day1()
    mock_sleep.assert_called_once_with(9.0)


# --- Summary Tests ---


def test_get_national_discussion_summaries_success():
    """Test successful national discussion summaries."""
    with patch(
        "accessiweather.services.national_discussion_scraper.fetch_wpc_short_range"
    ) as mock_wpc:
        with patch(
            "accessiweather.services.national_discussion_scraper.fetch_spc_day1"
        ) as mock_spc:
            mock_wpc.return_value = SAMPLE_WPC_TEXT
            mock_spc.return_value = SAMPLE_SPC_TEXT

            result = get_national_discussion_summaries()

            # The summary function takes the first 10 non-empty lines
            assert result["wpc"]["short_range_summary"] == EXPECTED_WPC_SUMMARY
            assert result["wpc"]["short_range_full"] == SAMPLE_WPC_TEXT
            assert result["spc"]["day1_summary"] == EXPECTED_SPC_SUMMARY
            assert result["spc"]["day1_full"] == SAMPLE_SPC_TEXT
            assert "attribution" in result
            assert "NOAA" in result["attribution"]


def test_get_national_discussion_summaries_wpc_error():
    """Test national discussion summaries with WPC error."""
    with patch(
        "accessiweather.services.national_discussion_scraper.fetch_wpc_short_range"
    ) as mock_wpc:
        with patch(
            "accessiweather.services.national_discussion_scraper.fetch_spc_day1"
        ) as mock_spc:
            mock_wpc.return_value = "Error fetching WPC discussion."
            mock_spc.return_value = SAMPLE_SPC_TEXT

            result = get_national_discussion_summaries()

            assert result["wpc"]["short_range_summary"] == "Error fetching WPC discussion."
            assert result["wpc"]["short_range_full"] == "Error fetching WPC discussion."
            assert result["spc"]["day1_summary"] == EXPECTED_SPC_SUMMARY
            assert result["spc"]["day1_full"] == SAMPLE_SPC_TEXT


def test_get_national_discussion_summaries_spc_error():
    """Test national discussion summaries with SPC error."""
    with patch(
        "accessiweather.services.national_discussion_scraper.fetch_wpc_short_range"
    ) as mock_wpc:
        with patch(
            "accessiweather.services.national_discussion_scraper.fetch_spc_day1"
        ) as mock_spc:
            mock_wpc.return_value = SAMPLE_WPC_TEXT
            mock_spc.return_value = "Error fetching SPC discussion."

            result = get_national_discussion_summaries()

            assert result["wpc"]["short_range_summary"] == EXPECTED_WPC_SUMMARY
            assert result["wpc"]["short_range_full"] == SAMPLE_WPC_TEXT
            assert result["spc"]["day1_summary"] == "Error fetching SPC discussion."
            assert result["spc"]["day1_full"] == "Error fetching SPC discussion."


def test_get_national_discussion_summaries_both_error():
    """Test national discussion summaries with both services erroring."""
    with patch(
        "accessiweather.services.national_discussion_scraper.fetch_wpc_short_range"
    ) as mock_wpc:
        with patch(
            "accessiweather.services.national_discussion_scraper.fetch_spc_day1"
        ) as mock_spc:
            mock_wpc.return_value = "Error fetching WPC discussion."
            mock_spc.return_value = "Error fetching SPC discussion."

            result = get_national_discussion_summaries()

            assert result["wpc"]["short_range_summary"] == "Error fetching WPC discussion."
            assert result["wpc"]["short_range_full"] == "Error fetching WPC discussion."
            assert result["spc"]["day1_summary"] == "Error fetching SPC discussion."
            assert result["spc"]["day1_full"] == "Error fetching SPC discussion."
