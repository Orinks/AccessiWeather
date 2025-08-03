"""Unit tests for the sound pack installer."""

import json
import tempfile
import zipfile
from pathlib import Path

import pytest

from accessiweather.notifications.sound_pack_installer import SoundPackInstaller


class TestSoundPackInstaller:
    """Test cases for the sound pack installer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.soundpacks_dir = Path(self.temp_dir)
        self.installer = SoundPackInstaller(self.soundpacks_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_pack_zip(self, pack_name: str, include_sounds: bool = True) -> Path:
        """Create a test sound pack ZIP file."""
        zip_path = Path(self.temp_dir) / f"{pack_name}.zip"

        with zipfile.ZipFile(zip_path, "w") as zip_file:
            # Create pack.json
            pack_data = {
                "name": f"Test {pack_name}",
                "author": "Test Author",
                "description": "Test sound pack",
                "version": "1.0.0",
                "sounds": {"alert": "alert.wav", "notify": "notify.wav"},
            }

            zip_file.writestr("pack.json", json.dumps(pack_data, indent=2))

            if include_sounds:
                # Create dummy sound files
                zip_file.writestr("alert.wav", b"dummy audio data")
                zip_file.writestr("notify.wav", b"dummy audio data")

        return zip_path

    def test_install_from_zip_success(self):
        """Test successful installation from ZIP file."""
        zip_path = self._create_test_pack_zip("nature")

        success, message = self.installer.install_from_zip(zip_path, "nature")

        assert success is True
        assert "Successfully installed" in message
        assert (self.soundpacks_dir / "nature" / "pack.json").exists()
        assert (self.soundpacks_dir / "nature" / "alert.wav").exists()

    def test_install_from_zip_missing_file(self):
        """Test installation with missing ZIP file."""
        missing_zip = Path(self.temp_dir) / "missing.zip"

        success, message = self.installer.install_from_zip(missing_zip)

        assert success is False
        assert "ZIP file not found" in message

    def test_install_from_zip_no_pack_json(self):
        """Test installation with ZIP missing pack.json."""
        zip_path = Path(self.temp_dir) / "invalid.zip"

        with zipfile.ZipFile(zip_path, "w") as zip_file:
            zip_file.writestr("alert.wav", b"dummy audio data")

        success, message = self.installer.install_from_zip(zip_path)

        assert success is False
        assert "No pack.json file found" in message

    def test_install_from_zip_missing_sounds(self):
        """Test installation with missing sound files."""
        zip_path = self._create_test_pack_zip("incomplete", include_sounds=False)

        success, message = self.installer.install_from_zip(zip_path)

        assert success is False
        assert "Missing sound files" in message

    def test_install_from_zip_already_exists(self):
        """Test installation when pack already exists."""
        zip_path = self._create_test_pack_zip("existing")

        # Install once
        self.installer.install_from_zip(zip_path, "existing")

        # Try to install again
        success, message = self.installer.install_from_zip(zip_path, "existing")

        assert success is False
        assert "already exists" in message

    def test_uninstall_pack_success(self):
        """Test successful pack uninstallation."""
        # Create a test pack
        pack_dir = self.soundpacks_dir / "test_pack"
        pack_dir.mkdir()
        (pack_dir / "pack.json").write_text('{"name": "Test Pack"}')

        success, message = self.installer.uninstall_pack("test_pack")

        assert success is True
        assert "Successfully uninstalled" in message
        assert not pack_dir.exists()

    def test_uninstall_pack_default_protection(self):
        """Test that default pack cannot be uninstalled."""
        success, message = self.installer.uninstall_pack("default")

        assert success is False
        assert "Cannot uninstall the default" in message

    def test_uninstall_pack_not_found(self):
        """Test uninstalling non-existent pack."""
        success, message = self.installer.uninstall_pack("nonexistent")

        assert success is False
        assert "not found" in message

    def test_export_pack_success(self):
        """Test successful pack export."""
        # Create a test pack
        pack_dir = self.soundpacks_dir / "export_test"
        pack_dir.mkdir()

        pack_data = {
            "name": "Export Test",
            "author": "Test Author",
            "sounds": {"alert": "alert.wav"},
        }

        with open(pack_dir / "pack.json", "w", encoding="utf-8") as f:
            json.dump(pack_data, f)

        (pack_dir / "alert.wav").write_bytes(b"dummy audio")

        output_path = Path(self.temp_dir) / "exported.zip"
        success, message = self.installer.export_pack("export_test", output_path)

        assert success is True
        assert "Successfully exported" in message
        assert output_path.exists()

        # Verify ZIP contents
        with zipfile.ZipFile(output_path, "r") as zip_file:
            files = zip_file.namelist()
            assert "pack.json" in files
            assert "alert.wav" in files

    def test_export_pack_not_found(self):
        """Test exporting non-existent pack."""
        output_path = Path(self.temp_dir) / "exported.zip"
        success, message = self.installer.export_pack("nonexistent", output_path)

        assert success is False
        assert "not found" in message

    def test_list_installed_packs(self):
        """Test listing installed packs."""
        # Create test packs
        for pack_name in ["pack1", "pack2"]:
            pack_dir = self.soundpacks_dir / pack_name
            pack_dir.mkdir()

            pack_data = {
                "name": f"Test {pack_name}",
                "author": "Test Author",
                "description": f"Description for {pack_name}",
                "version": "1.0.0",
            }

            with open(pack_dir / "pack.json", "w", encoding="utf-8") as f:
                json.dump(pack_data, f)

        packs = self.installer.list_installed_packs()

        assert len(packs) == 2
        assert packs[0]["name"] == "Test pack1"
        assert packs[1]["name"] == "Test pack2"
        assert all("directory" in pack for pack in packs)
        assert all("author" in pack for pack in packs)

    def test_list_installed_packs_empty(self):
        """Test listing packs when none are installed."""
        packs = self.installer.list_installed_packs()
        assert packs == []

    def test_create_pack_template_success(self):
        """Test successful pack template creation."""
        pack_info = {
            "name": "My Custom Pack",
            "author": "Custom Author",
            "description": "My custom sound pack",
            "version": "2.0.0",
        }

        success, message = self.installer.create_pack_template("custom", pack_info)

        assert success is True
        assert "Created sound pack template" in message

        pack_dir = self.soundpacks_dir / "custom"
        assert pack_dir.exists()
        assert (pack_dir / "pack.json").exists()
        assert (pack_dir / "alert.wav").exists()

        # Verify pack.json content
        with open(pack_dir / "pack.json", encoding="utf-8") as f:
            pack_data = json.load(f)

        assert pack_data["name"] == "My Custom Pack"
        assert pack_data["author"] == "Custom Author"
        assert pack_data["version"] == "2.0.0"

    def test_create_pack_template_already_exists(self):
        """Test template creation when pack already exists."""
        # Create existing pack
        (self.soundpacks_dir / "existing").mkdir()

        success, message = self.installer.create_pack_template("existing", {})

        assert success is False
        assert "already exists" in message

    def test_validate_extracted_pack_valid(self):
        """Test validation of a valid pack."""
        pack_dir = Path(self.temp_dir) / "valid_pack"
        pack_dir.mkdir()

        pack_data = {"name": "Valid Pack", "sounds": {"alert": "alert.wav"}}

        with open(pack_dir / "pack.json", "w", encoding="utf-8") as f:
            json.dump(pack_data, f)

        (pack_dir / "alert.wav").touch()

        is_valid, message = self.installer._validate_extracted_pack(pack_dir)

        assert is_valid is True
        assert "valid" in message.lower()

    def test_validate_extracted_pack_missing_pack_json(self):
        """Test validation with missing pack.json."""
        pack_dir = Path(self.temp_dir) / "invalid_pack"
        pack_dir.mkdir()

        is_valid, message = self.installer._validate_extracted_pack(pack_dir)

        assert is_valid is False
        assert "Missing pack.json" in message

    def test_validate_extracted_pack_invalid_json(self):
        """Test validation with invalid JSON."""
        pack_dir = Path(self.temp_dir) / "invalid_json_pack"
        pack_dir.mkdir()

        (pack_dir / "pack.json").write_text("invalid json content")

        is_valid, message = self.installer._validate_extracted_pack(pack_dir)

        assert is_valid is False
        assert "Invalid JSON" in message

    def test_validate_extracted_pack_missing_fields(self):
        """Test validation with missing required fields."""
        pack_dir = Path(self.temp_dir) / "incomplete_pack"
        pack_dir.mkdir()

        # Missing 'name' field
        pack_data = {"sounds": {"alert": "alert.wav"}}

        with open(pack_dir / "pack.json", "w", encoding="utf-8") as f:
            json.dump(pack_data, f)

        is_valid, message = self.installer._validate_extracted_pack(pack_dir)

        assert is_valid is False
        assert "Missing 'name' field" in message


if __name__ == "__main__":
    pytest.main([__file__])
