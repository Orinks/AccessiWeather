#!/usr/bin/env python3
"""Comprehensive test runner for AccessiWeather project.

This script provides different test execution modes for various development
and CI/CD scenarios, including unit tests, integration tests, and end-to-end tests.
"""

import argparse
import os
import subprocess
import sys
import time


def run_command(cmd, env=None, cwd=None):
    """Run a command and return the result."""
    print(f"🔧 Running: {cmd}")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=True,
            text=True,
            env=env,
            cwd=cwd,
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr


def setup_test_environment():
    """Set up environment variables for testing."""
    test_env = os.environ.copy()
    test_env.update(
        {
            "DISPLAY": "",  # Headless mode for GUI tests
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONPATH": "src",
            "ACCESSIWEATHER_TEST_MODE": "1",  # Flag for test-specific behavior
        }
    )
    return test_env


def run_unit_tests(coverage=True, verbose=True):
    """Run unit tests - fast, isolated tests."""
    print("🧪 Running unit tests...")

    cmd_parts = ["python", "-m", "pytest"]
    cmd_parts.extend(["-m", "unit"])

    if verbose:
        cmd_parts.append("-v")

    if coverage:
        cmd_parts.extend(
            [
                "--cov=src/accessiweather",
                "--cov-report=xml",
                "--cov-report=html",
                "--cov-report=term-missing",
            ]
        )

    cmd_parts.extend(["--tb=short", "tests/"])

    success, stdout, stderr = run_command(" ".join(cmd_parts), env=setup_test_environment())

    if success:
        print("✅ Unit tests passed")
    else:
        print("❌ Unit tests failed")
        print(f"STDOUT: {stdout}")
        print(f"STDERR: {stderr}")

    return success


def run_integration_tests(verbose=True):
    """Run integration tests - test component interactions."""
    print("🔗 Running integration tests...")

    cmd_parts = ["python", "-m", "pytest"]
    cmd_parts.extend(["-m", "integration"])

    if verbose:
        cmd_parts.append("-v")

    cmd_parts.extend(["--tb=short", "tests/"])

    success, stdout, stderr = run_command(" ".join(cmd_parts), env=setup_test_environment())

    if success:
        print("✅ Integration tests passed")
    else:
        print("❌ Integration tests failed")
        print(f"STDOUT: {stdout}")
        print(f"STDERR: {stderr}")

    return success


def run_gui_tests(verbose=True):
    """Run GUI tests - tests requiring wxPython components."""
    print("🖥️ Running GUI tests...")

    cmd_parts = ["python", "-m", "pytest"]
    cmd_parts.extend(["-m", "gui"])

    if verbose:
        cmd_parts.append("-v")

    cmd_parts.extend(["--tb=short", "tests/gui/"])

    success, stdout, stderr = run_command(" ".join(cmd_parts), env=setup_test_environment())

    if success:
        print("✅ GUI tests passed")
    else:
        print("❌ GUI tests failed")
        print(f"STDOUT: {stdout}")
        print(f"STDERR: {stderr}")

    return success


def run_e2e_tests(verbose=True):
    """Run end-to-end tests - full application workflow tests."""
    print("🎯 Running end-to-end tests...")

    cmd_parts = ["python", "-m", "pytest"]
    cmd_parts.extend(["-m", "e2e"])

    if verbose:
        cmd_parts.append("-v")

    cmd_parts.extend(["--tb=short", "tests/"])

    success, stdout, stderr = run_command(" ".join(cmd_parts), env=setup_test_environment())

    if success:
        print("✅ End-to-end tests passed")
    else:
        print("❌ End-to-end tests failed")
        print(f"STDOUT: {stdout}")
        print(f"STDERR: {stderr}")

    return success


def run_smoke_tests(verbose=True):
    """Run smoke tests - basic functionality verification."""
    print("💨 Running smoke tests...")

    cmd_parts = ["python", "-m", "pytest"]
    cmd_parts.extend(["-m", "smoke"])

    if verbose:
        cmd_parts.append("-v")

    cmd_parts.extend(["--tb=short", "tests/"])

    success, stdout, stderr = run_command(" ".join(cmd_parts), env=setup_test_environment())

    if success:
        print("✅ Smoke tests passed")
    else:
        print("❌ Smoke tests failed")
        print(f"STDOUT: {stdout}")
        print(f"STDERR: {stderr}")

    return success


def run_fast_tests(coverage=True, verbose=True):
    """Run fast tests only (excludes slow tests)."""
    print("⚡ Running fast tests...")

    cmd_parts = ["python", "-m", "pytest"]
    cmd_parts.extend(["-m", "not slow"])

    if verbose:
        cmd_parts.append("-v")

    if coverage:
        cmd_parts.extend(
            [
                "--cov=src/accessiweather",
                "--cov-report=xml",
                "--cov-report=html",
                "--cov-report=term-missing",
            ]
        )

    cmd_parts.extend(["--tb=short", "tests/"])

    success, stdout, stderr = run_command(" ".join(cmd_parts), env=setup_test_environment())

    if success:
        print("✅ Fast tests passed")
    else:
        print("❌ Fast tests failed")
        print(f"STDOUT: {stdout}")
        print(f"STDERR: {stderr}")

    return success


def run_all_tests(coverage=True, verbose=True):
    """Run all tests."""
    print("🎯 Running all tests...")

    cmd_parts = ["python", "-m", "pytest"]

    if verbose:
        cmd_parts.append("-v")

    if coverage:
        cmd_parts.extend(
            [
                "--cov=src/accessiweather",
                "--cov-report=xml",
                "--cov-report=html",
                "--cov-report=term-missing",
            ]
        )

    cmd_parts.extend(["--tb=short", "tests/"])

    success, stdout, stderr = run_command(" ".join(cmd_parts), env=setup_test_environment())

    if success:
        print("✅ All tests passed")
    else:
        print("❌ Some tests failed")
        print(f"STDOUT: {stdout}")
        print(f"STDERR: {stderr}")

    return success


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(description="AccessiWeather Test Runner")
    parser.add_argument(
        "test_type",
        choices=["unit", "integration", "gui", "e2e", "smoke", "fast", "all"],
        help="Type of tests to run",
    )
    parser.add_argument("--no-coverage", action="store_true", help="Disable coverage reporting")
    parser.add_argument("--quiet", action="store_true", help="Run tests in quiet mode")

    args = parser.parse_args()

    coverage = not args.no_coverage
    verbose = not args.quiet

    print(f"🚀 Starting {args.test_type} tests...")
    start_time = time.time()

    success = False

    if args.test_type == "unit":
        success = run_unit_tests(coverage=coverage, verbose=verbose)
    elif args.test_type == "integration":
        success = run_integration_tests(verbose=verbose)
    elif args.test_type == "gui":
        success = run_gui_tests(verbose=verbose)
    elif args.test_type == "e2e":
        success = run_e2e_tests(verbose=verbose)
    elif args.test_type == "smoke":
        success = run_smoke_tests(verbose=verbose)
    elif args.test_type == "fast":
        success = run_fast_tests(coverage=coverage, verbose=verbose)
    elif args.test_type == "all":
        success = run_all_tests(coverage=coverage, verbose=verbose)

    end_time = time.time()
    duration = end_time - start_time

    print(f"⏱️ Tests completed in {duration:.2f} seconds")

    if success:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("💥 Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
