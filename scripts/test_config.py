"""
Test configuration and performance optimization settings for AccessiWeather.

This module provides configuration for different test execution modes,
performance optimization settings, and test environment setup.
"""

import os
from typing import Dict, List, Optional


class TestConfig:
    """Configuration class for test execution."""

    # Test categories and their descriptions
    TEST_CATEGORIES = {
        "unit": {
            "description": "Fast, isolated unit tests",
            "markers": ["unit"],
            "timeout": 300,  # 5 minutes
            "parallel": True,
            "coverage": True,
        },
        "integration": {
            "description": "Integration tests for component interactions",
            "markers": ["integration"],
            "timeout": 600,  # 10 minutes
            "parallel": False,  # GUI tests may not be thread-safe
            "coverage": False,
        },
        "gui": {
            "description": "GUI tests requiring wxPython components",
            "markers": ["gui"],
            "timeout": 900,  # 15 minutes
            "parallel": False,  # GUI tests are not thread-safe
            "coverage": False,
        },
        "e2e": {
            "description": "End-to-end tests for full workflows",
            "markers": ["e2e"],
            "timeout": 1200,  # 20 minutes
            "parallel": False,
            "coverage": False,
        },
        "smoke": {
            "description": "Basic functionality verification",
            "markers": ["smoke"],
            "timeout": 180,  # 3 minutes
            "parallel": True,
            "coverage": False,
        },
        "slow": {
            "description": "Tests that take more than 5 seconds",
            "markers": ["slow"],
            "timeout": 1800,  # 30 minutes
            "parallel": False,
            "coverage": False,
        },
        "fast": {
            "description": "Fast tests (excludes slow tests)",
            "markers": ["not slow"],
            "timeout": 600,  # 10 minutes
            "parallel": True,
            "coverage": True,
        },
    }

    # Environment variables for different test modes
    TEST_ENVIRONMENTS = {
        "headless": {
            "DISPLAY": "",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "ACCESSIWEATHER_TEST_MODE": "1",
        },
        "ci": {
            "DISPLAY": "",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "ACCESSIWEATHER_TEST_MODE": "1",
            "CI": "true",
        },
        "local": {
            "ACCESSIWEATHER_TEST_MODE": "1",
        },
    }

    # Performance optimization settings
    PERFORMANCE_SETTINGS = {
        "pytest_args": {
            "base": ["-v", "--tb=short"],
            "fast": ["--maxfail=5", "-x"],  # Fail fast for quick feedback
            "thorough": ["--maxfail=10"],
            "coverage": [
                "--cov=src/accessiweather",
                "--cov-report=xml",
                "--cov-report=html",
                "--cov-report=term-missing",
            ],
        },
        "parallel": {
            "enabled": True,
            "workers": "auto",  # Use number of CPU cores
            "dist": "loadfile",  # Distribute by file
        },
    }

    @classmethod
    def get_test_command(
        cls,
        category: str,
        coverage: bool = None,
        parallel: bool = None,
        fast: bool = False,
        paths: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Generate pytest command for a specific test category.

        Args:
            category: Test category name
            coverage: Enable coverage reporting (overrides category default)
            parallel: Enable parallel execution (overrides category default)
            fast: Enable fast mode (fail fast, reduced output)
            paths: Specific test paths to run

        Returns:
            List of command arguments for pytest
        """
        if category not in cls.TEST_CATEGORIES:
            raise ValueError(f"Unknown test category: {category}")

        config = cls.TEST_CATEGORIES[category]
        cmd = ["python", "-m", "pytest"]

        # Add markers
        if config["markers"]:
            marker_expr = " or ".join(config["markers"])
            cmd.extend(["-m", marker_expr])

        # Add base arguments
        cmd.extend(cls.PERFORMANCE_SETTINGS["pytest_args"]["base"])

        # Add fast mode arguments
        if fast:
            cmd.extend(cls.PERFORMANCE_SETTINGS["pytest_args"]["fast"])
        else:
            cmd.extend(cls.PERFORMANCE_SETTINGS["pytest_args"]["thorough"])

        # Add coverage if enabled
        use_coverage = coverage if coverage is not None else config["coverage"]
        if use_coverage:
            cmd.extend(cls.PERFORMANCE_SETTINGS["pytest_args"]["coverage"])

        # Add parallel execution if enabled
        use_parallel = parallel if parallel is not None else config["parallel"]
        if use_parallel and cls.PERFORMANCE_SETTINGS["parallel"]["enabled"]:
            cmd.extend(
                [
                    "-n",
                    cls.PERFORMANCE_SETTINGS["parallel"]["workers"],
                    "--dist",
                    cls.PERFORMANCE_SETTINGS["parallel"]["dist"],
                ]
            )

        # Add timeout
        cmd.extend(["--timeout", str(config["timeout"])])

        # Add test paths
        if paths:
            cmd.extend(paths)
        else:
            cmd.append("tests/")

        return cmd

    @classmethod
    def get_environment(cls, mode: str = "local") -> Dict[str, str]:
        """
        Get environment variables for test execution.

        Args:
            mode: Environment mode (headless, ci, local)

        Returns:
            Dictionary of environment variables
        """
        if mode not in cls.TEST_ENVIRONMENTS:
            raise ValueError(f"Unknown environment mode: {mode}")

        env = os.environ.copy()
        env.update(cls.TEST_ENVIRONMENTS[mode])
        env["PYTHONPATH"] = "src"

        return env

    @classmethod
    def get_category_info(cls, category: str) -> Dict:
        """Get information about a test category."""
        if category not in cls.TEST_CATEGORIES:
            raise ValueError(f"Unknown test category: {category}")

        return cls.TEST_CATEGORIES[category].copy()

    @classmethod
    def list_categories(cls) -> List[str]:
        """List all available test categories."""
        return list(cls.TEST_CATEGORIES.keys())

    @classmethod
    def validate_category(cls, category: str) -> bool:
        """Validate if a category exists."""
        return category in cls.TEST_CATEGORIES


# Convenience functions for common test configurations
def get_unit_test_command(coverage: bool = True, fast: bool = False) -> List[str]:
    """Get command for running unit tests."""
    return TestConfig.get_test_command("unit", coverage=coverage, fast=fast)


def get_integration_test_command(fast: bool = False) -> List[str]:
    """Get command for running integration tests."""
    return TestConfig.get_test_command("integration", fast=fast)


def get_smoke_test_command(fast: bool = True) -> List[str]:
    """Get command for running smoke tests."""
    return TestConfig.get_test_command("smoke", fast=fast)


def get_all_test_command(coverage: bool = True, fast: bool = False) -> List[str]:
    """Get command for running all tests."""
    cmd = ["python", "-m", "pytest"]
    cmd.extend(TestConfig.PERFORMANCE_SETTINGS["pytest_args"]["base"])

    if fast:
        cmd.extend(TestConfig.PERFORMANCE_SETTINGS["pytest_args"]["fast"])

    if coverage:
        cmd.extend(TestConfig.PERFORMANCE_SETTINGS["pytest_args"]["coverage"])

    cmd.append("tests/")
    return cmd


def get_ci_environment() -> Dict[str, str]:
    """Get environment variables for CI execution."""
    return TestConfig.get_environment("ci")


def get_local_environment() -> Dict[str, str]:
    """Get environment variables for local execution."""
    return TestConfig.get_environment("local")


if __name__ == "__main__":
    # Print configuration information
    print("AccessiWeather Test Configuration")
    print("=" * 40)

    for category in TestConfig.list_categories():
        info = TestConfig.get_category_info(category)
        print(f"\n{category.upper()}:")
        print(f"  Description: {info['description']}")
        print(f"  Markers: {info['markers']}")
        print(f"  Timeout: {info['timeout']}s")
        print(f"  Parallel: {info['parallel']}")
        print(f"  Coverage: {info['coverage']}")

        # Show example command
        cmd = TestConfig.get_test_command(category)
        print(f"  Command: {' '.join(cmd)}")
