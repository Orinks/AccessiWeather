"""Backup and restore helpers for configuration import/export operations."""

from __future__ import annotations

from pathlib import Path


class BackupRestoreMixin:
    """Provide configuration backup and restore operations."""

    def backup_config(self, backup_path: Path | None = None) -> bool:
        """Create a backup copy of the current configuration file."""
        backup_target = backup_path or self._manager.config_file.with_suffix(".json.backup")

        try:
            if not self._manager.config_file.exists():
                self.logger.warning("No config file to backup")
                return False

            self._copy_file(self._manager.config_file, backup_target)
            self.logger.info(f"Config backed up to {backup_target}")
            return True
        except Exception as exc:
            self.logger.error(f"Failed to backup config: {exc}")
            return False

    def restore_config(self, backup_path: Path) -> bool:
        """Restore configuration from the provided backup file."""
        try:
            if not backup_path.exists():
                self.logger.error(f"Backup file not found: {backup_path}")
                return False

            self._copy_file(backup_path, self._manager.config_file)
            self._manager._config = None
            self._manager.load_config()

            self.logger.info(f"Config restored from {backup_path}")
            return True
        except Exception as exc:
            self.logger.error(f"Failed to restore config: {exc}")
            return False
