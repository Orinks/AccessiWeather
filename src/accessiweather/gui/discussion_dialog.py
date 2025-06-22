"""Dialog for displaying weather forecast discussion"""

import logging

import wx

logger = logging.getLogger(__name__)


class WeatherDiscussionDialog(wx.Dialog):
    """Dialog for displaying weather forecast discussion"""

    def __init__(self, parent, title, text):
        """Initialize the weather discussion dialog

        Args:
            parent: Parent window
            title: Dialog title
            text: Discussion text

        """
        # Create the dialog with a simple style first
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        # Log the discussion text for debugging
        logger.debug(
            f"Creating discussion dialog with text type: {type(text)}, length: {len(text)}"
        )
        if not text:
            logger.warning("Empty discussion text provided to dialog")
            text = "No discussion available"
        else:
            # Log a preview of the text
            preview = text[:100].replace("\n", "\\n")
            logger.debug(f"Text preview: {preview}...")

        try:
            # Create a simple panel
            logger.debug("Creating panel for discussion dialog")
            panel = wx.Panel(self)

            # Create a vertical box sizer
            sizer = wx.BoxSizer(wx.VERTICAL)

            # Create a text control for the discussion
            logger.debug("Creating text control for discussion dialog")
            self.text_ctrl = wx.TextCtrl(
                panel,
                style=wx.TE_MULTILINE | wx.TE_READONLY,  # Removed wx.TE_RICH2
                size=(780, 500),  # Set a fixed size for the text control
            )

            # Set a monospace font for better readability of formatted text
            logger.debug("Setting font for text control")
            font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
            self.text_ctrl.SetFont(font)

            # Normalize line endings for consistent screen reader behavior
            if isinstance(text, str):
                text = text.replace("\r\n", "\n").replace("\r", "\n")

            # Set the text after setting the font
            logger.debug(f"Setting text value (length: {len(text)})")
            self.text_ctrl.SetValue(text)
            logger.debug("Text value set successfully")

            # Set accessible name and description
            logger.debug("Setting accessible name for text control")
            self.text_ctrl.SetName("Weather Discussion Text")

            # Add to sizer with expansion
            logger.debug("Adding text control to sizer")
            sizer.Add(self.text_ctrl, 1, wx.ALL | wx.EXPAND, 10)

            # Create a simple close button
            logger.debug("Creating close button")
            close_button = wx.Button(panel, wx.ID_CLOSE, "Close")
            sizer.Add(close_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)

            # Set the sizer for the panel
            logger.debug("Setting panel sizer")
            panel.SetSizer(sizer)

            # Set the dialog size
            logger.debug("Setting dialog size")
            self.SetSize((800, 600))
            logger.debug("Dialog size set successfully")

            # Center the dialog on the parent
            logger.debug("Centering dialog on parent")
            self.CenterOnParent()

            # Bind the close button event
            logger.debug("Binding close button event")
            self.Bind(wx.EVT_BUTTON, self.OnClose, id=wx.ID_CLOSE)

            # Set initial focus for accessibility
            logger.debug("Setting initial focus to text control")
            self.text_ctrl.SetFocus()
            logger.debug("WeatherDiscussionDialog initialization complete")
        except Exception as e:
            logger.error(f"Error creating discussion dialog: {e}")
            # Show error message to user
            wx.MessageBox(
                f"Error creating discussion dialog: {e}", "Dialog Error", wx.OK | wx.ICON_ERROR
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
