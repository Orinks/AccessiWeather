"""Integration tests for sound pack system."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from accessiweather.notifications.sound_pack_installer import SoundPackInstaller
from accessiweather.notifications.sound_player import (
    get_available_sound_packs,
    get_sound_file,
    play_sample_sound,
)


class TestSoundPackIntegration:
    """Integration tests for the complete sound pack system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.soundpacks_dir = Path(self.temp_dir)
        self.installer = SoundPackInstaller(self.soundpacks_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_pack(self, pack_name: str, pack_data: dict) -> Path:
        """Create a test sound pack directory."""
        pack_dir = self.soundpacks_dir / pack_name
        pack_dir.mkdir(parents=True, exist_ok=True)

        # Create pack.json
        with open(pack_dir / "pack.json", "w", encoding="utf-8") as f:
            json.dump(pack_data, f, indent=2)

        # Create sound files
        for sound_file in pack_data.get("sounds", {}).values():
            (pack_dir / sound_file).write_bytes(b"dummy audio data")

        return pack_dir

    def test_end_to_end_sound_pack_workflow(self):
        """Test complete workflow: create, install, use, and uninstall sound packs."""
        # Step 1: Create a custom sound pack template
        pack_info = {
            "name": "Test Integration Pack",
            "author": "Test Author",
            "description": "Integration test pack",
            "version": "1.0.0",
        }

        success, message = self.installer.create_pack_template("integration_test", pack_info)
        assert success is True
        assert "Created sound pack template" in message

        # Step 2: Verify the pack was created correctly
        pack_dir = self.soundpacks_dir / "integration_test"
        assert pack_dir.exists()
        assert (pack_dir / "pack.json").exists()
        assert (pack_dir / "alert.wav").exists()

        # Step 3: List installed packs and verify our pack is there
        packs = self.installer.list_installed_packs()
        assert len(packs) == 1
        assert packs[0]["name"] == "Test Integration Pack"
        assert packs[0]["directory"] == "integration_test"

        # Step 4: Test sound file retrieval with our custom pack
        with patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir):
            sound_file = get_sound_file("alert", "integration_test")
            assert sound_file is not None
            assert sound_file.name == "alert.wav"

        # Step 5: Test getting available sound packs
        with patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir):
            available_packs = get_available_sound_packs()
            assert "integration_test" in available_packs
            assert available_packs["integration_test"]["name"] == "Test Integration Pack"

        # Step 6: Test sound preview functionality
        with (
            patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir),
            patch("accessiweather.notifications.sound_player.winsound") as mock_winsound,
            patch(
                "accessiweather.notifications.sound_player.platform.system",
                return_value="Windows",
            ),
        ):
            play_sample_sound("integration_test")

            # Verify winsound.PlaySound was called (primary method on Windows)
            mock_winsound.PlaySound.assert_called_once()
            args, kwargs = mock_winsound.PlaySound.call_args
            assert str(args[0]).endswith("alert.wav")
            assert args[1] == mock_winsound.SND_FILENAME | mock_winsound.SND_ASYNC

        # Step 7: Export the pack
        export_path = Path(self.temp_dir) / "exported_pack.zip"
        success, message = self.installer.export_pack("integration_test", export_path)
        assert success is True
        assert export_path.exists()

        # Step 8: Uninstall the pack
        success, message = self.installer.uninstall_pack("integration_test")
        assert success is True
        assert not pack_dir.exists()

        # Step 9: Reinstall from exported ZIP
        success, message = self.installer.install_from_zip(export_path, "reinstalled_pack")
        assert success is True

        # Step 10: Verify reinstalled pack works
        reinstalled_dir = self.soundpacks_dir / "reinstalled_pack"
        assert reinstalled_dir.exists()

        with patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir):
            sound_file = get_sound_file("alert", "reinstalled_pack")
            assert sound_file is not None

    def test_sound_pack_fallback_behavior(self):
        """Test fallback behavior when sound packs have issues."""
        # Create a default pack
        default_pack_data = {
            "name": "Default",
            "sounds": {"alert": "default_alert.wav", "notify": "default_notify.wav"},
        }
        self._create_test_pack("default", default_pack_data)

        # Create a broken pack (missing sound files)
        broken_pack_data = {
            "name": "Broken Pack",
            "sounds": {"alert": "missing_alert.wav", "notify": "missing_notify.wav"},
        }
        broken_dir = self._create_test_pack("broken", broken_pack_data)
        # Remove the sound files to simulate missing files
        for sound_file in broken_pack_data["sounds"].values():
            (broken_dir / sound_file).unlink()

        with patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir):
            # Should fallback to default pack when broken pack is requested
            sound_file = get_sound_file("alert", "broken")
            assert sound_file is not None
            assert sound_file.name == "default_alert.wav"

    def test_sound_pack_validation_integration(self):
        """Test sound pack validation during installation."""
        # Create a ZIP with invalid pack (missing required fields)
        import zipfile

        zip_path = Path(self.temp_dir) / "invalid_pack.zip"
        with zipfile.ZipFile(zip_path, "w") as zip_file:
            # Invalid pack.json (missing 'name' field)
            invalid_pack_data = {"sounds": {"alert": "alert.wav"}}
            zip_file.writestr("pack.json", json.dumps(invalid_pack_data))
            zip_file.writestr("alert.wav", b"dummy audio")

        # Installation should fail due to validation
        success, message = self.installer.install_from_zip(zip_path, "invalid_pack")
        assert success is False
        assert "Invalid sound pack" in message
        assert "Missing 'name' field" in message

    def test_multiple_sound_packs_management(self):
        """Test managing multiple sound packs simultaneously."""
        # Create multiple test packs
        pack_configs = [
            ("nature", {"name": "Nature Sounds", "sounds": {"alert": "bird.wav"}}),
            ("minimal", {"name": "Minimal", "sounds": {"alert": "beep.wav"}}),
            ("custom", {"name": "Custom Pack", "sounds": {"alert": "custom.wav"}}),
        ]

        for pack_name, pack_data in pack_configs:
            self._create_test_pack(pack_name, pack_data)

        # List all packs
        packs = self.installer.list_installed_packs()
        assert len(packs) == 3

        pack_names = [pack["name"] for pack in packs]
        assert "Nature Sounds" in pack_names
        assert "Minimal" in pack_names
        assert "Custom Pack" in pack_names

        # Test sound retrieval from different packs
        with patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir):
            nature_sound = get_sound_file("alert", "nature")
            minimal_sound = get_sound_file("alert", "minimal")
            custom_sound = get_sound_file("alert", "custom")

            assert nature_sound.name == "bird.wav"
            assert minimal_sound.name == "beep.wav"
            assert custom_sound.name == "custom.wav"

        # Test getting all available packs
        with patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir):
            available_packs = get_available_sound_packs()
            assert len(available_packs) == 3
            assert "nature" in available_packs
            assert "minimal" in available_packs
            assert "custom" in available_packs

    def test_sound_pack_settings_integration(self):
        """Test integration with settings dialog sound pack loading."""
        # Create test packs
        test_packs = [
            ("default", {"name": "Default Sounds"}),
            ("nature", {"name": "Nature Pack"}),
            ("minimal", {"name": "Minimal Sounds"}),
        ]

        for pack_name, pack_data in test_packs:
            pack_data["sounds"] = {"alert": f"{pack_name}_alert.wav"}
            self._create_test_pack(pack_name, pack_data)

        # Simulate settings dialog sound pack loading
        with patch("accessiweather.notifications.sound_player.SOUNDPACKS_DIR", self.soundpacks_dir):
            available_packs = get_available_sound_packs()

            # Verify all packs are available
            assert len(available_packs) == 3

            # Verify pack metadata is correctly loaded
            assert available_packs["nature"]["name"] == "Nature Pack"
            assert available_packs["minimal"]["name"] == "Minimal Sounds"
            assert available_packs["default"]["name"] == "Default Sounds"

            # Test that sound files can be retrieved for each pack
            for pack_name in ["default", "nature", "minimal"]:
                sound_file = get_sound_file("alert", pack_name)
                assert sound_file is not None
                assert sound_file.name == f"{pack_name}_alert.wav"


if __name__ == "__main__":
    pytest.main([__file__])
