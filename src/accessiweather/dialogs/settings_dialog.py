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
        self.display_tab = None
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

        # Display tab controls
        self.temperature_unit_selection = None

        # Advanced tab controls
        self.minimize_to_tray_switch = None

        # Updates tab controls
        self.auto_update_switch = None
        self.update_channel_selection = None
        self.update_method_selection = None
        self.update_check_interval_input = None
        self.check_updates_button = None
        self.update_status_label = None
        self.last_check_label = None
        self.platform_info_label = None
        self.update_capability_label = None

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
            "Visual Crossing (Global, requires API key)",
        ]

        self.data_source_selection = toga.Selection(
            items=data_source_options,
            style=Pack(margin_bottom=15),
            on_change=self._on_data_source_changed,
        )

        # Set current value based on stored configuration
        data_source_map = {
            "auto": 0,
            "nws": 1,
            "openmeteo": 2,
            "visualcrossing": 3,
        }

        try:
            current_data_source = self.current_settings.data_source
            selected_index = data_source_map.get(current_data_source, 0)
            self.data_source_selection.value = data_source_options[selected_index]
        except (IndexError, AttributeError) as e:
            logger.warning(f"Failed to set data source selection: {e}, using default")
            self.data_source_selection.value = data_source_options[0]

        general_box.add(self.data_source_selection)

        # Visual Crossing API Key Configuration (initially hidden)
        self.visual_crossing_config_box = toga.Box(style=Pack(direction=COLUMN))

        self.visual_crossing_config_box.add(
            toga.Label(
                "Visual Crossing API Configuration:",
                style=Pack(margin_top=15, margin_bottom=5, font_weight="bold"),
            )
        )

        # API Key input
        self.visual_crossing_config_box.add(toga.Label("API Key:", style=Pack(margin_bottom=5)))
        self.visual_crossing_api_key_input = toga.PasswordInput(
            value=getattr(self.current_settings, "visual_crossing_api_key", ""),
            placeholder="Enter your Visual Crossing API key",
            style=Pack(margin_bottom=10),
        )
        self.visual_crossing_config_box.add(self.visual_crossing_api_key_input)

        # API Key buttons row
        api_key_buttons_row = toga.Box(style=Pack(direction=ROW, margin_bottom=15))

        # API Key registration link button
        self.get_api_key_button = toga.Button(
            "Get Free API Key",
            on_press=self._on_get_visual_crossing_api_key,
            style=Pack(margin_right=10, width=150),
        )
        api_key_buttons_row.add(self.get_api_key_button)

        # API Key validation button
        self.validate_api_key_button = toga.Button(
            "Validate API Key",
            on_press=self._on_validate_visual_crossing_api_key,
            style=Pack(width=150),
        )
        api_key_buttons_row.add(self.validate_api_key_button)

        self.visual_crossing_config_box.add(api_key_buttons_row)

        general_box.add(self.visual_crossing_config_box)

        # Set initial visibility of Visual Crossing config based on current selection
        self._update_visual_crossing_visibility()

        # Update Interval
        general_box.add(toga.Label("Update Interval (minutes):", style=Pack(margin_bottom=5)))
        self.update_interval_input = toga.NumberInput(
            value=self.current_settings.update_interval_minutes,
            style=Pack(margin_bottom=15),
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
        general_box.add(
            toga.Label("Sound Notifications:", style=Pack(margin_top=15, font_weight="bold"))
        )

        # Enable Sounds Switch
        self.sound_enabled_switch = toga.Switch(
            "Enable Sounds",
            value=getattr(self.current_settings, "sound_enabled", True),
            style=Pack(margin_bottom=10),
            id="sound_enabled_switch",
            on_change=self._on_sound_enabled_changed,
        )
        general_box.add(self.sound_enabled_switch)

        # Sound Pack Selection (authoritative selector for active pack)
        self._load_sound_packs()

        # Label for clarity
        general_box.add(toga.Label("Active sound pack:", style=Pack(margin_bottom=5)))

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

        # Manage Sound Packs Button
        # Opens manager focused on the current pack for import/edit/organize only.
        # Active pack selection remains controlled by the selector above.
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

        update_channel_options = [
            "Stable (Production releases only)",
            "Beta (Pre-release testing)",
            "Development (Latest features, may be unstable)",
        ]
        self.update_channel_selection = toga.Selection(
            items=update_channel_options,
            style=Pack(margin_bottom=10),
            id="update_channel_selection",
            on_change=self._on_update_channel_changed,
        )

        # Set current value based on stored configuration
        current_channel = getattr(self.current_settings, "update_channel", "stable")
        if current_channel == "dev":
            self.update_channel_selection.value = "Development (Latest features, may be unstable)"
        elif current_channel == "beta":
            self.update_channel_selection.value = "Beta (Pre-release testing)"
        else:
            self.update_channel_selection.value = "Stable (Production releases only)"

        updates_box.add(self.update_channel_selection)

        # Channel description label
        self.channel_description_label = toga.Label(
            "",
            style=Pack(margin_bottom=15, font_size=11, font_style="italic"),
        )
        updates_box.add(self.channel_description_label)

        # Update description based on current selection
        self._update_channel_description()

        # Update method selection
        updates_box.add(toga.Label("Update Method:", style=Pack(margin_bottom=5)))

        update_method_options = [
            "Automatic (TUF for stable, GitHub for beta/dev)",
            "TUF Only (Secure, stable releases only)",
            "GitHub Only (All releases, less secure)",
        ]
        self.update_method_selection = toga.Selection(
            items=update_method_options,
            style=Pack(margin_bottom=10),
            id="update_method_selection",
            on_change=self._on_update_method_changed,
        )

        # Set current value based on stored configuration or TUF availability
        current_method = getattr(self.current_settings, "update_method", "auto")
        if current_method == "tuf":
            self.update_method_selection.value = "TUF Only (Secure, stable releases only)"
        elif current_method == "github":
            self.update_method_selection.value = "GitHub Only (All releases, less secure)"
        else:
            self.update_method_selection.value = "Automatic (TUF for stable, GitHub for beta/dev)"

        updates_box.add(self.update_method_selection)

        # Method description label
        self.method_description_label = toga.Label(
            "",
            style=Pack(margin_bottom=15, font_size=11, font_style="italic"),
        )
        updates_box.add(self.method_description_label)

        # Update description based on current selection
        self._update_method_description()

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

    def _load_sound_packs(self):
        """Load available sound packs."""
        import json
        from pathlib import Path

        soundpacks_dir = Path(__file__).parent.parent / "soundpacks"
        self.sound_pack_options = []
        self.sound_pack_map = {}
        if soundpacks_dir.exists():
            for pack_dir in soundpacks_dir.iterdir():
                if pack_dir.is_dir() and (pack_dir / "pack.json").exists():
                    try:
                        with open(pack_dir / "pack.json", encoding="utf-8") as f:
                            meta = json.load(f)
                        display_name = meta.get("name", pack_dir.name)
                        self.sound_pack_options.append(display_name)
                        self.sound_pack_map[display_name] = pack_dir.name
                    except Exception:
                        continue
        if not self.sound_pack_options:
            self.sound_pack_options = ["Default"]
            self.sound_pack_map["Default"] = "default"

    def _on_sound_enabled_changed(self, widget):
        enabled = widget.value
        self.sound_pack_selection.enabled = enabled

    async def _on_manage_soundpacks(self, widget):
        """Open the sound pack manager dialog.

        Note: The Sound Pack Manager is for importing, editing, and managing packs.
        The current pack selection is controlled by the selection widget in this Settings dialog.
        """
        try:
            from .soundpack_manager import SoundPackManagerDialog

            # Preserve the currently selected pack from settings (authoritative)
            current_pack_id = getattr(self.current_settings, "sound_pack", "default")

            # Open the manager focused on the current pack; do not treat its selection as app setting
            manager = SoundPackManagerDialog(self.app, current_pack_id)
            await manager.show()

            # After the manager closes, just refresh the available pack list (packs may have changed)
            self._load_sound_packs()
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
            self.app.main_window.error_dialog(
                "Sound Pack Manager Error", f"Failed to open sound pack manager: {e}"
            )

    def _on_data_source_changed(self, widget):
        """Handle data source selection change to show/hide Visual Crossing config."""
        self._update_visual_crossing_visibility()

    def _update_visual_crossing_visibility(self):
        """Update visibility of Visual Crossing configuration based on data source selection."""
        if not self.data_source_selection or not self.visual_crossing_config_box:
            return

        selected_value = str(self.data_source_selection.value)
        show_visual_crossing = "Visual Crossing" in selected_value

        # Show or hide the Visual Crossing configuration box by adding/removing from parent
        parent_box = self.visual_crossing_config_box.parent
        if parent_box:
            if show_visual_crossing:
                # Make sure it's visible (add if not already present)
                if self.visual_crossing_config_box not in parent_box.children:
                    # Find the position after data source selection
                    data_source_index = -1
                    for i, child in enumerate(parent_box.children):
                        if child == self.data_source_selection:
                            data_source_index = i
                            break

                    if data_source_index >= 0:
                        parent_box.insert(data_source_index + 1, self.visual_crossing_config_box)
                    else:
                        parent_box.add(self.visual_crossing_config_box)
            else:
                # Hide by removing from parent
                if self.visual_crossing_config_box in parent_box.children:
                    parent_box.remove(self.visual_crossing_config_box)

    def _on_update_channel_changed(self, widget):
        """Handle update channel selection change."""
        self._update_channel_description()
        self._update_method_description()  # Method description may change based on channel

    def _on_update_method_changed(self, widget):
        """Handle update method selection change."""
        self._update_method_description()

    def _update_channel_description(self):
        """Update the channel description based on current selection."""
        if not hasattr(self, "channel_description_label") or not self.channel_description_label:
            return

        channel_value = str(self.update_channel_selection.value)

        if "Stable" in channel_value:
            description = "🔒 Stable releases only. Maximum security with TUF verification. Recommended for most users."
        elif "Beta" in channel_value:
            description = "🧪 Pre-release versions for testing. Includes new features before stable release. May contain bugs."
        elif "Development" in channel_value:
            description = "🛠️ Latest development builds. Cutting-edge features but may be unstable. For developers and early testers."
        else:
            description = ""

        self.channel_description_label.text = description

    def _update_method_description(self):
        """Update the method description based on current selection."""
        if not hasattr(self, "method_description_label") or not self.method_description_label:
            return

        method_value = str(self.update_method_selection.value)
        channel_value = str(self.update_channel_selection.value)

        if "Automatic" in method_value:
            if "Stable" in channel_value:
                description = "🔄 Uses TUF for stable releases (secure) and GitHub for beta/dev releases (faster)."
            else:
                description = "🔄 Uses GitHub for beta/dev releases. TUF will be used when stable releases are available."
        elif "TUF Only" in method_value:
            if "Stable" in channel_value:
                description = "🔐 Maximum security with cryptographic verification. Only stable releases available."
            else:
                description = "⚠️ TUF only provides stable releases. Beta/dev releases not available with this method."
        elif "GitHub Only" in method_value:
            description = (
                "📦 All releases available but less secure than TUF. Good for beta testing."
            )
        else:
            description = ""

        self.method_description_label.text = description

    async def _on_get_visual_crossing_api_key(self, widget):
        """Handle Get API Key button press - open Visual Crossing registration page."""
        try:
            # Open Visual Crossing sign-up page in default browser
            import webbrowser

            webbrowser.open("https://www.visualcrossing.com/weather-query-builder/")

            # Show info dialog with instructions
            await self.app.main_window.info_dialog(
                "Visual Crossing API Key",
                "The Visual Crossing Weather Query Builder page has been opened in your browser.\n\n"
                "To get your free API key:\n"
                "1. Sign up for a free account\n"
                "2. Go to your account page\n"
                "3. Copy your API key\n"
                "4. Paste it into the API Key field below\n\n"
                "Free accounts include 1000 weather records per day.",
            )
        except Exception as e:
            logger.error(f"Failed to open Visual Crossing registration page: {e}")
            await self.app.main_window.error_dialog(
                "Error",
                "Failed to open the Visual Crossing registration page. "
                "Please visit https://www.visualcrossing.com/weather-query-builder/ manually.",
            )

    async def _on_validate_visual_crossing_api_key(self, widget):
        """Handle Validate API Key button press - test the API key with a simple call."""
        api_key = str(self.visual_crossing_api_key_input.value).strip()

        if not api_key:
            await self.app.main_window.error_dialog(
                "API Key Required", "Please enter your Visual Crossing API key before validating."
            )
            return

        try:
            # Import here to avoid circular imports
            import httpx

            from ..visual_crossing_client import VisualCrossingClient

            # Show a simple loading message (we can't show a progress dialog easily in Toga)
            # Instead, we'll disable the button temporarily
            original_text = self.validate_api_key_button.text
            self.validate_api_key_button.text = "Validating..."
            self.validate_api_key_button.enabled = False

            try:
                # Create a simple test client
                client = VisualCrossingClient(api_key, "AccessiWeather/2.0")

                # Make a simple test request to a known location (New York City)
                # This is a minimal request to test API key validity
                url = f"{client.base_url}/40.7128,-74.0060"
                params = {
                    "key": api_key,
                    "include": "current",
                    "unitGroup": "us",
                    "elements": "temp",  # Just get temperature to minimize data usage
                }

                async with httpx.AsyncClient(timeout=10.0) as http_client:
                    response = await http_client.get(url, params=params)

                    if response.status_code == 200:
                        # API key is valid
                        await self.app.main_window.info_dialog(
                            "API Key Valid",
                            "✅ Your Visual Crossing API key is valid and working!\n\n"
                            "You can now use Visual Crossing as your weather data source.",
                        )
                    elif response.status_code == 401:
                        # Invalid API key
                        await self.app.main_window.error_dialog(
                            "Invalid API Key",
                            "❌ The API key you entered is invalid.\n\n"
                            "Please check your API key and try again. Make sure you copied it correctly from your Visual Crossing account.",
                        )
                    elif response.status_code == 429:
                        # Rate limit exceeded
                        await self.app.main_window.error_dialog(
                            "Rate Limit Exceeded",
                            "⚠️ Your API key is valid, but you've exceeded your rate limit.\n\n"
                            "Please wait a moment before making more requests, or check your Visual Crossing account usage.",
                        )
                    else:
                        # Other error
                        await self.app.main_window.error_dialog(
                            "API Error",
                            f"❌ API validation failed with status code {response.status_code}.\n\n"
                            "Please check your internet connection and try again.",
                        )

            except httpx.TimeoutException:
                await self.app.main_window.error_dialog(
                    "Connection Timeout",
                    "⚠️ The validation request timed out.\n\n"
                    "Please check your internet connection and try again.",
                )
            except httpx.RequestError as e:
                await self.app.main_window.error_dialog(
                    "Connection Error",
                    f"❌ Failed to connect to Visual Crossing API.\n\n"
                    f"Error: {e}\n\n"
                    "Please check your internet connection and try again.",
                )
            finally:
                # Restore button state
                self.validate_api_key_button.text = original_text
                self.validate_api_key_button.enabled = True

        except Exception as e:
            logger.error(f"Failed to validate Visual Crossing API key: {e}")
            await self.app.main_window.error_dialog(
                "Validation Error",
                f"❌ An unexpected error occurred while validating your API key.\n\nError: {e}",
            )
            # Restore button state in case of error
            self.validate_api_key_button.text = original_text
            self.validate_api_key_button.enabled = True

    def _collect_settings_from_ui(self) -> AppSettings:
        """Collect current settings from UI controls."""
        # Map data source selection back to internal values

        try:
            # Get the selected value and map it directly to internal values
            selected_value = str(self.data_source_selection.value)
            if "Automatic" in selected_value:
                data_source = "auto"
            elif "National Weather Service" in selected_value:
                data_source = "nws"
            elif "Open-Meteo" in selected_value:
                data_source = "openmeteo"
            elif "Visual Crossing" in selected_value:
                data_source = "visualcrossing"
            else:
                data_source = "auto"  # Default fallback
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to get data source selection: {e}, using default")
            data_source = "auto"

        # Map temperature unit selection back to internal values

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
            channel_value = str(update_channel.value)
            if "Development" in channel_value:
                update_channel = "dev"
            elif "Beta" in channel_value:
                update_channel = "beta"
            else:
                update_channel = "stable"
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

        # Get update method
        update_method = getattr(self, "update_method_selection", None)
        if update_method and hasattr(update_method, "value"):
            method_value = str(update_method.value)
            if "TUF Only" in method_value:
                update_method = "tuf"
            elif "GitHub Only" in method_value:
                update_method = "github"
            else:
                update_method = "auto"
        else:
            update_method = "auto"

        sound_enabled = self.sound_enabled_switch.value
        pack_display = self.sound_pack_selection.value
        sound_pack = self.sound_pack_map.get(pack_display, "default")

        # Get Visual Crossing API key
        visual_crossing_api_key = ""
        if hasattr(self, "visual_crossing_api_key_input") and self.visual_crossing_api_key_input:
            visual_crossing_api_key = str(self.visual_crossing_api_key_input.value).strip()

        return AppSettings(
            temperature_unit=temperature_unit,
            update_interval_minutes=update_interval,
            show_detailed_forecast=self.show_detailed_forecast_switch.value,
            enable_alerts=self.enable_alerts_switch.value,
            minimize_to_tray=self.minimize_to_tray_switch.value,
            data_source=data_source,
            visual_crossing_api_key=visual_crossing_api_key,
            auto_update_enabled=auto_update_enabled,
            update_channel=update_channel,
            update_check_interval_hours=update_check_interval_hours,
            update_method=update_method,
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
                # Check TUF availability
                tuf_available = False
                update_method = "GitHub"

                if self.update_service:
                    tuf_available = self.update_service.tuf_available
                    update_method = self.update_service.current_method.upper()
                else:
                    try:
                        from ..services import TUFUpdateService

                        temp_service = TUFUpdateService("AccessiWeather")
                        tuf_available = temp_service.tuf_available
                        update_method = temp_service.current_method.upper()
                        temp_service.cleanup()
                    except Exception:
                        pass

                if platform_info.update_capable:
                    capability_text = f"Auto-updates: Supported via {update_method}"
                else:
                    capability_text = f"Auto-updates: Manual download via {update_method}"

                if tuf_available:
                    capability_text += " (TUF Secure)"

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

            # Use existing update service or create new one
            if self.update_service:
                update_service = self.update_service
            else:
                # Import and create update service
                from ..services import TUFUpdateService

                update_service = TUFUpdateService(
                    app_name="AccessiWeather",
                    config_dir=self.config_manager.config_dir if self.config_manager else None,
                )

            # Get selected channel and method
            channel_value = str(self.update_channel_selection.value)
            if "Development" in channel_value:
                channel = "dev"
            elif "Beta" in channel_value:
                channel = "beta"
            else:
                channel = "stable"

            method_value = str(self.update_method_selection.value)
            if "TUF Only" in method_value:
                method = "tuf"
            elif "GitHub Only" in method_value:
                method = "github"
            else:
                method = "auto"

            # Update service settings
            update_service.update_settings(channel=channel, method=method)

            # Check for updates
            update_info = await update_service.check_for_updates()

            if update_info:
                # Update available
                if self.update_status_label:
                    self.update_status_label.text = f"Update available: v{update_info.version}"

                # Build update message
                message = (
                    f"Update Available: Version {update_info.version}\n\n"
                    f"Current version: 2.0\n"
                    f"New version: {update_info.version}\n\n"
                )

                if update_info.release_notes:
                    message += f"Release Notes:\n{update_info.release_notes[:500]}"
                    if len(update_info.release_notes) > 500:
                        message += "..."

                # Ask user if they want to download
                should_download = await self.app.main_window.question_dialog(
                    "Update Available",
                    message + "\n\nWould you like to download and install this update?",
                )

                if should_download:
                    # Check platform capability
                    from ..services import PlatformDetector

                    platform_detector = PlatformDetector()
                    platform_info = platform_detector.get_platform_info()

                    if platform_info.update_capable:
                        # Start update process
                        await self._perform_update(update_service, update_info)
                    else:
                        # Platform not capable, just download
                        await self._download_only(update_service, update_info)
                else:
                    if self.update_status_label:
                        self.update_status_label.text = "Update available (not downloaded)"

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

    async def _download_only(self, update_service, update_info):
        """Download an update without installing (for platforms that can't auto-install)."""
        try:
            if self.update_status_label:
                self.update_status_label.text = f"Downloading update {update_info.version}..."

            # Download the update
            downloaded_file = await update_service.download_update(update_info)

            if downloaded_file:
                if self.update_status_label:
                    self.update_status_label.text = f"Update {update_info.version} downloaded"

                await self.app.main_window.info_dialog(
                    "Update Downloaded",
                    f"Update {update_info.version} has been downloaded successfully.\n\n"
                    f"Location: {downloaded_file}\n\n"
                    "Please close the application and run the installer to complete the update.",
                )
            else:
                if self.update_status_label:
                    self.update_status_label.text = "Update download failed"

                await self.app.main_window.error_dialog(
                    "Download Failed", "Failed to download the update. Please try again later."
                )

        except Exception as e:
            logger.error(f"Update download failed: {e}")
            if self.update_status_label:
                self.update_status_label.text = "Update download failed"

            await self.app.main_window.error_dialog(
                "Download Failed", f"Failed to download update: {str(e)}"
            )

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
