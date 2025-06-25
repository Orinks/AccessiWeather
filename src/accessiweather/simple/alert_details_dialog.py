"""Alert details dialog for the simple Toga AccessiWeather app.

This module provides a comprehensive alert details dialog that matches the functionality
and layout of the existing wx alert details dialog, but implemented using Toga widgets.
"""

import logging

import toga
from toga.style import Pack

logger = logging.getLogger(__name__)


class AlertDetailsDialog:
    """Toga-based alert details dialog with tabbed interface."""

    def __init__(self, app, title, alert_data):
        """Initialize the alert details dialog.

        Args:
            app: The Toga application instance
            title: Dialog title
            alert_data: Dictionary containing alert data or WeatherAlert object

        """
        self.app = app
        self.title = title
        self.alert_data = alert_data
        self.dialog_window = None

    def show(self):
        """Show the alert details dialog."""
        try:
            # Extract alert information
            if hasattr(self.alert_data, "event"):
                # WeatherAlert object
                event = self.alert_data.event or "Unknown Alert"
                severity = self.alert_data.severity or "Unknown"
                headline = self.alert_data.headline or "No headline available"
                description = self.alert_data.description or "No description available"
                instruction = self.alert_data.instruction or ""
                urgency = self.alert_data.urgency or "Unknown"
                certainty = self.alert_data.certainty or "Unknown"
            else:
                # Dictionary format
                event = self.alert_data.get("event", "Unknown Alert")
                severity = self.alert_data.get("severity", "Unknown")
                headline = self.alert_data.get("headline", "No headline available")
                description = self.alert_data.get("description", "No description available")
                instruction = self.alert_data.get("instruction", "")
                urgency = self.alert_data.get("urgency", "Unknown")
                certainty = self.alert_data.get("certainty", "Unknown")

            # For statement, try to get NWSheadline from parameters, fallback to headline
            statement = headline
            if hasattr(self.alert_data, "parameters") and self.alert_data.parameters:
                nws_headline = self.alert_data.parameters.get("NWSheadline", [])
                if isinstance(nws_headline, list) and len(nws_headline) > 0:
                    statement = nws_headline[0]
                elif isinstance(nws_headline, str):
                    statement = nws_headline
            elif isinstance(self.alert_data, dict):
                parameters = self.alert_data.get("parameters", {})
                nws_headline = parameters.get("NWSheadline", [])
                if isinstance(nws_headline, list) and len(nws_headline) > 0:
                    statement = nws_headline[0]
                elif isinstance(nws_headline, str):
                    statement = nws_headline

            # Create the dialog window
            self.dialog_window = toga.Window(title=self.title, size=(700, 500), resizable=True)

            # Create main container
            main_box = toga.Box(style=Pack(direction="column", margin=10))

            # Header section
            header_box = toga.Box(style=Pack(direction="column", margin_bottom=10))

            # Event and severity
            event_label = toga.Label(
                f"{event} - {severity}",
                style=Pack(font_weight="bold", font_size=14, margin_bottom=5),
            )
            header_box.add(event_label)

            # Additional info
            info_text = f"Urgency: {urgency} | Certainty: {certainty}"
            info_label = toga.Label(info_text, style=Pack(font_size=12, margin_bottom=5))
            header_box.add(info_label)

            # Headline
            headline_label = toga.Label(headline, style=Pack(font_size=12, margin_bottom=10))
            header_box.add(headline_label)

            main_box.add(header_box)

            # Add separator (using a divider)
            separator = toga.Divider(style=Pack(margin_bottom=10))
            main_box.add(separator)

            # Create tabbed interface using OptionContainer
            tab_container = toga.OptionContainer(style=Pack(flex=1))

            # Statement tab
            statement_box = toga.Box(style=Pack(direction="column", margin=10))
            statement_label = toga.Label(
                "Alert Statement:", style=Pack(font_weight="bold", margin_bottom=5)
            )
            statement_box.add(statement_label)
            statement_text = toga.MultilineTextInput(
                value=statement,
                readonly=True,
                style=Pack(flex=1, font_family="monospace"),
                placeholder="Alert statement content",
            )
            statement_box.add(statement_text)
            tab_container.content.append("Statement", statement_box)

            # Description tab
            description_box = toga.Box(style=Pack(direction="column", margin=10))
            description_label = toga.Label(
                "Alert Description:", style=Pack(font_weight="bold", margin_bottom=5)
            )
            description_box.add(description_label)
            description_text = toga.MultilineTextInput(
                value=description,
                readonly=True,
                style=Pack(flex=1, font_family="monospace"),
                placeholder="Alert description content",
            )
            description_box.add(description_text)
            tab_container.content.append("Description", description_box)

            # Instructions tab
            instruction_box = toga.Box(style=Pack(direction="column", margin=10))
            instruction_label = toga.Label(
                "Alert Instructions:", style=Pack(font_weight="bold", margin_bottom=5)
            )
            instruction_box.add(instruction_label)
            instruction_text = toga.MultilineTextInput(
                value=instruction if instruction else "No instructions available",
                readonly=True,
                style=Pack(flex=1, font_family="monospace"),
                placeholder="Alert instructions content",
            )
            instruction_box.add(instruction_text)
            tab_container.content.append("Instructions", instruction_box)

            main_box.add(tab_container)

            # Close button (centered)
            button_box = toga.Box(style=Pack(direction="row", margin_top=10))
            # Add flexible space before button
            button_box.add(toga.Box(style=Pack(flex=1)))
            close_button = toga.Button(
                "Close", on_press=self.on_close, style=Pack(margin=5, width=100)
            )
            button_box.add(close_button)
            # Add flexible space after button
            button_box.add(toga.Box(style=Pack(flex=1)))
            main_box.add(button_box)

            # Set the content and show the window
            self.dialog_window.content = main_box
            self.dialog_window.show()

            logger.debug(f"Alert details dialog shown for {event} ({severity})")

        except Exception as e:
            logger.error(f"Error creating alert details dialog: {e}")
            # Fallback to simple dialog
            self.app.main_window.error_dialog("Dialog Error", f"Error creating alert dialog: {e}")

    def on_close(self, widget):
        """Handle close button press."""
        try:
            if self.dialog_window:
                self.dialog_window.close()
                self.dialog_window = None
            logger.debug("Alert details dialog closed")
        except Exception as e:
            logger.error(f"Error closing alert details dialog: {e}")
