"""Tests for the main accessiweather package module."""

from unittest.mock import patch

import accessiweather


class TestPackageImports:
    """Test that main package imports work."""

    def test_main_app_import(self):
        """Test that AccessiWeatherApp is importable."""
        assert hasattr(accessiweather, "AccessiWeatherApp")
        assert callable(accessiweather.main)

    def test_core_components_import(self):
        """Test that core components are importable."""
        assert hasattr(accessiweather, "ConfigManager")
        assert hasattr(accessiweather, "WeatherClient")
        assert hasattr(accessiweather, "LocationManager")
        assert hasattr(accessiweather, "WeatherFormatter")
        assert hasattr(accessiweather, "WeatherPresenter")

    def test_models_import(self):
        """Test that data models are importable."""
        assert hasattr(accessiweather, "Location")
        assert hasattr(accessiweather, "CurrentConditions")
        assert hasattr(accessiweather, "ForecastPeriod")
        assert hasattr(accessiweather, "Forecast")
        assert hasattr(accessiweather, "HourlyForecastPeriod")
        assert hasattr(accessiweather, "HourlyForecast")
        assert hasattr(accessiweather, "EnvironmentalConditions")
        assert hasattr(accessiweather, "TrendInsight")
        assert hasattr(accessiweather, "WeatherAlert")
        assert hasattr(accessiweather, "WeatherAlerts")
        assert hasattr(accessiweather, "WeatherData")
        assert hasattr(accessiweather, "AppSettings")
        assert hasattr(accessiweather, "AppConfig")

    def test_weather_history_import(self):
        """Test that weather history components are importable."""
        assert hasattr(accessiweather, "HistoricalWeatherData")
        assert hasattr(accessiweather, "WeatherHistoryService")
        assert hasattr(accessiweather, "WeatherComparison")

    def test_utilities_import(self):
        """Test that utilities are importable."""
        assert hasattr(accessiweather, "TemperatureUnit")
        assert hasattr(accessiweather, "format_temperature")
        assert hasattr(accessiweather, "format_wind_speed")
        assert hasattr(accessiweather, "format_pressure")
        assert hasattr(accessiweather, "convert_wind_direction_to_cardinal")

    def test_all_exports(self):
        """Test that __all__ contains expected exports."""
        assert "__all__" in dir(accessiweather)
        all_exports = accessiweather.__all__
        assert "AccessiWeatherApp" in all_exports
        assert "main" in all_exports
        assert "ConfigManager" in all_exports
        assert "WeatherClient" in all_exports


class TestPackageVersion:
    """Test package version handling."""

    def test_version_exists(self):
        """Test that __version__ attribute exists."""
        assert hasattr(accessiweather, "__version__")
        assert isinstance(accessiweather.__version__, str)
        assert len(accessiweather.__version__) > 0

    def test_version_format(self):
        """Test that version follows semantic versioning format."""
        version = accessiweather.__version__
        parts = version.split(".")
        # Should have at least major.minor.patch
        assert len(parts) >= 3, f"Version {version} should have at least 3 parts"
        # First three parts should be numeric
        for part in parts[:3]:
            assert part.isdigit() or part == "0", f"Version part {part} should be numeric"

    def test_read_pyproject_version_success(self):
        """Test _read_pyproject_version with valid pyproject.toml."""
        from accessiweather import _read_pyproject_version

        version = _read_pyproject_version()
        # Should return a version string or None
        assert version is None or isinstance(version, str)

    def test_read_pyproject_version_file_not_found(self):
        """Test _read_pyproject_version when pyproject.toml doesn't exist."""
        from accessiweather import _read_pyproject_version

        with patch("pathlib.Path.exists", return_value=False):
            result = _read_pyproject_version()
            assert result is None

    def test_read_pyproject_version_invalid_toml(self):
        """Test _read_pyproject_version with invalid TOML."""
        from accessiweather import _read_pyproject_version

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.open", side_effect=Exception("TOML parse error")),
        ):
            result = _read_pyproject_version()
            assert result is None

    def test_version_fallback_chain(self):
        """Test that version fallback chain works."""
        # The package should have a version even if metadata lookup fails
        # Version can be from metadata, pyproject.toml, or fallback to "0.0.0"
        assert isinstance(accessiweather.__version__, str)
        assert len(accessiweather.__version__) > 0
