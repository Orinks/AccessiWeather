"""Tests for config_utils module."""

import os
import sys
from unittest import mock

from accessiweather.config_utils import ensure_config_defaults, get_config_dir, is_portable_mode


class TestIsPortableMode:
    """Tests for is_portable_mode()."""

    def test_not_frozen_returns_false(self):
        """Running from source (not frozen) should not be portable."""
        with (
            mock.patch.object(sys, "frozen", False, create=True),
            mock.patch.dict(os.environ, {}, clear=False),
        ):
            os.environ.pop("ACCESSIWEATHER_FORCE_PORTABLE", None)
            assert is_portable_mode() is False

    def test_force_portable_env_var(self):
        """ACCESSIWEATHER_FORCE_PORTABLE=1 forces portable mode."""
        with mock.patch.dict(os.environ, {"ACCESSIWEATHER_FORCE_PORTABLE": "1"}):
            assert is_portable_mode() is True

    def test_force_portable_true_string(self):
        """ACCESSIWEATHER_FORCE_PORTABLE=true forces portable mode."""
        with mock.patch.dict(os.environ, {"ACCESSIWEATHER_FORCE_PORTABLE": "true"}):
            assert is_portable_mode() is True

    def test_force_portable_yes_string(self):
        """ACCESSIWEATHER_FORCE_PORTABLE=yes forces portable mode."""
        with mock.patch.dict(os.environ, {"ACCESSIWEATHER_FORCE_PORTABLE": "yes"}):
            assert is_portable_mode() is True

    def test_force_portable_invalid_value(self):
        """Invalid ACCESSIWEATHER_FORCE_PORTABLE value should not force portable."""
        with mock.patch.dict(os.environ, {"ACCESSIWEATHER_FORCE_PORTABLE": "nope"}):
            # Not frozen, so returns False
            assert is_portable_mode() is False

    def test_frozen_uninstaller_detected(self, tmp_path):
        """Frozen app with uninstaller present should not be portable."""
        # Create a fake uninstaller
        uninstaller = tmp_path / "unins000.exe"
        uninstaller.write_text("fake")
        exe_path = str(tmp_path / "app.exe")

        with (
            mock.patch.object(sys, "frozen", True, create=True),
            mock.patch.object(sys, "executable", exe_path),
            mock.patch.dict(
                os.environ,
                {"ACCESSIWEATHER_FORCE_PORTABLE": "", "PROGRAMFILES": "", "PROGRAMFILES(X86)": ""},
            ),
        ):
            assert is_portable_mode() is False

    def test_frozen_in_program_files(self, tmp_path):
        """Frozen app under Program Files should not be portable."""
        pf = tmp_path / "Program Files" / "AccessiWeather"
        pf.mkdir(parents=True)
        exe_path = str(pf / "app.exe")

        with (
            mock.patch.object(sys, "frozen", True, create=True),
            mock.patch.object(sys, "executable", exe_path),
            mock.patch.dict(
                os.environ,
                {
                    "ACCESSIWEATHER_FORCE_PORTABLE": "",
                    "PROGRAMFILES": str(tmp_path / "Program Files"),
                    "PROGRAMFILES(X86)": "",
                },
            ),
            mock.patch("os.listdir", return_value=[]),
        ):
            assert is_portable_mode() is False

    def test_frozen_in_program_files_x86(self, tmp_path):
        """Frozen app under Program Files (x86) should not be portable."""
        pf = tmp_path / "Program Files (x86)" / "AccessiWeather"
        pf.mkdir(parents=True)
        exe_path = str(pf / "app.exe")

        with (
            mock.patch.object(sys, "frozen", True, create=True),
            mock.patch.object(sys, "executable", exe_path),
            mock.patch.dict(
                os.environ,
                {
                    "ACCESSIWEATHER_FORCE_PORTABLE": "",
                    "PROGRAMFILES": "",
                    "PROGRAMFILES(X86)": str(tmp_path / "Program Files (x86)"),
                },
            ),
            mock.patch("os.listdir", return_value=[]),
        ):
            assert is_portable_mode() is False

    def test_frozen_writable_directory_is_portable(self, tmp_path):
        """Frozen app in writable non-Program Files dir should be portable."""
        exe_path = str(tmp_path / "app.exe")

        with (
            mock.patch.object(sys, "frozen", True, create=True),
            mock.patch.object(sys, "executable", exe_path),
            mock.patch.dict(
                os.environ,
                {"ACCESSIWEATHER_FORCE_PORTABLE": "", "PROGRAMFILES": "", "PROGRAMFILES(X86)": ""},
            ),
            mock.patch("os.listdir", return_value=[]),
        ):
            assert is_portable_mode() is True

    def test_frozen_non_writable_directory_not_portable(self, tmp_path):
        """Frozen app in non-writable dir should not be portable."""
        exe_path = str(tmp_path / "app.exe")

        with (
            mock.patch.object(sys, "frozen", True, create=True),
            mock.patch.object(sys, "executable", exe_path),
            mock.patch.dict(
                os.environ,
                {"ACCESSIWEATHER_FORCE_PORTABLE": "", "PROGRAMFILES": "", "PROGRAMFILES(X86)": ""},
            ),
            mock.patch("os.listdir", return_value=[]),
            mock.patch("builtins.open", side_effect=PermissionError("no write")),
        ):
            assert is_portable_mode() is False


