"""Alert details dialog for AccessiWeather

This module provides a dialog for displaying alert details in a read-only text control.
"""

import logging

import wx

logger = logging.getLogger(__name__)


class AlertDetailsDialog(wx.Dialog):
    """Dialog for displaying alert details"""

    def __init__(self, parent, title, alert_data):
        """Initialize the alert details dialog

        Args:
            parent: Parent window
            title: Dialog title
            alert_data: Dictionary containing alert data
        """
        # Create the dialog with resize border
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        # Extract alert information
        event = alert_data.get("event", "Unknown Alert")
        severity = alert_data.get("severity", "Unknown")
        headline = alert_data.get("headline", "No headline available")
        description = alert_data.get("description", "No description available")
        instruction = alert_data.get(
            "instruction", ""
        )  # Changed to empty string instead of "No instructions available"
        if instruction is None:
            instruction = ""  # Ensure instruction is never None

        # Get parameters and log them for debugging
        parameters = alert_data.get("parameters", {})
        logger.debug(f"Alert parameters: {parameters}")

        # Extract NWSheadline properly
        nws_headline = parameters.get("NWSheadline", [])
        logger.debug(f"NWSheadline value: {nws_headline}, type: {type(nws_headline)}")

        # Make sure we handle both string and list formats
        if isinstance(nws_headline, list) and len(nws_headline) > 0:
            statement = nws_headline[0]
            logger.debug(f"Using first element from NWSheadline list: {statement}")
        elif isinstance(nws_headline, str):
            statement = nws_headline
            logger.debug(f"Using NWSheadline string directly: {statement}")
        else:
            # Fall back to headline if NWSheadline is not available
            statement = headline
            logger.debug(f"NWSheadline not available, using headline: {statement}")

        # Print to console for immediate feedback
        print(f"Alert parameters: {parameters}")
        print(f"NWSheadline value: {nws_headline}, type: {type(nws_headline)}")
        print(f"Final statement value: {statement}")

        # Log the alert data for debugging
        logger.debug(f"Creating alert dialog for {event} ({severity})")

        try:
            # Create a simple panel
            panel = wx.Panel(self)

            # Create a vertical box sizer
            sizer = wx.BoxSizer(wx.VERTICAL)

            # Create header information
            header_sizer = wx.BoxSizer(wx.VERTICAL)

            # Event and severity
            event_text = wx.StaticText(panel, label=f"{event} - {severity}")
            font = event_text.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            event_text.SetFont(font)
            header_sizer.Add(event_text, 0, wx.ALL, 5)

            # Headline
            headline_text = wx.StaticText(panel, label=headline)
            header_sizer.Add(headline_text, 0, wx.ALL, 5)

            sizer.Add(header_sizer, 0, wx.ALL | wx.EXPAND, 10)

            # Add a static line separator
            line = wx.StaticLine(panel, style=wx.LI_HORIZONTAL)
            sizer.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

            # Create a notebook for different sections
            notebook = wx.Notebook(panel)

            # Statement panel
            statement_panel = wx.Panel(notebook)
            statement_sizer = wx.BoxSizer(wx.VERTICAL)

            self.statement_text = wx.TextCtrl(
                statement_panel,
                value=statement,
                style=wx.TE_MULTILINE | wx.TE_READONLY,  # Removed wx.TE_RICH2
                size=(-1, 200),
            )

            # Set a monospace font for better readability
            font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
            self.statement_text.SetFont(font)

            # Set accessible name
            self.statement_text.SetName("Alert Statement Text")

            statement_sizer.Add(self.statement_text, 1, wx.ALL | wx.EXPAND, 10)
            statement_panel.SetSizer(statement_sizer)

            # Description panel
            description_panel = wx.Panel(notebook)
            description_sizer = wx.BoxSizer(wx.VERTICAL)

            self.description_text = wx.TextCtrl(
                description_panel,
                value=description,
                style=wx.TE_MULTILINE | wx.TE_READONLY,  # Removed wx.TE_RICH2
                size=(-1, 200),
            )

            # Set the same font
            self.description_text.SetFont(font)

            # Set accessible name
            self.description_text.SetName("Alert Description Text")

            description_sizer.Add(self.description_text, 1, wx.ALL | wx.EXPAND, 10)
            description_panel.SetSizer(description_sizer)

            # Instructions panel
            instruction_panel = wx.Panel(notebook)
            instruction_sizer = wx.BoxSizer(wx.VERTICAL)

            self.instruction_text = wx.TextCtrl(
                instruction_panel,
                value=instruction,
                style=wx.TE_MULTILINE | wx.TE_READONLY,  # Removed wx.TE_RICH2
                size=(-1, 200),
            )

            # Set the same font
            self.instruction_text.SetFont(font)

            # Set accessible name
            self.instruction_text.SetName("Alert Instructions Text")

            instruction_sizer.Add(self.instruction_text, 1, wx.ALL | wx.EXPAND, 10)
            instruction_panel.SetSizer(instruction_sizer)

            # Add pages to notebook
            notebook.AddPage(statement_panel, "Statement")
            notebook.AddPage(description_panel, "Description")
            notebook.AddPage(instruction_panel, "Instructions")

            sizer.Add(notebook, 1, wx.ALL | wx.EXPAND, 10)

            # Create a close button
            close_button = wx.Button(panel, wx.ID_CLOSE, "Close")
            sizer.Add(close_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)

            # Set the sizer for the panel
            panel.SetSizer(sizer)

            # Set the dialog size
            self.SetSize((700, 500))

            # Center the dialog on the parent
            self.CenterOnParent()

            # Bind the close button event
            self.Bind(wx.EVT_BUTTON, self.OnClose, id=wx.ID_CLOSE)

            # Set initial focus for accessibility
            notebook.SetFocus()

        except Exception as e:
            logger.error(f"Error creating alert dialog: {e}")
            # Show error message to user
            wx.MessageBox(
                f"Error creating alert dialog: {e}", "Dialog Error", wx.OK | wx.ICON_ERROR
            )
            raise

    def OnClose(self, event):  # event is required by wx
        """Handle close button event

        Args:
            event: Button event
        """
        logger.debug("Close button clicked, ending modal dialog")
        try:
            self.EndModal(wx.ID_CLOSE)
            logger.debug("Dialog closed successfully")
        except Exception as e:
            logger.error(f"Error closing dialog: {e}")
