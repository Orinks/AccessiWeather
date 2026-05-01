"""SettingsDialogHandlersMixin helpers for the settings dialog."""

from __future__ import annotations

import logging

import wx

logger = logging.getLogger("accessiweather.ui.dialogs.settings_dialog")


class SettingsDialogHandlersMixin:
    def _on_configure_event_sounds(self, event):
        """Open the event-sounds modal and persist accepted in-memory state."""
        updated_states = self._run_event_sounds_dialog()
        if updated_states is None:
            return
        self._event_sound_states = {
            event_key: updated_states.get(event_key, True)
            for event_key, _label in self._get_mutable_sound_events()
        }
        self._audio_tab._refresh_event_sound_summary()

    def _on_configure_source_settings(self, event) -> None:
        """Open the source settings modal and persist accepted in-memory state."""
        updated = self._run_source_settings_dialog()
        if updated is None:
            return
        self._source_settings_states = updated
        self._refresh_source_settings_summary()

    def _on_data_source_changed(self, event):
        """Update API key section visibility when data source changes."""
        self._update_api_key_visibility()

    def _update_api_key_visibility(self):
        """Show/hide API key sections based on selected data source."""
        selection = self._controls["data_source"].GetSelection()
        show_pw = selection in (0, 3)
        self._pw_config_sizer.ShowItems(show_pw)
        self._update_auto_source_key_state()
        parent = self._controls["data_source"].GetParent()
        parent.Layout()
        parent.FitInside()

    def _update_auto_source_key_state(self):
        """Keep the source settings summary in sync with API-key edits."""
        self._refresh_source_settings_summary()

    def _on_get_pw_api_key(self, event):
        """Open Pirate Weather signup page."""
        from . import settings_dialog as base_module

        base_module.webbrowser.open("https://pirate-weather.apiable.io/signup")

    def _on_validate_pw_api_key(self, event):
        """Validate Pirate Weather API key."""
        key = self._controls["pw_key"].GetValue()
        if not key:
            wx.MessageBox("Please enter an API key first.", "Validation", wx.OK | wx.ICON_WARNING)
            return

        wx.BeginBusyCursor()
        try:
            import asyncio

            from ...models import Location
            from ...pirate_weather_client import PirateWeatherApiError, PirateWeatherClient

            test_location = Location(name="Test", latitude=40.7128, longitude=-74.0060)
            client = PirateWeatherClient(api_key=key)

            async def test_key():
                try:
                    await client.get_current_conditions(test_location)
                    return True, None
                except PirateWeatherApiError as e:
                    if e.status_code == 401:
                        return False, "Invalid API key"
                    if e.status_code == 429:
                        return False, "Rate limit exceeded — but key appears valid"
                    return False, str(e)
                except Exception as e:
                    return False, str(e)

            loop = asyncio.new_event_loop()
            try:
                valid, error = loop.run_until_complete(test_key())
            finally:
                loop.close()

            if valid:
                wx.MessageBox(
                    "Pirate Weather API key is valid!",
                    "Validation Successful",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    f"Pirate Weather API key validation failed: {error}",
                    "Validation Failed",
                    wx.OK | wx.ICON_ERROR,
                )
        finally:
            wx.EndBusyCursor()

    def _on_validate_openrouter_key(self, event):
        """Validate OpenRouter API key."""
        key = self._controls["openrouter_key"].GetValue()
        if not key:
            wx.MessageBox("Please enter an API key first.", "Validation", wx.OK | wx.ICON_WARNING)
            return

        wx.BeginBusyCursor()
        try:
            import asyncio

            from ...ai_explainer import AIExplainer

            explainer = AIExplainer()

            loop = asyncio.new_event_loop()
            try:
                valid = loop.run_until_complete(explainer.validate_api_key(key))
            finally:
                loop.close()

            if valid:
                wx.MessageBox(
                    "API key is valid!",
                    "Validation Successful",
                    wx.OK | wx.ICON_INFORMATION,
                )
            else:
                wx.MessageBox(
                    "API key validation failed. Please check your key and try again.",
                    "Validation Failed",
                    wx.OK | wx.ICON_ERROR,
                )
        except Exception as e:
            logger.error(f"Error validating OpenRouter API key: {e}")
            wx.MessageBox(
                f"Error during validation: {e}",
                "Validation Error",
                wx.OK | wx.ICON_ERROR,
            )
        finally:
            wx.EndBusyCursor()

    def _on_browse_models(self, event):
        """Browse available AI models."""
        from .model_browser_dialog import show_model_browser_dialog

        api_key = self._controls["openrouter_key"].GetValue()
        selected_model_id = show_model_browser_dialog(self, api_key=api_key or None)

        if selected_model_id:
            if selected_model_id == "openrouter/free":
                self._controls["ai_model"].SetSelection(0)
            elif selected_model_id == "meta-llama/llama-3.3-70b-instruct:free":
                self._controls["ai_model"].SetSelection(1)
            elif selected_model_id == "openrouter/auto":
                self._controls["ai_model"].SetSelection(2)
            else:
                model_display = f"Selected: {selected_model_id.split('/')[-1]}"
                if self._controls["ai_model"].GetCount() > 3:
                    self._controls["ai_model"].SetString(3, model_display)
                else:
                    self._controls["ai_model"].Append(model_display)
                self._controls["ai_model"].SetSelection(3)
                self._selected_specific_model = selected_model_id

    def _on_reset_prompt(self, event):
        """Reset custom prompt to default."""
        self._controls["custom_prompt"].SetValue("")

    def _on_test_sound(self, event):
        """Play a test sound from the selected pack."""
        try:
            from ...notifications.sound_player import play_sample_sound

            pack_idx = self._controls["sound_pack"].GetSelection()
            if hasattr(self, "_sound_pack_ids") and pack_idx < len(self._sound_pack_ids):
                pack_id = self._sound_pack_ids[pack_idx]
            else:
                pack_id = "default"
            play_sample_sound(pack_id)
        except Exception as e:
            logger.error(f"Failed to play test sound: {e}")
            wx.MessageBox(f"Failed to play test sound: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_manage_soundpacks(self, event):
        """Open sound pack management."""
        try:
            from .soundpack_manager_dialog import show_soundpack_manager_dialog

            show_soundpack_manager_dialog(self, self.app)
            self._refresh_sound_pack_list()
        except Exception as e:
            logger.error(f"Failed to open sound pack manager: {e}")
            wx.MessageBox(
                f"Failed to open sound pack manager: {e}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def _refresh_sound_pack_list(self):
        """Refresh the sound pack dropdown after changes."""
        try:
            from ...notifications.sound_player import get_available_sound_packs

            current_idx = self._controls["sound_pack"].GetSelection()
            current_id = (
                self._sound_pack_ids[current_idx]
                if current_idx < len(self._sound_pack_ids)
                else "default"
            )

            packs = get_available_sound_packs()
            self._sound_pack_ids = list(packs.keys())
            pack_names = [packs[pid].get("name", pid) for pid in self._sound_pack_ids]

            self._controls["sound_pack"].Clear()
            for name in pack_names:
                self._controls["sound_pack"].Append(name)

            try:
                new_idx = self._sound_pack_ids.index(current_id)
                self._controls["sound_pack"].SetSelection(new_idx)
            except ValueError:
                if self._sound_pack_ids:
                    self._controls["sound_pack"].SetSelection(0)
        except Exception as e:
            logger.warning(f"Failed to refresh sound pack list: {e}")

    def _on_check_updates(self, event):
        """Check for updates using the UpdateService."""
        from . import settings_dialog as base_module

        if not base_module.is_compiled_runtime():
            wx.MessageBox(
                "Update checking is only available in installed builds.\n"
                "You're running from source — use git pull to update.",
                "Running from Source",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        self._controls["update_status"].SetLabel("Checking for updates...")

        def do_update_check():
            import asyncio

            from ...services.simple_update import (
                UpdateService,
                parse_nightly_date,
            )

            try:
                current_version = getattr(self.app, "version", "0.0.0")
                build_tag = getattr(self.app, "build_tag", None)
                current_nightly_date = parse_nightly_date(build_tag) if build_tag else None
                if current_nightly_date:
                    current_version = current_nightly_date

                channel_idx = self._controls["update_channel"].GetSelection()
                channel = "nightly" if channel_idx == 1 else "stable"

                async def check():
                    service = UpdateService("AccessiWeather")
                    try:
                        return await service.check_for_updates(
                            current_version=current_version,
                            current_nightly_date=current_nightly_date,
                            channel=channel,
                        )
                    finally:
                        await service.close()

                update_info = asyncio.run(check())

                if update_info is None:
                    if current_nightly_date and channel == "stable":
                        status_msg = (
                            f"You're on nightly ({current_nightly_date}).\n"
                            "No newer stable release available."
                        )
                    elif current_nightly_date:
                        status_msg = f"You're on the latest nightly ({current_nightly_date})."
                    else:
                        status_msg = f"You're up to date ({current_version})."

                    wx.CallAfter(self._controls["update_status"].SetLabel, status_msg)
                    wx.CallAfter(
                        wx.MessageBox,
                        status_msg,
                        "No Updates Available",
                        wx.OK | wx.ICON_INFORMATION,
                    )
                    return

                wx.CallAfter(
                    self._controls["update_status"].SetLabel,
                    f"Update available: {update_info.version}",
                )

                def prompt_download():
                    from .update_dialog import UpdateAvailableDialog

                    channel_label = "Nightly" if update_info.is_nightly else "Stable"
                    dlg = UpdateAvailableDialog(
                        parent=self,
                        current_version=current_version,
                        new_version=update_info.version,
                        channel_label=channel_label,
                        release_notes=update_info.release_notes,
                    )
                    result = dlg.ShowModal()
                    dlg.Destroy()
                    if result == wx.ID_OK:
                        self.app._download_and_apply_update(update_info)

                wx.CallAfter(prompt_download)

            except Exception as e:
                logger.error(f"Error checking for updates: {e}")
                wx.CallAfter(
                    self._controls["update_status"].SetLabel,
                    "Could not check for updates",
                )
                wx.CallAfter(
                    wx.MessageBox,
                    f"Failed to check for updates:\n{e}",
                    "Update Check Failed",
                    wx.OK | wx.ICON_ERROR,
                )

        import threading

        thread = threading.Thread(target=do_update_check, daemon=True)
        thread.start()

    def _on_reset_defaults(self, event):
        """Reset settings to defaults."""
        result = wx.MessageBox(
            "Are you sure you want to reset all settings to defaults?\n\n"
            "Your saved locations will be preserved.",
            "Confirm Reset",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if result == wx.YES:
            try:
                if self.config_manager.reset_to_defaults():
                    self._load_settings()
                    wx.MessageBox(
                        "Settings have been reset to defaults.\n\n"
                        "Your locations have been preserved.",
                        "Reset Complete",
                        wx.OK | wx.ICON_INFORMATION,
                    )
                else:
                    wx.MessageBox(
                        "Failed to reset settings. Please try again.",
                        "Reset Failed",
                        wx.OK | wx.ICON_ERROR,
                    )
            except Exception as e:
                logger.error(f"Error resetting settings: {e}")
                wx.MessageBox(
                    f"Error resetting settings: {e}",
                    "Reset Error",
                    wx.OK | wx.ICON_ERROR,
                )

    def _on_full_reset(self, event):
        """Full data reset."""
        result = wx.MessageBox(
            "Are you sure you want to reset ALL application data?\n\n"
            "This will delete:\n"
            "• All settings\n"
            "• All saved locations\n"
            "• All caches\n"
            "• Alert history\n\n"
            "This action cannot be undone!",
            "Confirm Full Reset",
            wx.YES_NO | wx.ICON_WARNING,
        )
        if result == wx.YES:
            result2 = wx.MessageBox(
                "This is your last chance to cancel.\n\n"
                "Are you absolutely sure you want to delete all data?",
                "Final Confirmation",
                wx.YES_NO | wx.ICON_EXCLAMATION,
            )
            if result2 == wx.YES:
                try:
                    if self.config_manager.reset_all_data():
                        self._load_settings()
                        wx.MessageBox(
                            "All application data has been reset.\n\n"
                            "The application will now use default settings.",
                            "Reset Complete",
                            wx.OK | wx.ICON_INFORMATION,
                        )
                    else:
                        wx.MessageBox(
                            "Failed to reset application data. Please try again.",
                            "Reset Failed",
                            wx.OK | wx.ICON_ERROR,
                        )
                except Exception as e:
                    logger.error(f"Error during full reset: {e}")
                    wx.MessageBox(
                        f"Error during reset: {e}",
                        "Reset Error",
                        wx.OK | wx.ICON_ERROR,
                    )

    def _on_open_config_dir(self, event):
        """Open configuration directory."""
        import os
        import subprocess

        config_dir = str(self.config_manager.config_dir)
        if os.path.exists(config_dir):
            subprocess.Popen(["explorer", config_dir])
        else:
            wx.MessageBox(
                f"Config directory not found: {config_dir}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )

    def _on_alert_advanced(self, event):
        """Open the advanced alert timing settings dialog."""
        from . import settings_dialog as base_module

        dlg = base_module.AlertAdvancedSettingsDialog(self, self._controls)
        dlg.ShowModal()
        dlg.Destroy()

    def _on_ok(self, event):
        """Handle OK button press."""
        if self._save_settings():
            self.EndModal(wx.ID_OK)
        else:
            wx.MessageBox("Failed to save settings.", "Error", wx.OK | wx.ICON_ERROR)

    def _on_minimize_tray_changed(self, event):
        """Handle minimize to tray checkbox state change."""
        minimize_to_tray_enabled = self._controls["minimize_tray"].GetValue()
        self._update_minimize_on_startup_state(minimize_to_tray_enabled)
        event.Skip()

    def _on_taskbar_icon_text_enabled_changed(self, event):
        """Enable/disable taskbar text controls when main toggle changes."""
        taskbar_text_enabled = self._controls["taskbar_icon_text_enabled"].GetValue()
        self._update_taskbar_text_controls_state(taskbar_text_enabled)
        event.Skip()

    def _update_minimize_on_startup_state(self, minimize_to_tray_enabled: bool):
        """Update the enabled state of minimize_on_startup based on minimize_to_tray."""
        self._controls["minimize_on_startup"].Enable(minimize_to_tray_enabled)
        if not minimize_to_tray_enabled:
            self._controls["minimize_on_startup"].SetValue(False)

    def _update_taskbar_text_controls_state(self, taskbar_text_enabled: bool):
        """Enable/disable dependent taskbar text controls."""
        self._controls["taskbar_icon_dynamic_enabled"].Enable(taskbar_text_enabled)
        self._controls["taskbar_icon_text_format_dialog"].Enable(taskbar_text_enabled)

    def _on_edit_taskbar_text_format(self, event):
        """Open the focused tray text format dialog."""
        from ...taskbar_icon_updater import TaskbarIconUpdater
        from .tray_text_format_dialog import TrayTextFormatDialog

        current_weather = getattr(self.app, "current_weather_data", None)
        current_location = None
        if current_weather and getattr(current_weather, "location", None):
            current_location = getattr(current_weather.location, "name", None)

        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=self._controls["taskbar_icon_dynamic_enabled"].GetValue(),
            format_string=self._controls["taskbar_icon_text_format"].GetValue(),
            temperature_unit=self._get_selected_temperature_unit(),
        )

        dialog = TrayTextFormatDialog(
            self,
            updater=updater,
            weather_data=current_weather,
            location_name=current_location,
            initial_format=self._controls["taskbar_icon_text_format"].GetValue(),
        )
        if dialog.ShowModal() == wx.ID_OK:
            self._controls["taskbar_icon_text_format"].SetValue(dialog.get_format_string())
        dialog.Destroy()
        event.Skip()

    def _get_selected_temperature_unit(self) -> str:
        """Return the temperature unit selection currently shown in the dialog."""
        if hasattr(self, "_display_tab"):
            return self._display_tab.get_selected_temperature_unit()
        temp_values = ["auto", "f", "c", "both"]
        selection = self._controls["temp_unit"].GetSelection()
        if selection < 0 or selection >= len(temp_values):
            return "both"
        return temp_values[selection]

    def _get_ai_model_preference(self) -> str:
        """Get the AI model preference based on UI selection."""
        selection = self._controls["ai_model"].GetSelection()
        if selection == 0:
            return "openrouter/free"
        if selection == 1:
            return "meta-llama/llama-3.3-70b-instruct:free"
        if selection == 2:
            return "auto"
        if selection == 3 and self._selected_specific_model:
            return self._selected_specific_model
        return "openrouter/free"

    def _on_open_soundpacks_dir(self, event):
        """Open sound packs directory."""
        import subprocess

        from ...soundpack_paths import get_soundpacks_dir

        soundpacks_dir = get_soundpacks_dir()
        if soundpacks_dir.exists():
            subprocess.Popen(["explorer", str(soundpacks_dir)])
        else:
            wx.MessageBox(
                f"Sound packs directory not found: {soundpacks_dir}",
                "Error",
                wx.OK | wx.ICON_ERROR,
            )
