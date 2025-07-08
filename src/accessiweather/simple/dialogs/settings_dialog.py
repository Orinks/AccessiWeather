"""Settings dialog for AccessiWeather Toga application.

This module provides a comprehensive settings dialog with tabbed interface
matching the functionality of the wxPython version.
"""

import logging

import toga
from toga.style import Pack
from travertino.constants import COLUMN, ROW

from ..models import AppSettings

logger = logging.getLogger(__name__)


class SettingsDialog:
    """Settings dialog with tabbed interface for configuration options."""

    def __init__(self, app: toga.App, config_manager):
        self.app = app
        self.config_manager = config_manager
        self.window = None  # Will be created fresh each time dialog is shown
        self.future = None  # Will be created fresh each time dialog is shown

        # Current settings (working copy)
        self.current_settings = None

        # UI components
        self.option_container = None
        self.general_tab = None
        self.display_tab = None
        self.advanced_tab = None
        self.updates_tab = None

        # General tab controls
        self.data_source_selection = None
        self.update_interval_input = None
        self.show_detailed_forecast_switch = None
        self.enable_alerts_switch = None
        self.debug_mode_switch = None

        # Display tab controls
        self.temperature_unit_selection = None

        # Advanced tab controls
        self.minimize_to_tray_switch = None

        # Updates tab controls (placeholder for future implementation)
        self.auto_update_switch = None

        # Sound settings controls
        self.sound_enabled_switch = None
        self.sound_pack_selection = None
        self.preview_sound_button = None
        self.manage_soundpacks_button = None

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

        # Create tabs
        self._create_general_tab()
        self._create_display_tab()
        self._create_advanced_tab()
        self._create_updates_tab()

        main_box.add(self.option_container)

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

        main_box.add(button_box)

        # Set window content
        self.window.content = main_box

        # Initialize update service and platform info
        try:
            self._initialize_update_info()
        except Exception as e:
            logger.error(f"Failed to initialize update info: {e}")
            # Set fallback text for platform info
            if hasattr(self, "platform_info_label"):
                self.platform_info_label.text = "Platform information unavailable"
            if hasattr(self, "update_capability_label"):
                self.update_capability_label.text = "Update capability unknown"

    def _create_general_tab(self):
        """Create the General settings tab."""
        general_box = toga.Box(style=Pack(direction=COLUMN, margin=10))

        # Data Source Selection
        general_box.add(toga.Label("Weather Data Source:", style=Pack(margin_bottom=5)))

        # Define data source options
        data_source_options = [
            "Automatic (NWS for US, Open-Meteo for non-US)",
            "National Weather Service (NWS)",
            "Open-Meteo (International)",
        ]

        self.data_source_selection = toga.Selection(
            items=data_source_options,
            style=Pack(margin_bottom=15),
            id="data_source_selection",
        )

        # Set current value based on stored configuration
        data_source_map = {
            "auto": 0,
            "nws": 1,
            "openmeteo": 2,
        }

        try:
            current_data_source = self.current_settings.data_source
            selected_index = data_source_map.get(current_data_source, 0)
            self.data_source_selection.value = data_source_options[selected_index]
        except (IndexError, AttributeError) as e:
            logger.warning(f"Failed to set data source selection: {e}, using default")
            self.data_source_selection.value = data_source_options[0]

        general_box.add(self.data_source_selection)

        # Update Interval
        general_box.add(toga.Label("Update Interval (minutes):", style=Pack(margin_bottom=5)))
        self.update_interval_input = toga.NumberInput(
            value=self.current_settings.update_interval_minutes,
            style=Pack(margin_bottom=15),
            id="update_interval_input",
        )
        general_box.add(self.update_interval_input)

        # Show Detailed Forecast
        self.show_detailed_forecast_switch = toga.Switch(
            "Show detailed forecast information",
            value=self.current_settings.show_detailed_forecast,
            style=Pack(margin_bottom=10),
            id="show_detailed_forecast_switch",
        )
        general_box.add(self.show_detailed_forecast_switch)

        # Enable Alerts
        self.enable_alerts_switch = toga.Switch(
            "Enable weather alerts",
            value=self.current_settings.enable_alerts,
            style=Pack(margin_bottom=10),
            id="enable_alerts_switch",
        )
        general_box.add(self.enable_alerts_switch)

        # Debug Mode
        self.debug_mode_switch = toga.Switch(
            "Enable Debug Mode",
            value=getattr(self.current_settings, "debug_mode", False),
            style=Pack(margin_bottom=10),
            id="debug_mode_switch",
        )
        general_box.add(self.debug_mode_switch)

        # --- Sound Settings ---
        general_box.add(toga.Label("Sound Notifications:", style=Pack(margin_top=15, font_weight="bold")))

        # Enable Sounds Switch
        self.sound_enabled_switch = toga.Switch(
            "Enable Sounds",
            value=getattr(self.current_settings, "sound_enabled", True),
            style=Pack(margin_bottom=10),
            id="sound_enabled_switch",
            on_change=self._on_sound_enabled_changed,
        )
        general_box.add(self.sound_enabled_switch)

        # Sound Pack Selection
        from pathlib import Path
        import json
        soundpacks_dir = Path(__file__).parent.parent / "soundpacks"
        self.sound_pack_options = []
        self.sound_pack_map = {}
        if soundpacks_dir.exists():
            for pack_dir in soundpacks_dir.iterdir():
                if pack_dir.is_dir() and (pack_dir / "pack.json").exists():
                    try:
                        with open(pack_dir / "pack.json", "r", encoding="utf-8") as f:
                            meta = json.load(f)
                        display_name = meta.get("name", pack_dir.name)
                        self.sound_pack_options.append(display_name)
                        self.sound_pack_map[display_name] = pack_dir.name
                    except Exception:
                        continue
        if not self.sound_pack_options:
            self.sound_pack_options = ["Default"]
            self.sound_pack_map["Default"] = "default"

        self.sound_pack_selection = toga.Selection(
            items=self.sound_pack_options,
            style=Pack(margin_bottom=10, width=200),
            id="sound_pack_selection",
        )
        # Set current value
        current_pack = getattr(self.current_settings, "sound_pack", "default")
        for k, v in self.sound_pack_map.items():
            if v == current_pack:
                self.sound_pack_selection.value = k
                break
        else:
            self.sound_pack_selection.value = self.sound_pack_options[0]
        general_box.add(self.sound_pack_selection)

        # Preview Button
        self.preview_sound_button = toga.Button(
            "Preview Sound",
            on_press=self._on_preview_sound,
            style=Pack(margin_right=10, width=120),
            enabled=self.sound_enabled_switch.value,
        )
        general_box.add(self.preview_sound_button)

        # Manage Sound Packs Button (stub)
        self.manage_soundpacks_button = toga.Button(
            "Manage Sound Packs...",
            on_press=self._on_manage_soundpacks,
            style=Pack(margin_bottom=10, width=180),
        )
        general_box.add(self.manage_soundpacks_button)

        # Add tab to container
        self.option_container.content.append("General", general_box)

    def _create_display_tab(self):
        """Create the Display settings tab."""
        display_box = toga.Box(style=Pack(direction=COLUMN, margin=10))

        # Temperature Unit Selection
        display_box.add(toga.Label("Temperature Display:", style=Pack(margin_bottom=5)))

        # Define temperature unit options
        temp_unit_options = [
            "Fahrenheit only",
            "Celsius only",
            "Both (Fahrenheit and Celsius)",
        ]

        self.temperature_unit_selection = toga.Selection(
            items=temp_unit_options,
            style=Pack(margin_bottom=15),
            id="temperature_unit_selection",
        )

        # Set current value based on stored configuration
        temp_unit_map = {
            "f": 0,
            "c": 1,
            "both": 2,
        }

        try:
            current_temp_unit = self.current_settings.temperature_unit
            selected_index = temp_unit_map.get(current_temp_unit, 2)
            self.temperature_unit_selection.value = temp_unit_options[selected_index]
        except (IndexError, AttributeError) as e:
            logger.warning(f"Failed to set temperature unit selection: {e}, using default")
            self.temperature_unit_selection.value = temp_unit_options[2]  # Default to "Both"

        display_box.add(self.temperature_unit_selection)

        # Add placeholder for future display options
        display_box.add(
            toga.Label(
                "Additional display options will be added in future versions.",
                style=Pack(margin_top=20, font_style="italic"),
            )
        )

        # Add tab to container
        self.option_container.content.append("Display", display_box)

    def _create_advanced_tab(self):
        """Create the Advanced settings tab."""
        advanced_box = toga.Box(style=Pack(direction=COLUMN, margin=10))

        # Minimize to Tray (note: not applicable to all platforms)
        self.minimize_to_tray_switch = toga.Switch(
            "Minimize to notification area when closing",
            value=self.current_settings.minimize_to_tray,
            style=Pack(margin_bottom=10),
            id="minimize_to_tray_switch",
        )
        advanced_box.add(self.minimize_to_tray_switch)

        # Add placeholder for future advanced options
        advanced_box.add(
            toga.Label(
                "Additional advanced options will be added in future versions.",
                style=Pack(margin_top=20, font_style="italic"),
            )
        )

        # Add tab to container
        self.option_container.content.append("Advanced", advanced_box)

    def _create_updates_tab(self):
        """Create the Updates settings tab with full functionality."""
        updates_box = toga.Box(style=Pack(direction=COLUMN, margin=10))

        # Auto-update settings
        self.auto_update_switch = toga.Switch(
            "Check for updates automatically",
            value=getattr(self.current_settings, "auto_update_enabled", True),
            style=Pack(margin_bottom=10),
            id="auto_update_switch",
        )
        updates_box.add(self.auto_update_switch)

        # Update channel selection
        updates_box.add(toga.Label("Update Channel:", style=Pack(margin_bottom=5)))

        update_channel_options = ["Stable", "Development"]
        self.update_channel_selection = toga.Selection(
            items=update_channel_options,
            style=Pack(margin_bottom=15),
            id="update_channel_selection",
        )

        # Set current value based on stored configuration
        current_channel = getattr(self.current_settings, "update_channel", "stable")
        if current_channel == "dev":
            self.update_channel_selection.value = "Development"
        else:
            self.update_channel_selection.value = "Stable"

        updates_box.add(self.update_channel_selection)

        # Check interval
        updates_box.add(toga.Label("Check Interval (hours):", style=Pack(margin_bottom=5)))
        self.update_check_interval_input = toga.NumberInput(
            value=getattr(self.current_settings, "update_check_interval_hours", 24),
            style=Pack(margin_bottom=15),
            id="update_check_interval_input",
        )
        updates_box.add(self.update_check_interval_input)

        # Platform information
        platform_info_box = toga.Box(style=Pack(direction=COLUMN, margin_bottom=15))
        platform_info_box.add(
            toga.Label("Platform Information:", style=Pack(font_weight="bold", margin_bottom=5))
        )

        # We'll populate this with actual platform info when the dialog is shown
        self.platform_info_label = toga.Label(
            "Detecting platform...",
            style=Pack(font_size=11, margin_bottom=5),
        )
        platform_info_box.add(self.platform_info_label)

        self.update_capability_label = toga.Label(
            "Checking update capability...",
            style=Pack(font_size=11, margin_bottom=10),
        )
        platform_info_box.add(self.update_capability_label)

        updates_box.add(platform_info_box)

        # Check now button
        self.check_updates_button = toga.Button(
            "Check for Updates Now",
            on_press=self._on_check_updates,
            style=Pack(margin_bottom=10),
            id="check_updates_button",
        )
        updates_box.add(self.check_updates_button)

        # Status display
        self.update_status_label = toga.Label(
            "Ready to check for updates",
            style=Pack(margin_bottom=10, font_style="italic"),
        )
        updates_box.add(self.update_status_label)

        # Last check information
        self.last_check_label = toga.Label(
            "Never checked for updates",
            style=Pack(font_size=11, margin_bottom=10),
        )
        updates_box.add(self.last_check_label)

        # Add tab to container
        self.option_container.content.append("Updates", updates_box)

    def _set_initial_focus(self):
        """Set initial focus to the first interactive control for accessibility."""
        try:
            # Set focus to the first interactive control (data source selection)
            # This ensures keyboard and screen reader users start at a logical point
            if self.data_source_selection:
                self.data_source_selection.focus()
                logger.debug("Set initial focus to data source selection")
            else:
                logger.warning("Data source selection not available for focus")
        except Exception as e:
            logger.warning(f"Failed to set initial focus: {e}")
            # Fallback: try to focus the option container itself
            try:
                if self.option_container:
                    self.option_container.focus()
                    logger.debug("Set fallback focus to option container")
            except Exception as fallback_error:
                logger.warning(f"Fallback focus also failed: {fallback_error}")

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

    async def _on_ok(self, widget):
        """Handle OK button press - save settings and close dialog."""
        logger.info("Settings dialog OK button pressed")

        try:
            # Collect settings from UI
            new_settings = self._collect_settings_from_ui()

            # Update configuration
            success = self.config_manager.update_settings(**new_settings.to_dict())

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
                await self.app.main_window.error_dialog(
                    "Settings Error", "Failed to save settings."
                )

        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            # Don't close dialog on error, let user try again or cancel
            await self.app.main_window.error_dialog("Settings Error", f"Error saving settings: {e}")

    async def _on_cancel(self, widget):
        """Handle Cancel button press - close dialog without saving."""
        logger.info("Settings dialog cancelled")
        if self.future and not self.future.done():
            self.future.set_result(False)
        if self.window:
            self.window.close()
            self.window = None  # Clear reference to help with cleanup

    def _on_sound_enabled_changed(self, widget):
        enabled = widget.value
        self.sound_pack_selection.enabled = enabled
        self.preview_sound_button.enabled = enabled

    def _on_preview_sound(self, widget):
        # Play a sample sound from the selected pack
        try:
            pack_display = self.sound_pack_selection.value
            pack_dir = self.sound_pack_map.get(pack_display, "default")
            from ..notifications.sound_player import play_sample_sound
            play_sample_sound(pack_dir)
        except Exception as e:
            logger.error(f"Failed to preview sound: {e}")

    def _on_manage_soundpacks(self, widget):
        # Placeholder for future sound pack management dialog
        self.app.main_window.info_dialog("Manage Sound Packs", "Sound pack management coming soon.")

    def _collect_settings_from_ui(self) -> AppSettings:
        """Collect current settings from UI controls."""
        # Map data source selection back to internal values
        data_source_reverse_map = {
            0: "auto",
            1: "nws",
            2: "openmeteo",
        }

        try:
            # Get the selected value and map it directly to internal values
            selected_value = str(self.data_source_selection.value)
            if "Automatic" in selected_value:
                data_source = "auto"
            elif "National Weather Service" in selected_value:
                data_source = "nws"
            elif "Open-Meteo" in selected_value:
                data_source = "openmeteo"
            else:
                data_source = "auto"  # Default fallback
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to get data source selection: {e}, using default")
            data_source = "auto"

        # Map temperature unit selection back to internal values
        temp_unit_reverse_map = {
            0: "f",
            1: "c",
            2: "both",
        }

        try:
            # Get the selected value and map it directly to internal values
            selected_value = str(self.temperature_unit_selection.value)
            if "Fahrenheit only" in selected_value:
                temperature_unit = "f"
            elif "Celsius only" in selected_value:
                temperature_unit = "c"
            elif "Both" in selected_value:
                temperature_unit = "both"
            else:
                temperature_unit = "both"  # Default fallback
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to get temperature unit selection: {e}, using default")
            temperature_unit = "both"

        # Validate and get update interval
        try:
            update_interval = int(self.update_interval_input.value)
            # Ensure it's within reasonable bounds (1 minute to 24 hours)
            update_interval = max(1, min(1440, update_interval))
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid update interval value: {e}, using default")
            update_interval = 10  # Default to 10 minutes

        # Get update-related settings
        auto_update_enabled = getattr(self, "auto_update_switch", None)
        auto_update_enabled = auto_update_enabled.value if auto_update_enabled else True

        update_channel = getattr(self, "update_channel_selection", None)
        if update_channel and hasattr(update_channel, "value"):
            update_channel = "dev" if update_channel.value == "Development" else "stable"
        else:
            update_channel = "stable"

        update_check_interval = getattr(self, "update_check_interval_input", None)
        if update_check_interval and hasattr(update_check_interval, "value"):
            try:
                update_check_interval_hours = int(update_check_interval.value)
                update_check_interval_hours = max(
                    1, min(168, update_check_interval_hours)
                )  # 1 hour to 1 week
            except (ValueError, TypeError):
                update_check_interval_hours = 24
        else:
            update_check_interval_hours = 24

        sound_enabled = self.sound_enabled_switch.value
        pack_display = self.sound_pack_selection.value
        sound_pack = self.sound_pack_map.get(pack_display, "default")

        return AppSettings(
            temperature_unit=temperature_unit,
            update_interval_minutes=update_interval,
            show_detailed_forecast=self.show_detailed_forecast_switch.value,
            enable_alerts=self.enable_alerts_switch.value,
            minimize_to_tray=self.minimize_to_tray_switch.value,
            data_source=data_source,
            auto_update_enabled=auto_update_enabled,
            update_channel=update_channel,
            update_check_interval_hours=update_check_interval_hours,
            debug_mode=self.debug_mode_switch.value,
            sound_enabled=sound_enabled,
            sound_pack=sound_pack,
        )

    def _initialize_update_info(self):
        """Initialize update service and platform information."""
        try:
            # Import here to avoid circular imports
            from ..services import PlatformDetector

            # Get platform information
            platform_detector = PlatformDetector()
            platform_info = platform_detector.get_platform_info()

            # Update platform info labels
            if hasattr(self, "platform_info_label"):
                platform_text = (
                    f"Platform: {platform_info.platform.title()} ({platform_info.architecture})"
                )
                deployment_text = f"Deployment: {platform_info.deployment_type.title()}"
                self.platform_info_label.text = f"{platform_text}, {deployment_text}"

            if hasattr(self, "update_capability_label"):
                if platform_info.update_capable:
                    capability_text = "Auto-updates: Supported"
                else:
                    capability_text = "Auto-updates: Manual download required"
                self.update_capability_label.text = capability_text

            # Update last check information if available
            self._update_last_check_info()

        except Exception as e:
            logger.error(f"Failed to initialize update info: {e}")
            if hasattr(self, "platform_info_label"):
                self.platform_info_label.text = "Platform information unavailable"
            if hasattr(self, "update_capability_label"):
                self.update_capability_label.text = "Update capability unknown"

    def _update_last_check_info(self):
        """Update the last check information display."""
        try:
            # This would typically get info from the update service
            # For now, we'll show a placeholder
            if hasattr(self, "last_check_label"):
                self.last_check_label.text = "Last check: Not implemented yet"

        except Exception as e:
            logger.error(f"Failed to update last check info: {e}")

    async def _on_check_updates(self, widget):
        """Handle check for updates button press."""
        logger.info("Manual update check requested")

        try:
            # Disable the button during check
            if self.check_updates_button:
                self.check_updates_button.enabled = False
                self.check_updates_button.text = "Checking..."

            # Update status
            if self.update_status_label:
                self.update_status_label.text = "Checking for updates..."

            # Import update service
            from ..services import BriefcaseUpdateService

            # Create update service instance
            update_service = BriefcaseUpdateService(self.app, self.config_manager)

            # Get selected channel
            channel = "dev" if self.update_channel_selection.value == "Development" else "stable"

            # Check for updates
            update_info = await update_service.check_for_updates(channel)

            if update_info:
                # Update available
                if self.update_status_label:
                    self.update_status_label.text = f"Update available: v{update_info.version}"

                # Show update notification
                from .update_progress_dialog import UpdateNotificationDialog

                platform_detector = update_service.platform_detector
                platform_info = platform_detector.get_platform_info()

                notification = UpdateNotificationDialog(self.app, update_info, platform_info)
                choice = await notification.show()

                if choice == "download" and platform_info.update_capable:
                    # Start update process
                    await self._perform_update(update_service, update_info)

            else:
                # No updates available
                if self.update_status_label:
                    self.update_status_label.text = "No updates available"

                await self.app.main_window.info_dialog(
                    "No Updates", "You are running the latest version of AccessiWeather."
                )

            # Update last check info
            self._update_last_check_info()

        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            if self.update_status_label:
                self.update_status_label.text = "Update check failed"

            await self.app.main_window.error_dialog(
                "Update Check Failed", f"Failed to check for updates: {str(e)}"
            )

        finally:
            # Re-enable the button
            if self.check_updates_button:
                self.check_updates_button.enabled = True
                self.check_updates_button.text = "Check for Updates Now"

    async def _perform_update(self, update_service, update_info):
        """Perform the update process with progress dialog."""
        try:
            # Import progress dialog
            from .update_progress_dialog import UpdateProgressDialog

            # Create and show progress dialog
            progress_dialog = UpdateProgressDialog(self.app, "Downloading Update")
            progress_dialog.show_and_prepare()

            # Download the update
            async def progress_callback(progress, downloaded, total):
                await progress_dialog.update_progress(progress, downloaded, total)
                return not progress_dialog.is_cancelled

            download_path = await update_service.download_update(update_info, progress_callback)

            if progress_dialog.is_cancelled:
                await progress_dialog.complete_error("Update cancelled by user")
                return

            if not download_path:
                await progress_dialog.complete_error("Failed to download update")
                return

            # Apply the update
            await progress_dialog.set_status("Installing update...", "Please wait...")

            success = await update_service.apply_update(download_path)

            if success:
                await progress_dialog.complete_success("Update installed successfully")

                # Show restart dialog
                restart_choice = await self.app.main_window.question_dialog(
                    "Restart Required",
                    "The update has been installed successfully. "
                    "AccessiWeather needs to restart to complete the update. "
                    "Restart now?",
                )

                if restart_choice:
                    # Close settings dialog and restart app
                    if self.future and not self.future.done():
                        self.future.set_result(True)
                    if self.window:
                        self.window.close()
                        self.window = None
                    # Note: Actual restart implementation would go here
                    await self.app.main_window.info_dialog(
                        "Restart", "Please restart AccessiWeather manually to complete the update."
                    )
            else:
                await progress_dialog.complete_error("Failed to install update")

            # Wait for user to close progress dialog
            await progress_dialog
            progress_dialog.close()

        except Exception as e:
            logger.error(f"Failed to perform update: {e}")
            await self.app.main_window.error_dialog(
                "Update Failed", f"Failed to perform update: {str(e)}"
            )
