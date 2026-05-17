"""Startup onboarding, key import, and guidance prompt helpers."""

from __future__ import annotations

import logging
from pathlib import Path

import wx

logger = logging.getLogger("accessiweather.app")


class _OnboardingCancelled(Exception):
    """Raised when the user exits first-start onboarding."""


class AppStartupGuidanceMixin:
    def _schedule_startup_guidance_prompts(self) -> None:
        """Schedule lightweight first-run and portable hints after startup."""
        wx.CallLater(400, self._maybe_auto_import_keys_file)
        wx.CallLater(800, self._maybe_show_first_start_onboarding)
        wx.CallLater(1400, self._maybe_show_portable_missing_keys_hint)

    # Keyring key used to cache the portable bundle passphrase for convenience.
    # Only the passphrase is stored here — API keys always live in the bundle.
    _PORTABLE_PASSPHRASE_KEYRING_KEY: str = "portable_bundle_passphrase"

    def _maybe_auto_import_keys_file(self) -> None:
        """
        Auto-import an encrypted API key bundle on startup (portable mode only).

        API keys always live in the bundle — keyring is not used for key storage.
        The bundle passphrase is cached in keyring purely for convenience so the
        user is not prompted on every launch.  On first launch (or new machine)
        the user is prompted once; on success the passphrase is stored in keyring
        for silent auto-import on subsequent launches.
        """
        if not self.main_window or not self.config_manager:
            return
        if not self._portable_mode:
            return

        # Skip if already imported this session.
        if self._portable_keys_imported_this_session:
            return

        config_dir = self.config_manager.config_dir
        candidate_names = ["api-keys.keys", "api-keys.awkeys"]
        keys_path = None
        for name in candidate_names:
            p = config_dir / name
            if p.exists():
                keys_path = p
                break

        if keys_path is None:
            return

        from .config.secure_storage import SecureStorage

        # Try cached passphrase for silent auto-import.
        stored = (SecureStorage.get_password(self._PORTABLE_PASSPHRASE_KEYRING_KEY) or "").strip()
        if stored:
            try:
                if self.config_manager.import_encrypted_api_keys(keys_path, stored):
                    self._portable_keys_imported_this_session = True
                    self._write_keys_file_after_import(config_dir, stored)
                    self.refresh_runtime_settings()
                    if self.main_window and hasattr(
                        self.main_window, "refresh_weather_async"
                    ):  # pragma: no cover
                        self.main_window.refresh_weather_async(force_refresh=True)
                    logger.info("Portable API keys auto-imported silently.")
                    return
            except Exception as exc:
                logger.warning("Silent auto-import failed: %s", exc)
            # Cached passphrase is stale — clear and fall through to prompt.
            SecureStorage.delete_password(self._PORTABLE_PASSPHRASE_KEYRING_KEY)

        # Prompt for passphrase with retry loop.
        while True:
            with wx.TextEntryDialog(
                self.main_window,
                "An encrypted API key bundle was found. Enter your passphrase to import your keys.",
                "Import API keys",
                style=wx.OK | wx.CANCEL | wx.TE_PASSWORD,
            ) as dlg:
                result = dlg.ShowModal()
                if result != wx.ID_OK:
                    return
                passphrase = dlg.GetValue().strip()

            if not passphrase:
                return

            try:
                success = self.config_manager.import_encrypted_api_keys(keys_path, passphrase)
            except Exception as exc:
                logger.warning("Auto-import of API keys failed: %s", exc)
                success = False

            if success:
                self._portable_keys_imported_this_session = True
                # Cache passphrase in keyring so next launch is silent.
                SecureStorage.set_password(self._PORTABLE_PASSPHRASE_KEYRING_KEY, passphrase)
                self._write_keys_file_after_import(config_dir, passphrase)
                self.refresh_runtime_settings()
                if self.main_window and hasattr(
                    self.main_window, "refresh_weather_async"
                ):  # pragma: no cover
                    self.main_window.refresh_weather_async(force_refresh=True)
                wx.MessageBox(
                    "API keys imported successfully. They are now active.",
                    "Keys imported",
                    wx.OK | wx.ICON_INFORMATION,
                )
                return

            # Wrong passphrase or other failure — offer retry or skip.
            retry_dlg = wx.MessageDialog(
                self.main_window,
                "The passphrase was incorrect or the key bundle could not be read.\n\n"
                "Would you like to try again?",
                "Import failed",
                wx.YES_NO | wx.ICON_WARNING,
            )
            retry_dlg.SetYesNoLabels("Try again", "Skip")
            retry_result = retry_dlg.ShowModal()
            retry_dlg.Destroy()
            if retry_result != wx.ID_YES:
                return

    def _write_keys_file_after_import(self, config_dir: Path, passphrase: str) -> None:
        """
        Write api-keys.keys to the portable config dir after a successful import.

        This ensures the canonical bundle file is always present so that a new
        machine or clean keyring can re-import from it.
        """
        keys_dest = config_dir / "api-keys.keys"
        try:
            self.config_manager.export_encrypted_api_keys(keys_dest, passphrase)
        except Exception as exc:
            logger.warning("Failed to write api-keys.keys after import: %s", exc)

    def _should_show_first_start_onboarding(self) -> bool:
        """Return True when first-start onboarding should be shown."""
        if not self.main_window or not self.config_manager:
            return False

        if self._force_wizard:
            if self.debug_mode:
                logger.debug("Wizard forced via --wizard flag")
            return True

        config = self.config_manager.get_config()
        settings = config.settings
        return not getattr(settings, "onboarding_wizard_shown", False) and not bool(
            config.locations
        )

    def _check_for_updates_after_startup_guidance(self) -> None:
        """Run startup update checks now, or defer until onboarding closes."""
        self._startup_update_check_deferred = self._should_show_first_start_onboarding()
        if self._startup_update_check_deferred:
            return
        self._check_for_updates_on_startup()

    def _run_deferred_startup_update_check(self) -> None:
        """Run the deferred startup update check once after onboarding finishes."""
        if not getattr(self, "_startup_update_check_deferred", False):
            return
        self._startup_update_check_deferred = False
        self._check_for_updates_on_startup()

    def _maybe_show_portable_missing_keys_hint(self) -> None:
        """Show a one-time hint when portable mode has no bundle and no keys entered."""
        if not self.main_window or not self.config_manager or not self._portable_mode:
            return

        settings = self.config_manager.get_settings()
        if getattr(settings, "portable_missing_api_keys_hint_shown", False):
            return

        # If the onboarding wizard is going to run (or did run), it covers key setup.
        if self._should_show_first_start_onboarding():
            return

        # If a bundle exists the import flow already handled it — no hint needed.
        config_dir = self.config_manager.config_dir
        bundle_exists = any(
            (config_dir / name).exists() for name in ("api-keys.keys", "api-keys.awkeys")
        )
        if bundle_exists:
            return

        # If keys were imported this session, no hint needed.
        if self._portable_keys_imported_this_session:
            return

        dialog = wx.MessageDialog(
            self.main_window,
            "This portable copy has no API keys yet.\n\n"
            "Pirate Weather provider keys can be entered in Settings > Data Sources. "
            "OpenRouter AI keys can be entered in Settings > AI.\n\n"
            "You can also create an encrypted key bundle to carry your keys with the portable install.",
            "Portable setup hint",
            wx.YES_NO | wx.CANCEL | wx.ICON_INFORMATION,
        )
        dialog.SetYesNoCancelLabels("Open Settings", "Later", "Cancel")
        result = dialog.ShowModal()
        dialog.Destroy()

        self.config_manager.update_settings(portable_missing_api_keys_hint_shown=True)

        if result == wx.ID_YES and self.main_window:
            self.main_window.open_settings()

    def _prompt_optional_secret(self, title: str, message: str) -> str:
        """Prompt for optional secret text value. Empty input means skip."""
        with wx.TextEntryDialog(
            self.main_window, message, title, style=wx.OK | wx.CANCEL | wx.TE_PASSWORD
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                raise _OnboardingCancelled
            return dlg.GetValue().strip() or ""

    def _prompt_optional_secret_with_link(
        self,
        title: str,
        message: str,
        key_page_url: str,
        key_page_action_label: str,
    ) -> str:
        """Prompt for an optional secret with an action to open its key page."""
        setup_dialog = wx.MessageDialog(
            self.main_window,
            f"{message}\n\nChoose Set up now to enter or get a key, Skip this key to keep going, "
            "or Configure myself to close the wizard.",
            title,
            wx.YES_NO | wx.CANCEL | wx.ICON_INFORMATION,
        )
        setup_dialog.SetYesNoCancelLabels("Set up now", "Skip this key", "Configure myself")
        setup_result = setup_dialog.ShowModal()
        setup_dialog.Destroy()

        if setup_result == wx.ID_NO:
            return ""
        if setup_result != wx.ID_YES:
            raise _OnboardingCancelled

        while True:
            choice_dialog = wx.MessageDialog(
                self.main_window,
                f"{message}\n\nChoose Enter key to type it now, {key_page_action_label}, "
                "or Configure myself to close the wizard.",
                title,
                wx.YES_NO | wx.CANCEL | wx.ICON_INFORMATION,
            )
            choice_dialog.SetYesNoCancelLabels(
                "Enter key", key_page_action_label, "Configure myself"
            )
            result = choice_dialog.ShowModal()
            choice_dialog.Destroy()

            if result == wx.ID_YES:
                return self._prompt_optional_secret(title, message)
            if result == wx.ID_NO:
                try:
                    from . import app as app_module

                    app_module.webbrowser.open(key_page_url)
                except Exception as exc:
                    logger.warning("Failed opening API key page %s: %s", key_page_url, exc)
                continue
            raise _OnboardingCancelled

    def _maybe_offer_test_key_now(self, key_name: str) -> None:
        """Offer to open settings so users can validate the entered key immediately."""
        if not self.main_window:
            return

        test_dialog = wx.MessageDialog(
            self.main_window,
            f"{key_name} saved. Test key now in Settings > AI?",
            "Key saved",
            wx.YES_NO | wx.ICON_INFORMATION,
        )
        test_dialog.SetYesNoLabels("Test key now", "Later")
        result = test_dialog.ShowModal()
        test_dialog.Destroy()

        if result == wx.ID_YES:
            self.main_window.open_settings(tab="AI")

    def _has_saved_api_key(self, key_name: str) -> bool:
        """Return True when a specific API key exists (in-memory config for portable, keyring for installed)."""
        if self._portable_mode:
            # In portable mode keys live in the bundle / in-memory config, not keyring.
            val = getattr(self.config_manager.get_config().settings, key_name, None)
            return bool((str(val).strip()) if val else "")
        from .config.secure_storage import SecureStorage

        return bool((SecureStorage.get_password(key_name) or "").strip())

    @staticmethod
    def _onboarding_status_text(enabled: bool) -> str:
        return "Yes" if enabled else "No"

    def _show_onboarding_readiness_summary(self) -> None:
        """Show an end-of-onboarding summary of key setup readiness."""
        if not self.main_window or not self.config_manager:
            return

        config = self.config_manager.get_config()
        summary_lines = [
            "Setup summary:",
            f"- Location configured: {self._onboarding_status_text(bool(config.locations))}",
            f"- OpenRouter key set: {self._onboarding_status_text(self._has_saved_api_key('openrouter_api_key'))}",
            f"- Pirate Weather provider key set: {self._onboarding_status_text(self._has_saved_api_key('pirate_weather_api_key'))}",
            *(
                [
                    f"- Portable key bundle created: {self._onboarding_status_text(self._portable_keys_imported_this_session)}"
                ]
                if self._portable_mode
                else []
            ),
        ]

        summary_dialog = wx.MessageDialog(
            self.main_window,
            "\n".join(summary_lines),
            "Onboarding readiness",
            wx.OK | wx.ICON_INFORMATION,
        )
        summary_dialog.ShowModal()
        summary_dialog.Destroy()

    def _finish_first_start_onboarding(self) -> None:
        """Mark onboarding complete and run any deferred startup work."""
        self._show_onboarding_readiness_summary()
        self.config_manager.update_settings(onboarding_wizard_shown=True)
        self._run_deferred_startup_update_check()

    def _skip_first_start_onboarding(self) -> None:
        """Close first-start onboarding so users can configure manually."""
        self.config_manager.update_settings(onboarding_wizard_shown=True)
        self._run_deferred_startup_update_check()

    def _refresh_after_onboarding_import(self) -> None:
        """Refresh app state after importing settings or keys during onboarding."""
        self.refresh_runtime_settings()
        if not self.main_window:
            return
        if hasattr(self.main_window, "_populate_locations"):
            self.main_window._populate_locations()
        if (
            hasattr(self.main_window, "refresh_weather_async")
            and self.config_manager.has_locations()
        ):
            self.main_window.refresh_weather_async(force_refresh=True)

    def _prompt_onboarding_settings_import(self) -> bool:
        """Prompt for and import an AccessiWeather settings export."""
        with wx.FileDialog(
            self.main_window,
            "Import AccessiWeather settings",
            wildcard="JSON files (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                raise _OnboardingCancelled
            import_path = Path(dlg.GetPath())

        if self.config_manager.import_settings(import_path):
            self._refresh_after_onboarding_import()
            wx.MessageBox(
                "Settings imported successfully. Any saved locations from the backup are ready to use.",
                "Settings imported",
                wx.OK | wx.ICON_INFORMATION,
            )
            return True

        wx.MessageBox(
            "Failed to import settings. The file may be invalid or corrupted.",
            "Settings import failed",
            wx.OK | wx.ICON_ERROR,
        )
        return False

    def _prompt_onboarding_api_key_import(self) -> bool:
        """Prompt for and import an encrypted API key bundle."""
        with wx.FileDialog(
            self.main_window,
            "Import API keys (encrypted)",
            wildcard="Encrypted bundle (*.keys)|*.keys|Legacy bundle (*.awkeys)|*.awkeys",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                raise _OnboardingCancelled
            import_path = Path(dlg.GetPath())

        passphrase = self._prompt_optional_secret(
            "Import API keys (encrypted)",
            "Enter the passphrase used when exporting this encrypted API key bundle.",
        )
        if not passphrase:
            return False

        if self.config_manager.import_encrypted_api_keys(import_path, passphrase):
            if self._portable_mode:
                self._portable_keys_imported_this_session = True
                from .config.secure_storage import SecureStorage

                SecureStorage.set_password(self._PORTABLE_PASSPHRASE_KEYRING_KEY, passphrase)
                self._write_keys_file_after_import(self.config_manager.config_dir, passphrase)
            self._refresh_after_onboarding_import()
            wx.MessageBox(
                "API keys imported successfully. They are now active.",
                "API keys imported",
                wx.OK | wx.ICON_INFORMATION,
            )
            return True

        wx.MessageBox(
            "Failed to import encrypted API keys. Check the passphrase and bundle file.",
            "API key import failed",
            wx.OK | wx.ICON_ERROR,
        )
        return False

    def _maybe_run_onboarding_import_flow(self) -> bool:
        """Offer first-run import of settings and encrypted API keys."""
        if not self.config_manager or not all(
            hasattr(self.config_manager, name)
            for name in ("import_settings", "import_encrypted_api_keys")
        ):
            return False

        imported_any = False
        settings_dialog = wx.MessageDialog(
            self.main_window,
            "Import a settings backup now? This can restore preferences and saved locations.\n\n"
            "Choose Configure myself, or press Escape, to close this wizard.",
            "Import settings",
            wx.YES_NO | wx.CANCEL | wx.ICON_INFORMATION,
        )
        settings_dialog.SetYesNoCancelLabels("Import settings", "Skip settings", "Configure myself")
        settings_choice = settings_dialog.ShowModal()
        settings_dialog.Destroy()
        if settings_choice == wx.ID_YES:
            imported_any = self._prompt_onboarding_settings_import() or imported_any
        elif settings_choice != wx.ID_NO:
            raise _OnboardingCancelled

        keys_dialog = wx.MessageDialog(
            self.main_window,
            "Import an encrypted API key bundle now?\n\n"
            "Choose Configure myself, or press Escape, to close this wizard.",
            "Import API keys",
            wx.YES_NO | wx.CANCEL | wx.ICON_INFORMATION,
        )
        keys_dialog.SetYesNoCancelLabels("Import API keys", "Skip API keys", "Configure myself")
        keys_choice = keys_dialog.ShowModal()
        keys_dialog.Destroy()
        if keys_choice == wx.ID_YES:
            imported_any = self._prompt_onboarding_api_key_import() or imported_any
        elif keys_choice != wx.ID_NO:
            raise _OnboardingCancelled

        return imported_any

    def _maybe_show_first_start_onboarding(self) -> None:
        """Show a minimal onboarding wizard once on fresh setup."""
        if not self._should_show_first_start_onboarding():
            self._run_deferred_startup_update_check()
            return

        total_steps = 4 if self._portable_mode else 3

        step1 = wx.MessageDialog(
            self.main_window,
            f"Welcome to AccessiWeather.\n\n"
            f"Step 1 of {total_steps}: Add your first location now?\n\n"
            "If you already have settings or API keys to bring over, choose Import existing.\n\n"
            "Choose Configure myself, or press Escape, to close this wizard and set things up later.",
            "Getting started",
            wx.YES_NO | wx.CANCEL | wx.ICON_INFORMATION,
        )
        step1.SetYesNoCancelLabels("Add location", "Import existing", "Configure myself")
        step1_result = step1.ShowModal()
        step1.Destroy()

        if step1_result == wx.ID_YES and self.main_window:
            self.main_window.on_add_location()
        elif step1_result == wx.ID_NO:
            try:
                imported = self._maybe_run_onboarding_import_flow()
            except _OnboardingCancelled:
                self._skip_first_start_onboarding()
                return
            if imported and self.config_manager.has_locations():
                self._finish_first_start_onboarding()
                return
        else:
            self._skip_first_start_onboarding()
            return

        from .config.secure_storage import is_keyring_available

        if not self._portable_mode and not is_keyring_available():
            _warn_dlg = wx.MessageDialog(
                self.main_window,
                "Your system keyring is not available.\n\n"
                "API keys you enter cannot be stored securely on this machine. "
                "On Linux, installing a keyring backend (e.g. gnome-keyring or KWallet) "
                "is recommended.\n\n"
                "You can still enter keys now; if portable mode is enabled with an encrypted "
                "bundle they will be saved there — otherwise they will be lost on exit.",
                "Secure storage unavailable",
                wx.OK | wx.ICON_WARNING,
            )
            _warn_dlg.ShowModal()
            _warn_dlg.Destroy()

        # Collect keys entered in later steps — in portable mode we write directly to
        # the bundle rather than going through keyring (which isn't used in portable).
        _wizard_keys: dict[str, str] = {}

        if not self._has_saved_api_key("openrouter_api_key"):
            try:
                openrouter_key = self._prompt_optional_secret_with_link(
                    "OpenRouter API key (optional)",
                    f"Step 2 of {total_steps}: Enter your OpenRouter API key now, or leave blank to skip.",
                    "https://openrouter.ai/keys",
                    "Get OpenRouter API key",
                )
            except _OnboardingCancelled:
                self._skip_first_start_onboarding()
                return
            if openrouter_key is not None and openrouter_key:
                if not self._portable_mode:
                    self.config_manager.update_settings(openrouter_api_key=openrouter_key)
                    self._maybe_offer_test_key_now("OpenRouter API key")
                else:
                    _wizard_keys["openrouter_api_key"] = openrouter_key

        if not self._has_saved_api_key("pirate_weather_api_key"):
            try:
                pirate_weather_key = self._prompt_optional_secret_with_link(
                    "Pirate Weather provider key (optional)",
                    f"Step 3 of {total_steps}: Enter your Pirate Weather provider key now, or leave blank to skip.",
                    "https://pirateweather.net/",
                    "Get Pirate Weather provider key",
                )
            except _OnboardingCancelled:
                self._skip_first_start_onboarding()
                return
            if pirate_weather_key is not None and pirate_weather_key:
                if not self._portable_mode:
                    self.config_manager.update_settings(pirate_weather_api_key=pirate_weather_key)
                    self._maybe_offer_test_key_now("Pirate Weather provider key")
                else:
                    _wizard_keys["pirate_weather_api_key"] = pirate_weather_key

        if self._portable_mode and _wizard_keys:
            # Keys were entered — prompt for passphrase and write bundle directly.
            try:
                passphrase = self._prompt_optional_secret(
                    f"Step {total_steps} of {total_steps}: Secure your API keys",
                    "Enter a passphrase to encrypt your API keys into a portable bundle.\n"
                    "This bundle travels with the app so your keys work on any machine.\n\n"
                    "Leave blank to skip (keys will not be saved).",
                )
            except _OnboardingCancelled:
                self._skip_first_start_onboarding()
                return
            if passphrase:
                try:
                    # Set keys in-memory first so export_encrypted_api_keys can read them.
                    for k, v in _wizard_keys.items():
                        setattr(self.config_manager.get_config().settings, k, v)
                    bundle_path = self.config_manager.get_portable_api_key_bundle_path()
                    success = self.config_manager.export_encrypted_api_keys(bundle_path, passphrase)
                    if success:
                        self._portable_keys_imported_this_session = True
                        # Cache passphrase so next launch is silent.
                        from .config.secure_storage import SecureStorage

                        SecureStorage.set_password(
                            self._PORTABLE_PASSPHRASE_KEYRING_KEY, passphrase
                        )
                        wx.MessageBox(
                            "API keys saved to encrypted bundle. They are now active.",
                            "Keys saved",
                            wx.OK | wx.ICON_INFORMATION,
                        )
                    else:
                        wx.MessageBox(
                            "Failed to save the key bundle. Keys will not persist after this session.",
                            "Bundle write failed",
                            wx.OK | wx.ICON_WARNING,
                        )
                except Exception as exc:
                    logger.error("Failed to write portable bundle: %s", exc)
                    wx.MessageBox(
                        "Failed to save the key bundle. Keys will not persist after this session.",
                        "Bundle write failed",
                        wx.OK | wx.ICON_WARNING,
                    )
            else:
                wx.MessageBox(
                    "No passphrase entered — API keys will not be saved.",
                    "Keys not saved",
                    wx.OK | wx.ICON_WARNING,
                )
        # No keys entered — skip step 4 entirely, nothing to bundle.

        self._finish_first_start_onboarding()

    def _show_force_start_dialog(self) -> bool:
        """
        Show a dialog offering to force start when another instance appears to be running.

        Returns
        -------
            bool: True if user chose to force start and lock was acquired, False to exit

        """
        dialog = wx.MessageDialog(
            None,
            "AccessiWeather appears to be already running, or a previous session "
            "didn't close properly.\n\n"
            "Would you like to force start? This will close any existing instance.",
            "AccessiWeather - Already Running",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )
        dialog.SetYesNoLabels("Force Start", "Cancel")

        result = dialog.ShowModal()
        dialog.Destroy()

        if result == wx.ID_YES:
            logger.info("User chose to force start")
            if self.single_instance_manager.force_remove_lock():
                if self.single_instance_manager.try_acquire_lock():
                    logger.info("Successfully acquired lock after force removal")
                    return True
                logger.error("Failed to acquire lock even after force removal")
                wx.MessageBox(
                    "Failed to start AccessiWeather.\n\n"
                    "Please try closing any running instances and try again.",
                    "Startup Error",
                    wx.OK | wx.ICON_ERROR,
                )
            else:
                wx.MessageBox(
                    "Failed to remove the lock file.\n\n"
                    "Please try manually deleting the lock file or restarting your computer.",
                    "Startup Error",
                    wx.OK | wx.ICON_ERROR,
                )
            return False
        logger.info("User cancelled force start")
        return False
