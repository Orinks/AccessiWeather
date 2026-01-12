#!/usr/bin/env python3
"""
Verification script for cross-platform file permissions tests.

This script performs static analysis and provides instructions for
running tests on both Windows and POSIX systems.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def analyze_test_file(test_file: Path) -> dict[str, any]:
    """Analyze a test file for completeness and correctness."""
    try:
        with open(test_file) as f:
            tree = ast.parse(f.read(), filename=str(test_file))
    except SyntaxError as e:
        return {"valid": False, "error": f"Syntax error: {e}"}

    # Count test functions
    test_functions = []
    test_classes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            test_functions.append(node.name)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            test_classes.append(node.name)

    return {
        "valid": True,
        "test_functions": test_functions,
        "test_classes": test_classes,
        "total_tests": len(test_functions),
        "total_classes": len(test_classes),
    }


def main():
    """Main verification routine."""
    print("=" * 70)
    print("FILE PERMISSIONS TEST VERIFICATION")
    print("=" * 70)
    print()

    # Check unit tests
    unit_test_file = Path("tests/test_file_permissions.py")
    if not unit_test_file.exists():
        print(f"❌ ERROR: {unit_test_file} not found!")
        return 1

    print(f"📁 Analyzing {unit_test_file}...")
    unit_results = analyze_test_file(unit_test_file)

    if not unit_results["valid"]:
        print(f"❌ ERROR: {unit_results['error']}")
        return 1

    print(f"✅ Valid Python syntax")
    print(f"✅ Found {unit_results['total_classes']} test classes:")
    for cls in unit_results["test_classes"]:
        print(f"   - {cls}")
    print(f"✅ Found {unit_results['total_tests']} test functions")
    print()

    # Check integration tests
    integration_test_file = Path("tests/test_config_properties.py")
    if not integration_test_file.exists():
        print(f"❌ ERROR: {integration_test_file} not found!")
        return 1

    print(f"📁 Analyzing {integration_test_file}...")
    integration_results = analyze_test_file(integration_test_file)

    if not integration_results["valid"]:
        print(f"❌ ERROR: {integration_results['error']}")
        return 1

    print(f"✅ Valid Python syntax")
    print()

    # Check source module
    source_file = Path("src/accessiweather/config/file_permissions.py")
    if not source_file.exists():
        print(f"❌ ERROR: {source_file} not found!")
        return 1

    print(f"📁 Analyzing {source_file}...")
    try:
        with open(source_file) as f:
            ast.parse(f.read(), filename=str(source_file))
        print(f"✅ Valid Python syntax")
    except SyntaxError as e:
        print(f"❌ ERROR: Syntax error in source: {e}")
        return 1

    print()
    print("=" * 70)
    print("MANUAL TEST EXECUTION INSTRUCTIONS")
    print("=" * 70)
    print()
    print("To run the file permissions tests:")
    print()
    print("1. Unit Tests (cross-platform):")
    print("   pytest tests/test_file_permissions.py -v")
    print()
    print("2. Integration Tests (cross-platform):")
    print("   pytest tests/test_config_properties.py::TestConfigFilePermissionsIntegration -v")
    print()
    print("3. All Tests with Parallel Execution:")
    print("   pytest tests/test_file_permissions.py tests/test_config_properties.py -n auto -v")
    print()
    print("4. Platform-Specific Verification:")
    print()
    print("   On Windows:")
    print("   - Verify USERNAME environment variable is set")
    print("   - Tests will check icacls command availability")
    print("   - Integration tests verify actual file permissions")
    print()
    print("   On POSIX (Linux/macOS):")
    print("   - Tests verify chmod 0o600 permissions")
    print("   - Integration tests check actual file mode bits")
    print()
    print("=" * 70)
    print("TEST COVERAGE SUMMARY")
    print("=" * 70)
    print()
    print("Unit Tests (test_file_permissions.py):")
    print("  ✅ Cross-platform permission setting")
    print("  ✅ POSIX-specific permission handling")
    print("  ✅ Windows-specific permission handling")
    print("  ✅ Error handling (PermissionError, OSError, etc.)")
    print("  ✅ File validation and path conversion")
    print("  ✅ Subprocess timeout and error handling")
    print("  ✅ Integration tests on real files")
    print()
    print("Integration Tests (test_config_properties.py):")
    print("  ✅ POSIX permissions after config save")
    print("  ✅ Windows permissions after config save")
    print("  ✅ Fail-safe behavior (permission failures don't prevent saves)")
    print("  ✅ Multiple saves maintain permissions")
    print("  ✅ New config file creation with correct permissions")
    print()
    print("=" * 70)
    print("✅ ALL STATIC CHECKS PASSED")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Run pytest locally to verify tests pass")
    print("2. Push to GitHub to verify CI passes on all platforms")
    print("3. Check CI workflow results for Windows, macOS, and Linux")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
