"""
Settings dialog for AccessiWeather Toga application.

This module provides a comprehensive settings dialog with tabbed interface
matching the functionality of the wxPython version.
"""

import asyncio
import contextlib
import logging
import os

import toga
from toga.style import Pack
from travertino.constants import COLUMN, ROW

from . import settings_handlers, settings_operations, settings_tabs

logger = logging.getLogger(__name__)
LOG_PREFIX = "SettingsDialog"


class _SafeEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """Event loop policy that auto-creates loops when needed."""

    def get_event_loop(self):  # pragma: no cover - exercised in tests
        if self._local._loop is None:
            self.set_event_loop(self.new_event_loop())
        return self._local._loop


def _ensure_asyncio_loop():
    """
    Ensure asyncio event loop policy is set for the current thread.

    Only configures the policy for testing; does not create event loops.
    Toga manages the event loop during normal app execution.
    """
    if os.environ.get("TOGA_BACKEND") == "toga_dummy":
        try:
            policy = asyncio.get_event_loop_policy()
            if not isinstance(policy, _SafeEventLoopPolicy):
                asyncio.set_event_loop_policy(_SafeEventLoopPolicy())
        except Exception:
            pass  # Ignore errors - Toga will handle event loop setup


_ensure_asyncio_loop()


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
        self.cancel_button = None

        # Notifications tab controls
        self.notifications_tab = None
        self.alert_notifications_enabled_switch = None
        self.alert_notify_extreme_switch = None
        self.alert_notify_severe_switch = None
        self.alert_notify_moderate_switch = None
        self.alert_notify_minor_switch = None
        self.alert_notify_unknown_switch = None
        self.alert_global_cooldown_input = None
        self.alert_per_alert_cooldown_input = None
        self.alert_max_notifications_input = None

        # Taskbar icon text controls (Display tab)
        self.taskbar_icon_text_enabled_switch = None
        self.taskbar_icon_dynamic_enabled_switch = None
        self.taskbar_icon_text_format_input = None
        self.taskbar_format_validation_label = None

    def __await__(self):
        """Make the dialog awaitable for modal behavior."""
        if self.future is None:
            raise RuntimeError("Dialog future not initialized. Call show_and_prepare() first.")
        return self.future.__await__()

    def show_and_prepare(self):
        """Prepare and show the settings dialog."""
        logger.info("%s: Showing settings dialog", LOG_PREFIX)

        try:
            # Create a fresh future for this dialog session
            self.future = self.app.loop.create_future()

            # Ensure a Toga app context exists (important for tests using dummy backend)
            self._ensure_toga_app_context()

            # Create a fresh window instance
            self.window = toga.Window(
                title="AccessiWeather Settings",
                size=(600, 500),
                resizable=True,
                minimizable=False,
                closable=False,  # Prevent closing via X button to enforce modal behavior
            )

            # Load current settings (fast - just reads from memory/config object)
            self.current_settings = self.config_manager.get_settings()
            logger.debug("%s: Loaded settings: %s", LOG_PREFIX, self.current_settings)

            # Create dialog content (UI construction)
            self._create_dialog_content()

            # Ensure window is registered with app before showing
            if self.window not in self.app.windows:
                self.app.windows.add(self.window)

            # Show the dialog immediately for responsive UX
            self.window.show()

            # Set initial focus to the first interactive control for accessibility
            self._set_initial_focus()

            # Defer slow operations to run after dialog is visible
            asyncio.create_task(self._deferred_init())

        except Exception as exc:
            logger.exception("%s: Failed to show settings dialog", LOG_PREFIX)
            if self.future and not self.future.done():
                self.future.set_exception(exc)

    async def _deferred_init(self) -> None:
        """Run slow initialization tasks after dialog is visible."""
        try:
            loop = asyncio.get_running_loop()

            # Sync startup setting in background (can involve file system checks)
            with contextlib.suppress(Exception):
                await loop.run_in_executor(None, self.config_manager.sync_startup_setting)

                # Update the startup switch if the actual state differs from loaded settings
                actual_startup = self.config_manager.get_settings().startup_enabled
                if (
                    hasattr(self, "startup_enabled_switch")
                    and self.startup_enabled_switch is not None
                    and self.startup_enabled_switch.value != actual_startup
                ):
                    self.startup_enabled_switch.value = actual_startup

            # Initialize update info (reads cache file from disk)
            with contextlib.suppress(Exception):
                settings_operations.initialize_update_info(self)

        except Exception as exc:
            logger.debug("%s: Deferred init error (non-fatal): %s", LOG_PREFIX, exc)

    def _ensure_toga_app_context(self):
        """Ensure a Toga application context exists for window creation."""
        if getattr(toga.App, "app", None) is not None:
            return

        os.environ.setdefault("TOGA_BACKEND", "toga_dummy")

        try:
            self._toga_app_guard = toga.App("AccessiWeather (Tests)", "com.accessiweather.tests")
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.debug("%s: Unable to create fallback Toga app: %s", LOG_PREFIX, exc)

    def _create_dialog_content(self):
        """Create the settings dialog content."""
        # Main container
        main_box = toga.Box(style=Pack(direction=COLUMN, margin=10))

        # Create tabbed interface
        self.option_container = toga.OptionContainer(style=Pack(flex=1))

        # Create tabs in new order
        settings_tabs.create_general_tab(self)
        settings_tabs.create_display_tab(self)
        settings_tabs.create_data_sources_tab(self)
        settings_tabs.create_notifications_tab(self)
        settings_tabs.create_audio_tab(self)
        settings_tabs.create_updates_tab(self)
        settings_tabs.create_ai_tab(self)
        settings_tabs.create_advanced_tab(self)

        main_box.add(self.option_container)

        # Ensure the first tab is selected initially for predictable UX
        try:
            self.option_container.current_tab = 0
        except Exception as exc:
            logger.warning("%s: Failed to select initial tab: %s", LOG_PREFIX, exc)

        # Button row
        button_box = toga.Box(style=Pack(direction=ROW, margin_top=10))

        # Add flexible space to push buttons to the right
        button_box.add(toga.Box(style=Pack(flex=1)))

        # Cancel button
        cancel_button = toga.Button(
            "Cancel", on_press=self._on_cancel, style=Pack(margin_right=10), id="cancel_button"
        )
        button_box.add(cancel_button)
        self.cancel_button = cancel_button

        # OK button
        ok_button = toga.Button(
            "OK", on_press=self._on_ok, style=Pack(margin_right=0), id="ok_button"
        )
        button_box.add(ok_button)
        self.ok_button = ok_button

        main_box.add(button_box)

        # Set window content
        self.window.content = main_box

        # Note: initialize_update_info is called in _deferred_init() for faster dialog open

    def _set_initial_focus(self):
        """Set initial focus to the first interactive control for accessibility."""
        try:
            if self.option_container is not None:
                self.option_container.current_tab = 0
        except Exception as exc:
            logger.warning("%s: Failed to select initial tab before focusing: %s", LOG_PREFIX, exc)

        # Focus on the first control in the General tab (first tab shown)
        target = self.update_interval_input or self.data_source_selection

        if target is None:
            logger.warning("%s: No primary control available for focus", LOG_PREFIX)
            if self.option_container is not None:
                try:
                    self.option_container.focus()
                    logger.debug("%s: Focused option container as fallback", LOG_PREFIX)
                except Exception as fallback_exc:
                    logger.debug(
                        "%s: Unable to focus option container fallback: %s",
                        LOG_PREFIX,
                        fallback_exc,
                    )
            return

        try:
            target.focus()
            identifier = getattr(target, "id", None) or target.__class__.__name__
            logger.debug("%s: Set initial focus to %s", LOG_PREFIX, identifier)
        except Exception as exc:
            logger.warning(
                "%s: Failed to set initial focus; focusing option container instead: %s",
                LOG_PREFIX,
                exc,
            )
            if self.option_container is not None:
                try:
                    self.option_container.focus()
                    logger.debug("%s: Focused option container as fallback", LOG_PREFIX)
                except Exception as fallback_exc:
                    logger.debug(
                        "%s: Unable to focus option container fallback: %s",
                        LOG_PREFIX,
                        fallback_exc,
                    )

    def _ensure_dialog_focus(self):
        """Ensure focus remains within the dialog window."""
        try:
            if self.window and hasattr(self.window, "focus"):
                self.window.focus()
                logger.debug("%s: Restored focus to settings dialog window", LOG_PREFIX)
        except Exception as exc:
            logger.warning("%s: Failed to restore dialog focus: %s", LOG_PREFIX, exc)

    def _return_focus_to_trigger(self):
        """Return focus to the element that triggered the dialog."""
        try:
            # In Toga, we can't directly control focus return to menu items,
            # but we can ensure the main window gets focus
            if self.app.main_window:
                self.app.main_window.focus()
                logger.debug("%s: Returned focus to main window", LOG_PREFIX)
        except Exception as exc:
            logger.warning("%s: Failed to return focus: %s", LOG_PREFIX, exc)

    async def _show_dialog_error(self, title, message):
        """Show error dialog relative to settings dialog to prevent focus loss."""
        try:
            # Try to use the dialog window for error display if possible
            if self.window and hasattr(self.window, "error_dialog"):
                await self.window.error_dialog(title, message)
            else:
                # Fallback to main window
                await self.app.main_window.error_dialog(title, message)
        except Exception:
            logger.exception("%s: Failed to show error dialog", LOG_PREFIX)
            # Last resort: just log the error
            logger.error("%s: %s - %s", LOG_PREFIX, title, message)
        finally:
            # Restore focus after any dialog interaction
            self._ensure_dialog_focus()

    async def _on_ok(self, widget):
        """Handle OK button press - save settings and close dialog."""
        logger.info("%s: OK button pressed", LOG_PREFIX)

        try:
            # Collect settings from UI (fast - just reads widget values)
            new_settings = settings_handlers.collect_settings_from_ui(self)

            # Capture current startup flag before persisting changes
            old_startup_enabled = self.config_manager.get_settings().startup_enabled

            # Update configuration
            # Note: to_dict() excludes secure keys (API keys) so we must pass them explicitly
            settings_dict = new_settings.to_dict()
            # Add secure keys that are excluded from to_dict() for security
            settings_dict["visual_crossing_api_key"] = new_settings.visual_crossing_api_key
            settings_dict["openrouter_api_key"] = new_settings.openrouter_api_key
            success = self.config_manager.update_settings(**settings_dict)

            if not success:
                logger.error("%s: Failed to save settings", LOG_PREFIX)
                await self._show_dialog_error("Settings Error", "Failed to save settings.")
                return

            logger.info("%s: Settings saved successfully", LOG_PREFIX)

            # Close dialog immediately for responsive UX - startup change runs in background
            if self.future and not self.future.done():
                self.future.set_result(True)
            if self.window:
                self.window.close()
                self.window = None

            # Refresh runtime components (fast - just updates object attributes)
            if hasattr(self.app, "refresh_runtime_settings"):
                self.app.refresh_runtime_settings()
            else:
                self._trigger_taskbar_icon_update(new_settings)

            # Handle startup setting change in background (can be slow on Windows)
            new_startup_enabled = new_settings.startup_enabled
            if old_startup_enabled != new_startup_enabled:
                logger.info(
                    "%s: Startup setting changed %s -> %s, applying in background",
                    LOG_PREFIX,
                    old_startup_enabled,
                    new_startup_enabled,
                )
                # Fire-and-forget - don't block UI for startup shortcut creation
                asyncio.create_task(self._apply_startup_setting_async(new_startup_enabled))

        except Exception as exc:
            logger.exception("%s: Error saving settings", LOG_PREFIX)
            await self._show_dialog_error("Settings Error", f"Error saving settings: {exc}")

    async def _apply_startup_setting_async(self, enable: bool) -> None:
        """Apply startup setting change in background without blocking UI."""
        try:
            loop = asyncio.get_running_loop()
            startup_method = (
                self.config_manager.enable_startup
                if enable
                else self.config_manager.disable_startup
            )

            startup_success, startup_message = await loop.run_in_executor(None, startup_method)

            if startup_success:
                logger.info("%s: Startup setting applied: %s", LOG_PREFIX, startup_message)
            else:
                logger.warning("%s: Startup setting failed: %s", LOG_PREFIX, startup_message)
                # Sync config to reflect actual state
                with contextlib.suppress(Exception):
                    self.config_manager.sync_startup_setting()

        except Exception as exc:
            logger.error("%s: Error applying startup setting: %s", LOG_PREFIX, exc)
            with contextlib.suppress(Exception):
                self.config_manager.sync_startup_setting()

    async def _on_cancel(self, widget):
        """Handle Cancel button press - close dialog without saving."""
        logger.info("%s: Cancel button pressed", LOG_PREFIX)
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
        """
        Open the sound pack manager dialog.

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

        except Exception as exc:
            logger.exception("%s: Failed to open sound pack manager", LOG_PREFIX)
            # Use dialog-relative error instead of main window error
            await self._show_dialog_error(
                "Sound Pack Manager Error",
                f"Failed to open sound pack manager: {exc}",
            )

    def _on_data_source_changed(self, widget):
        """Handle data source selection change to update UI visibility."""
        self._update_visual_crossing_config_visibility()
        self._update_priority_settings_visibility()

    def _get_selected_data_source(self) -> str:
        """Get the currently selected data source internal value."""
        if not self.data_source_selection:
            return "auto"
        selected_display = str(self.data_source_selection.value)
        return self.data_source_display_to_value.get(selected_display, "auto")

    def _update_visual_crossing_config_visibility(self):
        """Show Visual Crossing API config only when Visual Crossing is selected."""
        container = getattr(self, "data_sources_tab", None)
        if not container or not self.visual_crossing_config_box:
            return

        show = self._get_selected_data_source() == "visualcrossing"

        if show:
            if self.visual_crossing_config_box not in container.children:
                try:
                    idx = container.children.index(self.data_source_selection)
                    container.insert(idx + 1, self.visual_crossing_config_box)
                except ValueError:
                    container.add(self.visual_crossing_config_box)
        else:
            if self.visual_crossing_config_box in container.children:
                container.remove(self.visual_crossing_config_box)

    def _update_priority_settings_visibility(self):
        """Show source priority settings only when Automatic mode is selected."""
        container = getattr(self, "data_sources_tab", None)
        source_priority_box = getattr(self, "source_priority_config_box", None)
        if not container or not source_priority_box:
            return

        show = self._get_selected_data_source() == "auto"

        if show:
            if source_priority_box not in container.children:
                container.add(source_priority_box)
        else:
            if source_priority_box in container.children:
                container.remove(source_priority_box)

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

    async def _on_open_soundpacks_dir(self, widget):
        await settings_operations.open_soundpacks_directory(self)

    async def _on_get_visual_crossing_api_key(self, widget):
        await settings_operations.get_visual_crossing_api_key(self)

    async def _on_validate_visual_crossing_api_key(self, widget):
        await settings_operations.validate_visual_crossing_api_key(self)

    async def _on_validate_openrouter_api_key(self, widget):
        await settings_operations.validate_openrouter_api_key(self)

    async def _on_select_ai_model(self, widget):
        """Handle AI model selection button press."""
        from .model_selection import show_model_selection_dialog

        current_model = getattr(self.current_settings, "ai_model", "openrouter/auto")
        free_only = not getattr(self.current_settings, "allow_paid_models", False)

        def on_model_selected(model_id: str) -> None:
            """Handle model selection from the dialog."""
            if hasattr(self, "selected_model_label"):
                self.selected_model_label.text = model_id
            self._selected_specific_model = model_id
            if hasattr(self, "ai_model_selection"):
                if "Specific Model" not in self.ai_model_display_to_value:
                    self.ai_model_display_to_value["Specific Model"] = model_id
                    self.ai_model_value_to_display[model_id] = "Specific Model"
                else:
                    old_model = self.ai_model_display_to_value.get("Specific Model")
                    if old_model and old_model in self.ai_model_value_to_display:
                        del self.ai_model_value_to_display[old_model]
                    self.ai_model_display_to_value["Specific Model"] = model_id
                    self.ai_model_value_to_display[model_id] = "Specific Model"

                # Get current items from the ListSource (extract string values)
                current_items = [item.value for item in self.ai_model_selection.items]

                if "Specific Model" not in current_items:
                    current_items.append("Specific Model")
                    self.ai_model_selection.items = current_items

                self.ai_model_selection.value = "Specific Model"

        await show_model_selection_dialog(
            self.app, current_model, free_only=free_only, on_model_selected=on_model_selected
        )

    async def _on_reset_system_prompt(self, widget):
        """Reset the custom system prompt to default."""
        if hasattr(self, "custom_system_prompt_input"):
            self.custom_system_prompt_input.value = ""
        await self.main_window.info_dialog(
            "Prompt Reset",
            "System prompt has been reset to default.",
        )

    async def _on_reset_instructions(self, widget):
        """Reset the custom instructions."""
        if hasattr(self, "custom_instructions_input"):
            self.custom_instructions_input.value = ""
        await self.main_window.info_dialog(
            "Instructions Reset",
            "Custom instructions have been cleared.",
        )

    async def _on_preview_prompt(self, widget):
        """Show a preview of the AI prompt."""
        from accessiweather.ai_explainer import AIExplainer, ExplanationStyle

        # Get current values from UI
        custom_system_prompt = None
        if hasattr(self, "custom_system_prompt_input"):
            value = getattr(self.custom_system_prompt_input, "value", "") or ""
            custom_system_prompt = value.strip() if value.strip() else None

        custom_instructions = None
        if hasattr(self, "custom_instructions_input"):
            value = getattr(self.custom_instructions_input, "value", "") or ""
            custom_instructions = value.strip() if value.strip() else None

        # Create explainer with current settings
        explainer = AIExplainer(
            api_key="preview",
            custom_system_prompt=custom_system_prompt,
            custom_instructions=custom_instructions,
        )

        # Generate preview
        preview = explainer.get_prompt_preview(ExplanationStyle.STANDARD)

        # Show preview dialog
        preview_text = (
            f"=== SYSTEM PROMPT ===\n{preview['system_prompt']}\n\n"
            f"=== USER PROMPT (with sample data) ===\n{preview['user_prompt']}"
        )

        await self.main_window.info_dialog(
            "Prompt Preview",
            preview_text,
        )

    def _initialize_update_info(self):
        settings_operations.initialize_update_info(self)

    def _update_last_check_info(self):
        settings_operations.update_last_check_info(self)

    async def _on_check_updates(self, widget):
        await settings_operations.check_for_updates(self)

    async def _on_export_settings(self, widget):
        """Handle Export Settings button press."""
        await settings_operations.export_settings(self)

    async def _on_import_settings(self, widget):
        """Handle Import Settings button press."""
        # TODO: Implement in next subtask
        await self._show_dialog_error(
            "Not Implemented",
            "Import settings functionality will be implemented soon.",
        )

    def _trigger_taskbar_icon_update(self, new_settings):
        """
        Trigger immediate taskbar icon text update if settings changed.

        This method is called after settings are saved to apply taskbar icon
        changes without requiring an app restart.
        """
        try:
            if not hasattr(self.app, "status_icon") or self.app.status_icon is None:
                return

            if not getattr(self.app, "system_tray_available", False):
                return

            from ..ui_builder import update_tray_icon_tooltip

            weather_data = None
            if hasattr(self.app, "current_weather_data"):
                weather_data = self.app.current_weather_data

            update_tray_icon_tooltip(self.app, weather_data)
            logger.debug("%s: Taskbar icon text updated after settings change", LOG_PREFIX)

        except Exception as exc:
            logger.debug("%s: Failed to update taskbar icon: %s", LOG_PREFIX, exc)

    def _on_category_up(self, widget):
        """Move the selected category up in the order list."""
        if not hasattr(self, "category_order_list") or self.category_order_list is None:
            return

        try:
            current_value = self.category_order_list.value
            if current_value is None:
                return

            # Get current items from the ListSource
            items = [item.value for item in self.category_order_list.items]
            current_index = items.index(current_value)

            if current_index > 0:
                # Swap with the item above
                items[current_index], items[current_index - 1] = (
                    items[current_index - 1],
                    items[current_index],
                )
                # Update the selection with new order
                self.category_order_list.items = items
                self.category_order_list.value = current_value
                logger.debug(
                    "%s: Moved category '%s' up from position %d to %d",
                    LOG_PREFIX,
                    current_value,
                    current_index,
                    current_index - 1,
                )
        except Exception as exc:
            logger.warning("%s: Failed to move category up: %s", LOG_PREFIX, exc)

    def _on_category_down(self, widget):
        """Move the selected category down in the order list."""
        if not hasattr(self, "category_order_list") or self.category_order_list is None:
            return

        try:
            current_value = self.category_order_list.value
            if current_value is None:
                return

            # Get current items from the ListSource
            items = [item.value for item in self.category_order_list.items]
            current_index = items.index(current_value)

            if current_index < len(items) - 1:
                # Swap with the item below
                items[current_index], items[current_index + 1] = (
                    items[current_index + 1],
                    items[current_index],
                )
                # Update the selection with new order
                self.category_order_list.items = items
                self.category_order_list.value = current_value
                logger.debug(
                    "%s: Moved category '%s' down from position %d to %d",
                    LOG_PREFIX,
                    current_value,
                    current_index,
                    current_index + 1,
                )
        except Exception as exc:
            logger.warning("%s: Failed to move category down: %s", LOG_PREFIX, exc)

    def _on_reset_category_order(self, widget):
        """Reset the category order to the default order."""
        if not hasattr(self, "category_order_list") or self.category_order_list is None:
            return

        try:
            default_order = [
                "Temperature",
                "Precipitation",
                "Wind",
                "Humidity & Pressure",
                "Visibility & Clouds",
                "UV Index",
            ]
            self.category_order_list.items = default_order
            # Select the first item
            if default_order:
                self.category_order_list.value = default_order[0]
            logger.info("%s: Category order reset to default", LOG_PREFIX)
        except Exception as exc:
            logger.warning("%s: Failed to reset category order: %s", LOG_PREFIX, exc)
