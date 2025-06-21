"""Tests for NationalDiscussionScraper class."""

import time
import unittest

import requests_mock

from accessiweather.services.national_discussion_scraper import NationalDiscussionScraper


class TestNationalDiscussionScraper(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        # Create scraper with minimal delay for faster tests
        self.scraper = NationalDiscussionScraper(request_delay=0.01)

        # Load sample HTML responses
        with open("tests/data/wpc_sample.html") as f:
            self.wpc_html = f.read()

        with open("tests/data/spc_sample.html") as f:
            self.spc_html = f.read()

    def test_rate_limiting(self):
        """Test rate limiting between requests."""
        # Reset last request time for domain
        domain = "test.domain"
        self.scraper.last_request_time = {}

        # Set a longer delay for this test
        self.scraper.request_delay = 0.2

        # First call should not wait
        start_time = time.time()
        self.scraper._rate_limit(domain)
        elapsed = time.time() - start_time
        self.assertLess(elapsed, 0.1)  # Should be almost instant

        # Second immediate call should wait for the delay
        start_time = time.time()
        self.scraper._rate_limit(domain)
        elapsed = time.time() - start_time
        self.assertGreaterEqual(elapsed, 0.19)  # Should wait ~0.2s

    def test_fetch_wpc_discussion_success(self):
        """Test successful WPC discussion fetching."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdspd",
                text=self.wpc_html,
            )

            result = self.scraper.fetch_wpc_discussion()

            # Verify result structure
            self.assertIn("summary", result)
            self.assertIn("full", result)
            self.assertTrue(len(result["summary"]) > 0)
            self.assertTrue(len(result["full"]) > 0)

            # Summary should be shorter than full text
            self.assertLess(len(result["summary"]), len(result["full"]))

            # Verify content
            self.assertIn("Short-Range Forecast Discussion", result["summary"])
            self.assertIn("Snow is possible", result["full"])

            # Verify summary is first 150 chars of full text
            expected_summary = (
                result["full"][:150] + "..." if len(result["full"]) > 150 else result["full"]
            )
            self.assertEqual(result["summary"], expected_summary)

            # Verify summary includes important header lines
            self.assertIn("Weather Prediction Center", result["summary"])
            self.assertIn("EDT", result["summary"])

    def test_fetch_wpc_discussion_error(self):
        """Test WPC discussion fetching with error."""
        with requests_mock.Mocker() as m:
            # Mock all possible URLs that the scraper might try
            m.get(
                "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdspd",
                status_code=404,
            )
            m.get(
                "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdepd",
                status_code=404,
            )
            m.get(
                "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdhi",
                status_code=404,
            )
            m.get(
                "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdak",
                status_code=404,
            )

            result = self.scraper.fetch_wpc_discussion()

            # Verify error result
            self.assertIn("summary", result)
            self.assertIn("full", result)
            self.assertEqual("No discussion found. (WPC)", result["summary"])
            self.assertEqual("", result["full"])

    def test_fetch_wpc_discussion_no_pre_tag(self):
        """Test WPC discussion fetching with missing pre tag."""
        with requests_mock.Mocker() as m:
            # Mock all possible URLs that the scraper might try
            m.get(
                "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdspd",
                text="<html><body>No pre tag here</body></html>",
            )
            m.get(
                "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdepd",
                text="<html><body>No pre tag here</body></html>",
            )
            m.get(
                "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdhi",
                text="<html><body>No pre tag here</body></html>",
            )
            m.get(
                "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdak",
                text="<html><body>No pre tag here</body></html>",
            )

            result = self.scraper.fetch_wpc_discussion()

            # Verify error result
            self.assertIn("summary", result)
            self.assertIn("full", result)
            self.assertEqual("No discussion found. (WPC)", result["summary"])
            self.assertEqual("", result["full"])

    def test_fetch_spc_discussion_success(self):
        """Test successful SPC discussion fetching."""
        with requests_mock.Mocker() as m:
            m.get("https://www.spc.noaa.gov/products/outlook/day1otlk.html", text=self.spc_html)

            result = self.scraper.fetch_spc_discussion()

            # Verify result structure
            self.assertIn("summary", result)
            self.assertIn("full", result)
            self.assertTrue(len(result["summary"]) > 0)
            self.assertTrue(len(result["full"]) > 0)

            # Verify content
            self.assertIn("potent upper-level system", result["summary"])
            self.assertIn("TORNADO", result["full"])

            # Verify text is extracted after "...SUMMARY..."
            self.assertNotIn("Day 1 Convective Outlook", result["full"])
            self.assertIn("A potent upper-level system", result["full"])

            # Verify summary is first 150 chars of full text
            expected_summary = (
                result["full"][:150] + "..." if len(result["full"]) > 150 else result["full"]
            )
            self.assertEqual(result["summary"], expected_summary)

            # Verify regional details are included in full text
            self.assertIn("...REGIONAL DETAIL...", result["full"])
            self.assertIn("cold front", result["full"])

    def test_fetch_spc_discussion_error(self):
        """Test SPC discussion fetching with error."""
        with requests_mock.Mocker() as m:
            # Mock all possible URLs that the scraper might try
            m.get("https://www.spc.noaa.gov/products/outlook/day1otlk.html", status_code=500)
            m.get("https://www.spc.noaa.gov/products/outlook/day1otlk_1300.html", status_code=500)
            m.get("https://www.spc.noaa.gov/products/outlook/day1otlk_1630.html", status_code=500)
            m.get("https://www.spc.noaa.gov/products/outlook/day1otlk_2000.html", status_code=500)

            result = self.scraper.fetch_spc_discussion()

            # Verify error result
            self.assertIn("summary", result)
            self.assertIn("full", result)
            self.assertEqual("No discussion found. (SPC)", result["summary"])
            self.assertEqual("", result["full"])

    def test_fetch_spc_discussion_no_pre_tag(self):
        """Test SPC discussion fetching with missing pre tag."""
        with requests_mock.Mocker() as m:
            # Mock all possible URLs that the scraper might try
            m.get(
                "https://www.spc.noaa.gov/products/outlook/day1otlk.html",
                text="<html><body>No pre tag here</body></html>",
            )
            m.get(
                "https://www.spc.noaa.gov/products/outlook/day1otlk_1300.html",
                text="<html><body>No pre tag here</body></html>",
            )
            m.get(
                "https://www.spc.noaa.gov/products/outlook/day1otlk_1630.html",
                text="<html><body>No pre tag here</body></html>",
            )
            m.get(
                "https://www.spc.noaa.gov/products/outlook/day1otlk_2000.html",
                text="<html><body>No pre tag here</body></html>",
            )

            result = self.scraper.fetch_spc_discussion()

            # Verify error result
            self.assertIn("summary", result)
            self.assertIn("full", result)
            self.assertEqual("No discussion found. (SPC)", result["summary"])
            self.assertEqual("", result["full"])

    def test_fetch_spc_discussion_no_summary_marker(self):
        """Test SPC discussion fetching without ...SUMMARY... marker."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://www.spc.noaa.gov/products/outlook/day1otlk.html",
                text="<html><body><pre>Full text without marker</pre></body></html>",
            )

            result = self.scraper.fetch_spc_discussion()

            # Verify result uses full text when no marker found
            self.assertIn("summary", result)
            self.assertIn("full", result)
            self.assertEqual("Full text without marker", result["full"])
            self.assertEqual("Full text without marker", result["summary"])

    def test_fetch_all_discussions(self):
        """Test fetching all discussions."""
        with requests_mock.Mocker() as m:
            m.get(
                "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdspd",
                text=self.wpc_html,
            )
            m.get("https://www.spc.noaa.gov/products/outlook/day1otlk.html", text=self.spc_html)

            result = self.scraper.fetch_all_discussions()

            # Verify result structure
            self.assertIn("wpc", result)
            self.assertIn("spc", result)
            self.assertIn("summary", result["wpc"])
            self.assertIn("full", result["wpc"])
            self.assertIn("summary", result["spc"])
            self.assertIn("full", result["spc"])

            # Verify content
            self.assertIn("Short-Range Forecast Discussion", result["wpc"]["summary"])
            self.assertIn("Snow is possible", result["wpc"]["full"])
            self.assertIn("potent upper-level system", result["spc"]["summary"])
            self.assertIn("TORNADO", result["spc"]["full"])

    def test_fetch_all_discussions_partial_failure(self):
        """Test fetching all discussions with one service failing."""
        with requests_mock.Mocker() as m:
            # Mock WPC URLs
            m.get(
                "https://www.wpc.ncep.noaa.gov/discussions/hpcdiscussions.php?disc=pmdspd",
                text=self.wpc_html,
            )

            # Mock SPC URLs with failure status
            m.get("https://www.spc.noaa.gov/products/outlook/day1otlk.html", status_code=404)
            m.get("https://www.spc.noaa.gov/products/outlook/day1otlk_1300.html", status_code=404)
            m.get("https://www.spc.noaa.gov/products/outlook/day1otlk_1630.html", status_code=404)
            m.get("https://www.spc.noaa.gov/products/outlook/day1otlk_2000.html", status_code=404)

            result = self.scraper.fetch_all_discussions()

            # Verify result structure
            self.assertIn("wpc", result)
            self.assertIn("spc", result)

            # WPC should succeed
            self.assertIn("Short-Range Forecast Discussion", result["wpc"]["summary"])

            # SPC should fail gracefully
            self.assertEqual("No discussion found. (SPC)", result["spc"]["summary"])
            self.assertEqual("", result["spc"]["full"])


if __name__ == "__main__":
    unittest.main()