class TestGetConfigDir:
    """Tests for get_config_dir()."""

    def test_custom_dir_returned_directly(self):
        """Custom directory should be returned as-is."""
        result = get_config_dir("/my/custom/dir")
        assert result == "/my/custom/dir"

    def test_default_linux_config_dir(self):
        """On Linux (non-portable, non-Windows), should use ~/.accessiweather."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ACCESSIWEATHER_FORCE_PORTABLE", None)
            with (
                mock.patch("accessiweather.config_utils.is_portable_mode", return_value=False),
                mock.patch("accessiweather.config_utils.platform") as mock_platform,
            ):
                mock_platform.system.return_value = "Linux"
                result = get_config_dir()
                expected = os.path.expanduser("~/.accessiweather")
                assert result == expected

    def test_windows_appdata_config_dir(self):
        """On Windows with APPDATA set, should use APPDATA/.accessiweather."""
        with (
            mock.patch("accessiweather.config_utils.is_portable_mode", return_value=False),
            mock.patch("accessiweather.config_utils.platform") as mock_platform,
        ):
            mock_platform.system.return_value = "Windows"
            with mock.patch.dict(os.environ, {"APPDATA": "C:\\Users\\test\\AppData\\Roaming"}):
                result = get_config_dir()
                assert result == os.path.join(
                    "C:\\Users\\test\\AppData\\Roaming", ".accessiweather"
                )

    def test_portable_mode_config_dir(self):
        """In portable mode from source, should use project_root/config."""
        with (
            mock.patch.dict(os.environ, {"ACCESSIWEATHER_FORCE_PORTABLE": "1"}),
            mock.patch("accessiweather.config_utils.is_portable_mode", return_value=True),
        ):
            result = get_config_dir()
            assert result.endswith("config")

    def test_portable_frozen_config_dir(self, tmp_path):
        """In portable mode with frozen exe, should use exe_dir/config."""
        exe_path = str(tmp_path / "app.exe")
        with (
            mock.patch("accessiweather.config_utils.is_portable_mode", return_value=True),
            mock.patch.object(sys, "frozen", True, create=True),
            mock.patch.object(sys, "executable", exe_path),
        ):
            result = get_config_dir()
            assert result == os.path.join(str(tmp_path), "config")

    def test_windows_no_appdata_falls_to_default(self):
        """On Windows without APPDATA, should fall back to ~/.accessiweather."""
        with (
            mock.patch("accessiweather.config_utils.is_portable_mode", return_value=False),
            mock.patch("accessiweather.config_utils.platform") as mock_platform,
            mock.patch.dict(os.environ, {}, clear=False),
        ):
            os.environ.pop("APPDATA", None)
            mock_platform.system.return_value = "Windows"
            result = get_config_dir()
            assert result == os.path.expanduser("~/.accessiweather")


class TestEnsureConfigDefaults:
    """Tests for ensure_config_defaults()."""

    def test_empty_config_gets_defaults(self):
        """An empty config should get all default sections and settings."""
        result = ensure_config_defaults({})
        assert "settings" in result
        assert "api_keys" in result
        assert "api_settings" in result
        assert "data_source" in result["settings"]
        assert "auto_update_check_enabled" in result["settings"]
        assert "update_check_interval_hours" in result["settings"]
        assert "update_channel" in result["settings"]

    def test_existing_settings_preserved(self):
        """Existing settings should not be overwritten."""
        config = {
            "settings": {"data_source": "weatherapi", "custom_key": "custom_value"},
            "api_keys": {"my_key": "my_value"},
        }
        result = ensure_config_defaults(config)
        assert result["settings"]["data_source"] == "weatherapi"
        assert result["settings"]["custom_key"] == "custom_value"
        assert result["api_keys"]["my_key"] == "my_value"

    def test_original_config_not_mutated(self):
        """The original config dict should not be modified."""
        config = {"settings": {"data_source": "nws"}}
        result = ensure_config_defaults(config)
        # Original should be untouched
        assert "auto_update_check_enabled" not in config["settings"]
        # Result should have defaults
        assert "auto_update_check_enabled" in result["settings"]

    def test_missing_sections_added(self):
        """Missing sections (api_keys, api_settings) should be added."""
        config = {"settings": {}}
        result = ensure_config_defaults(config)
        assert result["api_keys"] == {}
        assert result["api_settings"] == {}
