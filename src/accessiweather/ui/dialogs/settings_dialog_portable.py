"""SettingsDialogPortableMixin helpers for the settings dialog."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import wx

logger = logging.getLogger("accessiweather.ui.dialogs.settings_dialog")


class SettingsDialogPortableMixin:
    _PORTABLE_KEY_SETTINGS = (
        "pirate_weather_api_key",
        "openrouter_api_key",
        "avwx_api_key",
    )

    def _maybe_update_portable_bundle_after_save(self, settings_dict: dict) -> None:
        """After saving settings in portable mode, keep the bundle in sync."""
        changed_keys = {
            k: v for k, v in settings_dict.items() if k in self._PORTABLE_KEY_SETTINGS and v
        }
        if not changed_keys:
            return

        from ...config.secure_storage import SecureStorage

        app = self.app
        _PASSPHRASE_KEY = getattr(
            app, "_PORTABLE_PASSPHRASE_KEYRING_KEY", "portable_bundle_passphrase"
        )
        config_dir = self.config_manager.config_dir
        bundle_names = ("api-keys.keys", "api-keys.awkeys")
        bundle_path = next(
            (config_dir / n for n in bundle_names if (config_dir / n).exists()), None
        )

        passphrase = (SecureStorage.get_password(_PASSPHRASE_KEY) or "").strip()

        if not passphrase:
            if bundle_path:
                msg = (
                    "Your API keys have been updated.\n\n"
                    "Enter your bundle passphrase to re-encrypt the portable key bundle, "
                    "or Cancel to leave the bundle unchanged (keys are active this session only)."
                )
            else:
                msg = (
                    "Your API keys have been updated.\n\n"
                    "Enter a passphrase to create an encrypted key bundle so your keys "
                    "persist across launches, or Cancel to skip (keys active this session only)."
                )
            with wx.TextEntryDialog(
                self,
                msg,
                "Portable key bundle",
                style=wx.OK | wx.CANCEL | wx.TE_PASSWORD,
            ) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return
                passphrase = dlg.GetValue().strip()
            if not passphrase:
                return
            SecureStorage.set_password(_PASSPHRASE_KEY, passphrase)

        if bundle_path is None:
            bundle_path = config_dir / "api-keys.keys"

        try:
            ok = self.config_manager.export_encrypted_api_keys(bundle_path, passphrase)
            if ok:
                logger.info("Portable key bundle updated after settings save.")
            else:
                wx.MessageBox(
                    "No API keys found to export. Keys are active this session but won't persist.",
                    "Bundle update skipped",
                    wx.OK | wx.ICON_WARNING,
                )
        except Exception as exc:
            logger.error("Failed to update portable key bundle: %s", exc)
            wx.MessageBox(
                "Failed to update the key bundle. Keys are active this session but won't persist.",
                "Bundle update failed",
                wx.OK | wx.ICON_WARNING,
            )

    def _is_runtime_portable_mode(self) -> bool:
        """Return portable mode using runtime app/config state."""
        app_portable = getattr(self.app, "_portable_mode", None)
        if app_portable is not None:
            return bool(app_portable)
        runtime_paths = getattr(self.app, "runtime_paths", None)
        if runtime_paths is not None:
            return bool(getattr(runtime_paths, "portable_mode", False))
        return False

    def _has_meaningful_installed_config_data(
        self, installed_config_dir: Path
    ) -> tuple[bool, str | None]:
        """Pre-check whether installed config has meaningful data to transfer."""
        if not installed_config_dir.exists() or not installed_config_dir.is_dir():
            return False, "Installed config directory not found."

        try:
            has_any_entries = any(installed_config_dir.iterdir())
        except Exception:
            has_any_entries = False
        if not has_any_entries:
            return False, "Installed config directory is empty."

        config_file = installed_config_dir / "accessiweather.json"
        if not config_file.exists() or not config_file.is_file():
            return False, "Required config file accessiweather.json is missing."

        try:
            if config_file.stat().st_size <= 0:
                return False, "Config file accessiweather.json is empty."
        except Exception:
            return False, "Could not read accessiweather.json."

        try:
            config_data = self._read_config_json(installed_config_dir)
        except Exception:
            return False, "Config file accessiweather.json is invalid or unreadable."

        locations = (
            config_data.get("locations") if isinstance(config_data.get("locations"), list) else []
        )

        if len(locations) == 0:
            return False, "Installed config has no saved locations to transfer."

        return True, None

    def _get_installed_config_dir(self):
        """Return the standard installed config directory path."""
        import os

        local_appdata = os.environ.get("LOCALAPPDATA")
        author = getattr(self.app.paths, "_author", "Orinks")
        app_name = getattr(self.app.paths, "_app_name", "AccessiWeather")
        if local_appdata:
            return Path(local_appdata) / str(author) / str(app_name) / "Config"
        return Path.home() / "AppData" / "Local" / str(author) / str(app_name) / "Config"

    def _on_open_installed_config_dir(self, event):
        """Open installed config directory."""
        import subprocess

        installed_config_dir = self._get_installed_config_dir()
        if installed_config_dir.exists():
            subprocess.Popen(["explorer", str(installed_config_dir)])
        else:
            wx.MessageBox(
                f"Installed config directory not found: {installed_config_dir}",
                "Info",
                wx.OK | wx.ICON_INFORMATION,
            )

    def _read_config_json(self, config_dir: Path) -> dict:
        """Read accessiweather.json from a config directory."""
        config_file = config_dir / "accessiweather.json"
        if not config_file.exists():
            raise FileNotFoundError(f"Required config file not found: {config_file}")
        with open(config_file, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Invalid config payload in {config_file}: expected object")
        return data

    def _validate_portable_copy(
        self, installed_config_dir: Path, portable_config_dir: Path
    ) -> tuple[bool, list[str]]:
        """Validate copied portable config has required non-secret settings/state."""
        messages: list[str] = []
        try:
            src_cfg = self._read_config_json(installed_config_dir)
            dst_cfg = self._read_config_json(portable_config_dir)
        except Exception as e:
            return False, [str(e)]

        src_settings = src_cfg.get("settings") if isinstance(src_cfg.get("settings"), dict) else {}
        dst_settings = dst_cfg.get("settings") if isinstance(dst_cfg.get("settings"), dict) else {}

        required_setting_keys = ["ai_model_preference", "data_source", "temperature_unit"]
        for key in required_setting_keys:
            src_value = src_settings.get(key)
            dst_value = dst_settings.get(key)
            if src_value != dst_value:
                messages.append(
                    f"Setting '{key}' did not copy correctly "
                    f"(installed={src_value!r}, portable={dst_value!r})."
                )

        src_locations = (
            src_cfg.get("locations") if isinstance(src_cfg.get("locations"), list) else []
        )
        dst_locations = (
            dst_cfg.get("locations") if isinstance(dst_cfg.get("locations"), list) else []
        )
        if len(src_locations) != len(dst_locations):
            messages.append(
                f"Location count mismatch after copy "
                f"(installed={len(src_locations)}, portable={len(dst_locations)})."
            )

        if messages:
            return False, messages
        return True, []

    def _build_portable_copy_summary(self, portable_config_dir: Path) -> list[str]:
        """Build concise summary lines describing migrated non-secret config values."""
        config_data = self._read_config_json(portable_config_dir)
        settings = (
            config_data.get("settings") if isinstance(config_data.get("settings"), dict) else {}
        )
        locations = (
            config_data.get("locations") if isinstance(config_data.get("locations"), list) else []
        )

        custom_prompt_present = any(
            bool(str(settings.get(key, "")).strip())
            for key in (
                "custom_system_prompt",
                "custom_instructions",
                "prompt",
                "assistant_prompt",
            )
            if key in settings
        )

        return [
            f"• locations: {len(locations)}",
            f"• data source: {settings.get('data_source', 'not set')}",
            f"• AI model preference: {settings.get('ai_model_preference', 'not set')}",
            f"• temperature unit: {settings.get('temperature_unit', 'not set')}",
            f"• custom prompt: {'yes' if custom_prompt_present else 'no'}",
        ]

    def _on_copy_installed_config_to_portable(self, event):
        """Copy installed config files into the current portable config directory."""
        import shutil

        portable_config_dir = self.config_manager.config_dir
        installed_config_dir = self._get_installed_config_dir()

        has_data, precheck_reason = self._has_meaningful_installed_config_data(installed_config_dir)
        if not has_data:
            detail = f"\n\nDetails: {precheck_reason}" if precheck_reason else ""
            wx.MessageBox(
                f"Nothing to transfer from installed config.\n{installed_config_dir}{detail}",
                "Nothing to copy",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if installed_config_dir.resolve() == portable_config_dir.resolve():
            wx.MessageBox(
                "Installed and portable config directories are the same location."
                "\n\nNo copy is needed.",
                "Nothing to copy",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        result = wx.MessageBox(
            "Copy settings and locations from installed config to this portable config?\n\n"
            "Only core config files are copied. Cache files are skipped and will regenerate.\n\n"
            "Existing files in portable config with the same name will be overwritten.",
            "Copy installed config to portable",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if result != wx.YES:
            return

        self.config_manager.save_config()

        try:
            portable_config_dir.mkdir(parents=True, exist_ok=True)

            transferable_items = ["accessiweather.json"]
            copied_items: list[str] = []

            for name in transferable_items:
                item = installed_config_dir / name
                if not item.exists():
                    continue

                dst = portable_config_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dst)
                copied_items.append(item.name)

            if not copied_items:
                wx.MessageBox(
                    "Nothing to transfer from installed config."
                    "\n\nNo transferable config files were found.",
                    "Nothing to copy",
                    wx.OK | wx.ICON_WARNING,
                )
                return

            valid, validation_errors = self._validate_portable_copy(
                installed_config_dir, portable_config_dir
            )
            if not valid:
                details = "\n".join(f"• {msg}" for msg in validation_errors)
                wx.MessageBox(
                    "Config copy completed, but validation found problems."
                    "\n\nPortable data may be incomplete."
                    f"\n\n{details}",
                    "Copy incomplete",
                    wx.OK | wx.ICON_WARNING,
                )
                return

            self.config_manager._config = None
            self.config_manager.load_config()
            self._load_settings()

            copied_list = "\n".join(f"• {name}" for name in copied_items)
            summary_lines = self._build_portable_copy_summary(portable_config_dir)
            summary_block = "\n".join(summary_lines)
            wx.MessageBox(
                "Copied these config item(s):\n"
                f"{copied_list}\n\n"
                "Copied settings summary:\n"
                f"{summary_block}\n\n"
                f"From:\n{installed_config_dir}\n\n"
                f"To:\n{portable_config_dir}",
                "Copy complete",
                wx.OK | wx.ICON_INFORMATION,
            )

            self._offer_api_key_export_after_copy(portable_config_dir)
        except Exception as e:
            logger.error(f"Failed to copy installed config to portable: {e}")
            wx.MessageBox(
                f"Failed to copy config: {e}",
                "Copy failed",
                wx.OK | wx.ICON_ERROR,
            )

    def _offer_api_key_export_after_copy(self, portable_config_dir: Path) -> None:
        """After copying installed config to portable, offer to export API keys."""
        result = wx.MessageBox(
            "Config copied. Your API keys are stored in the system keyring and were not "
            "copied.\n\n"
            "Would you like to export them to an encrypted bundle now so they work in "
            "portable mode?",
            "Export API keys?",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if result != wx.YES:
            wx.MessageBox(
                "You can export API keys later from Settings > Advanced > "
                "Export API keys (encrypted).",
                "API keys not exported",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        passphrase = self._prompt_passphrase(
            "Export API keys (encrypted)",
            "Enter a passphrase to encrypt your API keys.",
        )
        if passphrase is None:
            return

        confirm = self._prompt_passphrase(
            "Confirm passphrase",
            "Re-enter the passphrase to confirm.",
        )
        if confirm is None:
            return
        if passphrase != confirm:
            wx.MessageBox(
                "Passphrases do not match. API keys were not exported.",
                "Export cancelled",
                wx.OK | wx.ICON_WARNING,
            )
            return

        bundle_path = portable_config_dir / "api-keys.keys"
        try:
            ok = self.config_manager.export_encrypted_api_keys(bundle_path, passphrase)
            if ok:
                wx.MessageBox(
                    f"API keys exported to:\n{bundle_path}",
                    "Export complete",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    "No API keys found to export. You can add keys in Settings > Data Sources "
                    "or Settings > AI and export later.",
                    "No keys to export",
                    wx.OK | wx.ICON_WARNING,
                )
        except Exception as exc:
            logger.error("Failed to export API keys after config copy: %s", exc)
            wx.MessageBox(
                f"Failed to export API keys: {exc}",
                "Export failed",
                wx.OK | wx.ICON_ERROR,
            )
