"""Settings dialog for AccessiWeather Toga application.

This module provides a comprehensive settings dialog with tabbed interface
matching the functionality of the wxPython version.
"""

import asyncio
import contextlib
import logging

import toga
from toga.style import Pack
from travertino.constants import COLUMN, ROW

from . import settings_handlers, settings_operations, settings_tabs

logger = logging.getLogger(__name__)


class SettingsDialog:
    """Settings dialog with tabbed interface for configuration options."""

    def __init__(self, app: toga.App, config_manager, update_service=None):
        """Initialize the settings dialog."""
        self.app = app
        self.config_manager = config_manager
        self.update_service = update_service  # Optional update service from main app
        self.window = None  # Will be created fresh each time dialog is shown
        self.future = None  # Will be created fresh each time dialog is shown

        # Current settings (working copy)
        self.current_settings = None

        # UI components
        self.option_container = None
        self.general_tab = None
        self.advanced_tab = None
        self.updates_tab = None

        # General tab controls
        self.data_source_selection = None
        self.update_interval_input = None
        self.show_detailed_forecast_switch = None
        self.enable_alerts_switch = None
        self.debug_mode_switch = None

        # Visual Crossing API controls
        self.visual_crossing_config_box = None
        self.visual_crossing_api_key_input = None
        self.get_api_key_button = None
        self.validate_api_key_button = None

        # Advanced tab controls
        self.minimize_to_tray_switch = None
        self.startup_enabled_switch = None

        # Updates tab controls
        self.auto_update_switch = None
        self.update_channel_selection = None
        self.update_check_interval_input = None
        self.check_updates_button = None
        self.update_status_label = None
        self.last_check_label = None

        # Sound settings controls (Audio tab)
        self.sound_enabled_switch = None
        self.sound_pack_selection = None
        self.manage_soundpacks_button = None

        # General tab controls (moved from Display)
        self.temperature_unit_selection = None
        self.ok_button = None
        # Environmental controls
        self.air_quality_threshold_input = None

    def __await__(self):
        """Make the dialog awaitable for modal behavior."""
        if self.future is None:
            raise RuntimeError("Dialog future not initialized. Call show_and_prepare() first.")
        return self.future.__await__()

    def show_and_prepare(self):
        """Prepare and show the settings dialog."""
        logger.info("Showing settings dialog")

        try:
            # Create a fresh future for this dialog session
            self.future = self.app.loop.create_future()

            # Create a fresh window instance
            self.window = toga.Window(
                title="AccessiWeather Settings",
                size=(600, 500),
                resizable=True,
                minimizable=False,
                closable=False,  # Prevent closing via X button to enforce modal behavior
            )

            # Ensure startup configuration reflects actual system state before loading
            with contextlib.suppress(Exception):
                self.config_manager.sync_startup_setting()

            # Load current settings
            self.current_settings = self.config_manager.get_settings()
            logger.debug(f"Loaded settings: {self.current_settings}")

            # Create dialog content
            self._create_dialog_content()

            # Show the dialog
            self.window.show()

            # Set initial focus to the first interactive control for accessibility
            self._set_initial_focus()

        except Exception as e:
            logger.error(f"Failed to show settings dialog: {e}", exc_info=True)
            if self.future and not self.future.done():
                self.future.set_exception(e)

    def _create_dialog_content(self):
        """Create the settings dialog content."""
        # Main container
        main_box = toga.Box(style=Pack(direction=COLUMN, margin=10))

        # Create tabbed interface
        self.option_container = toga.OptionContainer(style=Pack(flex=1))

        # Create tabs in new order
        settings_tabs.create_general_tab(self)
        settings_tabs.create_data_sources_tab(self)
        settings_tabs.create_audio_tab(self)
        settings_tabs.create_updates_tab(self)
        settings_tabs.create_advanced_tab(self)

        main_box.add(self.option_container)

        # Ensure General tab is selected initially for predictable UX
        try:
            if self.general_tab is not None:
                self.option_container.current_tab = ("General", self.general_tab)
        except Exception:
            # Fallback to first tab index if tuple assignment isn't supported
            with contextlib.suppress(Exception):
                self.option_container.current_tab = 0

        # Button row
        button_box = toga.Box(style=Pack(direction=ROW, margin_top=10))

        # Add flexible space to push buttons to the right
        button_box.add(toga.Box(style=Pack(flex=1)))

        # Cancel button
        cancel_button = toga.Button(
            "Cancel", on_press=self._on_cancel, style=Pack(margin_right=10), id="cancel_button"
        )
        button_box.add(cancel_button)

        # OK button
        ok_button = toga.Button(
            "OK", on_press=self._on_ok, style=Pack(margin_right=0), id="ok_button"
        )
        button_box.add(ok_button)
        self.ok_button = ok_button

        main_box.add(button_box)

        # Set window content
        self.window.content = main_box

        # Initialize update service and platform info
        try:
            settings_operations.initialize_update_info(self)
        except Exception as e:
            logger.error(f"Failed to initialize update info: {e}")

    def _set_initial_focus(self):
        """Set initial focus to the first interactive control for accessibility."""
        try:
            # Focus Temperature Unit first (now first control on General tab)
            if self.temperature_unit_selection:
                # Ensure General tab is selected before focusing
                with contextlib.suppress(Exception):
                    self.option_container.current_tab = ("General", self.general_tab)
                with contextlib.suppress(Exception):
                    self.option_container.current_tab = 0
                self.temperature_unit_selection.focus()
                logger.debug("Set initial focus to temperature unit selection")
            elif self.data_source_selection:
                # Fallback to data source selection
                with contextlib.suppress(Exception):
                    self.option_container.current_tab = ("Data Sources", self.data_sources_tab)
                self.data_source_selection.focus()
                logger.debug("Set initial focus to data source selection (fallback)")
            else:
                logger.warning("No primary control available for focus")
        except Exception as e:
            logger.warning(f"Failed to set initial focus: {e}")
            # Fallback: try to focus the option container itself
            try:
                if self.option_container:
                    self.option_container.focus()
                    logger.debug("Set fallback focus to option container")
            except Exception as fallback_error:
                logger.warning(f"Fallback focus also failed: {fallback_error}")

    def _ensure_dialog_focus(self):
        """Ensure focus remains within the dialog window."""
        try:
            if self.window and hasattr(self.window, "focus"):
                self.window.focus()
                logger.debug("Restored focus to settings dialog window")
        except Exception as e:
            logger.warning(f"Failed to restore dialog focus: {e}")

    def _return_focus_to_trigger(self):
        """Return focus to the element that triggered the dialog."""
        try:
            # In Toga, we can't directly control focus return to menu items,
            # but we can ensure the main window gets focus
            if self.app.main_window:
                self.app.main_window.focus()
                logger.debug("Returned focus to main window")
        except Exception as e:
            logger.warning(f"Failed to return focus: {e}")

    async def _show_dialog_error(self, title, message):
        """Show error dialog relative to settings dialog to prevent focus loss."""
        try:
            # Try to use the dialog window for error display if possible
            if self.window and hasattr(self.window, "error_dialog"):
                await self.window.error_dialog(title, message)
            else:
                # Fallback to main window but restore focus afterward
                await self.app.main_window.error_dialog(title, message)
                # Restore focus to dialog after error dialog closes
                self._ensure_dialog_focus()
        except Exception as e:
            logger.error(f"Failed to show error dialog: {e}")
            # Last resort: just log the error
            logger.error(f"{title}: {message}")

    async def _on_ok(self, widget):
        """Handle OK button press - save settings and close dialog."""
        logger.info("Settings dialog OK button pressed")

        try:
            # Ensure focus stays in dialog during processing
            self._ensure_dialog_focus()

            # Collect settings from UI
            new_settings = settings_handlers.collect_settings_from_ui(self)

            # Capture current startup flag before persisting changes
            old_startup_enabled = self.config_manager.get_settings().startup_enabled

            # Update configuration
            success = self.config_manager.update_settings(**new_settings.to_dict())

            # Handle startup setting changes
            if success:
                try:
                    new_startup_enabled = new_settings.startup_enabled

                    if old_startup_enabled != new_startup_enabled:
                        logger.info(
                            f"Startup setting changed: {old_startup_enabled} -> {new_startup_enabled}"
                        )

                        loop = asyncio.get_running_loop()
                        startup_method = (
                            self.config_manager.enable_startup
                            if new_startup_enabled
                            else self.config_manager.disable_startup
                        )

                        # Prevent duplicate submissions while startup toggles
                        ok_button = getattr(self, "ok_button", None)
                        if ok_button is not None:
                            ok_button.enabled = False

                        try:
                            startup_success, startup_message = await loop.run_in_executor(
                                None, startup_method
                            )
                        finally:
                            if ok_button is not None:
                                ok_button.enabled = True

                        if not startup_success:
                            logger.warning(f"Startup management failed: {startup_message}")
                            # Show warning but don't prevent settings save
                            await self._show_dialog_error(
                                "Startup Setting Warning",
                                "Settings saved successfully, but startup setting could not be applied:\n\n"
                                f"{startup_message}\n\nYou may need to check your system permissions.",
                            )
                            with contextlib.suppress(Exception):
                                self.config_manager.sync_startup_setting()
                        else:
                            logger.info(f"Startup management successful: {startup_message}")

                except Exception as e:
                    logger.error(f"Error handling startup setting change: {e}")
                    # Show warning but don't prevent settings save
                    await self._show_dialog_error(
                        "Startup Setting Error",
                        "Settings saved successfully, but there was an error managing the startup setting:\n\n"
                        f"{str(e)}\n\nYou may need to check your system permissions.",
                    )
                    with contextlib.suppress(Exception):
                        self.config_manager.sync_startup_setting()

            if success:
                logger.info("Settings saved successfully")
                # Set result and close dialog
                if self.future and not self.future.done():
                    self.future.set_result(True)
                if self.window:
                    self.window.close()
                    self.window = None  # Clear reference to help with cleanup
                # No confirmation dialog - let focus return directly to main window
            else:
                logger.error("Failed to save settings")
                # Use dialog-relative error instead of main window error
                await self._show_dialog_error("Settings Error", "Failed to save settings.")

        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            # Don't close dialog on error, let user try again or cancel
            # Use dialog-relative error instead of main window error
            await self._show_dialog_error("Settings Error", f"Error saving settings: {e}")

    async def _on_cancel(self, widget):
        """Handle Cancel button press - close dialog without saving."""
        logger.info("Settings dialog cancelled")
        if self.future and not self.future.done():
            self.future.set_result(False)
        if self.window:
            self.window.close()
            self.window = None  # Clear reference to help with cleanup

    def _load_sound_packs(self):
        """Compatibility wrapper that delegates to the tab helpers."""
        settings_tabs.load_sound_packs(self)

    def _on_sound_enabled_changed(self, widget):
        enabled = getattr(widget, "value", True)
        sel = getattr(self, "sound_pack_selection", None)
        if sel is not None:
            sel.enabled = enabled

    async def _on_manage_soundpacks(self, widget):
        """Open the sound pack manager dialog.

        Note: The Sound Pack Manager is for importing, editing, and managing packs.
        The current pack selection is controlled by the selection widget in this Settings dialog.
        """
        try:
            # Ensure focus stays in dialog before opening sub-dialog
            self._ensure_dialog_focus()

            from .soundpack_manager import SoundPackManagerDialog

            # Preserve the currently selected pack from settings (authoritative)
            current_pack_id = getattr(self.current_settings, "sound_pack", "default")

            # Open the manager focused on the current pack; do not treat its selection as app setting
            manager = SoundPackManagerDialog(self.app, current_pack_id)
            await manager.show()

            # After the manager closes, restore focus to settings dialog and refresh pack list
            self._ensure_dialog_focus()
            settings_tabs.load_sound_packs(self)
            self.sound_pack_selection.items = self.sound_pack_options

            # Keep showing the current pack if it still exists; otherwise fall back to first option
            for display_name, pack_id in self.sound_pack_map.items():
                if pack_id == current_pack_id:
                    self.sound_pack_selection.value = display_name
                    break
            else:
                if self.sound_pack_options:
                    self.sound_pack_selection.value = self.sound_pack_options[0]

        except Exception as e:
            logger.error(f"Failed to open sound pack manager: {e}")
            # Use dialog-relative error instead of main window error
            await self._show_dialog_error(
                "Sound Pack Manager Error", f"Failed to open sound pack manager: {e}"
            )

    def _on_data_source_changed(self, widget):
        """Handle data source selection change to show/hide Visual Crossing config."""
        self._update_visual_crossing_visibility()

    def _update_visual_crossing_visibility(self):
        """Update visibility of Visual Crossing configuration based on data source selection."""
        if not self.data_source_selection or not self.visual_crossing_config_box:
            return

        selected_display = str(self.data_source_selection.value)
        # Map display back to internal value using mapping; default to 'auto'
        selected_internal = self.data_source_display_to_value.get(selected_display, "auto")
        show_visual_crossing = selected_internal == "visualcrossing"

        # Use a stable, known parent to manage add/remove so it can be re-added reliably
        container = getattr(self, "data_sources_tab", None)
        if not container:
            return

        if container:
            if show_visual_crossing:
                if self.visual_crossing_config_box not in container.children:
                    # Insert right after the data source selection control
                    try:
                        idx = container.children.index(self.data_source_selection)
                        container.insert(idx + 1, self.visual_crossing_config_box)
                    except ValueError:
                        container.add(self.visual_crossing_config_box)
            else:
                if self.visual_crossing_config_box in container.children:
                    container.remove(self.visual_crossing_config_box)

    def _on_update_channel_changed(self, widget):
        """Handle update channel selection change."""
        self._update_channel_description()

    # (Update method change handler removed)

    def _update_channel_description(self):
        """Update the channel description based on current selection."""
        if not hasattr(self, "channel_description_label") or not self.channel_description_label:
            return

        channel_value = str(self.update_channel_selection.value)

        if "Stable" in channel_value:
            description = (
                "🔒 Stable releases only. Production-ready versions. Recommended for most users."
            )
        elif "Beta" in channel_value:
            description = "🧪 Pre-release versions for testing. Includes new features before stable release. May contain bugs."
        elif "Development" in channel_value:
            description = "🛠️ Latest development builds. Cutting-edge features but may be unstable. For developers and early testers."
        else:
            description = ""

        self.channel_description_label.text = description

    # (Update method description removed)

    def _apply_settings_to_ui(self):
        """Compatibility wrapper for legacy callers."""
        settings_handlers.apply_settings_to_ui(self)

    def _collect_settings_from_ui(self):
        """Compatibility wrapper that delegates to the handlers module."""
        return settings_handlers.collect_settings_from_ui(self)

    def _map_channel_display_to_value(self, display: str) -> str:
        """Compatibility wrapper that delegates to the handlers module."""
        return settings_handlers.map_channel_display_to_value(display)

    async def _on_reset_to_defaults(self, widget):
        await settings_operations.reset_to_defaults(self)

    async def _on_full_reset(self, widget):
        await settings_operations.full_data_reset(self)

    async def _on_open_config_dir(self, widget):
        await settings_operations.open_config_directory(self)

    async def _on_get_visual_crossing_api_key(self, widget):
        await settings_operations.get_visual_crossing_api_key(self)

    async def _on_validate_visual_crossing_api_key(self, widget):
        await settings_operations.validate_visual_crossing_api_key(self)

    def _initialize_update_info(self):
        settings_operations.initialize_update_info(self)

    def _update_last_check_info(self):
        settings_operations.update_last_check_info(self)

    async def _on_check_updates(self, widget):
        await settings_operations.check_for_updates(self)
