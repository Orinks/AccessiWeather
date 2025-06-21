#!/usr/bin/env python3
"""
Local CI Testing Script
Simulates the GitHub Actions CI workflow locally to catch issues before pushing.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def run_command(cmd, cwd=None, env=None, check=True):
    """Run a command and return the result."""
    print(f"🔄 Running: {cmd}")
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True, check=check
        )
        if result.stdout:
            print(f"✅ Output: {result.stdout.strip()}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if e.stdout:
            print(f"📤 Stdout: {e.stdout}")
        if e.stderr:
            print(f"📥 Stderr: {e.stderr}")
        raise


def check_python_version():
    """Check if Python version is compatible."""
    print("🐍 Checking Python version...")
    result = run_command("python --version")
    version = result.stdout.strip()
    print(f"✅ Python version: {version}")
    return version


def setup_virtual_env():
    """Set up a virtual environment for testing."""
    print("🔧 Setting up virtual environment...")
    venv_path = Path("test_venv")

    if venv_path.exists():
        print("🗑️ Removing existing test virtual environment...")
        shutil.rmtree(venv_path)

    run_command(f"python -m venv {venv_path}")

    # Determine the correct paths based on OS
    if os.name == "nt":  # Windows
        pip_path = venv_path / "Scripts" / "pip.exe"
        python_path = venv_path / "Scripts" / "python.exe"
    else:  # Unix-like
        pip_path = venv_path / "bin" / "pip"
        python_path = venv_path / "bin" / "python"

    return str(python_path), str(pip_path)


def install_dependencies(python_path, pip_path):
    """Install project dependencies."""
    print("📦 Installing dependencies...")

    # Upgrade pip
    run_command(f"{python_path} -m pip install --upgrade pip")

    # Install project in development mode
    run_command(f"{pip_path} install -e .[dev]")

    # Install additional dev requirements
    if Path("requirements-dev.txt").exists():
        run_command(f"{pip_path} install -r requirements-dev.txt")

    # Install pre-commit and linting tools
    run_command(f"{pip_path} install pre-commit black isort flake8 mypy bandit safety")


def run_pre_commit_checks(python_path):
    """Run pre-commit hooks."""
    print("🔍 Running pre-commit checks...")

    # Install pre-commit hooks
    run_command(f"{python_path} -m pre_commit install --install-hooks")

    # Run all pre-commit hooks
    try:
        run_command(f"{python_path} -m pre_commit run --all-files")
        print("✅ Pre-commit checks passed")
    except subprocess.CalledProcessError:
        print("⚠️ Pre-commit checks failed - this may be expected for first run")


def run_linting_checks(python_path):
    """Run linting checks."""
    print("🔍 Running linting checks...")

    # Ruff linting and formatting check
    try:
        run_command("ruff check src/ tests/")
        print("✅ Ruff linting check passed")
    except subprocess.CalledProcessError:
        print("❌ Ruff linting check failed")
        print("💡 Run: ruff check --fix src/ tests/")

    # Ruff formatting check
    try:
        run_command("ruff format --check src/ tests/")
        print("✅ Ruff formatting check passed")
    except subprocess.CalledProcessError:
        print("❌ Ruff formatting check failed")
        print("💡 Run: ruff format src/ tests/")

    # mypy type checking
    try:
        run_command(f"{python_path} -m mypy src/accessiweather --ignore-missing-imports")
        print("✅ mypy check passed")
    except subprocess.CalledProcessError:
        print("❌ mypy check failed")


def run_security_checks(python_path):
    """Run security checks."""
    print("🔒 Running security checks...")

    # Bandit security linting
    try:
        run_command(f"{python_path} -m bandit -r src/accessiweather")
        print("✅ Bandit security check passed")
    except subprocess.CalledProcessError:
        print("❌ Bandit security check failed")

    # Safety dependency vulnerability check
    try:
        run_command(f"{python_path} -m safety check")
        print("✅ Safety check passed")
    except subprocess.CalledProcessError:
        print("❌ Safety check failed")


def run_tests(python_path):
    """Run the test suite."""
    print("🧪 Running tests...")

    # Set environment variables for headless testing
    test_env = os.environ.copy()
    test_env.update({"DISPLAY": "", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONPATH": "src"})

    try:
        run_command(
            f"{python_path} -m pytest tests/ -v --tb=short --cov=src/accessiweather --cov-report=xml --cov-report=html",
            env=test_env,
        )
        print("✅ Tests passed")
    except subprocess.CalledProcessError:
        print("❌ Tests failed")


def test_application_import(python_path):
    """Test that the application can be imported without errors."""
    print("🚀 Testing application import...")

    test_env = os.environ.copy()
    test_env.update({"DISPLAY": "", "PYTHONPATH": "src"})

    import_test = """
import os
os.environ['DISPLAY'] = ''
try:
    import src.accessiweather.main
    print('✓ Application imports successfully')
except Exception as e:
    print(f'✗ Import failed: {e}')
    raise
"""

    try:
        run_command(f'{python_path} -c "{import_test}"', env=test_env)
        print("✅ Application import test passed")
    except subprocess.CalledProcessError:
        print("❌ Application import test failed")


def cleanup(venv_path="test_venv"):
    """Clean up test environment."""
    print("🧹 Cleaning up...")
    venv_path = Path(venv_path)
    if venv_path.exists():
        shutil.rmtree(venv_path)
    print("✅ Cleanup complete")


def main():
    """Main test execution."""
    print("🚀 Starting local CI testing...")
    print("=" * 50)

    try:
        # Check Python version
        check_python_version()

        # Set up virtual environment
        python_path, pip_path = setup_virtual_env()

        # Install dependencies
        install_dependencies(python_path, pip_path)

        # Run checks
        run_linting_checks(python_path)
        run_security_checks(python_path)
        run_tests(python_path)
        test_application_import(python_path)

        print("=" * 50)
        print("🎉 Local CI testing completed!")

    except Exception as e:
        print(f"💥 Local CI testing failed: {e}")
        return 1
    finally:
        cleanup()

    return 0


if __name__ == "__main__":
    sys.exit(main())
