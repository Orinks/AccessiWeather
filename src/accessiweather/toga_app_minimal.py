"""Minimal Toga-based AccessiWeather application for debugging crashes.

This version gradually adds complexity to identify what causes the Windows crashes.
"""

import logging
import os

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

logger = logging.getLogger(__name__)


class AccessiWeatherMinimal(toga.App):
    """Minimal Toga application for AccessiWeather debugging."""

    def __init__(self, *args, **kwargs):
        """Initialize the minimal application."""
        super().__init__(*args, **kwargs)
        
        # Minimal state
        self.test_data = "No data loaded"

    def startup(self):
        """Initialize the minimal application UI."""
        logger.info("Starting minimal AccessiWeather Toga application")
        
        try:
            # Create minimal UI
            self._create_minimal_ui()
            
            # Test basic functionality
            self._test_basic_functionality()
            
            logger.info("Minimal AccessiWeather Toga application started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start minimal app: {e}")
            raise

    def _create_minimal_ui(self):
        """Create minimal user interface."""
        # Main container
        main_box = toga.Box(style=Pack(direction=COLUMN, margin=10))
        
        # Title
        title_label = toga.Label(
            'AccessiWeather - Minimal Debug Version',
            style=Pack(margin=(0, 0, 10, 0), font_size=14, font_weight='bold')
        )
        main_box.add(title_label)
        
        # Status display
        self.status_display = toga.Label(
            'Status: Starting up...',
            style=Pack(margin=(0, 0, 10, 0))
        )
        main_box.add(self.status_display)
        
        # Test button
        test_button = toga.Button(
            'Test Basic Function',
            on_press=self._on_test_pressed,
            style=Pack(margin=(0, 0, 10, 0))
        )
        main_box.add(test_button)
        
        # Simple text area
        self.text_area = toga.MultilineTextInput(
            readonly=True,
            value="Minimal Toga app is running.\n\nThis version tests basic functionality without complex service integration.",
            style=Pack(height=150, margin=(0, 0, 10, 0))
        )
        main_box.add(self.text_area)
        
        # Create minimal menu
        self._create_minimal_menu()
        
        # Set up main window
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.show()

    def _create_minimal_menu(self):
        """Create minimal menu system."""
        # File menu
        file_menu = toga.Group('File')
        exit_command = toga.Command(
            lambda _: self.exit(),
            'Exit',
            group=file_menu
        )
        
        # Test menu
        test_menu = toga.Group('Test')
        test_command = toga.Command(
            self._on_test_pressed,
            'Run Test',
            group=test_menu
        )
        
        # Help menu
        help_menu = toga.Group('Help')
        about_command = toga.Command(
            self._on_about_pressed,
            'About',
            group=help_menu
        )
        
        # Add commands to the app
        self.commands.add(exit_command, test_command, about_command)

    def _test_basic_functionality(self):
        """Test basic functionality without complex services."""
        try:
            # Test 1: Basic string operations
            test_result = "Basic functionality test passed"
            
            # Test 2: File system access (minimal)
            try:
                import tempfile
                temp_dir = tempfile.gettempdir()
                test_result += f"\nTemp directory access: {temp_dir}"
            except Exception as e:
                test_result += f"\nTemp directory access failed: {e}"
            
            # Test 3: Basic logging
            logger.info("Basic functionality test completed")
            test_result += "\nLogging test passed"
            
            self.test_data = test_result
            self.status_display.text = "Status: Basic tests completed"
            
        except Exception as e:
            logger.error(f"Basic functionality test failed: {e}")
            self.test_data = f"Basic functionality test failed: {e}"
            self.status_display.text = f"Status: Test failed - {e}"

    def _on_test_pressed(self, widget):
        """Handle test button press."""
        logger.info("Test button pressed")
        
        try:
            # Update display with test data
            self.text_area.value = f"Test Results:\n\n{self.test_data}\n\nButton press test successful!"
            self.status_display.text = "Status: Test button pressed successfully"
            
            # Show info dialog (using new API to avoid deprecation)
            try:
                from toga import InfoDialog
                dialog = InfoDialog("Test", "Test button pressed successfully!")
                self.main_window.dialog(dialog)
            except (ImportError, AttributeError):
                # Fallback to old API if new one not available
                self.main_window.info_dialog("Test", "Test button pressed successfully!")
                
        except Exception as e:
            logger.error(f"Test button press failed: {e}")
            self.status_display.text = f"Status: Test failed - {e}"

    def _on_about_pressed(self, widget):
        """Handle about menu item."""
        try:
            from toga import InfoDialog
            dialog = InfoDialog(
                'About AccessiWeather Minimal',
                'AccessiWeather - Minimal Debug Version\n\n'
                'This is a minimal Toga application for debugging Windows crashes.\n'
                'Built with Beeware/Toga framework.'
            )
            self.main_window.dialog(dialog)
        except (ImportError, AttributeError):
            # Fallback to old API
            self.main_window.info_dialog(
                'About AccessiWeather Minimal',
                'AccessiWeather - Minimal Debug Version\n\n'
                'This is a minimal Toga application for debugging Windows crashes.\n'
                'Built with Beeware/Toga framework.'
            )


def main():
    """Main entry point for the minimal Toga application."""
    return AccessiWeatherMinimal('AccessiWeather Minimal', 'net.orinks.accessiweather.minimal')
