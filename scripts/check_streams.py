#!/usr/bin/env python3
"""Check NOAA Weather Radio stream URLs for health.

Tests each stream URL with a short connection attempt and reports
dead/error streams. Can be run standalone or via CI/cron.

Usage:
    python scripts/check_streams.py [--timeout 10] [--json] [--fail-on-errors]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# Add src to path so we can import the stream URL provider
# This is necessary because the script is run from the scripts/ directory
# and needs to import modules from the src/accessiweather/ directory.
# We use Path(__file__).parent to get the directory of the current script,
# then go up one level to 'scripts' and then up another level to the root,
# finally down into 'src'.
src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

try:
    from accessiweather.noaa_radio.stream_url import StreamURLProvider
except ImportError:
    print("Error: Could not import StreamURLProvider.")
    print("Please ensure the script is run from the 'scripts/' directory")
    print("or that 'src/' is in your Python path.")
    sys.exit(1)

# Default timeout for checking each URL
DEFAULT_TIMEOUT = 10
# User agent to identify our stream check script
USER_AGENT = "AccessiWeather-StreamCheck/1.0"


def check_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Check if a stream URL is reachable.

    Performs a GET request and reads a small chunk of data to confirm
    the stream is active. Returns a dictionary with the URL, status,
    any error message, and the response time in milliseconds.

    Args:
        url: The URL to check.
        timeout: The connection timeout in seconds.

    Returns:
        A dictionary containing the check result.
    """
    start_time = time.monotonic()
    result = {"url": url, "status": "unknown", "error": None, "response_time_ms": 0}

    try:
        # Create a request object with a User-Agent and Icy-MetaData header
        # Icy-MetaData can help some Icecast servers negotiate stream details.
        req = urllib.request.Request(
            url, method="GET", headers={"User-Agent": USER_AGENT, "Icy-MetaData": "1"}
        )

        with urllib.request.urlopen(req, timeout=timeout) as response:
            # Read a small chunk (1KB) to confirm the stream is active and sending data.
            # This helps differentiate a connection that opens but immediately closes
            # or sends no data.
            data = response.read(1024)

            if not data:
                result["status"] = "empty_stream"
                result["error"] = "No data received from stream"
            else:
                result["status"] = "ok"
                result["content_type"] = response.headers.get("Content-Type", "N/A")
                # Check for common non-streaming content types
                content_type = result["content_type"].lower()
                if (
                    "html" in content_type
                    or "text/plain" in content_type
                    and not "audio" in content_type
                ):
                    result["status"] = "non_stream_content"
                    result["error"] = f"Expected audio, got content type: {result['content_type']}"

    except urllib.error.HTTPError as e:
        result["status"] = "http_error"
        result["error"] = f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        # This catches network errors like DNS resolution failure, connection refused, etc.
        result["status"] = "url_error"
        result["error"] = str(e.reason)
    except TimeoutError:
        result["status"] = "timeout"
        result["error"] = f"Connection timed out after {timeout}s"
    except Exception as e:
        # Catch any other unexpected errors
        result["status"] = "error"
        result["error"] = str(e)

    result["response_time_ms"] = round((time.monotonic() - start_time) * 1000)
    return result


def main():
    """Main function to parse arguments, run checks, and report results."""
    parser = argparse.ArgumentParser(
        description="Check NOAA Weather Radio stream health",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,  # Show default values in help
    )
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT, help="Connection timeout per URL (seconds)"
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument(
        "--fail-on-errors",
        action="store_true",
        help="Exit with code 1 if any streams are dead or errored",
    )
    args = parser.parse_args()

    provider = StreamURLProvider()

    # _STREAM_URLS is a protected member, but it's the most direct way to access the data.
    # In a real-world scenario where this might be considered 'private' API,
    # we might add a method like `get_all_stream_urls()` to the provider class.
    all_stations_streams = provider._STREAM_URLS

    total_urls_checked = 0
    healthy_urls = 0
    errored_checks = []
    all_results = []

    station_count = len(all_stations_streams)
    print(
        f"Checking {station_count} stations with {sum(len(urls) for urls in all_stations_streams.values())} total streams...\n",
        file=sys.stderr,
    )

    # Sort stations by call sign for consistent output
    for call_sign in sorted(all_stations_streams.keys()):
        urls = all_stations_streams[call_sign]
        for url in urls:
            total_urls_checked += 1
            result = check_url(url, timeout=args.timeout)
            result["call_sign"] = call_sign
            all_results.append(result)

            # Increment healthy count only if status is 'ok'
            if result["status"] == "ok":
                healthy_urls += 1
            else:
                errored_checks.append(result)
                # Print live errors if not in JSON mode
                if not args.json:
                    print(
                        f"  ✗ {result['call_sign']}: {result['url']} — {result['error']}",
                        file=sys.stderr,
                    )

    # Determine stations with no working streams
    dead_station_call_signs = set()
    for station_call_sign, station_stream_urls in all_stations_streams.items():
        # Check if all URLs for this station resulted in an error
        all_station_urls_failed = True
        for url_data in all_results:
            if url_data["call_sign"] == station_call_sign:
                if url_data["status"] == "ok":
                    all_station_urls_failed = False
                    break  # Found at least one working URL for this station
        if all_station_urls_failed:
            # Ensure the station actually had URLs defined
            if station_stream_urls:
                dead_station_call_signs.add(station_call_sign)

    # Prepare output
    output_data = {
        "total_stations": station_count,
        "total_urls_checked": total_urls_checked,
        "healthy_urls": healthy_urls,
        "errored_urls": len(errored_checks),
        "dead_station_call_signs": sorted(list(dead_station_call_signs)),
        "all_errors": errored_checks,
        "summary": {
            "healthy_ratio": healthy_urls / total_urls_checked if total_urls_checked else 0,
            "dead_station_count": len(dead_station_call_signs),
        },
    }

    if args.json:
        # Print JSON output to stdout
        print(json.dumps(output_data, indent=2))
    else:
        # Print formatted text output to stderr for progress/errors, summary to stdout
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(f"Stream Check Complete:", file=sys.stderr)
        print(f"  Total Stations: {output_data['total_stations']}", file=sys.stderr)
        print(f"  Total URLs Checked: {output_data['total_urls_checked']}", file=sys.stderr)
        print(f"  Healthy URLs: {output_data['healthy_urls']}", file=sys.stderr)
        print(f"  Errored URLs: {output_data['errored_urls']}", file=sys.stderr)

        if output_data["dead_station_call_signs"]:
            print(
                f"\nStations with NO working streams ({len(output_data['dead_station_call_signs'])}):",
                file=sys.stderr,
            )
            for cs in output_data["dead_station_call__signs"]:
                print(f"  - {cs}", file=sys.stderr)
        elif not errored_checks:
            print("\nAll streams are healthy ✓", file=sys.stderr)

        # Print all errors to stdout for easy review
        print("\n--- All Errored URLs ---")
        if errored_checks:
            for error_info in output_data["all_errors"]:
                print(
                    f"  {error_info['call_sign']}: {error_info['url']} — {error_info['error']} (Response Time: {error_info['response_time_ms']}ms)"
                )
        else:
            print("  No errors found.")

    # Exit with code 1 if --fail-on-errors is set and there were errors
    if args.fail_on_errors and (errored_checks or dead_station_call_signs):
        sys.exit(1)


if __name__ == "__main__":
    main()
