"""Sound pack installation and management utilities."""

import json
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)


class SoundPackInstaller:
    """Handles installation and management of sound packs."""

    def __init__(self, soundpacks_dir: Path):
        """
        Initialize the sound pack installer.

        Args:
        ----
            soundpacks_dir: Directory where sound packs are stored

        """
        self.soundpacks_dir = soundpacks_dir
        self.soundpacks_dir.mkdir(exist_ok=True)

    def install_from_zip(self, zip_path: Path, pack_name: str | None = None) -> tuple[bool, str]:
        """
        Install a sound pack from a ZIP file.

        Args:
        ----
            zip_path: Path to the ZIP file containing the sound pack
            pack_name: Optional name for the pack (defaults to ZIP filename)

        Returns:
        -------
            Tuple of (success, message)

        """
        if not zip_path.exists():
            return False, f"ZIP file not found: {zip_path}"

        if not pack_name:
            pack_name = zip_path.stem

        # Create temporary directory for extraction
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            try:
                # Extract ZIP file
                with zipfile.ZipFile(zip_path, "r") as zip_file:
                    zip_file.extractall(temp_path)

                # Find pack.json file
                pack_json_files = list(temp_path.rglob("pack.json"))
                if not pack_json_files:
                    return False, "No pack.json file found in ZIP archive"

                pack_json_path = pack_json_files[0]
                pack_dir = pack_json_path.parent

                # Validate the sound pack
                is_valid, error_msg = self._validate_extracted_pack(pack_dir)
                if not is_valid:
                    return False, f"Invalid sound pack: {error_msg}"

                # Install the pack
                target_dir = self.soundpacks_dir / pack_name
                if target_dir.exists():
                    return False, f"Sound pack '{pack_name}' already exists"

                shutil.copytree(pack_dir, target_dir)

                # Load pack metadata for confirmation
                with open(target_dir / "pack.json", encoding="utf-8") as f:
                    pack_data = json.load(f)

                pack_display_name = pack_data.get("name", pack_name)
                return True, f"Successfully installed sound pack '{pack_display_name}'"

            except zipfile.BadZipFile:
                return False, "Invalid ZIP file"
            except json.JSONDecodeError as e:
                return False, f"Invalid pack.json file: {e}"
            except Exception as e:
                logger.error(f"Error installing sound pack: {e}")
                return False, f"Installation failed: {e}"

    def uninstall_pack(self, pack_name: str) -> tuple[bool, str]:
        """
        Uninstall a sound pack.

        Args:
        ----
            pack_name: Name of the pack to uninstall

        Returns:
        -------
            Tuple of (success, message)

        """
        if pack_name == "default":
            return False, "Cannot uninstall the default sound pack"

        pack_dir = self.soundpacks_dir / pack_name
        if not pack_dir.exists():
            return False, f"Sound pack '{pack_name}' not found"

        try:
            shutil.rmtree(pack_dir)
            return True, f"Successfully uninstalled sound pack '{pack_name}'"
        except Exception as e:
            logger.error(f"Error uninstalling sound pack: {e}")
            return False, f"Uninstallation failed: {e}"

    def export_pack(self, pack_name: str, output_path: Path) -> tuple[bool, str]:
        """
        Export a sound pack to a ZIP file.

        Args:
        ----
            pack_name: Name of the pack to export
            output_path: Path where the ZIP file should be created

        Returns:
        -------
            Tuple of (success, message)

        """
        pack_dir = self.soundpacks_dir / pack_name
        if not pack_dir.exists():
            return False, f"Sound pack '{pack_name}' not found"

        try:
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for file_path in pack_dir.rglob("*"):
                    if file_path.is_file():
                        # Add file to ZIP with relative path
                        arcname = file_path.relative_to(pack_dir)
                        zip_file.write(file_path, arcname)

            return True, f"Successfully exported sound pack to {output_path}"
        except Exception as e:
            logger.error(f"Error exporting sound pack: {e}")
            return False, f"Export failed: {e}"

    def list_installed_packs(self) -> list[dict[str, str]]:
        """
        List all installed sound packs.

        Returns
        -------
            List of pack information dictionaries

        """
        packs: list[dict[str, str]] = []

        if not self.soundpacks_dir.exists():
            return packs

        for pack_dir in self.soundpacks_dir.iterdir():
            if not pack_dir.is_dir():
                continue

            pack_json = pack_dir / "pack.json"
            if not pack_json.exists():
                continue

            try:
                with open(pack_json, encoding="utf-8") as f:
                    pack_data = json.load(f)

                pack_info = {
                    "directory": pack_dir.name,
                    "name": pack_data.get("name", pack_dir.name),
                    "author": pack_data.get("author", "Unknown"),
                    "description": pack_data.get("description", "No description"),
                    "version": pack_data.get("version", "1.0.0"),
                    "path": str(pack_dir),
                }
                packs.append(pack_info)

            except Exception as e:
                logger.error(f"Failed to load sound pack {pack_dir.name}: {e}")

        return sorted(packs, key=lambda x: x["name"])

    def _validate_extracted_pack(self, pack_dir: Path) -> tuple[bool, str]:
        """
        Validate an extracted sound pack directory.

        Args:
        ----
            pack_dir: Path to the extracted pack directory

        Returns:
        -------
            Tuple of (is_valid, error_message)

        """
        pack_json = pack_dir / "pack.json"
        if not pack_json.exists():
            return False, "Missing pack.json file"

        try:
            with open(pack_json, encoding="utf-8") as f:
                pack_data = json.load(f)

            # Check required fields
            if "name" not in pack_data:
                return False, "Missing 'name' field in pack.json"

            if "sounds" not in pack_data:
                return False, "Missing 'sounds' field in pack.json"

            # Check if sound files exist
            sounds = pack_data["sounds"]
            missing_files = []

            for _sound_name, sound_file in sounds.items():
                sound_path = pack_dir / sound_file
                if not sound_path.exists():
                    missing_files.append(sound_file)

            if missing_files:
                return False, f"Missing sound files: {', '.join(missing_files)}"

            return True, "Sound pack is valid"

        except json.JSONDecodeError as e:
            return False, f"Invalid JSON in pack.json: {e}"
        except Exception as e:
            return False, f"Error validating sound pack: {e}"

    def create_pack_template(self, pack_name: str, pack_info: dict[str, str]) -> tuple[bool, str]:
        """
        Create a new sound pack template.

        Args:
        ----
            pack_name: Directory name for the pack
            pack_info: Pack metadata (name, author, description, etc.)

        Returns:
        -------
            Tuple of (success, message)

        """
        pack_dir = self.soundpacks_dir / pack_name
        if pack_dir.exists():
            return False, f"Sound pack '{pack_name}' already exists"

        try:
            pack_dir.mkdir(parents=True)

            # Create pack.json
            pack_data = {
                "name": pack_info.get("name", pack_name),
                "author": pack_info.get("author", "Unknown"),
                "description": pack_info.get("description", "Custom sound pack"),
                "version": pack_info.get("version", "1.0.0"),
                "sounds": {
                    "alert": "alert.wav",
                    "notify": "notify.wav",
                    "error": "error.wav",
                    "success": "success.wav",
                    "startup": "startup.wav",
                    "exit": "exit.wav",
                },
            }

            with open(pack_dir / "pack.json", "w", encoding="utf-8") as f:
                json.dump(pack_data, f, indent=4)

            # Create placeholder sound files
            for sound_file in pack_data["sounds"].values():
                (pack_dir / sound_file).touch()

            return True, f"Created sound pack template '{pack_name}'"

        except Exception as e:
            logger.error(f"Error creating sound pack template: {e}")
            return False, f"Template creation failed: {e}"
