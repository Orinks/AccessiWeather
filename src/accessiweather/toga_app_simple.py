"""Simple Toga-based AccessiWeather application for testing.

This is a minimal version to test basic Toga functionality without
the complex service layer integration.
"""

import logging

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

logger = logging.getLogger(__name__)


class AccessiWeatherSimple(toga.App):
    """Simple Toga application for AccessiWeather testing."""

    def startup(self):
        """Initialize the simple application UI."""
        logger.info("Starting simple AccessiWeather Toga application")
        
        # Main container
        main_box = toga.Box(style=Pack(direction=COLUMN, margin=10))
        
        # Title
        title_label = toga.Label(
            'AccessiWeather - Simple Test',
            style=Pack(margin=(0, 0, 10, 0), font_size=16, font_weight='bold')
        )
        main_box.add(title_label)
        
        # Test button
        test_button = toga.Button(
            'Test Button',
            on_press=self._on_test_pressed,
            style=Pack(margin=(0, 0, 10, 0))
        )
        main_box.add(test_button)
        
        # Test text display
        self.test_display = toga.MultilineTextInput(
            readonly=True,
            value="This is a test of the Toga framework.\n\nIf you can see this, the basic UI is working!",
            style=Pack(height=200, margin=(0, 0, 10, 0))
        )
        main_box.add(self.test_display)
        
        # Create simple menu
        self._create_simple_menu()
        
        # Set up main window
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.show()
        
        logger.info("Simple AccessiWeather Toga application started successfully")

    def _create_simple_menu(self):
        """Create a simple menu system."""
        # File menu
        file_menu = toga.Group('File')
        exit_command = toga.Command(
            lambda _: self.exit(),
            'Exit',
            group=file_menu,
            tooltip='Exit AccessiWeather'
        )
        
        # Help menu
        help_menu = toga.Group('Help')
        about_command = toga.Command(
            self._on_about_pressed,
            'About',
            group=help_menu,
            tooltip='About AccessiWeather'
        )
        
        # Add commands to the app
        self.commands.add(exit_command, about_command)

    def _on_test_pressed(self, widget):
        """Handle test button press."""
        logger.info("Test button pressed")
        self.test_display.value = "Test button was pressed!\n\nToga UI is working correctly."
        self.main_window.info_dialog(
            "Test",
            "Test button pressed successfully!"
        )

    def _on_about_pressed(self, widget):
        """Handle about menu item."""
        self.main_window.info_dialog(
            'About AccessiWeather',
            'AccessiWeather - Simple Test Version\n\n'
            'This is a minimal Toga application to test basic functionality.\n'
            'Built with Beeware/Toga framework for cross-platform compatibility.'
        )


def main():
    """Main entry point for the simple Toga application."""
    return AccessiWeatherSimple('AccessiWeather Simple', 'net.orinks.accessiweather.simple')
