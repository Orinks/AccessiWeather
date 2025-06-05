#!/usr/bin/env python3
"""Integration test runner for AccessiWeather.

This script runs the comprehensive integration test suite with proper
environment setup and reporting.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


def setup_test_environment():
    """Set up the test environment."""
    # Set headless mode for GUI tests
    os.environ["DISPLAY"] = ""

    # Disable pytest plugin autoload for cleaner output
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

    # Set Python path
    project_root = Path(__file__).parent.parent
    os.environ["PYTHONPATH"] = str(project_root / "src")

    print("✅ Test environment configured")


def run_command(cmd, description=""):
    """Run a command and return success status."""
    if description:
        print(f"🔄 {description}")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        print(f"✅ {description or 'Command'} completed successfully")
        return True, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        print(f"❌ {description or 'Command'} failed")
        print(f"Exit code: {e.returncode}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False, e.stdout, e.stderr


def run_integration_tests(test_type="all", verbose=True, coverage=True):
    """Run integration tests."""
    cmd_parts = ["python", "-m", "pytest"]

    # Test selection
    if test_type == "comprehensive":
        cmd_parts.extend(["tests/test_integration_comprehensive.py"])
    elif test_type == "gui":
        cmd_parts.extend(["tests/test_integration_gui.py"])
    elif test_type == "performance":
        cmd_parts.extend(["tests/test_integration_performance.py"])
    elif test_type == "all":
        cmd_parts.extend(
            [
                "tests/test_integration_comprehensive.py",
                "tests/test_integration_gui.py",
                "tests/test_integration_performance.py",
            ]
        )
    else:
        cmd_parts.extend(["-m", "integration"])

    # Add markers
    cmd_parts.extend(["-m", "integration"])

    # Verbosity
    if verbose:
        cmd_parts.append("-v")

    # Coverage
    if coverage:
        cmd_parts.extend(
            [
                "--cov=src/accessiweather",
                "--cov-report=xml",
                "--cov-report=html",
                "--cov-report=term-missing",
            ]
        )

    # Additional options
    cmd_parts.extend(["--tb=short", "--strict-markers", "--disable-warnings"])

    return run_command(" ".join(cmd_parts), f"Running {test_type} integration tests")


def run_smoke_tests():
    """Run smoke tests to verify basic functionality."""
    cmd = "python -m pytest tests/test_e2e_smoke.py -m smoke -v --tb=short"
    return run_command(cmd, "Running smoke tests")


def run_unit_tests():
    """Run unit tests to ensure basic functionality."""
    cmd = "python -m pytest -m unit -v --tb=short"
    return run_command(cmd, "Running unit tests")


def generate_test_report(results):
    """Generate a test report."""
    print("\n" + "=" * 60)
    print("INTEGRATION TEST REPORT")
    print("=" * 60)

    total_tests = len(results)
    passed_tests = sum(1 for success, _, _ in results.values() if success)
    failed_tests = total_tests - passed_tests

    print(f"Total test suites: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    print(f"Success rate: {(passed_tests / total_tests) * 100:.1f}%")

    print("\nTest Suite Results:")
    for test_name, (success, stdout, stderr) in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {test_name}")

        if not success and stderr:
            print(f"    Error: {stderr[:200]}...")

    print("\n" + "=" * 60)

    return failed_tests == 0


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Run AccessiWeather integration tests")
    parser.add_argument(
        "--type",
        choices=["all", "comprehensive", "gui", "performance", "smoke"],
        default="all",
        help="Type of tests to run",
    )
    parser.add_argument("--no-coverage", action="store_true", help="Disable coverage reporting")
    parser.add_argument("--quiet", action="store_true", help="Reduce output verbosity")
    parser.add_argument(
        "--quick", action="store_true", help="Run only smoke tests for quick validation"
    )

    args = parser.parse_args()

    print("🚀 Starting AccessiWeather Integration Tests")
    print(f"Test type: {args.type}")
    print(f"Coverage: {'disabled' if args.no_coverage else 'enabled'}")

    # Setup environment
    setup_test_environment()

    results = {}

    if args.quick:
        # Quick smoke test only
        results["smoke"] = run_smoke_tests()
    else:
        # Run unit tests first to ensure basic functionality
        print("\n📋 Running prerequisite unit tests...")
        unit_success, _, _ = run_unit_tests()
        if not unit_success:
            print("❌ Unit tests failed. Skipping integration tests.")
            return 1

        # Run smoke tests
        print("\n💨 Running smoke tests...")
        results["smoke"] = run_smoke_tests()

        # Run integration tests
        print(f"\n🔧 Running {args.type} integration tests...")
        results["integration"] = run_integration_tests(
            test_type=args.type, verbose=not args.quiet, coverage=not args.no_coverage
        )

    # Generate report
    success = generate_test_report(results)

    if success:
        print("🎉 All tests passed!")
        return 0
    else:
        print("💥 Some tests failed!")
        return 1


if __name__ == "__main__":
    start_time = time.time()
    exit_code = main()
    end_time = time.time()

    print(f"\n⏱️  Total execution time: {end_time - start_time:.2f} seconds")
    sys.exit(exit_code)
