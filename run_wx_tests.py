#!/usr/bin/env python
"""
Run wxPython tests with enhanced debugging and segmentation fault handling.

This script runs pytest with additional configuration to help debug
segmentation faults in wxPython tests.
"""

import argparse
import faulthandler
import gc
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run wxPython tests with enhanced debugging"
    )
    parser.add_argument(
        "test_path",
        nargs="?",
        default="tests/",
        help="Path to test file or directory (default: tests/)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "--memory-tracking",
        action="store_true",
        help="Enable memory tracking (slower but more informative)",
    )
    parser.add_argument(
        "--no-faulthandler",
        action="store_true",
        help="Disable faulthandler (not recommended)",
    )
    parser.add_argument(
        "--isolated",
        action="store_true",
        help="Run each test in a separate process for better isolation",
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Run tests with coverage"
    )
    parser.add_argument(
        "--repeat", type=int, default=1, help="Repeat tests multiple times"
    )
    parser.add_argument(
        "--timeout", type=int, default=30,
        help="Timeout in seconds for each test (default: 30)"
    )
    return parser.parse_args()


def setup_faulthandler():
    """Set up faulthandler for the current process."""
    # Create logs directory if it doesn't exist
    log_dir = Path("tests/logs")
    log_dir.mkdir(exist_ok=True, parents=True)

    # Enable faulthandler to stderr
    faulthandler.enable()

    # Create a log file for faulthandler
    fault_log_path = log_dir / "run_wx_tests_faulthandler.log"
    try:
        log_file = open(fault_log_path, "w")
        faulthandler.enable(file=log_file)
        logger.info(f"Faulthandler enabled, logging to {fault_log_path}")

        # Register for SIGUSR1 signal if on Unix
        if hasattr(signal, "SIGUSR1"):
            faulthandler.register(signal.SIGUSR1, file=log_file)
            logger.info("Registered faulthandler for SIGUSR1 signal")

        return log_file
    except Exception as e:
        logger.error(f"Failed to set up faulthandler log file: {e}")
        return None


def run_tests_isolated(args):
    """Run each test in a separate process for better isolation."""
    # Use a different approach to collect tests
    # Run pytest with the --collect-only flag but with a custom format
    collect_cmd = [
        sys.executable, "-m", "pytest",
        args.test_path,
        "--collect-only",
        "-q",  # Quiet mode
        "--no-header",  # No header
        "--no-summary",  # No summary
    ]
    logger.info(f"Collecting tests with command: {' '.join(collect_cmd)}")

    # Run the command to get a list of test nodeids
    result = subprocess.run(collect_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Failed to collect tests: {result.stderr}")
        return 1

    # Get the test nodeids from the output
    test_items = []
    for line in result.stdout.splitlines():
        if line.strip():
            test_items.append(line.strip())
            logger.debug(f"Found test: {line.strip()}")

    if not test_items:
        logger.error("No tests found")
        return 1

    # --- Debugging addition ---
    print(f"Collected test items: {test_items}")
    logger.info("Exiting after printing collected items for debugging.")
    sys.exit(1) # Exit here to prevent running the tests
    # --- End debugging addition ---

    logger.info(f"Running {len(test_items)} tests in isolated mode")

    # Run each test in a separate process
    failed_tests = []
    for i, test_item in enumerate(test_items):
        logger.info(f"Running test {i+1}/{len(test_items)}: {test_item}")

        # Build command
        cmd = [sys.executable, "-m", "pytest", test_item, "-v"]
        if args.memory_tracking:
            cmd.append("--memory-tracking")
        if args.coverage:
            cmd.extend(["--cov=src", "--cov-append"])

        # Run the test with timeout
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )

            # Read output with timeout
            start_time = time.time()
            output = []

            while True:
                # Check if process has finished
                if process.poll() is not None:
                    break

                # Check for timeout
                if time.time() - start_time > args.timeout:
                    logger.error(f"Test {test_item} timed out after {args.timeout} seconds")
                    process.kill()
                    failed_tests.append(test_item)
                    break

                # Read a line of output
                line = process.stdout.readline()
                if line:
                    print(line, end="")
                    output.append(line)
                else:
                    # No output, sleep briefly
                    time.sleep(0.1)

            # Get any remaining output
            remaining_output, _ = process.communicate()
            if remaining_output:
                print(remaining_output, end="")
                output.append(remaining_output)

            result = process
            result.stdout = ''.join(output) if output else ''
            result.stderr = ''
        except Exception as e:
            logger.error(f"Error running test {test_item}: {e}")
            failed_tests.append(test_item)
            continue

        # Log the result
        if result.returncode != 0:
            logger.error(f"Test {test_item} failed with exit code {result.returncode}")
            logger.error(f"Output: {result.stdout}")
            logger.error(f"Error: {result.stderr}")
            failed_tests.append(test_item)
        else:
            logger.info(f"Test {test_item} passed")

        # Force garbage collection between tests
        gc.collect()
        time.sleep(0.1)  # Small delay to allow OS to clean up resources

    # Report results
    if failed_tests:
        logger.error(f"{len(failed_tests)}/{len(test_items)} tests failed:")
        for test in failed_tests:
            logger.error(f"  - {test}")
        return 1
    else:
        logger.info(f"All {len(test_items)} tests passed")
        return 0


def run_tests_normal(args):
    """Run tests normally with pytest."""
    # Build command
    cmd = [sys.executable, "-m", "pytest", args.test_path]

    # Add options
    if args.verbose:
        cmd.append("-v")
    if args.debug:
        cmd.append("--log-cli-level=DEBUG")
    if args.memory_tracking:
        cmd.append("--memory-tracking")
    if args.coverage:
        cmd.extend(["--cov=src", "--cov-report=term"])

    # Add environment variables
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    env["ACCESSIWEATHER_TESTING"] = "1"
    env["ACCESSIWEATHER_SKIP_API_CALLS"] = "1"

    # If faulthandler is enabled in Python, make sure it's enabled in the subprocess
    if not args.no_faulthandler:
        env["PYTHONFAULTHANDLER"] = "1"

    # Run the tests
    logger.info(f"Running command: {' '.join(cmd)}")
    for _ in range(args.repeat):
        if args.repeat > 1:
            logger.info(f"Running tests (iteration {_+1}/{args.repeat})")

        try:
            # Run with timeout
            process = subprocess.Popen(
                cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )

            # Read output with timeout
            start_time = time.time()

            while True:
                # Check if process has finished
                if process.poll() is not None:
                    break

                # Check for timeout
                if time.time() - start_time > args.timeout:
                    logger.error(f"Tests timed out after {args.timeout} seconds")
                    process.kill()
                    return 1

                # Read a line of output
                line = process.stdout.readline()
                if line:
                    print(line, end="")
                else:
                    # No output, sleep briefly
                    time.sleep(0.1)

            # Get any remaining output
            remaining_output, _ = process.communicate()
            if remaining_output:
                print(remaining_output, end="")

            if process.returncode != 0:
                logger.error(f"Tests failed with exit code {process.returncode}")
                return process.returncode
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            return 1

    return 0


def main():
    """Main entry point."""
    args = parse_args()

    # Set log level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Set up faulthandler
    log_file = None
    if not args.no_faulthandler:
        log_file = setup_faulthandler()

    try:
        # Run tests
        if args.isolated:
            return run_tests_isolated(args)
        else:
            return run_tests_normal(args)
    finally:
        # Clean up
        if log_file is not None:
            try:
                log_file.close()
            except Exception as e:
                logger.warning(f"Error closing log file: {e}")


if __name__ == "__main__":
    sys.exit(main())
