"""Tests for data migration utilities."""

import os
import shutil
from unittest.mock import call, mock_open, patch

import pytest

from accessiweather.data_migration import migrate_config_directory

# --- Test Data ---

SAMPLE_FILES = ["config.json", "locations.json"]
SAMPLE_DIRS = ["cache"]
SAMPLE_OLD_DIR = "~/.noaa_weather_app"
SAMPLE_NEW_DIR = "~/.accessiweather"
EXPANDED_OLD_DIR = "/home/user/.noaa_weather_app"
EXPANDED_NEW_DIR = "/home/user/.accessiweather"

# --- Tests ---

def test_migrate_config_directory_old_dir_not_exists():
    """Test migration when old directory doesn't exist."""
    with patch("os.path.exists") as mock_exists:
        with patch("os.path.expanduser") as mock_expanduser:
            with patch("accessiweather.data_migration.get_config_dir", return_value=SAMPLE_NEW_DIR):
                # Set up mock to return False for old directory check but allow other exists checks
                mock_exists.side_effect = lambda path: path != EXPANDED_OLD_DIR
                mock_expanduser.side_effect = lambda p: p.replace("~", "/home/user")

                result = migrate_config_directory()

                assert result is True
                # Verify the old directory was checked
                mock_exists.assert_any_call(EXPANDED_OLD_DIR)
                mock_expanduser.assert_has_calls([
                    call(SAMPLE_OLD_DIR),
                    call(SAMPLE_NEW_DIR)
                ])

def test_migrate_config_directory_new_dir_has_data():
    """Test migration when new directory already has data."""
    with patch("os.path.exists") as mock_exists:
        with patch("os.listdir") as mock_listdir:
            with patch("os.path.expanduser") as mock_expanduser:
                with patch("accessiweather.data_migration.get_config_dir", return_value=SAMPLE_NEW_DIR):
                    mock_exists.return_value = True
                    mock_listdir.return_value = ["existing.json"]
                    mock_expanduser.side_effect = lambda p: p.replace("~", "/home/user")

                    result = migrate_config_directory()

                    assert result is True
                    mock_exists.assert_has_calls([
                        call(EXPANDED_OLD_DIR),
                        call(EXPANDED_NEW_DIR)
                    ])
                    mock_listdir.assert_called_once_with(EXPANDED_NEW_DIR)

def test_migrate_config_directory_successful():
    """Test successful migration of files and directories."""
    with patch("os.path.exists") as mock_exists:
        with patch("os.listdir") as mock_listdir:
            with patch("os.path.isfile") as mock_isfile:
                with patch("os.path.isdir") as mock_isdir:
                    with patch("os.makedirs") as mock_makedirs:
                        with patch("shutil.copy2") as mock_copy2:
                            with patch("shutil.copytree") as mock_copytree:
                                with patch("os.path.expanduser") as mock_expanduser:
                                    with patch("accessiweather.data_migration.get_config_dir", return_value=SAMPLE_NEW_DIR):
                                        # Set up mocks
                                        mock_exists.side_effect = lambda p: p == EXPANDED_OLD_DIR
                                        mock_listdir.return_value = SAMPLE_FILES + SAMPLE_DIRS
                                        mock_isfile.side_effect = lambda p: os.path.basename(p) in SAMPLE_FILES
                                        mock_isdir.side_effect = lambda p: os.path.basename(p) in SAMPLE_DIRS
                                        mock_expanduser.side_effect = lambda p: p.replace("~", "/home/user")

                                        result = migrate_config_directory()

                                        assert result is True
                                        # Verify directory creation
                                        mock_makedirs.assert_called_once_with(EXPANDED_NEW_DIR, exist_ok=True)
                                        # Verify file copies
                                        for file in SAMPLE_FILES:
                                            mock_copy2.assert_any_call(
                                                os.path.join(EXPANDED_OLD_DIR, file),
                                                os.path.join(EXPANDED_NEW_DIR, file)
                                            )
                                        # Verify directory copies
                                        for dir in SAMPLE_DIRS:
                                            mock_copytree.assert_any_call(
                                                os.path.join(EXPANDED_OLD_DIR, dir),
                                                os.path.join(EXPANDED_NEW_DIR, dir),
                                                dirs_exist_ok=True
                                            )

def test_migrate_config_directory_copy_error():
    """Test migration failure due to copy error."""
    with patch("os.path.exists") as mock_exists:
        with patch("os.listdir") as mock_listdir:
            with patch("os.path.isfile") as mock_isfile:
                with patch("os.makedirs") as mock_makedirs:
                    with patch("shutil.copy2") as mock_copy2:
                        with patch("os.path.expanduser") as mock_expanduser:
                            with patch("accessiweather.data_migration.get_config_dir", return_value=SAMPLE_NEW_DIR):
                                # Set up mocks
                                mock_exists.side_effect = lambda p: p == EXPANDED_OLD_DIR
                                mock_listdir.return_value = SAMPLE_FILES
                                mock_isfile.return_value = True
                                mock_copy2.side_effect = IOError("Permission denied")
                                mock_expanduser.side_effect = lambda p: p.replace("~", "/home/user")

                                result = migrate_config_directory()

                                assert result is False
                                mock_makedirs.assert_called_once_with(EXPANDED_NEW_DIR, exist_ok=True)
                                mock_copy2.assert_called_once()  # Should fail on first file

def test_migrate_config_directory_custom_new_dir():
    """Test migration with custom new directory."""
    custom_new_dir = "/custom/config/dir"

    with patch("os.path.exists") as mock_exists:
        with patch("os.listdir") as mock_listdir:
            with patch("os.path.expanduser") as mock_expanduser:
                with patch("accessiweather.data_migration.get_config_dir") as mock_get_config_dir:
                    mock_exists.return_value = False
                    mock_expanduser.side_effect = lambda p: (
                        p.replace("~", "/home/user") if p.startswith("~") else p
                    )

                    result = migrate_config_directory(new_dir=custom_new_dir)

                    assert result is True
                    mock_get_config_dir.assert_not_called()
                    mock_expanduser.assert_has_calls([
                        call(SAMPLE_OLD_DIR),
                        call(custom_new_dir)
                    ])

def test_migrate_config_directory_default_new_dir():
    """Test migration with default new directory from get_config_dir."""
    with patch("os.path.exists") as mock_exists:
        with patch("os.listdir") as mock_listdir:
            with patch("os.path.expanduser") as mock_expanduser:
                with patch("accessiweather.data_migration.get_config_dir") as mock_get_config_dir:
                    mock_exists.return_value = False
                    mock_get_config_dir.return_value = SAMPLE_NEW_DIR
                    mock_expanduser.side_effect = lambda p: p.replace("~", "/home/user")

                    result = migrate_config_directory()

                    assert result is True
                    mock_get_config_dir.assert_called_once()
                    mock_expanduser.assert_has_calls([
                        call(SAMPLE_OLD_DIR),
                        call(SAMPLE_NEW_DIR)
                    ])